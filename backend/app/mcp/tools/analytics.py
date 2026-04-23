"""MCP tools: analytics and cost tracking."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from sqlalchemy import func as sa_func, select

from app.mcp.session import db_session
from app.models.analytics import Analytics
from app.models.apollo_search_history import ApolloSearchHistory
from app.models.campaign import Campaign, CampaignStatus
from app.models.company import Company
from app.models.person import Person


def _parse_range(start: Optional[str], end: Optional[str]) -> tuple[date, date]:
    today = date.today()
    try:
        since = date.fromisoformat(start) if start else today - timedelta(days=30)
    except ValueError:
        since = today - timedelta(days=30)
    try:
        until = date.fromisoformat(end) if end else today
    except ValueError:
        until = today
    return since, until


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def dashboard_stats(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """Aggregated KPI + daily chart for a date range (YYYY-MM-DD). Defaults to last 30 days."""
        since, until = _parse_range(start_date, end_date)

        async with db_session() as db:
            people_count = (await db.execute(select(sa_func.count(Person.id)))).scalar() or 0
            companies_count = (await db.execute(select(sa_func.count(Company.id)))).scalar() or 0

            campaigns = (await db.execute(select(Campaign).where(Campaign.deleted_at.is_(None)))).scalars().all()
            active_campaigns = sum(1 for c in campaigns if c.status == CampaignStatus.ACTIVE)

            totals = (await db.execute(
                select(
                    sa_func.coalesce(sa_func.sum(Campaign.total_sent), 0),
                    sa_func.coalesce(sa_func.sum(Campaign.total_opened), 0),
                    sa_func.coalesce(sa_func.sum(Campaign.total_replied), 0),
                ).where(Campaign.deleted_at.is_(None))
            )).one()

            chart = (await db.execute(
                select(
                    Analytics.date,
                    sa_func.sum(Analytics.emails_sent),
                    sa_func.sum(Analytics.opens),
                    sa_func.sum(Analytics.replies),
                )
                .where(Analytics.date >= since, Analytics.date <= until)
                .group_by(Analytics.date)
                .order_by(Analytics.date.asc())
            )).all()

            converted = (await db.execute(
                select(sa_func.count(Person.id)).where(Person.converted_at.isnot(None))
            )).scalar() or 0

        return {
            "people_count": people_count,
            "companies_count": companies_count,
            "active_campaigns": active_campaigns,
            "total_sent": int(totals[0]),
            "total_opened": int(totals[1]),
            "total_replied": int(totals[2]),
            "converted_count": converted,
            "chart_data": [
                {"date": str(row[0]), "sent": row[1] or 0, "opens": row[2] or 0, "replies": row[3] or 0}
                for row in chart
            ],
            "date_range": {"start": str(since), "end": str(until)},
        }

    @mcp.tool()
    async def cost_breakdown(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        client_tag: Optional[str] = None,
    ) -> dict[str, Any]:
        """Sum of Apollo + Claude costs from search history. Dates YYYY-MM-DD."""
        since, until = _parse_range(start_date, end_date)

        async with db_session() as db:
            q = select(
                sa_func.coalesce(sa_func.sum(ApolloSearchHistory.apollo_credits_consumed), 0),
                sa_func.coalesce(sa_func.sum(ApolloSearchHistory.claude_input_tokens), 0),
                sa_func.coalesce(sa_func.sum(ApolloSearchHistory.claude_output_tokens), 0),
                sa_func.coalesce(sa_func.sum(ApolloSearchHistory.cost_apollo_usd), 0.0),
                sa_func.coalesce(sa_func.sum(ApolloSearchHistory.cost_claude_usd), 0.0),
                sa_func.coalesce(sa_func.sum(ApolloSearchHistory.cost_total_usd), 0.0),
                sa_func.count(ApolloSearchHistory.id),
            ).where(
                ApolloSearchHistory.created_at >= since,
                ApolloSearchHistory.created_at <= until,
            )
            if client_tag:
                q = q.where(ApolloSearchHistory.client_tag == client_tag)

            row = (await db.execute(q)).one()

            # Also daily breakdown
            daily_q = (
                select(
                    sa_func.date(ApolloSearchHistory.created_at).label("day"),
                    sa_func.coalesce(sa_func.sum(ApolloSearchHistory.cost_total_usd), 0.0),
                )
                .where(
                    ApolloSearchHistory.created_at >= since,
                    ApolloSearchHistory.created_at <= until,
                )
                .group_by(sa_func.date(ApolloSearchHistory.created_at))
                .order_by(sa_func.date(ApolloSearchHistory.created_at).asc())
            )
            if client_tag:
                daily_q = daily_q.where(ApolloSearchHistory.client_tag == client_tag)
            daily = (await db.execute(daily_q)).all()

        return {
            "searches": int(row[6]),
            "apollo_credits_consumed": int(row[0]),
            "claude_input_tokens": int(row[1]),
            "claude_output_tokens": int(row[2]),
            "cost_apollo_usd": float(row[3]),
            "cost_claude_usd": float(row[4]),
            "cost_total_usd": float(row[5]),
            "daily": [{"date": str(r[0]), "cost_usd": float(r[1])} for r in daily],
            "date_range": {"start": str(since), "end": str(until)},
            "client_tag": client_tag,
        }

    @mcp.tool()
    async def list_client_tags() -> dict[str, Any]:
        """Return every distinct client_tag used across people, companies, and search history."""
        async with db_session() as db:
            p_tags = (await db.execute(
                select(Person.client_tag).where(Person.client_tag.isnot(None)).distinct()
            )).all()
            c_tags = (await db.execute(
                select(Company.client_tag).where(Company.client_tag.isnot(None)).distinct()
            )).all()
            s_tags = (await db.execute(
                select(ApolloSearchHistory.client_tag).where(ApolloSearchHistory.client_tag.isnot(None)).distinct()
            )).all()

        all_tags: set[str] = set()
        for row_set in (p_tags, c_tags, s_tags):
            for row in row_set:
                raw = row[0] or ""
                for tag in raw.split(","):
                    tag = tag.strip()
                    if tag:
                        all_tags.add(tag)

        return {"client_tags": sorted(all_tags)}
