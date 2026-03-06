"""Enrichment tool handlers: enrich_companies, verify_emails."""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.models.company import Company
from app.services.chat_session import ChatSessionService
from app.services.enrichment import CompanyEnrichmentService


async def handle_enrich_companies(
    db: AsyncSession, session_id: int, tool_input: dict, session_service: ChatSessionService
) -> tuple[dict, Optional[dict]]:
    """Enrich companies from last search with contact emails."""
    session = await db.get(ChatSession, session_id)
    if not session:
        return ({"error": "Session not found", "count": 0}, None)

    if tool_input["company_ids"] == "all":
        last_search = session.session_metadata.get("last_apollo_search", {}) if session.session_metadata else {}
        company_ids = last_search.get("company_ids", [])
    else:
        company_ids = tool_input["company_ids"]

    if not company_ids:
        return ({"error": "No companies to enrich", "count": 0}, None)

    result = await db.execute(select(Company).where(Company.id.in_(company_ids)))
    companies = result.scalars().all()

    if not companies:
        return ({"error": "Companies not found", "count": 0}, None)

    enrichment_service = CompanyEnrichmentService(db)
    results = await enrichment_service.enrich_companies_batch(
        companies,
        max_concurrent=tool_input.get("max_concurrent", 3),
        force=tool_input.get("force", False)
    )

    await db.commit()

    completed = sum(1 for r in results if r.status == "completed")
    emails_found = sum(len(r.emails_found) for r in results)

    await session_service.update_session_metadata(session_id, {
        "last_enrichment": {
            "company_ids": [r.company_id for r in results if r.status == "completed"],
            "emails_found": emails_found,
            "completed": completed
        }
    })

    return (
        {
            "summary": f"Enriched {completed}/{len(companies)} companies, found {emails_found} emails",
            "completed": completed,
            "failed": sum(1 for r in results if r.status == "failed"),
            "total_emails": emails_found
        },
        None
    )


async def handle_verify_emails(
    db: AsyncSession, session_id: int, tool_input: dict, session_service: ChatSessionService
) -> tuple[dict, Optional[dict]]:
    """Verify emails - placeholder."""
    return (
        {"summary": "Email verification not yet implemented", "verified": 0, "invalid": 0, "risky": 0},
        None
    )
