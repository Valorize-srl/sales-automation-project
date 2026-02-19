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
from app.models.person import Person
from app.models.company import Company

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
    person_titles: list[str] | None = None
    person_locations: list[str] | None = None
    person_seniorities: list[str] | None = None
    organization_locations: list[str] | None = None
    organization_keywords: list[str] | None = None
    organization_sizes: list[str] | None = None
    technologies: list[str] | None = None
    keywords: str | None = None


class ApolloSearchRequest(BaseModel):
    search_type: str  # "people" | "companies"
    filters: ApolloFilters
    per_page: int = 25


class ApolloImportRequest(BaseModel):
    results: list[dict]
    target: str  # "people" | "companies"


@router.post("/apollo/search")
async def apollo_search(request: ApolloSearchRequest):
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

        return {
            "results": results,
            "total": total,
            "search_type": request.search_type,
            "returned": len(results),
            "credits_consumed": raw.get("credits_consumed", 0),
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

        for item in request.results:
            try:
                email = (item.get("email") or "").strip().lower() or None
                first_name = (item.get("first_name") or "").strip() or "Unknown"
                last_name = (item.get("last_name") or "").strip() or "Unknown"

                if email and email in existing_emails:
                    duplicates_skipped += 1
                    continue

                person = Person(
                    first_name=first_name,
                    last_name=last_name,
                    email=email or f"noemail_{imported}@apollo.import",
                    phone=item.get("phone"),
                    company_name=item.get("company"),
                    linkedin_url=item.get("linkedin_url"),
                    industry=item.get("industry"),
                    location=item.get("location"),
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

        def _extract_domain(website: str | None) -> str | None:
            if not website:
                return None
            domain = website.lower().replace("https://", "").replace("http://", "").split("/")[0]
            return domain or None

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
                )
                db.add(company)
                existing_names.add(name.lower())
                imported += 1
            except Exception:
                errors += 1

    await db.flush()
    return {"imported": imported, "duplicates_skipped": duplicates_skipped, "errors": errors}
