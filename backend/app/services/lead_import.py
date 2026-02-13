"""
Lead import service - handles CSV data import with deduplication.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead, LeadSource


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

            lead = Lead(
                icp_id=icp_id,
                first_name=first_name.strip(),
                last_name=last_name.strip(),
                email=email,
                company=(_get_mapped_value(row, mapping.get("company")) or "").strip() or None,
                job_title=(_get_mapped_value(row, mapping.get("job_title")) or "").strip() or None,
                linkedin_url=(_get_mapped_value(row, mapping.get("linkedin_url")) or "").strip() or None,
                phone=(_get_mapped_value(row, mapping.get("phone")) or "").strip() or None,
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
