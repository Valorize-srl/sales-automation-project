"""Companies API - manage company records with CSV import and people matching."""
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.company import Company
from app.models.person import Person
from app.schemas.company import (
    CompanyCreate,
    CompanyResponse,
    CompanyListResponse,
    CompanyCSVMapping,
    CompanyCSVUploadResponse,
    CompanyCSVImportRequest,
    CompanyCSVImportResponse,
)
from app.services.csv_mapper import csv_mapper_service

logger = logging.getLogger(__name__)
router = APIRouter()

COMPANY_FIELDS = ["name", "email", "phone", "linkedin_url", "industry", "location", "signals", "website"]

COMPANY_MAPPING_SYSTEM_PROMPT = """You are a data mapping assistant. You receive CSV column headers \
and sample data, and must map them to company database fields.

Company fields to map:
- name: Company/organization name (required)
- email: General contact email address
- phone: Phone/telephone number
- linkedin_url: LinkedIn company page URL
- industry: Industry sector or category
- location: Location (city, country or region)
- signals: Funding events, acquisitions, news, or other business signals
- website: Company website URL

Rules:
- Map each CSV column to the most appropriate company field
- The name field is the most important - always try to identify it
- If a column clearly does not match any company field, set it to null
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


def _extract_domain(email: str | None) -> str | None:
    """Extract domain from email address."""
    if not email or "@" not in email:
        return None
    return email.split("@", 1)[1].lower().strip()


def _company_to_response(company: Company, people_count: int = 0) -> CompanyResponse:
    resp = CompanyResponse.model_validate(company)
    resp.people_count = people_count
    return resp


async def _find_matching_company(db: AsyncSession, company_name: str | None, email_domain: str | None) -> Company | None:
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


@router.get("", response_model=CompanyListResponse)
async def list_companies(
    search: str | None = Query(None),
    industry: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List companies with optional search and industry filter."""
    query = select(Company).order_by(Company.name.asc())
    if search:
        query = query.where(Company.name.ilike(f"%{search}%"))
    if industry is not None:
        query = query.where(Company.industry == industry)
    result = await db.execute(query)
    companies = result.scalars().all()

    # Get people counts in one query
    count_result = await db.execute(
        select(Person.company_id, sa_func.count(Person.id).label("cnt"))
        .where(Person.company_id.isnot(None))
        .group_by(Person.company_id)
    )
    counts = {row.company_id: row.cnt for row in count_result.all()}

    items = [_company_to_response(c, counts.get(c.id, 0)) for c in companies]
    return CompanyListResponse(companies=items, total=len(items))


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(company_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single company by ID."""
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")
    count_result = await db.execute(
        select(sa_func.count(Person.id)).where(Person.company_id == company_id)
    )
    count = count_result.scalar() or 0
    return _company_to_response(company, count)


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
    await db.refresh(company)
    return _company_to_response(company)


@router.delete("/{company_id}", status_code=204)
async def delete_company(company_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a company (people are set to company_id=NULL)."""
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")
    await db.delete(company)


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

    imported = 0
    duplicates_skipped = 0
    errors = 0

    # Fetch existing company names for deduplication
    existing_result = await db.execute(select(sa_func.lower(Company.name)))
    existing_names = {row[0] for row in existing_result.all()}

    for row in data.rows:
        try:
            name = _clean(row, data.mapping.name)
            if not name:
                errors += 1
                continue
            if name.lower() in existing_names:
                duplicates_skipped += 1
                continue

            email = _clean(row, data.mapping.email)
            company = Company(
                name=name,
                email=email,
                email_domain=_extract_domain(email),
                phone=_clean(row, data.mapping.phone),
                linkedin_url=_clean(row, data.mapping.linkedin_url),
                industry=_clean(row, data.mapping.industry),
                location=_clean(row, data.mapping.location),
                signals=_clean(row, data.mapping.signals),
                website=_clean(row, data.mapping.website),
            )
            db.add(company)
            existing_names.add(name.lower())
            imported += 1

        except Exception:
            errors += 1
            continue

    await db.flush()

    # After import, link existing unmatched people to newly created companies
    new_companies_result = await db.execute(
        select(Company).order_by(Company.created_at.desc()).limit(imported)
    )
    for company in new_companies_result.scalars().all():
        await _link_people_to_company(db, company)

    return CompanyCSVImportResponse(imported=imported, duplicates_skipped=duplicates_skipped, errors=errors)


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


def _clean(row: dict, column_name: str | None) -> str | None:
    if not column_name:
        return None
    val = row.get(column_name)
    if not val:
        return None
    val = str(val).strip()
    return val or None
