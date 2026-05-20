from typing import Optional
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.analytics import Analytics
from app.models.campaign import Campaign, CampaignStatus
from app.models.email_response import EmailResponse, MessageDirection
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
async def get_dashboard_stats(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate stats for the dashboard overview with optional date range."""

    # Parse date range
    if start_date:
        try:
            since = date.fromisoformat(start_date)
        except ValueError:
            since = date.today() - timedelta(days=30)
    else:
        since = date.today() - timedelta(days=30)

    if end_date:
        try:
            until = date.fromisoformat(end_date)
        except ValueError:
            until = date.today()
    else:
        until = date.today()

    # People count
    people_result = await db.execute(select(sa_func.count(Person.id)))
    people_count = people_result.scalar() or 0

    # Companies count
    companies_result = await db.execute(select(sa_func.count(Company.id)))
    companies_count = companies_result.scalar() or 0

    # Campaigns: active count
    campaigns_result = await db.execute(select(Campaign))
    campaigns = campaigns_result.scalars().all()
    active_campaigns = sum(1 for c in campaigns if c.status == CampaignStatus.ACTIVE)

    # Totals from Campaign table (always up-to-date after sync)
    totals_result = await db.execute(
        select(
            sa_func.coalesce(sa_func.sum(Campaign.total_sent), 0).label("sent"),
            sa_func.coalesce(sa_func.sum(Campaign.total_opened), 0).label("opened"),
            sa_func.coalesce(sa_func.sum(Campaign.total_replied), 0).label("replied"),
        )
        .where(Campaign.deleted_at.is_(None))
    )
    totals = totals_result.one()
    total_sent = int(totals.sent)
    total_opened = int(totals.opened)
    total_replied = int(totals.replied)

    # Chart data within date range
    chart_result = await db.execute(
        select(
            Analytics.date,
            sa_func.sum(Analytics.emails_sent).label("sent"),
            sa_func.sum(Analytics.opens).label("opens"),
            sa_func.sum(Analytics.replies).label("replies"),
        )
        .where(Analytics.date >= since, Analytics.date <= until)
        .group_by(Analytics.date)
        .order_by(Analytics.date.asc())
    )
    chart_data = [
        {"date": str(row.date), "sent": row.sent or 0, "opens": row.opens or 0, "replies": row.replies or 0}
        for row in chart_result.all()
    ]

    # Converted leads count
    converted_result = await db.execute(
        select(sa_func.count(Person.id)).where(Person.converted_at.isnot(None))
    )
    converted_count = converted_result.scalar() or 0

    # Reply intent breakdown — derived from EmailResponse rows landed in the
    # window (counted by Smartlead lead_category when present, falling back
    # to our internal sentiment bucket). Inbound replies only.
    since_dt = datetime.combine(since, datetime.min.time())
    until_dt = datetime.combine(until, datetime.max.time())
    date_col = sa_func.coalesce(EmailResponse.received_at, EmailResponse.created_at)

    cat_result = await db.execute(
        select(EmailResponse.lead_category, sa_func.count())
        .where(
            EmailResponse.direction == MessageDirection.INBOUND,
            date_col >= since_dt,
            date_col <= until_dt,
        )
        .group_by(EmailResponse.lead_category)
    )
    intent_breakdown: list[dict] = []
    for cat_name, cnt in cat_result.all():
        intent_breakdown.append({
            "category": cat_name or "Uncategorized",
            "count": int(cnt),
        })
    intent_breakdown.sort(key=lambda r: r["count"], reverse=True)

    # Top campaigns by reply rate (reply_count / sent_count). Only campaigns
    # with non-trivial volume (sent >= 5) and at least one reply make the
    # cut, sorted desc, capped at 5.
    top_q = await db.execute(
        select(
            Campaign.id,
            Campaign.name,
            Campaign.total_sent,
            Campaign.total_opened,
            Campaign.total_replied,
        )
        .where(
            Campaign.deleted_at.is_(None),
            Campaign.total_sent >= 5,
        )
    )
    top_rows = []
    for row in top_q.all():
        sent = int(row.total_sent or 0)
        replied = int(row.total_replied or 0)
        if sent <= 0:
            continue
        top_rows.append({
            "id": row.id,
            "name": row.name,
            "total_sent": sent,
            "total_opened": int(row.total_opened or 0),
            "total_replied": replied,
            "reply_rate": round((replied / sent) * 100, 1),
        })
    top_rows.sort(key=lambda r: (-r["reply_rate"], -r["total_replied"]))
    top_campaigns = top_rows[:5]

    return {
        "people_count": people_count,
        "companies_count": companies_count,
        "active_campaigns": active_campaigns,
        "total_sent": total_sent,
        "total_opened": total_opened,
        "total_replied": total_replied,
        "converted_count": converted_count,
        "chart_data": chart_data,
        "intent_breakdown": intent_breakdown,
        "top_campaigns": top_campaigns,
        "date_range": {"start": str(since), "end": str(until)},
    }
