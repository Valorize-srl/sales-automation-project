"""Activity log API: read-only timeline of events on accounts and contacts."""
from __future__ import annotations

import math
from datetime import datetime
from typing import Optional, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.activity_log import ActivityLog

router = APIRouter()


class ActivityEntryOut(BaseModel):
    id: int
    target_type: str
    target_id: int
    action: str
    payload: Optional[dict[str, Any]] = None
    actor: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ActivityListResponse(BaseModel):
    activities: list[ActivityEntryOut]
    total: int
    page: int
    page_size: int
    total_pages: int


@router.get("", response_model=ActivityListResponse)
async def list_activity(
    target_type: Optional[str] = Query(None, description="'account' | 'contact'"),
    target_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    actor: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    q = select(ActivityLog).order_by(ActivityLog.created_at.desc())
    if target_type:
        q = q.where(ActivityLog.target_type == target_type)
    if target_id is not None:
        q = q.where(ActivityLog.target_id == target_id)
    if action:
        q = q.where(ActivityLog.action == action)
    if actor:
        q = q.where(ActivityLog.actor == actor)

    total = (await db.execute(select(sa_func.count()).select_from(q.subquery()))).scalar() or 0
    rows = (await db.execute(q.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return ActivityListResponse(
        activities=[ActivityEntryOut.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 1,
    )
