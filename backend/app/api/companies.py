from typing import Optional
"""Companies API - manage company records with CSV import and people matching."""
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from sqlalchemy import select, func as sa_func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.company import Company
from app.models.person import Person
from app.models.campaign import Campaign
from app.models.campaign_lead_list import CampaignLeadList
from app.schemas.company import (
    CompanyCreate,
    CompanyUpdate,
    CompanyResponse,
    CompanyListResponse,
    CompanyCSVMapping,
    CompanyCSVUploadResponse,
    CompanyCSVImportRequest,
    CompanyCSVImportResponse,
    CompanyScoreRequest,
    CompanyScoreResponse,
    FindPeopleRequest,
)
from app.schemas.enrichment import (
    EnrichmentResult,
    CompanyEnrichmentResponse,
    EnrichBatchRequest,
)
from app.services.enrichment import CompanyEnrichmentService
from app.services.csv_mapper import csv_mapper_service
from app.services.apollo import ApolloService, ApolloAPIError

logger = logging.getLogger(__name__)
router = APIRouter()

COMPANY_FIELDS = [
    "name", "email", "phone", "linkedin_url", "industry",
    "location", "signals", "website", "revenue", "employee_count", "province",
]

COMPANY_MAPPING_SYSTEM_PROMPT = """You are a data mapping assistant. You receive CSV column headers \
and sample data, and must map them to company database fields.

Company fields to map:
- name: Company/organization name (required)
- email: General contact email address
- phone: Phone/telephone number
- linkedin_url: LinkedIn company page URL
- industry: Industry sector or category
- location: City or location text
- province: Italian "Provincia" 2-letter code (MI, RM, BG, etc.) if a dedicated column exists
- signals: Funding events, acquisitions, news, or other business signals
- website: Company website URL
- revenue: Annual revenue / fatturato (any numeric or formatted column like "729.269.649 €")
- employee_count: Headcount / number of employees / dipendenti

Rules:
- Map each CSV column to the most appropriate company field
- The name field is the most important - always try to identify it
- ANY unmapped column will automatically become a custom_fields entry on the company —
  so prefer leaving it null if it doesn't fit a known field, instead of forcing a poor match.
- Use the map_columns tool to return your mapping"""

COMPANY_MAPPING_TOOL = {
    "name": "map_columns",
    "description": "Map CSV column headers to company database fields",
    "input_schema": {
        "type": "object",
        "properties": {
            field: {
                "type": ["string", "null"],
                "description": f"CSV column name that maps to {field}",
            }
            for field in COMPANY_FIELDS
        },
        "required": COMPANY_FIELDS,
    },
}


def _extract_domain(email: Optional[str]) -> Optional[str]:
    """Extract domain from email address."""
    if not email or "@" not in email:
        return None
    return email.split("@", 1)[1].lower().strip()


def _parse_int(value) -> Optional[int]:
    """Parse a possibly-formatted integer string ('1.234', '1,234', '11-50') -> int or None."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    # Handle ranges like "11-50" by taking the lower bound
    if "-" in s and not s.startswith("-"):
        s = s.split("-", 1)[0].strip()
    digits = "".join(ch for ch in s if ch.isdigit())
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _parse_revenue(value) -> Optional[int]:
    """Parse a revenue string ('729.269.649 €', '€1,234.56M') into euro int.

    Handles common formats:
    - "729.269.649 €" / "729,269,649€"      -> 729269649
    - "1.5M" / "1,5 mln"                    -> 1500000
    - "12.3K"                               -> 12300
    - plain numbers
    """
    if value is None:
        return None
    raw = str(value).strip().lower()
    if not raw:
        return None
    raw = raw.replace("€", "").replace("eur", "").replace("euro", "").strip()
    multiplier = 1
    if any(suffix in raw for suffix in ("mln", "milion", "million")):
        multiplier = 1_000_000
        for s in ("mln", "milione", "milioni", "million", "millions"):
            raw = raw.replace(s, "")
    elif raw.endswith("m"):
        multiplier = 1_000_000
        raw = raw[:-1]
    elif raw.endswith("k"):
        multiplier = 1_000
        raw = raw[:-1]
    elif raw.endswith("b") or "miliard" in raw:
        multiplier = 1_000_000_000
        for s in ("b", "mld", "miliardi", "miliardo"):
            raw = raw.replace(s, "")

    raw = raw.replace(" ", "").replace("'", "")
    # If there are both commas and dots, drop the thousands separator (whichever
    # appears first); the last separator before the decimals is the decimal sep.
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "")
            raw = raw.replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        # Treat as thousands sep if 3-digit groups; otherwise decimal
        parts = raw.split(",")
        if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
            raw = raw.replace(",", "")
        else:
            raw = raw.replace(",", ".")
    elif "." in raw:
        # Italian thousands separator like "729.269.649"
        parts = raw.split(".")
        if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
            raw = raw.replace(".", "")
        # else assume it's a decimal: leave as-is

    try:
        n = float(raw)
    except ValueError:
        return None
    return int(round(n * multiplier))


def _merge_email(company: Company, new_email: str) -> bool:
    """Add email to company's generic_emails if not already present. Returns True if merged."""
    import json
    existing: list[str] = json.loads(company.generic_emails) if company.generic_emails else []
    existing_lower = {e.lower() for e in existing}

    # Include the primary email in dedup check
    if company.email:
        existing_lower.add(company.email.lower())

    if new_email.lower() in existing_lower:
        return False  # Already present

    existing.append(new_email)
    new_value = json.dumps(existing)
    # Safety: skip if would exceed old VARCHAR(1000) before migration runs
    if len(new_value) > 950:
        existing.pop()
        return False
    company.generic_emails = new_value
    return True


def _company_to_response(company: Company, people_count: int = 0) -> CompanyResponse:
    resp = CompanyResponse.model_validate(company)
    resp.people_count = people_count
    # Include multi-list membership IDs so the UI can render list chips
    try:
        resp.list_ids = [ll.id for ll in (company.lists or [])]
    except Exception:
        resp.list_ids = []
    # Aggregate work emails of linked decision makers
    try:
        resp.work_emails = [
            p.email for p in (company.people or [])
            if getattr(p, "email", None)
        ]
    except Exception:
        resp.work_emails = []
    return resp


async def _find_matching_company(db: AsyncSession, company_name: Optional[str], email_domain: Optional[str]) -> Optional[Company]:
    """Find a company by name or email domain match."""
    if company_name:
        result = await db.execute(
            select(Company).where(sa_func.lower(Company.name) == company_name.lower().strip())
        )
        company = result.scalar_one_or_none()
        if company:
            return company
    if email_domain:
        result = await db.execute(
            select(Company).where(Company.email_domain == email_domain)
        )
        return result.scalar_one_or_none()
    return None


# --- Endpoints ---

@router.get("/custom-field-keys", response_model=list[str])
async def list_custom_field_keys(db: AsyncSession = Depends(get_db)):
    """Distinct keys present in any company's custom_fields. Used by the UI to
    derive the dynamic columns to render in the Clay-style table.

    NOTE: This must be declared BEFORE any `/{company_id}` route to avoid
    FastAPI matching "custom-field-keys" as an integer path parameter.
    """
    result = await db.execute(select(Company.custom_fields).where(Company.custom_fields.isnot(None)))
    keys: set[str] = set()
    for row in result.all():
        cf = row[0]
        if isinstance(cf, dict):
            keys.update(k for k in cf.keys() if k)
    return sorted(keys)


@router.get("/industries", response_model=list[str])
async def get_industries(db: AsyncSession = Depends(get_db)):
    """Get unique list of industries from companies."""
    result = await db.execute(
        select(Company.industry)
        .where(Company.industry.isnot(None))
        .distinct()
        .order_by(Company.industry)
    )
    industries = [row[0] for row in result.all()]
    return industries


def _build_company_filter_query(
    *,
    search,
    industry,
    client_tag,
    province,
    location,
    priority_tier,
    lifecycle_stage,
    list_id,
    has_email,
    has_phone,
    has_linkedin,
    has_website,
    has_score,
    revenue_min,
    revenue_max,
    employee_count_min,
    employee_count_max,
    score_min,
    score_max,
    filters,
):
    """Build the SQLAlchemy SELECT for /companies (and /companies/ids).

    Centralised so both endpoints stay in sync.
    """
    import json
    from sqlalchemy import cast, Float
    from app.models.company import company_lead_list

    q = select(Company)
    if search:
        q = q.where(Company.name.ilike(f"%{search}%"))
    if industry is not None:
        q = q.where(Company.industry == industry)
    if province is not None:
        q = q.where(Company.province == province)
    if location is not None:
        q = q.where(Company.location.ilike(f"%{location}%"))
    if client_tag is not None:
        q = q.where(Company.client_tag.ilike(f"%{client_tag}%"))
    if priority_tier is not None:
        q = q.where(Company.priority_tier == priority_tier)
    if lifecycle_stage is not None:
        q = q.where(Company.lifecycle_stage == lifecycle_stage)
    if list_id is not None:
        q = q.join(
            company_lead_list, Company.id == company_lead_list.c.company_id
        ).where(company_lead_list.c.lead_list_id == list_id)
    if has_email is True:
        q = q.where(Company.email.isnot(None), Company.email != "")
    elif has_email is False:
        q = q.where(or_(Company.email.is_(None), Company.email == ""))
    if has_phone is True:
        q = q.where(Company.phone.isnot(None), Company.phone != "")
    elif has_phone is False:
        q = q.where(or_(Company.phone.is_(None), Company.phone == ""))
    if has_linkedin is True:
        q = q.where(Company.linkedin_url.isnot(None), Company.linkedin_url != "")
    elif has_linkedin is False:
        q = q.where(or_(Company.linkedin_url.is_(None), Company.linkedin_url == ""))
    if has_website is True:
        q = q.where(Company.website.isnot(None), Company.website != "")
    elif has_website is False:
        q = q.where(or_(Company.website.is_(None), Company.website == ""))
    if has_score is True:
        q = q.where(Company.icp_score.isnot(None))
    elif has_score is False:
        q = q.where(Company.icp_score.is_(None))
    if revenue_min is not None:
        q = q.where(Company.revenue >= revenue_min)
    if revenue_max is not None:
        q = q.where(Company.revenue <= revenue_max)
    if employee_count_min is not None:
        q = q.where(Company.employee_count >= employee_count_min)
    if employee_count_max is not None:
        q = q.where(Company.employee_count <= employee_count_max)
    if score_min is not None:
        q = q.where(Company.icp_score >= score_min)
    if score_max is not None:
        q = q.where(Company.icp_score <= score_max)

    if filters:
        try:
            advanced = json.loads(filters)
        except json.JSONDecodeError:
            advanced = None
        if isinstance(advanced, dict):
            if isinstance(advanced.get("name_contains"), str):
                q = q.where(Company.name.ilike(f"%{advanced['name_contains']}%"))
            cf_filters = advanced.get("cf") or {}
            if isinstance(cf_filters, dict):
                for key, spec in cf_filters.items():
                    if not isinstance(key, str) or not key:
                        continue
                    cf_text = Company.custom_fields[key].astext  # type: ignore[index]
                    if isinstance(spec, str):
                        q = q.where(cf_text.ilike(f"%{spec}%"))
                    elif isinstance(spec, dict):
                        if "eq" in spec:
                            q = q.where(cf_text == str(spec["eq"]))
                        if "contains" in spec and isinstance(spec["contains"], str):
                            q = q.where(cf_text.ilike(f"%{spec['contains']}%"))
                        if "min" in spec or "max" in spec:
                            cast_num = cast(cf_text, Float)
                            if "min" in spec and spec["min"] is not None:
                                q = q.where(cast_num >= float(spec["min"]))
                            if "max" in spec and spec["max"] is not None:
                                q = q.where(cast_num <= float(spec["max"]))
    return q


@router.get("/ids", response_model=list[int])
async def list_company_ids(
    search: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    client_tag: Optional[str] = Query(None),
    province: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    priority_tier: Optional[str] = Query(None),
    lifecycle_stage: Optional[str] = Query(None),
    list_id: Optional[int] = Query(None),
    has_email: Optional[bool] = Query(None),
    has_phone: Optional[bool] = Query(None),
    has_linkedin: Optional[bool] = Query(None),
    has_website: Optional[bool] = Query(None),
    has_score: Optional[bool] = Query(None),
    revenue_min: Optional[int] = Query(None),
    revenue_max: Optional[int] = Query(None),
    employee_count_min: Optional[int] = Query(None),
    employee_count_max: Optional[int] = Query(None),
    score_min: Optional[int] = Query(None),
    score_max: Optional[int] = Query(None),
    filters: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Return only the IDs of companies matching the same filters as GET /companies.

    Used by the Clay-style "Select all N matching" banner so bulk actions
    (add to list / score / delete) can operate on the entire filtered set
    without paginating through every page first.
    """
    base_query = _build_company_filter_query(
        search=search, industry=industry, client_tag=client_tag, province=province,
        location=location, priority_tier=priority_tier, lifecycle_stage=lifecycle_stage,
        list_id=list_id, has_email=has_email, has_phone=has_phone,
        has_linkedin=has_linkedin, has_website=has_website, has_score=has_score,
        revenue_min=revenue_min, revenue_max=revenue_max,
        employee_count_min=employee_count_min, employee_count_max=employee_count_max,
        score_min=score_min, score_max=score_max, filters=filters,
    )
    id_query = base_query.with_only_columns(Company.id)
    rows = (await db.execute(id_query)).all()
    return [r[0] for r in rows]


@router.get("", response_model=CompanyListResponse)
async def list_companies(
    search: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    client_tag: Optional[str] = Query(None),
    province: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    priority_tier: Optional[str] = Query(None),
    lifecycle_stage: Optional[str] = Query(None),
    list_id: Optional[int] = Query(None, description="Filter to companies that belong to this lead_list"),
    has_email: Optional[bool] = Query(None),
    has_phone: Optional[bool] = Query(None),
    has_linkedin: Optional[bool] = Query(None),
    has_website: Optional[bool] = Query(None),
    has_score: Optional[bool] = Query(None),
    revenue_min: Optional[int] = Query(None),
    revenue_max: Optional[int] = Query(None),
    employee_count_min: Optional[int] = Query(None),
    employee_count_max: Optional[int] = Query(None),
    score_min: Optional[int] = Query(None),
    score_max: Optional[int] = Query(None),
    filters: Optional[str] = Query(None, description="JSON-encoded advanced filters, incl. custom_fields"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List companies with rich filtering. `filters` may be a URL-encoded JSON object:

      {
        "cf": {"My Column": {"contains": "foo"}, "Score Q4": {"min": 50, "max": 100}},
        "name_contains": "acme"
      }
    """
    import math

    base_query = _build_company_filter_query(
        search=search, industry=industry, client_tag=client_tag, province=province,
        location=location, priority_tier=priority_tier, lifecycle_stage=lifecycle_stage,
        list_id=list_id, has_email=has_email, has_phone=has_phone,
        has_linkedin=has_linkedin, has_website=has_website, has_score=has_score,
        revenue_min=revenue_min, revenue_max=revenue_max,
        employee_count_min=employee_count_min, employee_count_max=employee_count_max,
        score_min=score_min, score_max=score_max, filters=filters,
    )

    # Count total matching records
    count_query = select(sa_func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    # Paginated data query — eagerly load list memberships and linked persons
    # (only the email field is needed for work_emails aggregation, but we
    # selectinload the relationship for simplicity).
    offset = (page - 1) * page_size
    data_query = (
        base_query.options(selectinload(Company.lists), selectinload(Company.people))
        .order_by(Company.name.asc())
        .offset(offset).limit(page_size)
    )
    result = await db.execute(data_query)
    companies = result.scalars().all()

    # Get people counts only for companies on this page
    company_ids = [c.id for c in companies]
    if company_ids:
        count_result = await db.execute(
            select(Person.company_id, sa_func.count(Person.id).label("cnt"))
            .where(Person.company_id.in_(company_ids))
            .group_by(Person.company_id)
        )
        counts = {row.company_id: row.cnt for row in count_result.all()}
    else:
        counts = {}

    items = [_company_to_response(c, counts.get(c.id, 0)) for c in companies]
    return CompanyListResponse(
        companies=items, total=total,
        page=page, page_size=page_size, total_pages=total_pages
    )


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(company_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single company by ID."""
    result = await db.execute(
        select(Company)
        .options(selectinload(Company.lists), selectinload(Company.people))
        .where(Company.id == company_id)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")
    count_result = await db.execute(
        select(sa_func.count(Person.id)).where(Person.company_id == company_id)
    )
    count = count_result.scalar() or 0
    return _company_to_response(company, count)


@router.get("/{company_id}/detail")
async def get_company_detail(company_id: int, db: AsyncSession = Depends(get_db)):
    """Get full company detail including people and campaigns."""
    result = await db.execute(
        select(Company).options(selectinload(Company.people)).where(Company.id == company_id)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")

    # Get campaigns via list_id → CampaignLeadList → Campaign
    campaigns = []
    if company.list_id:
        camp_result = await db.execute(
            select(Campaign).join(CampaignLeadList, Campaign.id == CampaignLeadList.campaign_id)
            .where(CampaignLeadList.lead_list_id == company.list_id, Campaign.deleted_at.is_(None))
        )
        campaigns = [
            {"id": c.id, "name": c.name, "status": c.status.value, "total_sent": c.total_sent, "total_opened": c.total_opened, "total_replied": c.total_replied}
            for c in camp_result.scalars().all()
        ]

    resp = CompanyResponse.model_validate(company)
    resp.people_count = len(company.people)

    people_list = [
        {
            "id": p.id, "first_name": p.first_name, "last_name": p.last_name,
            "email": p.email, "phone": p.phone, "linkedin_url": p.linkedin_url,
            "title": getattr(p, "title", None), "location": p.location,
            "converted_at": p.converted_at.isoformat() if p.converted_at else None,
        }
        for p in company.people
    ]

    return {
        "company": resp.model_dump(),
        "people": people_list,
        "campaigns": campaigns,
    }


@router.get("/{company_id}/campaigns")
async def get_company_campaigns(company_id: int, db: AsyncSession = Depends(get_db)):
    """Get campaigns associated with a company via its lead lists."""
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    if not company.list_id:
        return {"campaigns": []}

    result = await db.execute(
        select(Campaign).join(CampaignLeadList, Campaign.id == CampaignLeadList.campaign_id)
        .where(CampaignLeadList.lead_list_id == company.list_id, Campaign.deleted_at.is_(None))
    )
    campaigns = [
        {"id": c.id, "name": c.name, "status": c.status.value, "total_sent": c.total_sent, "total_opened": c.total_opened, "total_replied": c.total_replied}
        for c in result.scalars().all()
    ]
    return {"campaigns": campaigns}


@router.post("", response_model=CompanyResponse, status_code=201)
async def create_company(data: CompanyCreate, db: AsyncSession = Depends(get_db)):
    """Create a single company."""
    company = Company(
        **data.model_dump(),
        email_domain=_extract_domain(data.email),
    )
    db.add(company)
    await db.flush()
    # After creating company, try to link unmatched people
    await _link_people_to_company(db, company)
    # Reload with relationships eager-loaded for the response
    result = await db.execute(
        select(Company)
        .options(selectinload(Company.lists), selectinload(Company.people))
        .where(Company.id == company.id)
    )
    company = result.scalar_one()
    return _company_to_response(company)


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(company_id: int, data: CompanyUpdate, db: AsyncSession = Depends(get_db)):
    """Update a company's fields."""
    from app.services.activity import log_activity, diff_for_log

    result = await db.execute(
        select(Company)
        .options(selectinload(Company.lists), selectinload(Company.people))
        .where(Company.id == company_id)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")

    before = {k: getattr(company, k, None) for k in (
        "name", "email", "phone", "linkedin_url", "industry", "location",
        "province", "signals", "website", "client_tag", "notes",
        "revenue", "employee_count",
    )}

    updates = data.model_dump(exclude_unset=True)
    if "email" in updates:
        updates["email_domain"] = _extract_domain(updates["email"])

    for field, value in updates.items():
        setattr(company, field, value)

    await db.flush()
    await db.refresh(company)

    after = {k: getattr(company, k, None) for k in before.keys()}
    diff = diff_for_log(before, after, before.keys())
    if diff:
        await log_activity(
            db, target_type="account", target_id=company.id,
            action="field_updated", payload=diff, actor="user",
        )

    count_result = await db.execute(
        select(sa_func.count(Person.id)).where(Person.company_id == company_id)
    )
    count = count_result.scalar() or 0
    return _company_to_response(company, count)


@router.delete("/{company_id}", status_code=204)
async def delete_company(company_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a company (people are set to company_id=NULL)."""
    from app.services.activity import log_activity

    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")
    await log_activity(
        db, target_type="account", target_id=company.id,
        action="deleted", payload={"name": company.name}, actor="user",
    )
    await db.delete(company)


# ==============================================================================
# Custom fields (Clay-style "+ Add column")
# ==============================================================================

class CustomFieldUpsert(BaseModel):
    key: str
    value: Optional[str] = None  # null/empty deletes the key


@router.put("/{company_id}/custom-field", response_model=CompanyResponse)
async def upsert_custom_field(
    company_id: int,
    payload: CustomFieldUpsert,
    db: AsyncSession = Depends(get_db),
):
    """Set or remove a single custom_fields[key] = value on a company."""
    from app.services.activity import log_activity

    result = await db.execute(
        select(Company)
        .options(selectinload(Company.lists), selectinload(Company.people))
        .where(Company.id == company_id)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")
    cf = dict(company.custom_fields or {})
    key = payload.key.strip()
    if not key:
        raise HTTPException(400, "Custom field key required")
    old_value = cf.get(key)
    if payload.value is None or payload.value == "":
        cf.pop(key, None)
        action = "custom_field_removed"
        log_payload = {"key": key, "previous": old_value}
    else:
        cf[key] = payload.value
        action = "custom_field_set"
        log_payload = {"key": key, "from": old_value, "to": payload.value}
    company.custom_fields = cf or None
    await db.flush()
    await db.refresh(company)
    await log_activity(
        db, target_type="account", target_id=company.id,
        action=action, payload=log_payload, actor="user",
    )
    return _company_to_response(company)


# ==============================================================================
# Lead Planner & Scorer
# ==============================================================================

# Pricing for cost reporting (Sonnet 4.5)
_CLAUDE_INPUT_USD_PER_1M = 3.00
_CLAUDE_OUTPUT_USD_PER_1M = 15.00


def _revenue_to_raw(value):
    """Best-effort string repr of revenue for the planner input."""
    if value is None:
        return None
    return str(value)


@router.post("/score", response_model=CompanyScoreResponse)
async def score_companies(
    payload: CompanyScoreRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run the Lead Planner & Scorer over the requested companies (or all if
    `company_ids` is omitted). Updates each Company's icp_*, priority_tier,
    lifecycle_stage, *_band, industry_standardized, reason_summary fields, and
    inserts ``enrichment_tasks`` rows for tier A/B accounts.
    """
    from datetime import datetime, timezone
    from app.models.icp import ICP
    from app.models.enrichment_task import EnrichmentTask
    from app.services.lead_planner import get_lead_planner_service

    # Validate ICP
    icp = await db.get(ICP, payload.icp_id)
    if not icp:
        raise HTTPException(404, "ICP not found")

    # Build ICP dict for the prompt
    icp_dict = {
        "name": icp.name,
        "description": icp.description,
        "industry": icp.industry,
        "company_size": icp.company_size,
        "job_titles": icp.job_titles,
        "geography": icp.geography,
        "revenue_range": icp.revenue_range,
        "keywords": icp.keywords,
    }

    # Fetch companies in stable order (oldest first) so the same indexing maps
    # back deterministically.
    q = select(Company).order_by(Company.id.asc())
    if payload.company_ids:
        q = q.where(Company.id.in_(payload.company_ids))
    companies = (await db.execute(q)).scalars().all()
    if not companies:
        raise HTTPException(400, "No companies to score")

    # Convert to planner input shape (1-indexed mapping by list position)
    raw_input = [
        {
            "raw_company_name": c.name or "",
            "raw_website_url": c.website,
            "raw_revenue": _revenue_to_raw(getattr(c, "revenue", None)),
            "raw_employee_count": _revenue_to_raw(getattr(c, "employee_count", None)),
            "raw_country": None,
            "raw_city": c.location,
            "source": c.enrichment_source or "miriade",
        }
        for c in companies
    ]

    # Run Claude
    service = get_lead_planner_service()
    try:
        result = await service.score_companies(icp_dict, raw_input)
    except Exception as e:
        logger.exception("Lead Planner failed")
        raise HTTPException(502, f"Scoring failed: {e}") from e

    accounts = result.get("accounts") or []
    enrichment_tasks = result.get("enrichment_tasks") or []
    usage = result.get("_usage") or {}

    # Persist account-level scoring (positional match: i-th account ↔ i-th company).
    from app.services.activity import log_activity
    now = datetime.now(timezone.utc)
    tier_counts = {"A": 0, "B": 0, "C": 0}
    pairs = list(zip(companies, accounts))
    for company, acct in pairs:
        company.icp_score = acct.get("icp_score")
        company.priority_tier = acct.get("priority_tier")
        company.lifecycle_stage = acct.get("lifecycle_stage") or "new"
        company.revenue_band = acct.get("revenue_band")
        company.employee_count_band = acct.get("employee_count_band")
        company.industry_standardized = acct.get("industry_standardized")
        company.reason_summary = acct.get("reason_summary")
        company.last_scored_at = now
        company.scored_with_icp_id = icp.id
        await log_activity(
            db, target_type="account", target_id=company.id,
            action="scored",
            payload={"icp_id": icp.id, "icp_score": company.icp_score, "tier": company.priority_tier},
            actor="user",
        )
        if company.priority_tier in tier_counts:
            tier_counts[company.priority_tier] += 1

    # Resolve enrichment_tasks via target_temp_id → real Company.id (1-indexed)
    tasks_inserted = 0
    for t in enrichment_tasks:
        try:
            idx = int(str(t.get("target_temp_id", "0")).rsplit("-", 1)[-1])
        except ValueError:
            continue
        if idx < 1 or idx > len(companies):
            continue
        target_company = companies[idx - 1]
        priority = t.get("priority")
        if not isinstance(priority, int) or priority < 1 or priority > 5:
            priority = 3
        task_type = t.get("task_type") or ""
        if not task_type:
            continue
        db.add(
            EnrichmentTask(
                target_type="account",
                target_id=target_company.id,
                task_type=task_type,
                priority=priority,
                reason=t.get("reason"),
                status="pending",
                created_by_icp_id=icp.id,
            )
        )
        tasks_inserted += 1

    await db.flush()

    in_tok = usage.get("input_tokens", 0)
    out_tok = usage.get("output_tokens", 0)
    cost = (in_tok / 1_000_000) * _CLAUDE_INPUT_USD_PER_1M + (out_tok / 1_000_000) * _CLAUDE_OUTPUT_USD_PER_1M

    return CompanyScoreResponse(
        icp_id=icp.id,
        scored_count=len(pairs),
        tier_a=tier_counts["A"],
        tier_b=tier_counts["B"],
        tier_c=tier_counts["C"],
        enrichment_tasks_created=tasks_inserted,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=round(cost, 4),
    )


@router.post("/csv/upload", response_model=CompanyCSVUploadResponse)
async def upload_csv(file: UploadFile = File(...)):
    """Upload a CSV file and auto-map columns with Claude."""
    filename = file.filename or ""
    if not filename.lower().endswith(".csv"):
        raise HTTPException(400, "Only CSV files are supported")
    if file.size and file.size > 5 * 1024 * 1024:
        raise HTTPException(400, "File too large. Maximum size is 5MB.")

    content = await file.read()
    headers, rows = csv_mapper_service.parse_csv(content)
    if not headers or not rows:
        raise HTTPException(400, "CSV file is empty or has no data rows")

    # Use Claude with company-specific prompt
    import json
    import anthropic
    from app.config import settings

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    sample_text = f"CSV Headers: {headers}\n\nSample data (first 3 rows):\n"
    for i, row in enumerate(rows[:3]):
        sample_text += f"Row {i + 1}: {json.dumps(row)}\n"

    message = await client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=512,
        system=COMPANY_MAPPING_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": sample_text}],
        tools=[COMPANY_MAPPING_TOOL],
    )
    mapping_dict = {field: None for field in COMPANY_FIELDS}
    for block in message.content:
        if block.type == "tool_use" and block.name == "map_columns":
            mapping_dict = block.input
            break

    mapping = CompanyCSVMapping(**mapping_dict)
    mapped_columns = {v for v in mapping_dict.values() if v}
    unmapped = [h for h in headers if h not in mapped_columns]

    return CompanyCSVUploadResponse(
        headers=headers,
        mapping=mapping,
        rows=rows,
        preview_rows=rows[:5],
        total_rows=len(rows),
        unmapped_headers=unmapped,
    )


@router.post("/csv/import", response_model=CompanyCSVImportResponse)
async def import_csv(data: CompanyCSVImportRequest, db: AsyncSession = Depends(get_db)):
    """Import companies from CSV with confirmed column mapping."""
    if not data.mapping.name:
        raise HTTPException(400, "Company name column mapping is required")

    logger.info("CSV import started: %d rows, mapping=%s, defaults=%s", len(data.rows), data.mapping, data.defaults)

    imported = 0
    duplicates_skipped = 0
    merged = 0
    errors = 0

    try:
        # Fetch existing company names for deduplication
        existing_result = await db.execute(select(sa_func.lower(Company.name)))
        existing_names = {row[0] for row in existing_result.all()}

        defs = dict(data.defaults or {})

        # Column max lengths (from model)
        LIMITS = {"name": 255, "email": 255, "phone": 50, "linkedin_url": 500,
                  "industry": 255, "location": 255, "website": 500}

        def _val(row: dict, mapping_col, field: str):
            limit = LIMITS.get(field, 0)
            v = _clean(row, mapping_col, limit)
            if v:
                return v
            d = defs.get(field)
            if d and limit and len(d) > limit:
                return d[:limit]
            return d

        # Track companies created in this batch for merging
        companies_by_name: dict[str, Company] = {}

        for row in data.rows:
            try:
                name = _clean(row, data.mapping.name, 255)
                if not name:
                    errors += 1
                    continue

                if name.lower() in existing_names:
                    # Duplicate: try to merge email instead of skipping
                    email = _val(row, data.mapping.email, "email")
                    if email:
                        company = companies_by_name.get(name.lower())
                        if not company:
                            # Look up in DB and cache for future rows
                            db_result = await db.execute(
                                select(Company).where(sa_func.lower(Company.name) == name.lower())
                            )
                            company = db_result.scalar_one_or_none()
                            if company:
                                companies_by_name[name.lower()] = company
                        if company and _merge_email(company, email):
                            merged += 1
                        else:
                            duplicates_skipped += 1
                    else:
                        duplicates_skipped += 1
                    continue

                email = _val(row, data.mapping.email, "email")
                # Parse numeric fields out of the raw row (revenue / employee_count)
                rev_raw = _clean(row, data.mapping.revenue, 0)
                emp_raw = _clean(row, data.mapping.employee_count, 0)
                rev_val = _parse_revenue(rev_raw) if rev_raw else None
                emp_val = _parse_int(emp_raw) if emp_raw else None
                # Capture every CSV column the mapping didn't claim into custom_fields
                mapped_cols = {
                    v for v in data.mapping.model_dump().values() if v
                }
                cf: dict[str, str] = {}
                for k, v in row.items():
                    if not k or k in mapped_cols:
                        continue
                    cleaned = (str(v).strip() if v is not None else "")
                    if cleaned:
                        cf[k] = cleaned[:500]

                company = Company(
                    name=name,
                    email=email,
                    email_domain=_extract_domain(email),
                    phone=_val(row, data.mapping.phone, "phone"),
                    linkedin_url=_val(row, data.mapping.linkedin_url, "linkedin_url"),
                    industry=_val(row, data.mapping.industry, "industry"),
                    location=_val(row, data.mapping.location, "location"),
                    province=_val(row, data.mapping.province, "province"),
                    signals=_val(row, data.mapping.signals, "signals"),
                    website=_val(row, data.mapping.website, "website"),
                    revenue=rev_val,
                    employee_count=emp_val,
                    custom_fields=cf or None,
                )
                db.add(company)
                companies_by_name[name.lower()] = company
                existing_names.add(name.lower())
                imported += 1

                # Flush in batches to avoid huge transaction
                if imported % 500 == 0:
                    await db.flush()
                    logger.info("CSV import progress: %d imported so far", imported)

            except Exception as row_err:
                logger.warning("CSV import row error: %s", row_err)
                errors += 1
                continue

        await db.flush()
        logger.info("CSV import flush done: imported=%d, merged=%d, duplicates=%d, errors=%d",
                     imported, merged, duplicates_skipped, errors)

        # After import, batch-link unmatched people to new companies
        if imported > 0:
            new_companies_result = await db.execute(
                select(Company).order_by(Company.created_at.desc()).limit(imported)
            )
            new_companies = list(new_companies_result.scalars().all())

            name_map: dict[str, int] = {}
            domain_map: dict[str, int] = {}
            for c in new_companies:
                name_map[c.name.lower()] = c.id
                if c.email_domain:
                    domain_map[c.email_domain.lower()] = c.id

            # Only load unmatched people whose company_name or email domain matches new companies
            match_filters = []
            if name_map:
                match_filters.append(sa_func.lower(Person.company_name).in_(list(name_map.keys())))
            if domain_map:
                domain_likes = [Person.email.ilike(f"%@{d}") for d in domain_map.keys()]
                match_filters.extend(domain_likes)

            if match_filters:
                unmatched_result = await db.execute(
                    select(Person).where(
                        Person.company_id.is_(None),
                        or_(*match_filters)
                    )
                )
                unmatched_people = list(unmatched_result.scalars().all())

                for person in unmatched_people:
                    if person.company_name and person.company_name.lower() in name_map:
                        person.company_id = name_map[person.company_name.lower()]
                    elif person.email and "@" in person.email:
                        domain = person.email.split("@")[-1].lower()
                        if domain in domain_map:
                            person.company_id = domain_map[domain]

            logger.info("CSV import: linked people to companies")

        return CompanyCSVImportResponse(imported=imported, duplicates_skipped=duplicates_skipped, merged=merged, errors=errors)

    except Exception as e:
        logger.exception("CSV import failed: %s", e)
        raise HTTPException(500, f"Import failed: {str(e)}")


@router.post("/{company_id}/enrich", response_model=EnrichmentResult)
async def enrich_company(
    company_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Manually enrich single company with email data from website.

    Scrapes the company's website to find generic contact emails
    like info@, contact@, sales@, etc.
    """
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    enrichment_service = CompanyEnrichmentService(db)
    try:
        result = await enrichment_service.enrich_company(company, force=True)
        await db.commit()
        return result
    finally:
        await enrichment_service.close()


@router.post("/enrich-batch", response_model=CompanyEnrichmentResponse)
async def enrich_companies_batch(
    request: EnrichBatchRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Enrich multiple companies in batch.

    Scrapes company websites to find generic contact emails.
    Rate-limited to avoid overwhelming servers.
    """
    # Fetch companies
    result = await db.execute(
        select(Company).where(Company.id.in_(request.company_ids))
    )
    companies = result.scalars().all()

    if not companies:
        raise HTTPException(status_code=404, detail="No companies found")

    enrichment_service = CompanyEnrichmentService(db)
    try:
        results = await enrichment_service.enrich_companies_batch(
            companies,
            max_concurrent=3,
            force=request.force
        )
        await db.commit()

        # Calculate summary
        enriched = sum(1 for r in results if r.status == "completed")
        failed = sum(1 for r in results if r.status == "failed")
        skipped = sum(1 for r in results if r.status == "skipped")

        return CompanyEnrichmentResponse(
            enriched=enriched,
            failed=failed,
            skipped=skipped,
            results=results
        )
    finally:
        await enrichment_service.close()


async def _link_people_to_company(db: AsyncSession, company: Company) -> None:
    """Link unmatched people to this company by name or email domain."""
    # Match by company name
    name_result = await db.execute(
        select(Person).where(
            Person.company_id.is_(None),
            sa_func.lower(Person.company_name) == company.name.lower(),
        )
    )
    for person in name_result.scalars().all():
        person.company_id = company.id

    # Match by email domain
    if company.email_domain:
        domain_result = await db.execute(
            select(Person).where(
                Person.company_id.is_(None),
                Person.email.like(f"%@{company.email_domain}"),
            )
        )
        for person in domain_result.scalars().all():
            person.company_id = company.id


def _clean(row: dict, column_name: Optional[str], max_len: int = 0) -> Optional[str]:
    if not column_name:
        return None
    val = row.get(column_name)
    if not val:
        return None
    val = str(val).strip()
    if not val:
        return None
    if max_len and len(val) > max_len:
        val = val[:max_len]
    return val


@router.post("/{company_id}/find-people")
async def find_people_at_company(
    company_id: int,
    body: FindPeopleRequest,
    db: AsyncSession = Depends(get_db),
):
    """Search Apollo for people working at this company (free, 0 credits)."""
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    apollo = ApolloService()
    try:
        raw = await apollo.search_people(
            person_titles=body.titles or None,
            person_seniorities=body.seniorities or None,
            organization_keywords=[company.name],
            per_page=body.per_page,
        )
    except ApolloAPIError as e:
        raise HTTPException(e.status_code, e.detail)

    results = apollo.format_people_results(raw)
    total = raw.get("pagination", {}).get("total_entries", len(results))

    return {
        "company_id": company_id,
        "company_name": company.name,
        "results": results,
        "total": total,
    }


# ==============================================================================
# Bulk Operations
# ==============================================================================

@router.post("/bulk-tag")
async def bulk_tag_companies(
    company_ids: list[int],
    tags_to_add: Optional[list[str]] = None,
    tags_to_remove: Optional[list[str]] = None,
    db: AsyncSession = Depends(get_db),
):
    """Bulk add/remove tags to companies."""
    result = await db.execute(select(Company).where(Company.id.in_(company_ids)))
    companies = list(result.scalars().all())

    for company in companies:
        if not company.tags:
            company.tags = []

        if tags_to_add:
            for tag in tags_to_add:
                if tag not in company.tags:
                    company.tags.append(tag)

        if tags_to_remove:
            company.tags = [t for t in company.tags if t not in tags_to_remove]

    await db.commit()

    return {
        "companies_tagged": len(companies),
        "message": f"Tagged {len(companies)} companies"
    }


@router.post("/bulk-delete")
async def bulk_delete_companies(
    company_ids: list[int],
    db: AsyncSession = Depends(get_db),
):
    """Bulk delete companies."""
    from sqlalchemy import delete as sql_delete

    result = await db.execute(
        sql_delete(Company).where(Company.id.in_(company_ids))
    )
    await db.commit()

    deleted_count = result.rowcount

    return {
        "deleted_count": deleted_count,
        "message": f"Deleted {deleted_count} companies"
    }


@router.post("/bulk-export")
async def bulk_export_companies(
    company_ids: list[int],
    db: AsyncSession = Depends(get_db),
):
    """Export selected companies to CSV."""
    import csv
    import io

    result = await db.execute(select(Company).where(Company.id.in_(company_ids)))
    companies = list(result.scalars().all())

    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        "Name", "Website", "Email", "Phone", "LinkedIn",
        "Location", "Industry", "Description", "Tags"
    ])

    # Write companies
    for company in companies:
        writer.writerow([
            company.name or "",
            company.website or "",
            company.email or "",
            company.phone or "",
            company.linkedin_url or "",
            company.location or "",
            company.industry or "",
            company.description or "",
            ",".join(company.tags) if company.tags else "",
        ])

    csv_content = output.getvalue()
    output.close()

    from fastapi import Response
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=companies_export_{len(companies)}.csv"
        },
    )
