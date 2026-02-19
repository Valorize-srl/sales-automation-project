"""People API - manage person records with CSV import and company matching."""
import json
import logging

import anthropic
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_db
from app.models.company import Company
from app.models.person import Person
from app.schemas.person import (
    PersonCreate,
    PersonResponse,
    PersonListResponse,
    PersonCSVMapping,
    PersonCSVUploadResponse,
    PersonCSVImportRequest,
    PersonCSVImportResponse,
)
from app.services.csv_mapper import csv_mapper_service

logger = logging.getLogger(__name__)
router = APIRouter()

PERSON_FIELDS = ["first_name", "last_name", "company_name", "email", "linkedin_url", "phone", "industry", "location"]

PERSON_MAPPING_SYSTEM_PROMPT = """You are a data mapping assistant. You receive CSV column headers \
and sample data, and must map them to person/contact database fields.

Person fields to map:
- first_name: The person's first/given name
- last_name: The person's last/family/surname
- company_name: Company or organization the person works for
- email: Email address (required)
- linkedin_url: LinkedIn profile URL
- phone: Phone/telephone number
- industry: Industry sector or category
- location: Location (city, country or region)

Rules:
- Map each CSV column to the most appropriate person field
- If a CSV has a single "name" or "full_name" column, map it to first_name and set last_name to null
- The email field is the most important - always try to identify it
- If a column clearly does not match any person field, set it to null
- Use the map_columns tool to return your mapping"""

PERSON_MAPPING_TOOL = {
    "name": "map_columns",
    "description": "Map CSV column headers to person database fields",
    "input_schema": {
        "type": "object",
        "properties": {
            field: {
                "type": ["string", "null"],
                "description": f"CSV column name that maps to {field}",
            }
            for field in PERSON_FIELDS
        },
        "required": PERSON_FIELDS,
    },
}


async def _find_matching_company(db: AsyncSession, company_name: str | None, email: str | None) -> int | None:
    """Find company_id by name or email domain match."""
    if company_name:
        result = await db.execute(
            select(Company.id).where(sa_func.lower(Company.name) == company_name.lower().strip())
        )
        company_id = result.scalar_one_or_none()
        if company_id:
            return company_id

    if email and "@" in email:
        domain = email.split("@", 1)[1].lower().strip()
        result = await db.execute(
            select(Company.id).where(Company.email_domain == domain)
        )
        return result.scalar_one_or_none()

    return None


# --- Endpoints ---

@router.get("/industries", response_model=list[str])
async def get_industries(db: AsyncSession = Depends(get_db)):
    """Get unique list of industries from people."""
    result = await db.execute(
        select(Person.industry)
        .where(Person.industry.isnot(None))
        .distinct()
        .order_by(Person.industry)
    )
    industries = [row[0] for row in result.all()]
    return industries


@router.get("", response_model=PersonListResponse)
async def list_people(
    search: str | None = Query(None),
    company_id: int | None = Query(None),
    industry: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List people with optional search, company, and industry filters."""
    query = select(Person).order_by(Person.last_name.asc(), Person.first_name.asc())
    if search:
        query = query.where(
            sa_func.concat(Person.first_name, " ", Person.last_name).ilike(f"%{search}%")
            | Person.email.ilike(f"%{search}%")
        )
    if company_id is not None:
        query = query.where(Person.company_id == company_id)
    if industry is not None:
        query = query.where(Person.industry == industry)
    result = await db.execute(query)
    people = result.scalars().all()
    return PersonListResponse(people=people, total=len(people))


@router.get("/{person_id}", response_model=PersonResponse)
async def get_person(person_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single person by ID."""
    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(404, "Person not found")
    return person


@router.post("", response_model=PersonResponse, status_code=201)
async def create_person(data: PersonCreate, db: AsyncSession = Depends(get_db)):
    """Create a single person and attempt company matching."""
    company_id = await _find_matching_company(db, data.company_name, data.email)
    person = Person(
        **data.model_dump(),
        company_id=company_id,
    )
    db.add(person)
    await db.flush()
    await db.refresh(person)
    return person


@router.delete("/{person_id}", status_code=204)
async def delete_person(person_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a person."""
    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(404, "Person not found")
    await db.delete(person)


@router.post("/csv/upload", response_model=PersonCSVUploadResponse)
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

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    sample_text = f"CSV Headers: {headers}\n\nSample data (first 3 rows):\n"
    for i, row in enumerate(rows[:3]):
        sample_text += f"Row {i + 1}: {json.dumps(row)}\n"

    message = await client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=512,
        system=PERSON_MAPPING_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": sample_text}],
        tools=[PERSON_MAPPING_TOOL],
    )
    mapping_dict = {field: None for field in PERSON_FIELDS}
    for block in message.content:
        if block.type == "tool_use" and block.name == "map_columns":
            mapping_dict = block.input
            break

    mapping = PersonCSVMapping(**mapping_dict)
    mapped_columns = {v for v in mapping_dict.values() if v}
    unmapped = [h for h in headers if h not in mapped_columns]

    return PersonCSVUploadResponse(
        headers=headers,
        mapping=mapping,
        rows=rows,
        preview_rows=rows[:5],
        total_rows=len(rows),
        unmapped_headers=unmapped,
    )


@router.post("/csv/import", response_model=PersonCSVImportResponse)
async def import_csv(data: PersonCSVImportRequest, db: AsyncSession = Depends(get_db)):
    """Import people from CSV with confirmed column mapping and company matching."""
    if not data.mapping.email:
        raise HTTPException(400, "Email column mapping is required")

    imported = 0
    duplicates_skipped = 0
    errors = 0

    # Fetch existing emails for deduplication
    existing_result = await db.execute(select(Person.email))
    existing_emails = {row[0].lower() for row in existing_result.all()}

    for row in data.rows:
        try:
            email = _clean(row, data.mapping.email)
            if not email:
                errors += 1
                continue
            email = email.lower()
            if email in existing_emails:
                duplicates_skipped += 1
                continue

            first_name = _clean(row, data.mapping.first_name) or ""
            last_name = _clean(row, data.mapping.last_name) or ""

            # Split full name if needed
            if not last_name and " " in first_name:
                parts = first_name.split(" ", 1)
                first_name, last_name = parts[0], parts[1]

            company_name = _clean(row, data.mapping.company_name)
            company_id = await _find_matching_company(db, company_name, email)

            person = Person(
                first_name=first_name or "Unknown",
                last_name=last_name or "Unknown",
                email=email,
                company_id=company_id,
                company_name=company_name,
                linkedin_url=_clean(row, data.mapping.linkedin_url),
                phone=_clean(row, data.mapping.phone),
                industry=_clean(row, data.mapping.industry),
                location=_clean(row, data.mapping.location),
            )
            db.add(person)
            existing_emails.add(email)
            imported += 1

        except Exception:
            errors += 1
            continue

    await db.flush()
    return PersonCSVImportResponse(imported=imported, duplicates_skipped=duplicates_skipped, errors=errors)


def _clean(row: dict, column_name: str | None) -> str | None:
    if not column_name:
        return None
    val = row.get(column_name)
    if not val:
        return None
    val = str(val).strip()
    return val or None
