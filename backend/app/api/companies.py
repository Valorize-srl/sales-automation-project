from typing import Optional
"""Companies API - manage company records with CSV import and people matching."""
import logging
import re

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
    # Aggregate work emails + decision-maker summary of linked persons
    try:
        from app.schemas.company import DecisionMakerSummary
        people = company.people or []
        resp.work_emails = [p.email for p in people if getattr(p, "email", None)]
        resp.decision_makers = [
            DecisionMakerSummary.model_validate(p) for p in people
        ]
    except Exception:
        resp.work_emails = []
        resp.decision_makers = []
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
    list_id,
    has_email,
    has_phone,
    has_linkedin,
    has_website,
    revenue_min,
    revenue_max,
    employee_count_min,
    employee_count_max,
    decision_maker_name_contains=None,
    filters=None,
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
    if list_id is not None:
        q = q.join(
            company_lead_list, Company.id == company_lead_list.c.company_id
        ).where(company_lead_list.c.lead_list_id == list_id)
    if decision_maker_name_contains:
        # Filter to companies that have at least one Person whose first/last
        # name (or full name) matches the given substring (case-insensitive).
        like = f"%{decision_maker_name_contains.lower()}%"
        sub = (
            select(Person.company_id)
            .where(
                Person.company_id == Company.id,
                or_(
                    sa_func.lower(Person.first_name).ilike(like),
                    sa_func.lower(Person.last_name).ilike(like),
                    sa_func.lower(sa_func.concat(Person.first_name, " ", Person.last_name)).ilike(like),
                ),
            )
            .correlate(Company)
            .exists()
        )
        q = q.where(sub)
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
    if revenue_min is not None:
        q = q.where(Company.revenue >= revenue_min)
    if revenue_max is not None:
        q = q.where(Company.revenue <= revenue_max)
    if employee_count_min is not None:
        q = q.where(Company.employee_count >= employee_count_min)
    if employee_count_max is not None:
        q = q.where(Company.employee_count <= employee_count_max)

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
    list_id: Optional[int] = Query(None),
    has_email: Optional[bool] = Query(None),
    has_phone: Optional[bool] = Query(None),
    has_linkedin: Optional[bool] = Query(None),
    has_website: Optional[bool] = Query(None),
    revenue_min: Optional[int] = Query(None),
    revenue_max: Optional[int] = Query(None),
    employee_count_min: Optional[int] = Query(None),
    employee_count_max: Optional[int] = Query(None),
    decision_maker_name_contains: Optional[str] = Query(None),
    filters: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Return only the IDs of companies matching the same filters as GET /companies.

    Used by the Clay-style "Select all N matching" banner so bulk actions
    (add to list / delete) can operate on the entire filtered set
    without paginating through every page first.
    """
    base_query = _build_company_filter_query(
        search=search, industry=industry, client_tag=client_tag, province=province,
        location=location,
        list_id=list_id, has_email=has_email, has_phone=has_phone,
        has_linkedin=has_linkedin, has_website=has_website,
        revenue_min=revenue_min, revenue_max=revenue_max,
        employee_count_min=employee_count_min, employee_count_max=employee_count_max,
        decision_maker_name_contains=decision_maker_name_contains, filters=filters,
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
    list_id: Optional[int] = Query(None, description="Filter to companies that belong to this lead_list"),
    has_email: Optional[bool] = Query(None),
    has_phone: Optional[bool] = Query(None),
    has_linkedin: Optional[bool] = Query(None),
    has_website: Optional[bool] = Query(None),
    revenue_min: Optional[int] = Query(None),
    revenue_max: Optional[int] = Query(None),
    employee_count_min: Optional[int] = Query(None),
    employee_count_max: Optional[int] = Query(None),
    decision_maker_name_contains: Optional[str] = Query(None, description="Filter to companies with at least one Person whose name matches"),
    filters: Optional[str] = Query(None, description="JSON-encoded advanced filters, incl. custom_fields"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List companies with rich filtering. `filters` may be a URL-encoded JSON object:

      {
        "cf": {"My Column": {"contains": "foo"}},
        "name_contains": "acme"
      }
    """
    import math

    base_query = _build_company_filter_query(
        search=search, industry=industry, client_tag=client_tag, province=province,
        location=location,
        list_id=list_id, has_email=has_email, has_phone=has_phone,
        has_linkedin=has_linkedin, has_website=has_website,
        revenue_min=revenue_min, revenue_max=revenue_max,
        employee_count_min=employee_count_min, employee_count_max=employee_count_max,
        decision_maker_name_contains=decision_maker_name_contains, filters=filters,
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


class PushToCampaignRequest(BaseModel):
    campaign_id: int


class SaveScrapedDataRequest(BaseModel):
    """Persist the result of a website scrape into the company record."""
    emails: list[str] = []
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None


class FindDMViaLinkedInRequest(BaseModel):
    """Find decision makers via Google -> LinkedIn (no LinkedIn auth required).
    Powered by Claude's built-in web_search tool — see services/linkedin_via_claude.py.
    """
    target_titles: list[str]
    max_results: int = 5


@router.post("/{company_id}/save-scraped", response_model=CompanyResponse)
async def save_scraped_data(
    company_id: int,
    payload: SaveScrapedDataRequest,
    db: AsyncSession = Depends(get_db),
):
    """Merge website-scraper results into a Company record.

    - LinkedIn URL: saved when missing OR when the new value is the canonical
      `linkedin.com/company/...` form and the existing one isn't.
    - Emails: the first new email becomes companies.email if currently empty;
      every other email is appended to generic_emails (dedup via _merge_email).
    - Phone: saved only when companies.phone is empty.
    - Updates enrichment_source / enrichment_date / enrichment_status and
      writes one `enriched_via_scraper` activity_log entry summarising changes.
    """
    from datetime import datetime, timezone
    from app.services.activity import log_activity

    result = await db.execute(
        select(Company)
        .options(selectinload(Company.lists), selectinload(Company.people))
        .where(Company.id == company_id)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")

    new_emails = [e.strip().lower() for e in payload.emails or [] if isinstance(e, str) and "@" in e]
    new_emails = list(dict.fromkeys(new_emails))
    linked_value = (payload.linkedin_url or "").strip() or None
    phone_value = (payload.phone or "").strip() or None

    added_generic = 0
    primary_set = False
    linkedin_set = False
    phone_set = False

    if new_emails and not company.email:
        company.email = new_emails[0]
        company.email_domain = _extract_domain(new_emails[0])
        primary_set = True

    for email in new_emails:
        if _merge_email(company, email):
            added_generic += 1

    if linked_value:
        current = (company.linkedin_url or "").lower()
        new_lower = linked_value.lower()
        is_canonical_new = "/company/" in new_lower
        is_canonical_current = "/company/" in current
        if not company.linkedin_url:
            company.linkedin_url = linked_value[:500]
            linkedin_set = True
        elif is_canonical_new and not is_canonical_current:
            company.linkedin_url = linked_value[:500]
            linkedin_set = True

    if phone_value and not company.phone:
        company.phone = phone_value[:50]
        phone_set = True

    if primary_set or added_generic or linkedin_set or phone_set:
        now = datetime.now(timezone.utc)
        had_apollo = (company.enrichment_source or "").lower() == "apollo"
        company.enrichment_source = "both" if had_apollo else "web_scrape"
        company.enrichment_date = now
        company.enrichment_status = "completed"
        await log_activity(
            db, target_type="account", target_id=company.id,
            action="enriched_via_scraper",
            payload={
                "primary_email_set": primary_set,
                "generic_emails_added": added_generic,
                "linkedin_set": linkedin_set,
                "phone_set": phone_set,
                "source": "native_scraper",
            },
            actor="user",
        )

    await db.flush()
    await db.refresh(company)
    return _company_to_response(company)


@router.post("/{company_id}/push-to-campaign")
async def push_company_decision_makers_to_campaign(
    company_id: int,
    payload: PushToCampaignRequest,
    db: AsyncSession = Depends(get_db),
):
    """Push every Person linked to this company as a lead in the given Instantly
    campaign. Skips persons without a valid email. Writes one activity_log row
    per uploaded contact.
    """
    from app.models.campaign import Campaign
    from app.services.instantly import instantly_service, InstantlyAPIError
    from app.services.activity import log_activity

    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    campaign = await db.get(Campaign, payload.campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if not campaign.instantly_campaign_id:
        raise HTTPException(400, "Campaign is not synced to Instantly yet")

    persons = (await db.execute(
        select(Person).where(Person.company_id == company_id, Person.email.isnot(None))
    )).scalars().all()
    if not persons:
        return {"company_id": company_id, "campaign_id": payload.campaign_id,
                "uploaded": 0, "message": "No decision makers with email"}

    leads = [{
        "email": p.email,
        "first_name": p.first_name,
        "last_name": p.last_name,
        "company_name": company.name or "",
        "phone": p.phone or "",
        "custom_variables": {
            "title": p.title or "",
            "industry": p.industry or company.industry or "",
            "linkedin_url": p.linkedin_url or "",
        },
    } for p in persons]

    try:
        result = await instantly_service.add_leads_to_campaign(
            campaign.instantly_campaign_id, leads
        )
    except InstantlyAPIError as e:
        raise HTTPException(e.status_code, e.detail) from e

    for p in persons:
        await log_activity(
            db, target_type="contact", target_id=p.id,
            action="pushed_to_campaign",
            payload={"campaign_id": payload.campaign_id, "campaign_name": campaign.name},
            actor="user",
        )
    await log_activity(
        db, target_type="account", target_id=company.id,
        action="pushed_decision_makers_to_campaign",
        payload={"campaign_id": payload.campaign_id, "campaign_name": campaign.name, "count": len(leads)},
        actor="user",
    )

    return {
        "company_id": company.id,
        "campaign_id": campaign.id,
        "campaign_name": campaign.name,
        "uploaded": len(leads),
        "instantly_result": result,
    }


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


@router.post("/{company_id}/find-and-import-decision-makers")
async def find_and_import_decision_makers(
    company_id: int,
    body: FindPeopleRequest,
    db: AsyncSession = Depends(get_db),
):
    """One-shot: Apollo-search decision makers at this company AND persist
    them as Person records linked to the company. Replaces the legacy
    find-people + apollo-import chain that lived under /api/chat/apollo.
    """
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

    existing_emails_result = await db.execute(
        select(Person.email).where(Person.email.isnot(None))
    )
    existing_emails = {r[0].lower() for r in existing_emails_result.all() if r[0]}

    imported_count = 0
    skipped_dup = 0
    for item in results:
        email = (item.get("email") or "").strip().lower() or None
        if email and email in existing_emails:
            skipped_dup += 1
            continue
        first_name = (item.get("first_name") or "").strip() or "Unknown"
        last_name = (item.get("last_name") or "").strip() or "Unknown"
        person = Person(
            first_name=first_name[:100],
            last_name=last_name[:100],
            email=email,
            phone=item.get("phone"),
            company_id=company.id,
            company_name=company.name,
            linkedin_url=item.get("linkedin_url"),
            title=item.get("title"),
            industry=item.get("industry"),
            location=item.get("location"),
            client_tag=company.client_tag,
        )
        db.add(person)
        if email:
            existing_emails.add(email)
        imported_count += 1

    await db.flush()

    return {
        "company_id": company_id,
        "company_name": company.name,
        "candidates": len(results),
        "imported_count": imported_count,
        "duplicates_skipped": skipped_dup,
    }


@router.post("/{company_id}/find-decision-makers-linkedin")
async def find_decision_makers_via_linkedin(
    company_id: int,
    body: FindDMViaLinkedInRequest,
    db: AsyncSession = Depends(get_db),
):
    """Find decision makers at this company via Google -> LinkedIn (no LinkedIn auth).

    Uses Claude's built-in web_search tool to dork Google for
    `site:linkedin.com/in/ "<company>"` style queries, parses the SERP entries
    into name/title/url tuples, filters by the user-supplied target titles,
    and persists the results as Person records linked to the company.

    Email is left null (LinkedIn-only contact) — enrich later via Apollo /
    site scrape to fill in.
    """
    from app.services.linkedin_via_claude import find_company_employees_via_linkedin

    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    titles = [t.strip() for t in (body.target_titles or []) if t.strip()]
    if not titles:
        raise HTTPException(400, "target_titles is required")
    max_results = max(1, min(body.max_results or 5, 20))

    try:
        candidates = await find_company_employees_via_linkedin(
            company_name=company.name,
            target_titles=titles,
            max_results=max_results,
            company_linkedin_url=company.linkedin_url,
        )
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        # Surface Anthropic / web_search errors as plain text so the frontend
        # dialog can show the actual cause (e.g. "credit balance is too low",
        # "rate limit exceeded") instead of "API error: 502".
        msg = str(e)
        # Try to extract the message field from Anthropic's error envelope:
        # "Error code: 400 - {'type': 'error', 'error': {'type': '...', 'message': 'Your credit ...'}}"
        m = re.search(r"'message':\s*'([^']+)'", msg) or re.search(r'"message":\s*"([^"]+)"', msg)
        if m:
            msg = m.group(1)
        if "credit balance is too low" in msg.lower():
            msg = "Credito Anthropic esaurito — ricarica su console.anthropic.com/settings/billing"
        elif "rate_limit" in msg.lower() or "rate limit" in msg.lower():
            msg = f"Rate limit Anthropic — riprova fra qualche secondo ({msg})"
        logger.warning("LinkedIn DM finder failed for company_id=%s: %s", company_id, e)
        raise HTTPException(502, msg)

    # Persist as Person records, dedup by linkedin_url scoped to this company
    existing_urls_result = await db.execute(
        select(Person.linkedin_url).where(
            Person.company_id == company_id,
            Person.linkedin_url.isnot(None),
        )
    )
    existing_urls = {row[0] for row in existing_urls_result.all()}

    imported: list[Person] = []
    for c in candidates:
        if c.linkedin_url in existing_urls:
            continue
        existing_urls.add(c.linkedin_url)
        person = Person(
            first_name=c.first_name,
            last_name=c.last_name,
            company_id=company.id,
            company_name=company.name,
            email=None,
            linkedin_url=c.linkedin_url,
            title=c.title,
            location=c.location,
            client_tag=company.client_tag,
        )
        db.add(person)
        imported.append(person)

    if imported:
        await db.commit()
        for p in imported:
            await db.refresh(p)

    return {
        "company_id": company_id,
        "company_name": company.name,
        "candidates_found": len(candidates),
        "imported_count": len(imported),
        "people": [
            {
                "id": p.id,
                "first_name": p.first_name,
                "last_name": p.last_name,
                "title": p.title,
                "linkedin_url": p.linkedin_url,
                "location": p.location,
            }
            for p in imported
        ],
    }


@router.post("/{company_id}/findymail-enrich-decision-makers")
async def findymail_enrich_decision_makers(
    company_id: int,
    db: AsyncSession = Depends(get_db),
):
    """For every Person linked to this company that has no email but has a
    `linkedin_url` (or full name + the company's email_domain), call
    Findymail to fetch the professional email and persist it on the Person.

    Powered by https://findymail.com — chains naturally after the LinkedIn
    DM finder (which provides the linkedin_url).

    Returns counts and the list of newly-enriched people.
    """
    from app.services.findymail import FindymailService, FindymailError

    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    people_result = await db.execute(
        select(Person).where(Person.company_id == company_id)
    )
    people = list(people_result.scalars().all())

    candidates = [
        p for p in people
        if (not p.email or not p.email.strip())
        and (p.linkedin_url or (p.first_name and p.last_name and (company.email_domain or _domain_from_website(company.website))))
    ]
    if not candidates:
        return {
            "company_id": company_id,
            "company_name": company.name,
            "checked": 0,
            "enriched_count": 0,
            "skipped_no_email_found": 0,
            "people": [],
        }

    try:
        service = FindymailService()
    except RuntimeError as e:
        raise HTTPException(500, str(e))

    fallback_domain = (company.email_domain or _domain_from_website(company.website) or "").strip().lower() or None
    enriched: list[Person] = []
    not_found = 0
    for person in candidates:
        try:
            contact = None
            if person.linkedin_url:
                contact = await service.find_email_by_linkedin(person.linkedin_url)
            if not contact and fallback_domain and person.first_name and person.last_name:
                full_name = f"{person.first_name} {person.last_name}".strip()
                contact = await service.find_email_by_name(full_name, fallback_domain)
        except FindymailError as e:
            # Hard error (auth/credits/rate-limit): stop the loop and report.
            raise HTTPException(502, e.detail)

        if not contact:
            not_found += 1
            continue
        person.email = (contact.get("email") or "").strip()[:255] or None
        # Backfill Person.title and location from Findymail if we don't have them
        if not person.title and contact.get("job_title"):
            person.title = str(contact["job_title"])[:255]
        if not person.location and contact.get("city"):
            loc_parts = [contact.get("city"), contact.get("region"), contact.get("country")]
            person.location = ", ".join(p for p in loc_parts if p)[:255]
        enriched.append(person)

    if enriched:
        await db.commit()
        for p in enriched:
            await db.refresh(p)

    return {
        "company_id": company_id,
        "company_name": company.name,
        "checked": len(candidates),
        "enriched_count": len(enriched),
        "skipped_no_email_found": not_found,
        "people": [
            {
                "id": p.id,
                "first_name": p.first_name,
                "last_name": p.last_name,
                "title": p.title,
                "email": p.email,
                "linkedin_url": p.linkedin_url,
            }
            for p in enriched
        ],
    }


def _domain_from_website(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    s = url.strip().lower()
    if s.startswith("http://"): s = s[7:]
    elif s.startswith("https://"): s = s[8:]
    if s.startswith("www."): s = s[4:]
    s = s.split("/", 1)[0]
    return s or None


class FindymailFindDMRequest(BaseModel):
    """Find decision makers at a company by job titles via Findymail."""
    target_titles: list[str]


@router.post("/{company_id}/findymail-find-decision-makers")
async def findymail_find_decision_makers(
    company_id: int,
    body: FindymailFindDMRequest,
    db: AsyncSession = Depends(get_db),
):
    """Find decision makers at this company matching `target_titles` via
    Findymail's POST /search/domain. Returns nome+email+linkedin in one shot
    (1 Findymail credit per contact returned).

    Persists each new contact as a Person record linked to the company,
    deduplicating by email AND linkedin_url within the company.
    """
    from app.services.findymail import FindymailService, FindymailError

    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    titles = [t.strip() for t in (body.target_titles or []) if t.strip()]
    if not titles:
        raise HTTPException(400, "target_titles is required")
    # Findymail's /search/domain accepts max 3 roles per request.
    if len(titles) > 3:
        raise HTTPException(
            400,
            f"Findymail accetta massimo 3 ruoli per ricerca (ne hai indicati {len(titles)}). "
            "Riduci la lista o lancia ricerche separate.",
        )

    try:
        service = FindymailService()
    except RuntimeError as e:
        raise HTTPException(500, str(e))

    # Resolution order:
    #   1. company.website  → real corporate domain (most reliable)
    #   2. company.email_domain  → may be a PEC domain (legalmail.it, pec.it, …)
    #      for Italian companies, which is useless for Findymail. Used only
    #      when website is missing AND the email_domain doesn't look like a PEC.
    #   3. lookup_company_domain(linkedin_url=…)  via Findymail /search/company
    PEC_DOMAINS = {
        "legalmail.it", "pec.it", "postacert.it", "postacertificata.it",
        "registerpec.it", "arubapec.it", "pec-poste.it", "pec.aruba.it",
    }
    website_domain = _domain_from_website(company.website)
    email_domain = (company.email_domain or "").strip().lower() or None
    is_pec = email_domain in PEC_DOMAINS or (
        email_domain and any(email_domain.endswith(suffix) for suffix in (".pec.it", ".legalmail.it"))
    )

    domain = website_domain or (None if is_pec else email_domain)
    domain_resolved_via = "db" if domain else None

    # Fallback: no clean domain in the DB but we have a company LinkedIn URL
    # → ask Findymail's /search/company to resolve it.
    if not domain and company.linkedin_url:
        try:
            domain = await service.lookup_company_domain(linkedin_url=company.linkedin_url)
            domain_resolved_via = "linkedin"
        except FindymailError as e:
            raise HTTPException(502, e.detail)

    if not domain:
        msg = ("L'azienda non ha né sito web né LinkedIn URL aziendale: "
               "impossibile dedurre un dominio per la ricerca Findymail.")
        if is_pec and not website_domain and not company.linkedin_url:
            msg = (f"L'unico dominio noto è una PEC ({email_domain}) — non utilizzabile per "
                   "Findymail. Aggiungi sito web o LinkedIn URL aziendale.")
        raise HTTPException(400, msg)

    try:
        contacts = await service.find_contacts_by_domain_and_roles(domain, titles)
    except FindymailError as e:
        raise HTTPException(502, e.detail)

    # Dedup against existing Persons for this company (by email or linkedin_url)
    existing_result = await db.execute(
        select(Person.email, Person.linkedin_url).where(Person.company_id == company_id)
    )
    existing_emails: set[str] = set()
    existing_li: set[str] = set()
    for em, li in existing_result.all():
        if em: existing_emails.add(em.lower())
        if li: existing_li.add(li)

    imported: list[Person] = []
    skipped_dup = 0
    for c in contacts:
        email = (c.get("email") or "").strip().lower()[:255] or None
        full_name = (c.get("name") or "").strip()
        first_name = (c.get("first_name") or "").strip()
        if not first_name and full_name:
            first_name = full_name.split(" ", 1)[0]
        last_name = ""
        if full_name:
            parts = full_name.split(" ", 1)
            if len(parts) == 2:
                last_name = parts[1]
        last_name = last_name.strip() or "Unknown"
        first_name = first_name.strip() or "Unknown"

        linkedin_url = (c.get("linkedin_url") or c.get("linkedinUrl") or "").strip() or None
        if email and email in existing_emails:
            skipped_dup += 1
            continue
        if linkedin_url and linkedin_url in existing_li:
            skipped_dup += 1
            continue

        person = Person(
            first_name=first_name[:100],
            last_name=last_name[:100],
            company_id=company.id,
            company_name=company.name,
            email=email,
            linkedin_url=linkedin_url,
            title=(c.get("job_title") or c.get("jobTitle") or "").strip()[:255] or None,
            client_tag=company.client_tag,
        )
        db.add(person)
        imported.append(person)
        if email: existing_emails.add(email)
        if linkedin_url: existing_li.add(linkedin_url)

    if imported:
        await db.commit()
        for p in imported:
            await db.refresh(p)

    return {
        "company_id": company_id,
        "company_name": company.name,
        "domain": domain,
        "domain_resolved_via": domain_resolved_via,  # 'db' | 'linkedin'
        "candidates_found": len(contacts),
        "imported_count": len(imported),
        "duplicates_skipped": skipped_dup,
        "people": [
            {
                "id": p.id,
                "first_name": p.first_name,
                "last_name": p.last_name,
                "title": p.title,
                "email": p.email,
                "linkedin_url": p.linkedin_url,
            }
            for p in imported
        ],
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
    """Export selected companies to CSV.

    One row per company, with the same columns the Clay-style /leads table
    shows: anagrafica + revenue/employees + emails (incl. generic_emails) +
    LinkedIn + lists membership + decision-maker chips (joined) + every
    custom_fields key present in the selection (one column each).
    """
    import csv
    import io
    import json as _json
    from fastapi import Response

    if not company_ids:
        raise HTTPException(400, "company_ids is required")

    result = await db.execute(
        select(Company)
        .options(selectinload(Company.lists), selectinload(Company.people))
        .where(Company.id.in_(company_ids))
        .order_by(Company.name.asc())
    )
    companies = list(result.scalars().all())

    # Discover the union of custom_fields keys across the selection so we can
    # emit one column per key instead of dumping a JSON blob.
    cf_keys: list[str] = sorted({
        k
        for c in companies
        if isinstance(c.custom_fields, dict)
        for k in c.custom_fields.keys()
    })

    output = io.StringIO()
    writer = csv.writer(output)

    base_header = [
        "id", "name", "website", "linkedin_url",
        "industry", "province", "location",
        "revenue", "employee_count",
        "email", "generic_emails", "work_emails",
        "phone", "client_tag", "notes",
        "lists", "decision_makers",
        "created_at",
    ]
    writer.writerow(base_header + [f"cf:{k}" for k in cf_keys])

    def _generic_emails(c: Company) -> str:
        raw = c.generic_emails
        if not raw:
            return ""
        if isinstance(raw, list):
            return ", ".join(raw)
        try:
            return ", ".join(_json.loads(raw)) if raw else ""
        except Exception:
            return str(raw)

    def _dm_chip(p) -> str:
        """Join name (title) <email> linkedin into one human-readable token."""
        bits = []
        name = " ".join([p.first_name or "", p.last_name or ""]).strip()
        if name:
            bits.append(name)
        if p.title:
            bits.append(f"({p.title})")
        if p.email:
            bits.append(f"<{p.email}>")
        if p.linkedin_url:
            bits.append(p.linkedin_url)
        return " ".join(bits)

    for company in companies:
        people = company.people or []
        work_emails = [p.email for p in people if p.email]
        dm_str = " | ".join(_dm_chip(p) for p in people)
        lists_str = ", ".join(ll.name for ll in (company.lists or []))
        cf = company.custom_fields if isinstance(company.custom_fields, dict) else {}

        writer.writerow([
            company.id,
            company.name or "",
            company.website or "",
            company.linkedin_url or "",
            company.industry or "",
            company.province or "",
            company.location or "",
            company.revenue if company.revenue is not None else "",
            company.employee_count if company.employee_count is not None else "",
            company.email or "",
            _generic_emails(company),
            ", ".join(work_emails),
            company.phone or "",
            company.client_tag or "",
            (company.notes or "").replace("\n", " ").replace("\r", " "),
            lists_str,
            dm_str,
            company.created_at.isoformat() if company.created_at else "",
        ] + [str(cf.get(k, "")) for k in cf_keys])

    csv_content = output.getvalue()
    output.close()

    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="companies_export_{len(companies)}.csv"',
        },
    )
