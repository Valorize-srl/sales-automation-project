"""Session tool handlers: get_session_context, import_leads."""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.services.chat_session import ChatSessionService


async def handle_get_session_context(
    db: AsyncSession, session_id: int, tool_input: dict, session_service: ChatSessionService
) -> tuple[dict, Optional[dict]]:
    """Return current session state."""
    session = await db.get(ChatSession, session_id)
    if not session:
        return ({"error": "Session not found"}, None)

    last_search = session.session_metadata.get("last_search") if session.session_metadata else None
    # Backward compat: check old key too
    if not last_search and session.session_metadata:
        last_search = session.session_metadata.get("last_apollo_search")

    return (
        {
            "icp_draft": session.current_icp_draft,
            "last_search": {
                "source": last_search.get("source", "unknown") if last_search else None,
                "type": last_search.get("type") if last_search else None,
                "count": last_search.get("count", 0) if last_search else 0,
            } if last_search else None,
            "last_enrichment": session.session_metadata.get("last_enrichment") if session.session_metadata else None,
            "total_cost_usd": round(session.total_cost_usd, 4),
            "summary": "Session context retrieved"
        },
        None
    )


async def handle_import_leads(
    db: AsyncSession, session_id: int, tool_input: dict, session_service: ChatSessionService
) -> tuple[dict, Optional[dict]]:
    """Import leads from last search into People or Companies."""
    from app.models.person import Person
    from app.models.company import Company

    session = await db.get(ChatSession, session_id)
    if not session:
        return ({"error": "Session not found", "summary": "Session not found"}, None)

    # Try new key first, then old key for backward compat
    last_search = (session.session_metadata or {}).get("last_search", {})
    if not last_search.get("results"):
        last_search = (session.session_metadata or {}).get("last_apollo_search", {})

    results = last_search.get("results", [])
    if not results:
        return ({"error": "No search results to import", "summary": "Nessun risultato da importare. Esegui prima una ricerca."}, None)

    target = tool_input["target"]
    client_tag = tool_input.get("client_tag")
    industry = tool_input.get("industry")

    imported = 0
    duplicates_skipped = 0
    errors = 0

    if target == "people":
        existing_result = await db.execute(select(Person.email).where(Person.email.isnot(None)))
        existing_emails = {r[0].lower() for r in existing_result.all() if r[0]}

        for item in results:
            try:
                email = (item.get("email") or "").strip().lower() or None
                first_name = (item.get("first_name") or item.get("name", "")).strip() or "Unknown"
                last_name = (item.get("last_name") or "").strip() or ""

                if email and email in existing_emails:
                    duplicates_skipped += 1
                    continue

                person = Person(
                    first_name=first_name,
                    last_name=last_name,
                    email=email or f"noemail_{imported}@prospecting.import",
                    phone=item.get("phone"),
                    company_name=item.get("company") or item.get("company_name") or item.get("name"),
                    linkedin_url=item.get("linkedin_url"),
                    industry=industry or item.get("industry"),
                    location=item.get("location") or item.get("address"),
                    client_tag=client_tag,
                )
                db.add(person)
                if email:
                    existing_emails.add(email)
                imported += 1
            except Exception:
                errors += 1

    else:  # companies
        from sqlalchemy import func as sa_func
        existing_result = await db.execute(select(sa_func.lower(Company.name)))
        existing_names = {r[0] for r in existing_result.all() if r[0]}

        for item in results:
            try:
                name = (item.get("name") or "").strip()
                if not name:
                    errors += 1
                    continue
                if name.lower() in existing_names:
                    duplicates_skipped += 1
                    continue

                website = item.get("website") or item.get("url")
                domain = None
                if website:
                    domain = website.lower().replace("https://", "").replace("http://", "").split("/")[0] or None

                company = Company(
                    name=name,
                    email=item.get("email"),
                    phone=item.get("phone"),
                    email_domain=domain,
                    linkedin_url=item.get("linkedin_url"),
                    industry=industry or item.get("industry") or item.get("category"),
                    location=item.get("location") or item.get("address"),
                    website=website,
                    client_tag=client_tag,
                )
                db.add(company)
                existing_names.add(name.lower())
                imported += 1
            except Exception:
                errors += 1

    await db.commit()

    summary = f"Importati {imported} {target}"
    if duplicates_skipped:
        summary += f", {duplicates_skipped} duplicati saltati"
    if errors:
        summary += f", {errors} errori"

    import_result = {
        "target": target,
        "imported": imported,
        "duplicates_skipped": duplicates_skipped,
        "errors": errors,
    }

    sse_data = {"type": "import_complete", "data": import_result}

    return (
        {"summary": summary, **import_result},
        sse_data
    )
