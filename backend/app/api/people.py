from typing import Optional
"""People API - manage person records with CSV import and company matching."""
import json
import logging
from datetime import datetime, timezone

import anthropic
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy import select, func as sa_func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_db
from app.models.company import Company
from app.models.person import Person
from app.models.campaign import Campaign
from app.models.campaign_lead_list import CampaignLeadList
from app.schemas.person import (
    PersonCreate,
    PersonUpdate,
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


async def _find_matching_company(db: AsyncSession, company_name: Optional[str], email: Optional[str]) -> Optional[int]:
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


@router.get("/client-tags", response_model=list[str])
async def get_client_tags(db: AsyncSession = Depends(get_db)):
    """Get unique list of client tags from people (splits comma-separated values)."""
    result = await db.execute(
        select(Person.client_tag)
        .where(Person.client_tag.isnot(None))
        .distinct()
    )
    all_tags = set()
    for row in result.all():
        for tag in row[0].split(","):
            tag = tag.strip()
            if tag:
                all_tags.add(tag)
    return sorted(all_tags)


@router.get("", response_model=PersonListResponse)
async def list_people(
    search: Optional[str] = Query(None),
    company_id: Optional[int] = Query(None),
    industry: Optional[str] = Query(None),
    client_tag: Optional[str] = Query(None),
    has_email: Optional[bool] = Query(None),
    has_phone: Optional[bool] = Query(None),
    has_linkedin: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List people with optional search, company, industry, client_tag, presence filters and pagination."""
    import math

    base_query = select(Person)
    if search:
        base_query = base_query.where(
            sa_func.concat(Person.first_name, " ", Person.last_name).ilike(f"%{search}%")
            | Person.email.ilike(f"%{search}%")
        )
    if company_id is not None:
        base_query = base_query.where(Person.company_id == company_id)
    if industry is not None:
        base_query = base_query.where(Person.industry == industry)
    if client_tag is not None:
        base_query = base_query.where(Person.client_tag.ilike(f"%{client_tag}%"))
    # Presence filters
    if has_email is True:
        base_query = base_query.where(Person.email.isnot(None), Person.email != "")
    elif has_email is False:
        base_query = base_query.where(or_(Person.email.is_(None), Person.email == ""))
    if has_phone is True:
        base_query = base_query.where(Person.phone.isnot(None), Person.phone != "")
    elif has_phone is False:
        base_query = base_query.where(or_(Person.phone.is_(None), Person.phone == ""))
    if has_linkedin is True:
        base_query = base_query.where(Person.linkedin_url.isnot(None), Person.linkedin_url != "")
    elif has_linkedin is False:
        base_query = base_query.where(or_(Person.linkedin_url.is_(None), Person.linkedin_url == ""))

    # Count total matching records
    count_query = select(sa_func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    # Paginated data query
    offset = (page - 1) * page_size
    data_query = base_query.order_by(
        Person.last_name.asc(), Person.first_name.asc()
    ).offset(offset).limit(page_size)
    result = await db.execute(data_query)
    people = result.scalars().all()

    return PersonListResponse(
        people=people, total=total,
        page=page, page_size=page_size, total_pages=total_pages
    )


@router.get("/{person_id}", response_model=PersonResponse)
async def get_person(person_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single person by ID."""
    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(404, "Person not found")
    return person


@router.get("/{person_id}/campaigns")
async def get_person_campaigns(person_id: int, db: AsyncSession = Depends(get_db)):
    """Get campaigns associated with a person via their lead list."""
    person = await db.get(Person, person_id)
    if not person:
        raise HTTPException(404, "Person not found")
    if not person.list_id:
        return {"campaigns": []}

    result = await db.execute(
        select(Campaign).join(CampaignLeadList, Campaign.id == CampaignLeadList.campaign_id)
        .where(CampaignLeadList.lead_list_id == person.list_id, Campaign.deleted_at.is_(None))
    )
    campaigns = [
        {"id": c.id, "name": c.name, "status": c.status.value, "total_sent": c.total_sent, "total_opened": c.total_opened, "total_replied": c.total_replied}
        for c in result.scalars().all()
    ]
    return {"campaigns": campaigns}


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


@router.put("/{person_id}", response_model=PersonResponse)
async def update_person(
    person_id: int,
    data: PersonUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a person's fields."""
    from app.services.activity import log_activity, diff_for_log

    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(404, "Person not found")

    track_keys = (
        "first_name", "last_name", "email", "phone", "linkedin_url",
        "title", "company_name", "industry", "location", "client_tag", "notes",
    )
    before = {k: getattr(person, k, None) for k in track_keys}

    updates = data.model_dump(exclude_unset=True)

    # Handle virtual 'converted' field → converted_at timestamp
    if "converted" in updates:
        converted = updates.pop("converted")
        if converted:
            person.converted_at = datetime.now(timezone.utc)
            await log_activity(db, target_type="contact", target_id=person.id,
                               action="converted", payload=None, actor="user")
        else:
            person.converted_at = None
            await log_activity(db, target_type="contact", target_id=person.id,
                               action="unconverted", payload=None, actor="user")

    if "company_name" in updates:
        person.company_id = await _find_matching_company(
            db, updates.get("company_name"), person.email
        )

    for field, value in updates.items():
        setattr(person, field, value)

    await db.flush()
    await db.refresh(person)

    after = {k: getattr(person, k, None) for k in track_keys}
    diff = diff_for_log(before, after, track_keys)
    if diff:
        await log_activity(db, target_type="contact", target_id=person.id,
                           action="field_updated", payload=diff, actor="user")
    return person


@router.delete("/{person_id}", status_code=204)
async def delete_person(person_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a person."""
    from app.services.activity import log_activity

    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(404, "Person not found")
    await log_activity(db, target_type="contact", target_id=person.id,
                       action="deleted",
                       payload={"name": f"{person.first_name} {person.last_name}", "email": person.email},
                       actor="user")
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

    # Pre-load company lookup maps to avoid N+1 queries
    company_name_result = await db.execute(
        select(Company.id, sa_func.lower(Company.name).label("name_lower"))
    )
    company_name_map: dict[str, int] = {row.name_lower: row.id for row in company_name_result.all()}

    company_domain_result = await db.execute(
        select(Company.id, Company.email_domain)
        .where(Company.email_domain.isnot(None))
    )
    company_domain_map: dict[str, int] = {row.email_domain.lower(): row.id for row in company_domain_result.all()}

    # Merge defaults: new "defaults" dict takes priority, fallback to old fields
    defs = dict(data.defaults or {})
    if data.industry and "industry" not in defs:
        defs["industry"] = data.industry
    if data.client_tag and "client_tag" not in defs:
        defs["client_tag"] = data.client_tag

    # Column max lengths (from model)
    LIMITS = {"first_name": 100, "last_name": 100, "email": 255, "company_name": 255,
              "linkedin_url": 500, "phone": 50, "industry": 255, "location": 255, "client_tag": 200}

    def _val(row: dict, mapping_col: Optional[str], field: str) -> Optional[str]:
        limit = LIMITS.get(field, 0)
        v = _clean(row, mapping_col)
        if v:
            return v[:limit] if limit and len(v) > limit else v
        d = defs.get(field)
        if d:
            return d[:limit] if limit and len(d) > limit else d
        return None

    for row in data.rows:
        try:
            email = _clean(row, data.mapping.email)
            if not email:
                errors += 1
                continue
            email = email.lower()[:255]
            if email in existing_emails:
                duplicates_skipped += 1
                continue

            first_name = _val(row, data.mapping.first_name, "first_name") or ""
            last_name = _val(row, data.mapping.last_name, "last_name") or ""

            # Split full name if needed
            if not last_name and " " in first_name:
                parts = first_name.split(" ", 1)
                first_name, last_name = parts[0], parts[1]

            company_name = _val(row, data.mapping.company_name, "company_name")
            # In-memory company lookup (no DB query per row)
            company_id = None
            if company_name:
                company_id = company_name_map.get(company_name.lower().strip())
            if not company_id and email and "@" in email:
                domain = email.split("@", 1)[1].lower().strip()
                company_id = company_domain_map.get(domain)

            person = Person(
                first_name=(first_name or "Unknown")[:100],
                last_name=(last_name or "Unknown")[:100],
                email=email,
                company_id=company_id,
                company_name=company_name,
                linkedin_url=_val(row, data.mapping.linkedin_url, "linkedin_url"),
                phone=_val(row, data.mapping.phone, "phone"),
                industry=_val(row, data.mapping.industry, "industry"),
                location=_val(row, data.mapping.location, "location"),
                client_tag=_val(row, None, "client_tag"),
            )
            db.add(person)
            existing_emails.add(email)
            imported += 1

            if imported % 500 == 0:
                await db.flush()

        except Exception:
            errors += 1
            continue

    await db.flush()
    return PersonCSVImportResponse(imported=imported, duplicates_skipped=duplicates_skipped, errors=errors)


def _clean(row: dict, column_name: Optional[str]) -> Optional[str]:
    if not column_name:
        return None
    val = row.get(column_name)
    if not val:
        return None
    val = str(val).strip()
    return val or None


# ==============================================================================
# Bulk Operations
# ==============================================================================

VERIFICATION_TTL_DAYS = 180


@router.post("/bulk-enrich")
async def bulk_enrich_people(
    person_ids: list[int],
    force: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Bulk enrich selected people via Apollo API.

    Skips contacts whose email/phone was verified in the last 180 days unless
    `force=true` is passed — saves Apollo credits on already-known data.
    Writes one `email_verified` / `phone_verified` activity_log entry per
    successful update so the timeline of a contact is auditable.
    """
    from datetime import datetime, timezone, timedelta
    from app.services.apollo import ApolloService
    from app.services.activity import log_activity

    # Fetch people
    result = await db.execute(select(Person).where(Person.id.in_(person_ids)))
    people = list(result.scalars().all())
    if not people:
        raise HTTPException(404, "No people found with provided IDs")

    cutoff = datetime.now(timezone.utc) - timedelta(days=VERIFICATION_TTL_DAYS)
    skipped_cached = 0
    if not force:
        candidates = []
        for p in people:
            email_fresh = p.last_email_verified_at and p.last_email_verified_at > cutoff
            phone_fresh = p.last_phone_verified_at and p.last_phone_verified_at > cutoff
            if email_fresh and phone_fresh:
                skipped_cached += 1
                continue
            candidates.append(p)
        people = candidates

    apollo = ApolloService()
    enriched_count = 0
    credits_consumed = 0
    now = datetime.now(timezone.utc)

    for i in range(0, len(people), 10):
        batch = people[i:i + 10]
        apollo_people = [
            {
                "id": p.id,
                "first_name": p.first_name,
                "last_name": p.last_name,
                "organization_name": p.company_name,
                "linkedin_url": p.linkedin_url,
            }
            for p in batch
        ]

        try:
            enrich_result = await apollo.enrich_people(apollo_people)
            matches = enrich_result.get("matches", [])
            for match in matches:
                person_id = match.get("id")
                if not person_id:
                    continue
                person = next((p for p in batch if p.id == person_id), None)
                if not person:
                    continue
                if match.get("email"):
                    person.email = match["email"]
                    person.last_email_verified_at = now
                    person.email_verification_source = "apollo"
                    await log_activity(
                        db, target_type="contact", target_id=person.id,
                        action="email_verified", payload={"source": "apollo"}, actor="system",
                    )
                if match.get("phone_numbers"):
                    person.phone = match["phone_numbers"][0].get("sanitized_number")
                    person.last_phone_verified_at = now
                    person.phone_verification_source = "apollo"
                    await log_activity(
                        db, target_type="contact", target_id=person.id,
                        action="phone_verified", payload={"source": "apollo"}, actor="system",
                    )
                person.enriched_at = now
                enriched_count += 1
            credits_consumed += len(batch)
        except Exception as e:
            logger.error(f"Apollo enrich error: {e}")

    await db.commit()

    return {
        "enriched_count": enriched_count,
        "credits_consumed": credits_consumed,
        "skipped_cached": skipped_cached,
        "ttl_days": VERIFICATION_TTL_DAYS,
        "message": (
            f"Enriched {enriched_count} people using {credits_consumed} Apollo credits"
            + (f"; skipped {skipped_cached} cached (verified < {VERIFICATION_TTL_DAYS}d)" if skipped_cached else "")
        ),
    }


@router.post("/bulk-tag")
async def bulk_tag_people(
    person_ids: list[int],
    tags_to_add: Optional[list[str]] = None,
    tags_to_remove: Optional[list[str]] = None,
    db: AsyncSession = Depends(get_db),
):
    """Bulk add/remove tags to people."""
    result = await db.execute(select(Person).where(Person.id.in_(person_ids)))
    people = list(result.scalars().all())

    for person in people:
        if not person.tags:
            person.tags = []

        if tags_to_add:
            for tag in tags_to_add:
                if tag not in person.tags:
                    person.tags.append(tag)

        if tags_to_remove:
            person.tags = [t for t in person.tags if t not in tags_to_remove]

    await db.commit()

    return {
        "people_tagged": len(people),
        "message": f"Tagged {len(people)} people"
    }


@router.post("/bulk-delete")
async def bulk_delete_people(
    person_ids: list[int],
    db: AsyncSession = Depends(get_db),
):
    """Bulk delete people."""
    from sqlalchemy import delete as sql_delete

    result = await db.execute(
        sql_delete(Person).where(Person.id.in_(person_ids))
    )
    await db.commit()

    deleted_count = result.rowcount

    return {
        "deleted_count": deleted_count,
        "message": f"Deleted {deleted_count} people"
    }


@router.post("/bulk-export")
async def bulk_export_people(
    person_ids: list[int],
    db: AsyncSession = Depends(get_db),
):
    """Export selected people to CSV."""
    import csv
    import io

    result = await db.execute(select(Person).where(Person.id.in_(person_ids)))
    people = list(result.scalars().all())

    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        "First Name", "Last Name", "Email", "Phone", "Company",
        "Title", "LinkedIn", "Location", "Industry", "Tags"
    ])

    # Write people
    for person in people:
        writer.writerow([
            person.first_name or "",
            person.last_name or "",
            person.email or "",
            person.phone or "",
            person.company_name or "",
            person.title or "",
            person.linkedin_url or "",
            person.location or "",
            person.industry or "",
            ",".join(person.tags) if person.tags else "",
        ])

    csv_content = output.getvalue()
    output.close()

    from fastapi import Response
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=people_export_{len(people)}.csv"
        },
    )
