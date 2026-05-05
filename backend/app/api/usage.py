from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.apollo_search_history import ApolloSearchHistory
from app.schemas.usage import (
    SearchHistoryOut, SearchHistoryListResponse, UsageStats, UsageStatsResponse,
    ClientCostSummary, ClientSummaryResponse,
)

router = APIRouter()


@router.get("/stats", response_model=UsageStatsResponse)
async def get_usage_stats(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    client_tag: Optional[str] = Query(None, description="Filter by client tag"),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate usage statistics for a date range. Tracks Apollo searches +
    Claude tokens recorded against ApolloSearchHistory only — chat-based
    token tracking was removed when the in-app chat was deprecated.
    """
    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        start_dt = datetime.now() - timedelta(days=30)

    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    else:
        end_dt = datetime.now() + timedelta(days=1)

    query = select(ApolloSearchHistory).where(
        ApolloSearchHistory.created_at >= start_dt,
        ApolloSearchHistory.created_at < end_dt,
    )
    if client_tag:
        query = query.where(ApolloSearchHistory.client_tag == client_tag)

    result = await db.execute(query)
    searches = result.scalars().all()

    total_searches = len(searches)
    total_results = sum(s.results_count for s in searches)
    total_apollo_credits = sum(s.apollo_credits_consumed for s in searches)
    total_apollo_cost = sum(s.cost_apollo_usd for s in searches)
    total_claude_input_tokens = sum(s.claude_input_tokens for s in searches)
    total_claude_output_tokens = sum(s.claude_output_tokens for s in searches)
    total_claude_cost = sum(s.cost_claude_usd for s in searches)
    total_cost_usd = total_apollo_cost + total_claude_cost

    cost_by_tool: dict[str, float] = {}
    for s in searches:
        tool_type = s.search_type or "unknown"
        cost_by_tool[tool_type] = cost_by_tool.get(tool_type, 0) + s.cost_total_usd

    searches_by_day: dict[str, dict] = {}
    for s in searches:
        day_key = s.created_at.date().isoformat()
        if day_key not in searches_by_day:
            searches_by_day[day_key] = {"date": day_key, "count": 0, "cost_usd": 0.0}
        searches_by_day[day_key]["count"] += 1
        searches_by_day[day_key]["cost_usd"] += s.cost_total_usd

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
            "by_tool": {k: round(v, 4) for k, v in sorted(cost_by_tool.items(), key=lambda x: -x[1])},
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
    query = select(ApolloSearchHistory).order_by(ApolloSearchHistory.created_at.desc())

    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        query = query.where(ApolloSearchHistory.created_at >= start_dt)
    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        query = query.where(ApolloSearchHistory.created_at < end_dt)
    if client_tag:
        query = query.where(ApolloSearchHistory.client_tag == client_tag)

    count_query = select(func.count()).select_from(ApolloSearchHistory)
    if start_date or end_date or client_tag:
        count_query = count_query.where(*query.whereclause.clauses)
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    query = query.limit(limit)
    result = await db.execute(query)
    history = result.scalars().all()

    return SearchHistoryListResponse(
        history=[SearchHistoryOut.model_validate(h) for h in history],
        total=total,
    )


@router.get("/client-summary", response_model=ClientSummaryResponse)
async def get_client_summary(
    db: AsyncSession = Depends(get_db),
):
    """Cost summary grouped by client tag, aggregating Apollo searches.

    NOTE: chat-session-based aggregation was removed when the in-app chat
    feature was deprecated. Costs here cover Apollo + Claude tokens spent on
    Apollo enrichment / find-people only.
    """
    result = await db.execute(
        select(ApolloSearchHistory).where(ApolloSearchHistory.client_tag.isnot(None))
    )
    searches = result.scalars().all()

    clients_data: dict[str, dict] = {}
    for s in searches:
        tag = s.client_tag
        if tag not in clients_data:
            clients_data[tag] = {
                "client_tag": tag,
                "total_searches": 0,
                "total_apollo_credits": 0,
                "total_claude_input_tokens": 0,
                "total_claude_output_tokens": 0,
                "total_cost_usd": 0.0,
                "first_activity": s.created_at,
                "last_activity": s.created_at,
            }
        d = clients_data[tag]
        d["total_searches"] += 1
        d["total_apollo_credits"] += s.apollo_credits_consumed
        d["total_claude_input_tokens"] += s.claude_input_tokens
        d["total_claude_output_tokens"] += s.claude_output_tokens
        d["total_cost_usd"] += s.cost_total_usd
        if s.created_at < d["first_activity"]:
            d["first_activity"] = s.created_at
        if s.created_at > d["last_activity"]:
            d["last_activity"] = s.created_at

    clients = []
    grand_total_cost = 0.0
    grand_total_apollo = 0
    grand_total_claude_tokens = 0

    for tag, data in sorted(clients_data.items(), key=lambda x: x[1]["total_cost_usd"], reverse=True):
        apollo_cost = data["total_apollo_credits"] * 0.10
        claude_input_cost = (data["total_claude_input_tokens"] / 1_000_000) * 3.0
        claude_output_cost = (data["total_claude_output_tokens"] / 1_000_000) * 15.0
        claude_cost = claude_input_cost + claude_output_cost
        clients.append(ClientCostSummary(
            client_tag=tag,
            total_sessions=0,  # chat sessions removed
            total_searches=data["total_searches"],
            total_apollo_credits=data["total_apollo_credits"],
            total_claude_input_tokens=data["total_claude_input_tokens"],
            total_claude_output_tokens=data["total_claude_output_tokens"],
            cost_apollo_usd=round(apollo_cost, 4),
            cost_claude_usd=round(claude_cost, 4),
            total_cost_usd=round(data["total_cost_usd"], 4),
            first_activity=data["first_activity"],
            last_activity=data["last_activity"],
        ))
        grand_total_cost += data["total_cost_usd"]
        grand_total_apollo += data["total_apollo_credits"]
        grand_total_claude_tokens += data["total_claude_input_tokens"] + data["total_claude_output_tokens"]

    return ClientSummaryResponse(
        clients=clients,
        totals={
            "total_cost_usd": round(grand_total_cost, 4),
            "total_apollo_credits": grand_total_apollo,
            "total_claude_tokens": grand_total_claude_tokens,
            "total_clients": len(clients),
        },
    )
