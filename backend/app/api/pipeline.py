"""Pipeline API — Manage lead generation pipeline runs and review queue."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.pipeline import (
    PipelineRunCreate,
    PipelineRunResponse,
    PipelineRunListResponse,
    PipelineLeadResponse,
    PipelineLeadListResponse,
    PipelineDiscardRequest,
    PipelineFirstLineEdit,
)
from app.services.pipeline_service import PipelineService

logger = logging.getLogger(__name__)
router = APIRouter()


# === Pipeline Runs ===


@router.post("/run", response_model=PipelineRunResponse)
async def start_pipeline_run(
    data: PipelineRunCreate,
    db: AsyncSession = Depends(get_db),
):
    """Start a new pipeline run."""
    service = PipelineService(db)
    try:
        run = await service.create_run(
            ai_agent_id=data.ai_agent_id,
            client_tag=data.client_tag,
            icp_override=data.icp_override,
        )
        await db.commit()

        # Trigger Celery task (lazy import to avoid startup failures)
        try:
            from app.workers.pipeline_tasks import run_pipeline_task
            run_pipeline_task.delay(run.id)
        except Exception as exc:
            logger.warning(f"Celery task dispatch failed (will run manually): {exc}")
        logger.info(f"Pipeline run started: {run.run_id}")

        return run
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/runs", response_model=PipelineRunListResponse)
async def list_pipeline_runs(
    client_tag: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List pipeline runs with optional filters."""
    service = PipelineService(db)
    runs, total = await service.list_runs(client_tag, status, skip, limit)
    return PipelineRunListResponse(runs=runs, total=total)


@router.get("/runs/{run_id}", response_model=PipelineRunResponse)
async def get_pipeline_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get pipeline run detail by UUID."""
    service = PipelineService(db)
    run = await service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return run


@router.post("/runs/{run_id}/cancel", response_model=PipelineRunResponse)
async def cancel_pipeline_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running pipeline."""
    service = PipelineService(db)
    try:
        run = await service.cancel_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Pipeline run not found")
        await db.commit()
        return run
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# === Review Queue ===


@router.get("/review", response_model=PipelineLeadListResponse)
async def get_review_queue(
    client_tag: Optional[str] = Query(None),
    score: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get pipeline leads in review queue (scored + review_postponed)."""
    service = PipelineService(db)
    leads, total, total_pages = await service.get_review_queue(
        client_tag, score, page, page_size
    )
    return PipelineLeadListResponse(
        leads=leads,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/review/{lead_id}/approve", response_model=PipelineLeadResponse)
async def approve_pipeline_lead(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Approve a lead from the review queue."""
    service = PipelineService(db)
    lead = await service.approve_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Pipeline lead not found")
    await db.commit()
    return lead


@router.post("/review/{lead_id}/discard", response_model=PipelineLeadResponse)
async def discard_pipeline_lead(
    lead_id: int,
    data: Optional[PipelineDiscardRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """Discard a lead from the review queue."""
    service = PipelineService(db)
    reason = data.reason if data else None
    lead = await service.discard_lead(lead_id, reason)
    if not lead:
        raise HTTPException(status_code=404, detail="Pipeline lead not found")
    await db.commit()
    return lead


@router.post("/review/{lead_id}/postpone", response_model=PipelineLeadResponse)
async def postpone_pipeline_lead(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Postpone a lead in the review queue."""
    service = PipelineService(db)
    lead = await service.postpone_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Pipeline lead not found")
    await db.commit()
    return lead


@router.patch("/review/{lead_id}/first-line", response_model=PipelineLeadResponse)
async def edit_first_line(
    lead_id: int,
    data: PipelineFirstLineEdit,
    db: AsyncSession = Depends(get_db),
):
    """Edit the first line email for a lead."""
    service = PipelineService(db)
    lead = await service.update_first_line(lead_id, data.first_line_email)
    if not lead:
        raise HTTPException(status_code=404, detail="Pipeline lead not found")
    await db.commit()
    return lead
