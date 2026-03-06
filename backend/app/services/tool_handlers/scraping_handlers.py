"""Website scraping tool handler."""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.models.apollo_search_history import ApolloSearchHistory
from app.services.chat_session import ChatSessionService
from app.config import settings as app_settings

logger = logging.getLogger(__name__)


async def handle_scrape_websites(
    db: AsyncSession, session_id: int, tool_input: dict, session_service: ChatSessionService
) -> tuple[dict, Optional[dict]]:
    """Extract emails, phone numbers, and social profiles from websites."""
    from app.services.apify_scraper import ApifyScraperService

    source = tool_input.get("source", "last_search")
    urls = tool_input.get("urls", [])

    # If source is last_search, get URLs from session metadata
    if source == "last_search" and not urls:
        session = await db.get(ChatSession, session_id)
        if not session or not session.session_metadata:
            return ({"error": "No previous search found", "summary": "Nessuna ricerca precedente."}, None)

        last_search = session.session_metadata.get("last_search", {})
        results_data = last_search.get("results", [])
        urls = [r.get("website") or r.get("url", "") for r in results_data if r.get("website") or r.get("url")]
        urls = [u for u in urls if u and u.startswith("http")]

    if not urls:
        return ({"error": "No URLs to scrape", "summary": "Nessun URL da scrapare."}, None)

    # Limit to 50 URLs per run
    urls = urls[:50]

    try:
        scraper = ApifyScraperService(app_settings.apify_api_token)
        raw = await scraper.run_actor(
            actor_id="anchor/email-phone-extractor",
            input_data={
                "startUrls": [{"url": u} for u in urls],
                "maxDepth": 2,
            },
            timeout=300,
        )

        # Collect contacts per domain
        contacts_by_domain = {}
        for item in raw.get("results", []):
            domain = (item.get("domain") or item.get("url", "")).lower()
            if domain not in contacts_by_domain:
                contacts_by_domain[domain] = {
                    "emails": [],
                    "phones": [],
                    "social": {},
                }
            emails = item.get("emails") or item.get("emailAddresses") or []
            phones = item.get("phones") or item.get("phoneNumbers") or []
            if isinstance(emails, list):
                contacts_by_domain[domain]["emails"].extend(emails)
            if isinstance(phones, list):
                contacts_by_domain[domain]["phones"].extend(phones)

            # Social profiles
            for key in ["facebook", "twitter", "linkedin", "instagram"]:
                val = item.get(key)
                if val:
                    contacts_by_domain[domain]["social"][key] = val

        # Merge contacts back into last search results if available
        session = await db.get(ChatSession, session_id)
        if session and session.session_metadata:
            last_search = session.session_metadata.get("last_search", {})
            search_results = last_search.get("results", [])
            enriched = 0
            for result in search_results:
                site = (result.get("website") or result.get("url") or "").lower()
                if not site:
                    continue
                # Try to match by domain
                for domain, contacts in contacts_by_domain.items():
                    if domain in site or site in domain:
                        if contacts["emails"] and not result.get("email"):
                            result["email"] = contacts["emails"][0]
                            enriched += 1
                        if contacts["phones"] and not result.get("phone"):
                            result["phone"] = contacts["phones"][0]
                        break

            # Update session metadata with enriched results
            last_search["results"] = search_results
            await session_service.update_session_metadata(session_id, {
                "last_search": last_search
            })

        # Cost tracking
        cost_usd = raw.get("cost_usd", 0.0)
        total_emails = sum(len(c["emails"]) for c in contacts_by_domain.values())
        total_phones = sum(len(c["phones"]) for c in contacts_by_domain.values())

        search_history = ApolloSearchHistory(
            search_type="website_contacts",
            search_query=f"{len(urls)} URLs scraped",
            filters_applied={"urls_count": len(urls)},
            results_count=total_emails + total_phones,
            apollo_credits_consumed=0,
            cost_apollo_usd=cost_usd,
            cost_total_usd=cost_usd,
            client_tag=session.client_tag if session else None,
            session_id=session_id,
        )
        db.add(search_history)
        if session and cost_usd > 0:
            session.total_cost_usd += cost_usd
        await db.commit()

        summary = (
            f"Scrapati {len(urls)} siti web. "
            f"Trovate {total_emails} email e {total_phones} numeri di telefono."
        )

        return (
            {
                "summary": summary,
                "urls_scraped": len(urls),
                "emails_found": total_emails,
                "phones_found": total_phones,
                "domains_with_contacts": len(contacts_by_domain),
            },
            None
        )

    except Exception as e:
        logger.error(f"Website scraping error: {e}")
        return ({"error": str(e), "summary": f"Website scraping failed: {e}"}, None)
