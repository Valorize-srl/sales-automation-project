"""Search tool handlers: Apollo, Google Maps, LinkedIn."""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.models.apollo_search_history import ApolloSearchHistory
from app.services.chat_session import ChatSessionService
from app.config import settings as app_settings

logger = logging.getLogger(__name__)


async def handle_search_apollo(
    db: AsyncSession, session_id: int, tool_input: dict, session_service: ChatSessionService
) -> tuple[dict, Optional[dict]]:
    """Search Apollo.io for people or companies (kept for non-prospecting mode)."""
    from app.services.apollo import apollo_service

    search_type = tool_input.get("search_type", "people")
    per_page = min(tool_input.get("per_page", 25), 100)

    try:
        if search_type == "people":
            raw = await apollo_service.search_people(
                person_titles=tool_input.get("person_titles"),
                person_locations=tool_input.get("person_locations"),
                person_seniorities=tool_input.get("person_seniorities"),
                organization_keywords=tool_input.get("organization_keywords"),
                organization_sizes=tool_input.get("organization_sizes"),
                keywords=tool_input.get("keywords"),
                per_page=per_page,
                auto_enrich=False,
            )
            results = apollo_service.format_people_results(raw)
            person_locations = tool_input.get("person_locations")
            if person_locations:
                fallback_location = ", ".join(person_locations)
                for r in results:
                    if not r.get("location"):
                        r["location"] = fallback_location
            total = raw.get("pagination", {}).get("total_entries", len(results))
        elif search_type == "companies":
            raw = await apollo_service.search_organizations(
                organization_locations=tool_input.get("organization_locations"),
                organization_keywords=tool_input.get("organization_keywords"),
                organization_sizes=tool_input.get("organization_sizes"),
                technologies=tool_input.get("technologies"),
                keywords=tool_input.get("keywords"),
                per_page=per_page,
            )
            results = apollo_service.format_org_results(raw)
            total = raw.get("pagination", {}).get("total_entries", len(results))
        else:
            return ({"error": f"Unknown search_type: {search_type}", "summary": "Invalid search type"}, None)

        # Store in session metadata
        await session_service.update_session_metadata(session_id, {
            "last_search": {
                "source": "apollo",
                "type": search_type,
                "count": total,
                "returned": len(results),
                "params": tool_input,
                "results": results,
            }
        })

        # Build summary
        summary_parts = [f"Found {total} {search_type} total, showing {len(results)}."]
        if search_type == "people" and results:
            titles = {}
            for r in results[:25]:
                t = r.get("title", "Unknown")
                titles[t] = titles.get(t, 0) + 1
            top_titles = sorted(titles.items(), key=lambda x: -x[1])[:5]
            summary_parts.append(f"Top titles: {', '.join(f'{t} ({n})' for t, n in top_titles)}")

        # Cost tracking
        credits_consumed = raw.get("credits_consumed", 0)
        apollo_cost_usd = credits_consumed * 0.10

        session = await db.get(ChatSession, session_id)
        search_history = ApolloSearchHistory(
            search_type=search_type,
            search_query=tool_input.get("keywords"),
            filters_applied=tool_input,
            results_count=len(results),
            apollo_credits_consumed=credits_consumed,
            claude_input_tokens=0,
            claude_output_tokens=0,
            cost_apollo_usd=apollo_cost_usd,
            cost_claude_usd=0.0,
            cost_total_usd=apollo_cost_usd,
            client_tag=session.client_tag if session else None,
            session_id=session_id,
        )
        db.add(search_history)
        if session and credits_consumed > 0:
            session.total_apollo_credits += credits_consumed
            session.total_cost_usd += apollo_cost_usd
        await db.commit()

        # SSE event for results panel
        sse_data = {
            "type": "search_results",
            "data": {
                "source": "apollo",
                "results": results,
                "total": total,
                "returned": len(results),
                "search_type": search_type,
                "search_params": tool_input,
            }
        }

        return (
            {"summary": " ".join(summary_parts), "total": total, "returned": len(results), "search_type": search_type},
            sse_data
        )

    except Exception as e:
        logger.error(f"Apollo search error: {e}")
        return ({"error": str(e), "summary": f"Apollo search failed: {e}"}, None)


async def handle_search_google_maps(
    db: AsyncSession, session_id: int, tool_input: dict, session_service: ChatSessionService
) -> tuple[dict, Optional[dict]]:
    """Search Google Maps via Apify scraper."""
    from app.services.apify_scraper import ApifyScraperService

    query = tool_input["query"]
    location = tool_input["location"]
    max_results = min(tool_input.get("max_results", 25), 100)

    try:
        scraper = ApifyScraperService(app_settings.apify_api_token)
        raw = await scraper.run_actor(
            actor_id="compass/crawler-google-places",
            input_data={
                "searchStringsArray": [f"{query} {location}"],
                "maxCrawledPlacesPerSearch": max_results,
                "language": "it",
                "maxReviews": 0,
                "maxImages": 0,
            },
            timeout=300,
        )

        # Format results
        results = []
        for item in raw.get("results", []):
            results.append({
                "name": item.get("title") or item.get("name", ""),
                "address": item.get("address", ""),
                "phone": item.get("phone", ""),
                "website": item.get("website") or item.get("url", ""),
                "email": item.get("email", ""),
                "category": item.get("categoryName") or item.get("category", ""),
                "rating": item.get("totalScore") or item.get("rating"),
                "reviews_count": item.get("reviewsCount", 0),
                "google_maps_url": item.get("url") or item.get("googleMapsUrl", ""),
                "location": location,
            })

        # Store in session metadata
        await session_service.update_session_metadata(session_id, {
            "last_search": {
                "source": "google_maps",
                "type": "companies",
                "count": len(results),
                "returned": len(results),
                "params": tool_input,
                "results": results,
            }
        })

        # Cost tracking
        cost_usd = raw.get("cost_usd", 0.0)
        session = await db.get(ChatSession, session_id)
        search_history = ApolloSearchHistory(
            search_type="google_maps",
            search_query=query,
            filters_applied=tool_input,
            results_count=len(results),
            apollo_credits_consumed=0,
            claude_input_tokens=0,
            claude_output_tokens=0,
            cost_apollo_usd=cost_usd,
            cost_claude_usd=0.0,
            cost_total_usd=cost_usd,
            client_tag=session.client_tag if session else None,
            session_id=session_id,
        )
        db.add(search_history)
        if session and cost_usd > 0:
            session.total_cost_usd += cost_usd
        await db.commit()

        # SSE event
        sse_data = {
            "type": "search_results",
            "data": {
                "source": "google_maps",
                "results": results,
                "total": len(results),
                "returned": len(results),
                "search_params": tool_input,
            }
        }

        summary = f"Trovate {len(results)} attivita' su Google Maps per '{query}' a {location}."
        if results:
            categories = {}
            for r in results:
                cat = r.get("category", "Altro")
                categories[cat] = categories.get(cat, 0) + 1
            top_cats = sorted(categories.items(), key=lambda x: -x[1])[:3]
            summary += f" Categorie: {', '.join(f'{c} ({n})' for c, n in top_cats)}."

        return ({"summary": summary, "total": len(results), "returned": len(results)}, sse_data)

    except Exception as e:
        logger.error(f"Google Maps search error: {e}")
        return ({"error": str(e), "summary": f"Google Maps search failed: {e}"}, None)


async def handle_search_linkedin_companies(
    db: AsyncSession, session_id: int, tool_input: dict, session_service: ChatSessionService
) -> tuple[dict, Optional[dict]]:
    """Search LinkedIn company profiles via Apify scraper."""
    from app.services.apify_scraper import ApifyScraperService

    company_urls = tool_input.get("company_urls", [])
    company_names = tool_input.get("company_names", [])

    if not company_urls and not company_names:
        return ({"error": "Provide company_urls or company_names", "summary": "Nessuna azienda specificata."}, None)

    try:
        scraper = ApifyScraperService(app_settings.apify_api_token)

        # Build input based on what's provided
        input_data = {}
        if company_urls:
            input_data["startUrls"] = [{"url": u} for u in company_urls]
        elif company_names:
            # Use search URLs
            input_data["startUrls"] = [
                {"url": f"https://www.linkedin.com/company/{name.lower().replace(' ', '-')}"}
                for name in company_names
            ]

        raw = await scraper.run_actor(
            actor_id="curious_coder/linkedin-company-scraper",
            input_data=input_data,
            timeout=300,
        )

        results = []
        for item in raw.get("results", []):
            results.append({
                "name": item.get("name", ""),
                "description": item.get("description", ""),
                "industry": item.get("industry", ""),
                "employee_count": item.get("staffCount") or item.get("employeeCount", 0),
                "specialties": item.get("specialities") or item.get("specialties", []),
                "website": item.get("website", ""),
                "linkedin_url": item.get("url") or item.get("linkedInUrl", ""),
                "followers": item.get("followerCount", 0),
                "headquarters": item.get("headquarters", ""),
                "founded": item.get("foundedOn", ""),
            })

        # Cost tracking
        cost_usd = raw.get("cost_usd", 0.0)
        session = await db.get(ChatSession, session_id)
        search_history = ApolloSearchHistory(
            search_type="linkedin_companies",
            search_query=", ".join(company_names or [u.split("/")[-1] for u in company_urls[:5]]),
            filters_applied=tool_input,
            results_count=len(results),
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

        summary = f"Trovati {len(results)} profili LinkedIn aziendali."
        return ({"summary": summary, "results": results, "total": len(results)}, None)

    except Exception as e:
        logger.error(f"LinkedIn companies search error: {e}")
        return ({"error": str(e), "summary": f"LinkedIn companies search failed: {e}"}, None)


async def handle_search_linkedin_people(
    db: AsyncSession, session_id: int, tool_input: dict, session_service: ChatSessionService
) -> tuple[dict, Optional[dict]]:
    """Search LinkedIn people profiles via Apify scraper."""
    from app.services.apify_scraper import ApifyScraperService

    keywords = tool_input["keywords"]
    company = tool_input.get("company", "")
    location = tool_input.get("location", "")
    max_results = min(tool_input.get("max_results", 5), 25)

    try:
        scraper = ApifyScraperService(app_settings.apify_api_token)

        search_query = keywords
        if company:
            search_query += f" {company}"
        if location:
            search_query += f" {location}"

        raw = await scraper.run_actor(
            actor_id="harvestapi/linkedin-profile-search",
            input_data={
                "searchTerms": [search_query],
                "maxResults": max_results,
            },
            timeout=180,
        )

        results = []
        for item in raw.get("results", []):
            results.append({
                "name": item.get("fullName") or item.get("name", ""),
                "first_name": item.get("firstName", ""),
                "last_name": item.get("lastName", ""),
                "headline": item.get("headline", ""),
                "title": item.get("title") or item.get("headline", ""),
                "company": item.get("companyName") or item.get("company", ""),
                "location": item.get("location", ""),
                "linkedin_url": item.get("profileUrl") or item.get("url", ""),
                "email": item.get("email", ""),
            })

        # Cost tracking
        cost_usd = raw.get("cost_usd", 0.0)
        session = await db.get(ChatSession, session_id)
        search_history = ApolloSearchHistory(
            search_type="linkedin_people",
            search_query=search_query,
            filters_applied=tool_input,
            results_count=len(results),
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

        summary = f"Trovati {len(results)} profili LinkedIn"
        if company:
            summary += f" per '{keywords}' a {company}"
        return ({"summary": summary, "results": results, "total": len(results)}, None)

    except Exception as e:
        logger.error(f"LinkedIn people search error: {e}")
        return ({"error": str(e), "summary": f"LinkedIn people search failed: {e}"}, None)
