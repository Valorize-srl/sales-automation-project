"""Bandi Monitor API — list, fetch, analyze government grants."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.bando import Bando, BandoSource, BandoStatus
from app.schemas.bando import (
    BandoOut,
    BandoListResponse,
    BandoStatsOut,
    FetchBandiResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/stats", response_model=BandoStatsOut)
async def get_bandi_stats(db: AsyncSession = Depends(get_db)):
    """Get bandi KPI statistics."""
    from app.services.bandi_monitor import BandiMonitorService
    service = BandiMonitorService(db)
    return await service.get_stats()


@router.get("", response_model=BandoListResponse)
async def list_bandi(
    source: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    ateco: Optional[str] = Query(None, description="ATECO code to filter by"),
    region: Optional[str] = Query(None),
    deadline_before: Optional[str] = Query(None, description="YYYY-MM-DD"),
    deadline_after: Optional[str] = Query(None, description="YYYY-MM-DD"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List bandi with optional filters."""
    query = select(Bando).order_by(Bando.created_at.desc())

    if source:
        query = query.where(Bando.source == source)
    if status:
        query = query.where(Bando.status == status)
    if search:
        query = query.where(
            Bando.title.ilike(f"%{search}%")
            | Bando.ai_summary.ilike(f"%{search}%")
        )
    if ateco:
        from sqlalchemy import Text as SAText
        query = query.where(Bando.ateco_codes.cast(SAText).ilike(f"%{ateco}%"))
    if region:
        from sqlalchemy import Text as SAText
        query = query.where(Bando.regions.cast(SAText).ilike(f"%{region}%"))
    if deadline_before:
        dt = datetime.fromisoformat(deadline_before + "T23:59:59+00:00")
        query = query.where(Bando.deadline <= dt)
    if deadline_after:
        dt = datetime.fromisoformat(deadline_after + "T00:00:00+00:00")
        query = query.where(Bando.deadline >= dt)

    # Count total before pagination
    count_query = select(sa_func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    bandi = result.scalars().all()

    return BandoListResponse(
        bandi=[BandoOut.model_validate(b) for b in bandi],
        total=total,
    )


@router.get("/{bando_id}", response_model=BandoOut)
async def get_bando(bando_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single bando by ID."""
    bando = await db.get(Bando, bando_id)
    if not bando:
        raise HTTPException(404, "Bando not found")
    return BandoOut.model_validate(bando)


@router.post("/fetch", response_model=FetchBandiResponse)
async def fetch_bandi(db: AsyncSession = Depends(get_db)):
    """Fetch new bandi from all sources. AI analysis runs in background."""
    from app.services.bandi_monitor import BandiMonitorService
    service = BandiMonitorService(db)

    # Fetch only (fast: RSS + scraping, typically <5s)
    fetch_result = await service.fetch_all_sources()

    # Trigger AI analysis in background (slow: Claude API calls)
    import asyncio
    asyncio.create_task(_analyze_in_background())

    return FetchBandiResponse(
        fetched=fetch_result["fetched"],
        analyzed=0,
        errors=fetch_result["errors"],
        message=f"Trovati {fetch_result['fetched']} nuovi bandi. Analisi AI in corso in background.",
    )


async def _analyze_in_background():
    """Run AI analysis in a separate DB session (background task)."""
    try:
        from app.db.database import async_session_factory
        from app.services.bandi_monitor import BandiMonitorService
        async with async_session_factory() as db:
            service = BandiMonitorService(db)
            analyzed = await service.analyze_new_bandi()
            logger.info(f"Background analysis completed: {analyzed} bandi analyzed")
    except Exception as e:
        logger.error(f"Background bandi analysis failed: {e}")


@router.post("/{bando_id}/analyze", response_model=BandoOut)
async def analyze_bando(bando_id: int, db: AsyncSession = Depends(get_db)):
    """Re-analyze a specific bando with AI."""
    bando = await db.get(Bando, bando_id)
    if not bando:
        raise HTTPException(404, "Bando not found")

    # Reset status to trigger re-analysis
    bando.status = BandoStatus.NEW
    await db.flush()

    from app.services.bandi_monitor import BandiMonitorService
    service = BandiMonitorService(db)
    await service.analyze_new_bandi()

    await db.refresh(bando)
    return BandoOut.model_validate(bando)


@router.get("/{bando_id}/matches")
async def get_bando_matches(bando_id: int, db: AsyncSession = Depends(get_db)):
    """Find companies matching a bando's criteria."""
    from app.services.bandi_monitor import BandiMonitorService
    service = BandiMonitorService(db)
    matches = await service.find_matching_companies(bando_id)
    return {"matches": matches, "total": len(matches)}


@router.post("/{bando_id}/archive", response_model=BandoOut)
async def archive_bando(bando_id: int, db: AsyncSession = Depends(get_db)):
    """Archive a bando."""
    bando = await db.get(Bando, bando_id)
    if not bando:
        raise HTTPException(404, "Bando not found")
    bando.status = BandoStatus.ARCHIVED
    await db.commit()
    await db.refresh(bando)
    return BandoOut.model_validate(bando)
