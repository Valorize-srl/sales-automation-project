from typing import Optional
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.analytics import Analytics
from app.models.campaign import Campaign
from app.models.person import Person
from app.models.company import Company

router = APIRouter()


@router.get("")
async def get_analytics(
    campaign_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get analytics entries, optionally filtered by campaign."""
    query = select(Analytics).order_by(Analytics.date.desc())
    if campaign_id is not None:
        query = query.where(Analytics.campaign_id == campaign_id)
    result = await db.execute(query)
    entries = result.scalars().all()
    return {"entries": entries, "total": len(entries)}


@router.get("/dashboard")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Aggregate stats for the dashboard overview."""

    # People count
    people_result = await db.execute(select(sa_func.count(Person.id)))
    people_count = people_result.scalar() or 0

    # Companies count
    companies_result = await db.execute(select(sa_func.count(Company.id)))
    companies_count = companies_result.scalar() or 0

    # Campaigns: active count + totals across all campaigns
    campaigns_result = await db.execute(select(Campaign))
    campaigns = campaigns_result.scalars().all()
    active_campaigns = sum(1 for c in campaigns if c.status == "active")
    total_sent = sum(c.total_sent for c in campaigns)
    total_opened = sum(c.total_opened for c in campaigns)
    total_replied = sum(c.total_replied for c in campaigns)

    # Analytics last 30 days, aggregated by date
    since = date.today() - timedelta(days=30)
    chart_result = await db.execute(
        select(
            Analytics.date,
            sa_func.sum(Analytics.emails_sent).label("sent"),
            sa_func.sum(Analytics.replies).label("replies"),
        )
        .where(Analytics.date >= since)
        .group_by(Analytics.date)
        .order_by(Analytics.date.asc())
    )
    chart_data = [
        {"date": str(row.date), "sent": row.sent or 0, "replies": row.replies or 0}
        for row in chart_result.all()
    ]

    return {
        "people_count": people_count,
        "companies_count": companies_count,
        "active_campaigns": active_campaigns,
        "total_sent": total_sent,
        "total_opened": total_opened,
        "total_replied": total_replied,
        "chart_data": chart_data,
    }
