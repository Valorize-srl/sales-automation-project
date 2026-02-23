from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.apollo_search_history import ApolloSearchHistory
from app.schemas.usage import SearchHistoryOut, SearchHistoryListResponse, UsageStats, UsageStatsResponse

router = APIRouter()


@router.get("/stats", response_model=UsageStatsResponse)
async def get_usage_stats(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    client_tag: Optional[str] = Query(None, description="Filter by client tag"),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregate usage statistics for a date range."""

    # Parse dates or use defaults
    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        start_dt = datetime.now() - timedelta(days=30)  # Last 30 days

    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)  # Include end date
    else:
        end_dt = datetime.now() + timedelta(days=1)

    # Build query
    query = select(ApolloSearchHistory).where(
        ApolloSearchHistory.created_at >= start_dt,
        ApolloSearchHistory.created_at < end_dt,
    )

    if client_tag:
        query = query.where(ApolloSearchHistory.client_tag == client_tag)

    result = await db.execute(query)
    searches = result.scalars().all()

    # Calculate aggregates
    total_searches = len(searches)
    total_results = sum(s.results_count for s in searches)
    total_apollo_credits = sum(s.apollo_credits_consumed for s in searches)
    total_claude_input_tokens = sum(s.claude_input_tokens for s in searches)
    total_claude_output_tokens = sum(s.claude_output_tokens for s in searches)
    total_cost_usd = sum(s.cost_total_usd for s in searches)
    total_apollo_cost = sum(s.cost_apollo_usd for s in searches)
    total_claude_cost = sum(s.cost_claude_usd for s in searches)

    # Group by day
    searches_by_day = {}
    for search in searches:
        day_key = search.created_at.date().isoformat()
        if day_key not in searches_by_day:
            searches_by_day[day_key] = {"date": day_key, "count": 0, "cost_usd": 0.0}
        searches_by_day[day_key]["count"] += 1
        searches_by_day[day_key]["cost_usd"] += search.cost_total_usd

    searches_by_day_list = sorted(searches_by_day.values(), key=lambda x: x["date"])

    stats = UsageStats(
        total_searches=total_searches,
        total_results=total_results,
        total_apollo_credits=total_apollo_credits,
        total_claude_input_tokens=total_claude_input_tokens,
        total_claude_output_tokens=total_claude_output_tokens,
        total_cost_usd=round(total_cost_usd, 4),
        cost_breakdown={
            "apollo_usd": round(total_apollo_cost, 4),
            "claude_usd": round(total_claude_cost, 4),
        },
        searches_by_day=searches_by_day_list,
    )

    return UsageStatsResponse(
        stats=stats,
        date_range={
            "start_date": start_dt.date().isoformat(),
            "end_date": (end_dt - timedelta(days=1)).date().isoformat(),
        },
    )


@router.get("/history", response_model=SearchHistoryListResponse)
async def get_search_history(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    client_tag: Optional[str] = Query(None, description="Filter by client tag"),
    limit: int = Query(100, ge=1, le=500, description="Max results to return"),
    db: AsyncSession = Depends(get_db),
):
    """Get search history with optional filters."""

    # Parse dates
    query = select(ApolloSearchHistory).order_by(ApolloSearchHistory.created_at.desc())

    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        query = query.where(ApolloSearchHistory.created_at >= start_dt)

    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        query = query.where(ApolloSearchHistory.created_at < end_dt)

    if client_tag:
        query = query.where(ApolloSearchHistory.client_tag == client_tag)

    # Get total count
    count_query = select(func.count()).select_from(ApolloSearchHistory)
    if start_date or end_date or client_tag:
        count_query = count_query.where(*query.whereclause.clauses)
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Get limited results
    query = query.limit(limit)
    result = await db.execute(query)
    history = result.scalars().all()

    return SearchHistoryListResponse(
        history=[SearchHistoryOut.model_validate(h) for h in history],
        total=total,
    )
