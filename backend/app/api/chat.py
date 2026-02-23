from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.db.database import get_db
from app.schemas.chat import ChatRequest
from app.services.icp_parser import icp_parser_service
from app.services.file_parser import extract_text_from_file
from app.services.apollo import apollo_service, ApolloAPIError
from app.services.enrichment import CompanyEnrichmentService
from app.models.person import Person
from app.models.company import Company
from app.models.apollo_search_history import ApolloSearchHistory

router = APIRouter()


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """SSE streaming endpoint for chat with Claude."""
    return StreamingResponse(
        icp_parser_service.stream_chat(request.messages, request.file_content),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a document and extract its text content."""
    allowed_extensions = {".pdf", ".docx", ".txt"}
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in allowed_extensions:
        raise HTTPException(
            400,
            f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}",
        )

    if file.size and file.size > 10 * 1024 * 1024:
        raise HTTPException(400, "File too large. Maximum size is 10MB.")

    try:
        text = await extract_text_from_file(file)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {"filename": filename, "text": text, "length": len(text)}


# ---------------------------------------------------------------------------
# Apollo endpoints
# ---------------------------------------------------------------------------

class ApolloFilters(BaseModel):
    person_titles: Optional[list[str]] = None
    person_locations: Optional[list[str]] = None
    person_seniorities: Optional[list[str]] = None
    organization_locations: Optional[list[str]] = None
    organization_keywords: Optional[list[str]] = None
    organization_sizes: Optional[list[str]] = None
    technologies: Optional[list[str]] = None
    keywords: Optional[str] = None


class ApolloSearchRequest(BaseModel):
    search_type: str  # "people" | "companies"
    filters: ApolloFilters
    per_page: int = 25
    client_tag: Optional[str] = None
    claude_tokens: Optional[dict] = None  # {input_tokens, output_tokens, total_tokens}


class ApolloImportRequest(BaseModel):
    results: list[dict]
    target: str  # "people" | "companies"
    client_tag: Optional[str] = None
    auto_enrich: bool = False  # Auto-enrich companies with website scraping


@router.post("/apollo/search")
async def apollo_search(request: ApolloSearchRequest, db: AsyncSession = Depends(get_db)):
    """Search Apollo and return a preview of results."""
    try:
        if request.search_type == "people":
            raw = await apollo_service.search_people(
                person_titles=request.filters.person_titles,
                person_locations=request.filters.person_locations,
                person_seniorities=request.filters.person_seniorities,
                organization_keywords=request.filters.organization_keywords,
                organization_sizes=request.filters.organization_sizes,
                keywords=request.filters.keywords,
                per_page=request.per_page,
            )
            results = apollo_service.format_people_results(raw)
            total = raw.get("pagination", {}).get("total_entries", len(results))
        elif request.search_type == "companies":
            raw = await apollo_service.search_organizations(
                organization_locations=request.filters.organization_locations,
                organization_keywords=request.filters.organization_keywords,
                organization_sizes=request.filters.organization_sizes,
                technologies=request.filters.technologies,
                keywords=request.filters.keywords,
                per_page=request.per_page,
            )
            results = apollo_service.format_org_results(raw)
            total = raw.get("pagination", {}).get("total_entries", len(results))
        else:
            raise HTTPException(400, "search_type must be 'people' or 'companies'")

        credits_consumed = raw.get("credits_consumed", 0)

        # Calculate costs
        apollo_cost_usd = credits_consumed * 0.10  # $0.10 per credit
        claude_input_tokens = request.claude_tokens.get("input_tokens", 0) if request.claude_tokens else 0
        claude_output_tokens = request.claude_tokens.get("output_tokens", 0) if request.claude_tokens else 0
        claude_cost_usd = (claude_input_tokens / 1_000_000 * 3.0) + (claude_output_tokens / 1_000_000 * 15.0)
        total_cost_usd = apollo_cost_usd + claude_cost_usd

        # Save search history to database
        search_history = ApolloSearchHistory(
            search_type=request.search_type,
            search_query=request.filters.keywords,
            filters_applied=request.filters.model_dump(),
            results_count=len(results),
            apollo_credits_consumed=credits_consumed,
            claude_input_tokens=claude_input_tokens,
            claude_output_tokens=claude_output_tokens,
            cost_apollo_usd=round(apollo_cost_usd, 4),
            cost_claude_usd=round(claude_cost_usd, 4),
            cost_total_usd=round(total_cost_usd, 4),
            client_tag=request.client_tag,
            icp_id=None,  # Could be extracted from context if needed
        )
        db.add(search_history)
        await db.flush()
        await db.refresh(search_history)

        return {
            "results": results,
            "total": total,
            "search_type": request.search_type,
            "returned": len(results),
            "credits_consumed": credits_consumed,
            "history_id": search_history.id,
        }

    except ApolloAPIError as e:
        raise HTTPException(e.status_code, e.detail)


@router.get("/apollo/credits")
async def get_apollo_credits():
    """Get Apollo API credits status."""
    try:
        result = await apollo_service.get_credits_status()
        # Extract relevant credits info from the health endpoint response
        # The actual structure depends on Apollo's API response
        return {
            "status": "ok",
            "data": result,
        }
    except ApolloAPIError as e:
        raise HTTPException(e.status_code, e.detail)


@router.post("/apollo/import")
async def apollo_import(request: ApolloImportRequest, db: AsyncSession = Depends(get_db)):
    """Import Apollo search results into People or Companies table."""
    if request.target not in ("people", "companies"):
        raise HTTPException(400, "target must be 'people' or 'companies'")

    imported = 0
    duplicates_skipped = 0
    errors = 0

    if request.target == "people":
        from sqlalchemy import select, func as sa_func
        existing_result = await db.execute(select(Person.email))
        existing_emails = {r[0].lower() for r in existing_result.all() if r[0]}

        # Pre-load all companies for auto-matching
        companies_result = await db.execute(select(Company.id, Company.name))
        companies_map = {name.lower().strip(): cid for cid, name in companies_result.all()}

        for item in request.results:
            try:
                email = (item.get("email") or "").strip().lower() or None
                first_name = (item.get("first_name") or "").strip() or "Unknown"
                last_name = (item.get("last_name") or "").strip() or "Unknown"

                if email and email in existing_emails:
                    duplicates_skipped += 1
                    continue

                # Auto-match company by name
                company_name = (item.get("company") or "").strip() or None
                company_id = None
                if company_name:
                    company_id = companies_map.get(company_name.lower())

                person = Person(
                    first_name=first_name,
                    last_name=last_name,
                    email=email or f"noemail_{imported}@apollo.import",
                    phone=item.get("phone"),
                    company_id=company_id,
                    company_name=company_name,
                    linkedin_url=item.get("linkedin_url"),
                    industry=item.get("industry"),
                    location=item.get("location"),
                    client_tag=request.client_tag,
                )
                db.add(person)
                if email:
                    existing_emails.add(email)
                imported += 1
            except Exception:
                errors += 1

    else:  # companies
        from sqlalchemy import select, func as sa_func
        existing_result = await db.execute(
            select(sa_func.lower(Company.name))
        )
        existing_names = {r[0] for r in existing_result.all() if r[0]}

        def _extract_domain(website: Optional[str]) -> Optional[str]:
            if not website:
                return None
            domain = website.lower().replace("https://", "").replace("http://", "").split("/")[0]
            return domain or None

        companies_to_enrich = []
        for item in request.results:
            try:
                name = (item.get("name") or "").strip()
                if not name:
                    errors += 1
                    continue
                if name.lower() in existing_names:
                    duplicates_skipped += 1
                    continue

                website = item.get("website")
                company = Company(
                    name=name,
                    email=item.get("email"),
                    phone=item.get("phone"),
                    email_domain=_extract_domain(website),
                    linkedin_url=item.get("linkedin_url"),
                    industry=item.get("industry"),
                    location=item.get("location"),
                    signals=item.get("signals"),
                    website=website,
                    client_tag=request.client_tag,
                )
                db.add(company)
                existing_names.add(name.lower())
                companies_to_enrich.append(company)
                imported += 1
            except Exception:
                errors += 1

        # Flush to get IDs
        await db.flush()

        # Auto-enrich companies if requested
        if request.auto_enrich and companies_to_enrich:
            enrichment_service = CompanyEnrichmentService(db)
            try:
                await enrichment_service.enrich_companies_batch(
                    companies_to_enrich,
                    max_concurrent=3
                )
            finally:
                await enrichment_service.close()

    await db.flush()
    return {"imported": imported, "duplicates_skipped": duplicates_skipped, "errors": errors}
