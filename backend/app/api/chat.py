from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.db.database import get_db
from app.schemas.chat import ChatRequest, CreateSessionRequest, ChatStreamRequest, SessionResponse
from app.services.icp_parser import icp_parser_service
from app.services.file_parser import extract_text_from_file
from app.services.apollo import apollo_service, ApolloAPIError
from app.services.apify_enrichment import apify_enrichment_service, ApifyEnrichmentError
from app.services.enrichment import CompanyEnrichmentService
from app.services.conversational_chat import ConversationalChatService
from app.models.person import Person
from app.models.company import Company
from app.models.apollo_search_history import ApolloSearchHistory

router = APIRouter()


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """SSE streaming endpoint for chat with Claude (legacy - stateless)."""
    return StreamingResponse(
        icp_parser_service.stream_chat(request.messages, request.file_content),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Session-based conversational chat endpoints
# ---------------------------------------------------------------------------

@router.post("/sessions", response_model=SessionResponse)
async def create_chat_session(
    request: CreateSessionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create a new chat session."""
    service = ConversationalChatService(db)
    session = await service.create_session(
        client_tag=request.client_tag,
        title=request.title
    )
    await db.commit()
    return session


@router.get("/sessions/{session_uuid}")
async def get_chat_session(
    session_uuid: str,
    db: AsyncSession = Depends(get_db)
):
    """Get session details with messages and summary."""
    service = ConversationalChatService(db)
    session = await service.get_session(session_uuid)

    if not session:
        raise HTTPException(404, "Session not found")

    summary = await service.get_session_summary(session_uuid)

    return {
        "session": {
            "session_uuid": session.session_uuid,
            "title": session.title,
            "status": session.status,
            "client_tag": session.client_tag,
            "created_at": session.created_at,
            "last_message_at": session.last_message_at,
            "total_cost_usd": session.total_cost_usd,
            "total_claude_input_tokens": session.total_claude_input_tokens,
            "total_claude_output_tokens": session.total_claude_output_tokens,
            "total_apollo_credits": session.total_apollo_credits,
            "current_icp_draft": session.current_icp_draft,
            "session_metadata": session.session_metadata,
        },
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "tool_calls": msg.tool_calls,
                "tool_results": msg.tool_results,
                "created_at": msg.created_at,
            }
            for msg in session.messages
        ],
        "summary": summary,
    }


@router.post("/sessions/{session_uuid}/stream")
async def stream_conversational_chat(
    session_uuid: str,
    request: ChatStreamRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Main streaming endpoint with multi-turn tool orchestration.

    Handles conversational chat with RAG capabilities:
    - Remembers session context (ICP draft, last search, enrichment)
    - Multi-turn tool execution (Claude -> tool -> Claude -> tool)
    - Streams SSE events: text, tool_start, tool_complete, done
    """
    service = ConversationalChatService(db)

    # Check if session exists
    session = await service.get_session(session_uuid)
    if not session:
        raise HTTPException(404, "Session not found")

    return StreamingResponse(
        service.stream_chat(
            session_uuid=session_uuid,
            user_message=request.message,
            file_content=request.file_content,
            mode=request.mode,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions")
async def list_chat_sessions(
    client_tag: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """List chat sessions with pagination."""
    service = ConversationalChatService(db)
    sessions = await service.list_sessions(
        client_tag=client_tag,
        status=status,
        limit=limit,
        offset=offset
    )

    return {
        "sessions": [
            {
                "session_uuid": s.session_uuid,
                "title": s.title,
                "status": s.status,
                "client_tag": s.client_tag,
                "created_at": s.created_at,
                "last_message_at": s.last_message_at,
                "total_cost_usd": s.total_cost_usd,
                "message_count": len(s.messages) if s.messages else 0,
            }
            for s in sessions
        ],
        "limit": limit,
        "offset": offset,
    }


@router.delete("/sessions/{session_uuid}")
async def archive_chat_session(
    session_uuid: str,
    db: AsyncSession = Depends(get_db)
):
    """Archive a chat session (soft delete)."""
    service = ConversationalChatService(db)
    await service.archive_session(session_uuid)
    await db.commit()
    return {"status": "archived", "session_uuid": session_uuid}


class SearchContextRequest(BaseModel):
    search_type: str
    total: int
    returned: int
    filters: dict


@router.post("/sessions/{session_uuid}/search-context")
async def save_search_context(
    session_uuid: str,
    request: SearchContextRequest,
    db: AsyncSession = Depends(get_db),
):
    """Save manual form search context into session metadata so AI chat knows about it."""
    service = ConversationalChatService(db)
    session = await service.get_session(session_uuid)
    if not session:
        raise HTTPException(404, "Session not found")

    from app.services.chat_session import ChatSessionService
    session_service = ChatSessionService(db)
    await session_service.update_session_metadata(session.id, {
        "last_apollo_search": {
            "type": request.search_type,
            "count": request.total,
            "returned": request.returned,
            "params": request.filters,
        }
    })
    await db.commit()

    return {"status": "ok"}


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
    auto_enrich: bool = False  # When True, enriches all results (1 credit/person)


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
                auto_enrich=request.auto_enrich,
            )
            results = apollo_service.format_people_results(raw)
            # Inject searched location as fallback when Apollo doesn't return it
            if request.filters.person_locations:
                fallback_location = ", ".join(request.filters.person_locations)
                for r in results:
                    if not r.get("location"):
                        r["location"] = fallback_location
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


class ApolloEnrichRequest(BaseModel):
    people: list[dict]  # Apollo person records with id, first_name, last_name, organization_name
    source: str = "apollo"  # "apollo" or "apify"


@router.post("/apollo/enrich")
async def apollo_enrich_selected(request: ApolloEnrichRequest, db: AsyncSession = Depends(get_db)):
    """Enrich selected people on-demand. source=apollo (default) or source=apify (fallback)."""
    if not request.people:
        raise HTTPException(400, "No people to enrich")

    if request.source == "apify":
        return await _enrich_via_apify(request.people, db)

    # Default: Apollo enrichment
    try:
        enriched_data = {}
        total_credits = 0

        for i in range(0, len(request.people), 10):
            batch = request.people[i:i+10]
            result = await apollo_service.enrich_people(batch)
            credits = result.get("credits_consumed", 0)
            total_credits += credits
            for match in result.get("matches", []):
                if match.get("id"):
                    enriched_data[match["id"]] = {
                        "id": match["id"],
                        "email": match.get("email"),
                        "phone": match.get("phone"),
                        "direct_phone": match.get("direct_phone"),
                        "linkedin_url": match.get("linkedin_url"),
                        "first_name": match.get("first_name"),
                        "last_name": match.get("last_name"),
                        "city": match.get("city"),
                        "state": match.get("state"),
                        "country": match.get("country"),
                    }

        # Track in search history
        history = ApolloSearchHistory(
            search_type="enrich",
            results_count=len(enriched_data),
            apollo_credits_consumed=total_credits,
            cost_apollo_usd=total_credits * 0.10,
            cost_total_usd=total_credits * 0.10,
        )
        db.add(history)
        await db.commit()

        return {
            "enriched": enriched_data,
            "credits_consumed": total_credits,
            "enriched_count": len(enriched_data),
        }
    except ApolloAPIError as e:
        # If credits exhausted (402), tell frontend to offer Apify fallback
        if e.status_code == 402:
            return {
                "error": "credits_exhausted",
                "message": "Crediti Apollo esauriti. Vuoi usare Apify (~$0.005/lead)?",
                "enriched": {},
                "credits_consumed": 0,
                "enriched_count": 0,
            }
        raise HTTPException(e.status_code, e.detail)


async def _enrich_via_apify(people: list[dict], db: AsyncSession) -> dict:
    """Enrich people using Apify Waterfall as fallback."""
    try:
        result = await apify_enrichment_service.enrich_people(people)

        # Track in search history
        history = ApolloSearchHistory(
            search_type="apify_enrich",
            results_count=result.get("enriched_count", 0),
            apollo_credits_consumed=0,
            cost_apollo_usd=0,
            cost_total_usd=result.get("apify_cost_usd", 0),
        )
        db.add(history)
        await db.commit()

        return {
            "enriched": result["enriched"],
            "credits_consumed": 0,
            "enriched_count": result["enriched_count"],
            "source": "apify",
            "apify_cost_usd": result.get("apify_cost_usd", 0),
        }
    except ApifyEnrichmentError as e:
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
