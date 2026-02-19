"""
Lead import service - handles CSV data import with deduplication.
Supports standard fields + custom_fields JSON for unmapped columns.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead, LeadSource

# Fields that map directly to Lead model columns
STANDARD_FIELDS = {
    "first_name", "last_name", "email", "company", "job_title",
    "industry", "linkedin_url", "phone", "address", "city", "state",
    "zip_code", "country", "website",
}


async def import_leads_from_csv(
    db: AsyncSession,
    icp_id: int,
    mapping: dict,
    rows: list[dict],
) -> dict:
    """
    Import leads from mapped CSV data into the database.

    Args:
        db: Async database session
        icp_id: Target ICP ID
        mapping: Column mapping {lead_field: csv_column_name}
        rows: List of CSV row dicts {csv_header: value}

    Returns:
        {"imported": N, "duplicates_skipped": N, "errors": N}
    """
    imported = 0
    duplicates_skipped = 0
    errors = 0

    # Determine which CSV columns are mapped vs unmapped
    mapped_columns = {v for v in mapping.values() if v}
    all_headers = set()
    if rows:
        all_headers = set(rows[0].keys())
    unmapped_headers = all_headers - mapped_columns

    # Fetch existing emails for this ICP to deduplicate
    result = await db.execute(
        select(Lead.email).where(Lead.icp_id == icp_id)
    )
    existing_emails = {row[0].lower() for row in result.all()}

    for row in rows:
        try:
            email = _get_mapped_value(row, mapping.get("email"))
            if not email or not email.strip():
                errors += 1
                continue

            email = email.strip().lower()
            if email in existing_emails:
                duplicates_skipped += 1
                continue

            first_name = _get_mapped_value(row, mapping.get("first_name")) or ""
            last_name = _get_mapped_value(row, mapping.get("last_name")) or ""

            # Split full name if last_name is empty but first_name has a space
            if not last_name.strip() and " " in first_name.strip():
                parts = first_name.strip().split(" ", 1)
                first_name = parts[0]
                last_name = parts[1]

            if not first_name.strip():
                first_name = "Unknown"
            if not last_name.strip():
                last_name = "Unknown"

            # Build custom_fields from unmapped CSV columns
            custom_fields = {}
            for header in unmapped_headers:
                val = row.get(header, "").strip()
                if val:
                    custom_fields[header] = val

            lead = Lead(
                icp_id=icp_id,
                first_name=first_name.strip(),
                last_name=last_name.strip(),
                email=email,
                company=_clean(row, mapping.get("company")),
                job_title=_clean(row, mapping.get("job_title")),
                industry=_clean(row, mapping.get("industry")),
                linkedin_url=_clean(row, mapping.get("linkedin_url")),
                phone=_clean(row, mapping.get("phone")),
                address=_clean(row, mapping.get("address")),
                city=_clean(row, mapping.get("city")),
                state=_clean(row, mapping.get("state")),
                zip_code=_clean(row, mapping.get("zip_code")),
                country=_clean(row, mapping.get("country")),
                website=_clean(row, mapping.get("website")),
                custom_fields=custom_fields or None,
                source=LeadSource.CSV,
                verified=False,
            )
            db.add(lead)
            existing_emails.add(email)
            imported += 1

        except Exception:
            errors += 1
            continue

    await db.flush()
    return {"imported": imported, "duplicates_skipped": duplicates_skipped, "errors": errors}


def _get_mapped_value(row: dict, column_name: str | None) -> str | None:
    """Get a value from a CSV row dict using the mapped column name."""
    if not column_name:
        return None
    return row.get(column_name)


def _clean(row: dict, column_name: str | None) -> str | None:
    """Get and clean a mapped value, returning None for empty strings."""
    val = _get_mapped_value(row, column_name)
    if not val:
        return None
    val = val.strip()
    return val or None
