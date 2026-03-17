"""Direct REST API endpoints for prospecting tools (Apollo, Google Maps, scraping)."""

import csv
import io
import base64
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.config import settings as app_settings
from app.models.apollo_search_history import ApolloSearchHistory
from app.schemas.tools import (
    ApolloSearchPeopleRequest,
    ApolloSearchCompaniesRequest,
    ApolloEnrichRequest,
    ApolloEnrichResponse,
    GoogleMapsSearchRequest,
    LinkedInSearchPeopleRequest,
    LinkedInSearchCompaniesRequest,
    ScrapeWebsitesRequest,
    ImportLeadsRequest,
    ImportLeadsResponse,
    GenerateCsvRequest,
    ToolSearchResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Apollo Search People ────────────────────────────────────────────

@router.post("/apollo/search-people", response_model=ToolSearchResponse)
async def apollo_search_people(
    req: ApolloSearchPeopleRequest,
    db: AsyncSession = Depends(get_db),
):
    """Search Apollo.io for people."""
    from app.services.apollo import apollo_service

    try:
        raw = await apollo_service.search_people(
            person_titles=req.person_titles,
            person_locations=req.person_locations,
            person_seniorities=req.person_seniorities,
            organization_keywords=req.organization_keywords,
            organization_sizes=req.organization_sizes,
            keywords=req.keywords,
            per_page=req.per_page,
            auto_enrich=False,
        )
    except Exception as e:
        raise HTTPException(502, f"Apollo API error: {e}")

    results = apollo_service.format_people_results(raw)

    # Backfill location from search params
    if req.person_locations:
        fallback = ", ".join(req.person_locations)
        for r in results:
            if not r.get("location"):
                r["location"] = fallback

    total = raw.get("pagination", {}).get("total_entries", len(results))
    credits_consumed = raw.get("credits_consumed", 0)
    cost_usd = credits_consumed * 0.10

    # Cost tracking
    await _log_search(db, "people", req.keywords, req.model_dump(), len(results),
                      credits_consumed, cost_usd, req.client_tag)

    return ToolSearchResponse(
        results=results, total=total,
        credits_used=credits_consumed, cost_usd=cost_usd,
    )


# ── Apollo Search Companies ─────────────────────────────────────────

@router.post("/apollo/search-companies", response_model=ToolSearchResponse)
async def apollo_search_companies(
    req: ApolloSearchCompaniesRequest,
    db: AsyncSession = Depends(get_db),
):
    """Search Apollo.io for companies."""
    from app.services.apollo import apollo_service

    try:
        raw = await apollo_service.search_organizations(
            organization_locations=req.organization_locations,
            organization_keywords=req.organization_keywords,
            organization_sizes=req.organization_sizes,
            technologies=req.technologies,
            keywords=req.keywords,
            per_page=req.per_page,
        )
    except Exception as e:
        raise HTTPException(502, f"Apollo API error: {e}")

    results = apollo_service.format_org_results(raw)
    total = raw.get("pagination", {}).get("total_entries", len(results))
    credits_consumed = raw.get("credits_consumed", 0)
    cost_usd = credits_consumed * 0.10

    await _log_search(db, "companies", req.keywords, req.model_dump(), len(results),
                      credits_consumed, cost_usd, req.client_tag)

    return ToolSearchResponse(
        results=results, total=total,
        credits_used=credits_consumed, cost_usd=cost_usd,
    )


# ── Apollo Enrich ───────────────────────────────────────────────────

@router.post("/apollo/enrich", response_model=ApolloEnrichResponse)
async def apollo_enrich_people(
    req: ApolloEnrichRequest,
    db: AsyncSession = Depends(get_db),
):
    """Enrich existing Person records with Apollo (email, phone, LinkedIn). 1 credit/person."""
    from app.services.apollo import apollo_service
    from app.models.person import Person

    # Load persons from DB
    result = await db.execute(
        select(Person).where(Person.id.in_(req.person_ids))
    )
    persons = result.scalars().all()
    if not persons:
        raise HTTPException(404, "No persons found with given IDs")

    total_enriched = 0
    total_credits = 0

    # Process in batches of 10 (Apollo limit)
    for i in range(0, len(persons), 10):
        batch = persons[i:i + 10]
        people_data = [
            {
                "first_name": p.first_name,
                "last_name": p.last_name,
                "organization_name": p.company_name,
                "linkedin_url": p.linkedin_url,
            }
            for p in batch
        ]

        try:
            enrich_result = await apollo_service.enrich_people(people_data)
        except Exception as e:
            logger.error(f"Apollo enrich batch error: {e}")
            continue

        credits = enrich_result.get("credits_consumed", 0)
        total_credits += credits
        matches = enrich_result.get("matches", [])

        # Update Person records with enriched data
        for j, person in enumerate(batch):
            if j < len(matches) and matches[j]:
                match = matches[j]
                if match.get("email"):
                    person.email = match["email"]
                if match.get("phone") or match.get("direct_phone"):
                    person.phone = match.get("phone") or match.get("direct_phone")
                if match.get("linkedin_url"):
                    person.linkedin_url = match["linkedin_url"]
                if match.get("city"):
                    loc_parts = filter(None, [match.get("city"), match.get("state"), match.get("country")])
                    person.location = ", ".join(loc_parts)
                total_enriched += 1

    await db.flush()

    cost_usd = total_credits * 0.10
    await _log_search(db, "enrich", None, {"person_ids": req.person_ids[:10]},
                      total_enriched, total_credits, cost_usd, req.client_tag)

    return ApolloEnrichResponse(
        enriched=total_enriched,
        total_requested=len(persons),
        credits_used=total_credits,
        cost_usd=cost_usd,
        message=f"Arricchiti {total_enriched}/{len(persons)} contatti",
    )


# ── Google Maps Search ──────────────────────────────────────────────

@router.post("/google-maps/search", response_model=ToolSearchResponse)
async def google_maps_search(
    req: GoogleMapsSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Search local businesses via Google Maps (Apify scraper)."""
    from app.services.apify_scraper import ApifyScraperService

    if not app_settings.apify_api_token:
        raise HTTPException(400, "Apify API token not configured")

    search_str = f"{req.query} {req.location}" if req.location else req.query

    try:
        scraper = ApifyScraperService(app_settings.apify_api_token)
        raw = await scraper.run_actor(
            actor_id="compass/crawler-google-places",
            input_data={
                "searchStringsArray": [search_str],
                "maxCrawledPlacesPerSearch": req.max_results,
                "language": "it",
                "maxReviews": 0,
                "maxImages": 0,
            },
            timeout=300,
        )
    except Exception as e:
        raise HTTPException(502, f"Google Maps search failed: {e}")

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
            "location": req.location or "",
        })

    cost_usd = raw.get("cost_usd", 0.0)
    await _log_search(db, "google_maps", req.query, req.model_dump(),
                      len(results), 0, cost_usd, req.client_tag)

    return ToolSearchResponse(
        results=results, total=len(results),
        credits_used=0, cost_usd=cost_usd,
    )


# ── Website Scraper ─────────────────────────────────────────────────

@router.post("/scrape-websites", response_model=ToolSearchResponse)
async def scrape_websites(
    req: ScrapeWebsitesRequest,
    db: AsyncSession = Depends(get_db),
):
    """Extract emails and phone numbers from websites."""
    from app.services.apify_scraper import ApifyScraperService

    if not app_settings.apify_api_token:
        raise HTTPException(400, "Apify API token not configured")

    urls = [u for u in req.urls if u.startswith("http")][:50]
    if not urls:
        raise HTTPException(400, "No valid URLs provided")

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
    except Exception as e:
        raise HTTPException(502, f"Website scraping failed: {e}")

    # Collect contacts per domain
    contacts_by_domain: dict[str, dict] = {}
    for item in raw.get("results", []):
        domain = (item.get("domain") or item.get("url", "")).lower()
        if domain not in contacts_by_domain:
            contacts_by_domain[domain] = {"emails": [], "phones": [], "social": {}}
        emails = item.get("emails") or item.get("emailAddresses") or []
        phones = item.get("phones") or item.get("phoneNumbers") or []
        if isinstance(emails, list):
            contacts_by_domain[domain]["emails"].extend(emails)
        if isinstance(phones, list):
            contacts_by_domain[domain]["phones"].extend(phones)
        for key in ["facebook", "twitter", "linkedin", "instagram"]:
            val = item.get(key)
            if val:
                contacts_by_domain[domain]["social"][key] = val

    # Format results as flat list
    results = []
    for domain, contacts in contacts_by_domain.items():
        unique_emails = list(dict.fromkeys(contacts["emails"]))
        unique_phones = list(dict.fromkeys(contacts["phones"]))
        results.append({
            "domain": domain,
            "emails": unique_emails,
            "phones": unique_phones,
            "email": unique_emails[0] if unique_emails else "",
            "phone": unique_phones[0] if unique_phones else "",
            "social": contacts["social"],
        })

    cost_usd = raw.get("cost_usd", 0.0)
    await _log_search(db, "website_contacts", f"{len(urls)} URLs",
                      {"urls_count": len(urls)}, len(results), 0, cost_usd, req.client_tag)

    return ToolSearchResponse(
        results=results, total=len(results),
        credits_used=0, cost_usd=cost_usd,
    )


# ── LinkedIn Search People ──────────────────────────────────────────

@router.post("/linkedin/search-people", response_model=ToolSearchResponse)
async def linkedin_search_people(
    req: LinkedInSearchPeopleRequest,
    db: AsyncSession = Depends(get_db),
):
    """Search LinkedIn for people/decision makers via Apify scraper."""
    from app.services.apify_scraper import ApifyScraperService

    if not app_settings.apify_api_token:
        raise HTTPException(400, "Apify API token not configured")

    search_query = req.keywords
    if req.company:
        search_query += f" {req.company}"
    if req.location:
        search_query += f" {req.location}"

    try:
        scraper = ApifyScraperService(app_settings.apify_api_token)
        raw = await scraper.run_actor(
            actor_id="harvestapi/linkedin-profile-search",
            input_data={
                "searchTerms": [search_query],
                "maxResults": req.max_results,
            },
            timeout=180,
        )
    except Exception as e:
        raise HTTPException(502, f"LinkedIn people search failed: {e}")

    results = []
    for item in raw.get("results", []):
        results.append({
            "first_name": item.get("firstName", ""),
            "last_name": item.get("lastName", ""),
            "name": item.get("fullName") or item.get("name", ""),
            "headline": item.get("headline", ""),
            "title": item.get("title") or item.get("headline", ""),
            "company": item.get("companyName") or item.get("company", ""),
            "location": item.get("location", ""),
            "linkedin_url": item.get("profileUrl") or item.get("url", ""),
            "email": item.get("email", ""),
        })

    cost_usd = raw.get("cost_usd", 0.0)
    await _log_search(db, "linkedin_people", search_query, req.model_dump(),
                      len(results), 0, cost_usd, req.client_tag)

    return ToolSearchResponse(
        results=results, total=len(results),
        credits_used=0, cost_usd=cost_usd,
    )


# ── LinkedIn Search Companies ──────────────────────────────────────

@router.post("/linkedin/search-companies", response_model=ToolSearchResponse)
async def linkedin_search_companies(
    req: LinkedInSearchCompaniesRequest,
    db: AsyncSession = Depends(get_db),
):
    """Search LinkedIn company profiles via Apify scraper."""
    from app.services.apify_scraper import ApifyScraperService

    if not app_settings.apify_api_token:
        raise HTTPException(400, "Apify API token not configured")

    if not req.company_urls and not req.company_names:
        raise HTTPException(400, "Provide company_urls or company_names")

    input_data = {}
    if req.company_urls:
        input_data["startUrls"] = [{"url": u} for u in req.company_urls]
    elif req.company_names:
        input_data["startUrls"] = [
            {"url": f"https://www.linkedin.com/company/{name.lower().replace(' ', '-')}"}
            for name in req.company_names
        ]

    try:
        scraper = ApifyScraperService(app_settings.apify_api_token)
        raw = await scraper.run_actor(
            actor_id="curious_coder/linkedin-company-scraper",
            input_data=input_data,
            timeout=300,
        )
    except Exception as e:
        raise HTTPException(502, f"LinkedIn companies search failed: {e}")

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

    cost_usd = raw.get("cost_usd", 0.0)
    query_label = ", ".join(req.company_names or [u.split("/")[-1] for u in (req.company_urls or [])[:5]])
    await _log_search(db, "linkedin_companies", query_label, req.model_dump(),
                      len(results), 0, cost_usd, req.client_tag)

    return ToolSearchResponse(
        results=results, total=len(results),
        credits_used=0, cost_usd=cost_usd,
    )


# ── Import Leads ────────────────────────────────────────────────────

@router.post("/import-leads", response_model=ImportLeadsResponse)
async def import_leads(
    req: ImportLeadsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Import selected results into People or Companies table."""
    from app.models.person import Person
    from app.models.company import Company

    imported = 0
    skipped = 0
    errors = 0

    if req.import_type == "people":
        existing_result = await db.execute(
            select(Person.email).where(Person.email.isnot(None))
        )
        existing_emails = {r[0].lower() for r in existing_result.all() if r[0]}

        for item in req.results:
            try:
                email = (item.get("email") or "").strip().lower() or None
                first_name = (item.get("first_name") or item.get("name", "")).strip() or "Unknown"
                last_name = (item.get("last_name") or "").strip() or ""

                if email and email in existing_emails:
                    skipped += 1
                    continue

                person = Person(
                    first_name=first_name,
                    last_name=last_name,
                    email=email or f"noemail_{imported}@prospecting.import",
                    phone=item.get("phone"),
                    company_name=item.get("company") or item.get("company_name") or item.get("name"),
                    linkedin_url=item.get("linkedin_url"),
                    industry=item.get("industry"),
                    location=item.get("location") or item.get("address"),
                    client_tag=req.client_tag,
                    list_id=req.list_id,
                )
                db.add(person)
                if email:
                    existing_emails.add(email)
                imported += 1
            except Exception:
                errors += 1

    else:  # companies
        existing_result = await db.execute(
            select(sa_func.lower(Company.name))
        )
        existing_names = {r[0] for r in existing_result.all() if r[0]}

        for item in req.results:
            try:
                name = (item.get("name") or "").strip()
                if not name:
                    errors += 1
                    continue
                if name.lower() in existing_names:
                    skipped += 1
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
                    industry=item.get("industry") or item.get("category"),
                    location=item.get("location") or item.get("address"),
                    website=website,
                    client_tag=req.client_tag,
                    list_id=req.list_id,
                )
                db.add(company)
                existing_names.add(name.lower())
                imported += 1
            except Exception:
                errors += 1

    await db.flush()

    msg = f"Importati {imported} {req.import_type}"
    if skipped:
        msg += f", {skipped} duplicati saltati"
    if errors:
        msg += f", {errors} errori"

    return ImportLeadsResponse(imported=imported, skipped=skipped, errors=errors, message=msg)


# ── Generate CSV ────────────────────────────────────────────────────

@router.post("/generate-csv")
async def generate_csv(req: GenerateCsvRequest):
    """Generate a downloadable CSV from results."""
    if not req.results:
        raise HTTPException(400, "No results to export")

    columns = req.columns or list(req.results[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in req.results:
        writer.writerow(row)

    content = output.getvalue()
    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    filename = req.filename or "export.csv"

    return {
        "filename": filename,
        "rows": len(req.results),
        "columns": columns,
        "content_base64": encoded,
    }


# ── Helper ──────────────────────────────────────────────────────────

async def _log_search(
    db: AsyncSession,
    search_type: str,
    query: Optional[str],
    filters: dict,
    results_count: int,
    credits: int,
    cost_usd: float,
    client_tag: Optional[str],
):
    """Log a search to ApolloSearchHistory for cost tracking."""
    history = ApolloSearchHistory(
        search_type=search_type,
        search_query=query,
        filters_applied=filters,
        results_count=results_count,
        apollo_credits_consumed=credits,
        claude_input_tokens=0,
        claude_output_tokens=0,
        cost_apollo_usd=cost_usd,
        cost_claude_usd=0.0,
        cost_total_usd=cost_usd,
        client_tag=client_tag,
        session_id=None,
    )
    db.add(history)
    await db.flush()
