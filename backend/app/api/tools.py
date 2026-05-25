"""Prospecting endpoints — slimmed to Apollo Search People + import + CSV export.

The previous version exposed 7 tools (Apollo people/companies/enrich + Apify
LinkedIn people/companies + Google Maps + Website scraper). Per user
direction (2026-05-25), only Apollo Search People is retained — the other
six were either unused or duplicated functionality already in /leads.

The remaining UI consumer is the `ApolloSearchPeopleDialog` in
`/leads → Arricchisci ▾ → Cerca nuove persone (Apollo)`.
"""

import csv
import io
import base64
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.apollo_search_history import ApolloSearchHistory
from app.schemas.tools import (
    ApolloSearchPeopleRequest,
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
    """Search Apollo.io for people. Each result costs 1 Apollo credit."""
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

    # Backfill location from search params when Apollo doesn't supply one.
    if req.person_locations:
        fallback = ", ".join(req.person_locations)
        for r in results:
            if not r.get("location"):
                r["location"] = fallback

    total = raw.get("pagination", {}).get("total_entries", len(results))
    credits_consumed = raw.get("credits_consumed", 0)
    cost_usd = credits_consumed * 0.10

    await _log_search(
        db, "people", req.keywords, req.model_dump(),
        len(results), credits_consumed, cost_usd, req.client_tag,
    )

    return ToolSearchResponse(
        results=results, total=total,
        credits_used=credits_consumed, cost_usd=cost_usd,
    )


# ── Import Leads (people only — companies path retained for future) ─


@router.post("/import-leads", response_model=ImportLeadsResponse)
async def import_leads(
    req: ImportLeadsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Import selected search results into the People or Companies tables."""
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
                    domain = (
                        website.lower()
                        .replace("https://", "")
                        .replace("http://", "")
                        .split("/")[0]
                        or None
                    )

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

    return ImportLeadsResponse(
        imported=imported, skipped=skipped, errors=errors, message=msg,
    )


# ── CSV Export ──────────────────────────────────────────────────────


@router.post("/generate-csv")
async def generate_csv(req: GenerateCsvRequest):
    """Generate a downloadable CSV from a list of result dicts."""
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
