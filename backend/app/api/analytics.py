from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.analytics import Analytics

router = APIRouter()


@router.get("")
async def get_analytics(
    campaign_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get analytics entries, optionally filtered by campaign."""
    query = select(Analytics).order_by(Analytics.date.desc())
    if campaign_id is not None:
        query = query.where(Analytics.campaign_id == campaign_id)
    result = await db.execute(query)
    entries = result.scalars().all()
    return {"entries": entries, "total": len(entries)}
