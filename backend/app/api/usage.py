from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.apollo_search_history import ApolloSearchHistory
from app.models.chat_session import ChatSession
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

    # Calculate aggregates from search history
    total_searches = len(searches)
    total_results = sum(s.results_count for s in searches)
    total_apollo_credits = sum(s.apollo_credits_consumed for s in searches)
    total_apollo_cost = sum(s.cost_apollo_usd for s in searches)

    # Get Claude token costs from ChatSession (includes all chat tokens, not just search-related)
    session_query = select(ChatSession).where(
        ChatSession.created_at >= start_dt,
        ChatSession.created_at < end_dt,
    )
    if client_tag:
        session_query = session_query.where(ChatSession.client_tag == client_tag)

    session_result = await db.execute(session_query)
    sessions = session_result.scalars().all()

    total_claude_input_tokens = sum(s.total_claude_input_tokens for s in sessions)
    total_claude_output_tokens = sum(s.total_claude_output_tokens for s in sessions)
    claude_input_cost = (total_claude_input_tokens / 1_000_000) * 3.0
    claude_output_cost = (total_claude_output_tokens / 1_000_000) * 15.0
    total_claude_cost = claude_input_cost + claude_output_cost
    total_cost_usd = total_apollo_cost + total_claude_cost

    # Group by day (searches + session costs)
    searches_by_day = {}
    for search in searches:
        day_key = search.created_at.date().isoformat()
        if day_key not in searches_by_day:
            searches_by_day[day_key] = {"date": day_key, "count": 0, "cost_usd": 0.0}
        searches_by_day[day_key]["count"] += 1
        searches_by_day[day_key]["cost_usd"] += search.cost_apollo_usd
    for sess in sessions:
        day_key = sess.created_at.date().isoformat()
        if day_key not in searches_by_day:
            searches_by_day[day_key] = {"date": day_key, "count": 0, "cost_usd": 0.0}
        sess_claude_cost = sess.total_cost_usd - (sess.total_apollo_credits * 0.10)
        searches_by_day[day_key]["cost_usd"] += max(0, sess_claude_cost)

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


@router.get("/client-summary", response_model=ClientSummaryResponse)
async def get_client_summary(
    db: AsyncSession = Depends(get_db),
):
    """Get cost summary grouped by client tag, aggregating all sessions and searches."""

    # Get all sessions with a client_tag
    sessions_result = await db.execute(
        select(ChatSession).where(ChatSession.client_tag.isnot(None))
    )
    sessions = sessions_result.scalars().all()

    # Get Apollo search counts grouped by client_tag
    search_counts_result = await db.execute(
        select(
            ApolloSearchHistory.client_tag,
            func.count(ApolloSearchHistory.id).label("search_count"),
        )
        .where(ApolloSearchHistory.client_tag.isnot(None))
        .group_by(ApolloSearchHistory.client_tag)
    )
    search_counts = {row.client_tag: row.search_count for row in search_counts_result}

    # Aggregate by client_tag
    clients_data: dict[str, dict] = {}
    for session in sessions:
        tag = session.client_tag
        if tag not in clients_data:
            clients_data[tag] = {
                "client_tag": tag,
                "total_sessions": 0,
                "total_apollo_credits": 0,
                "total_claude_input_tokens": 0,
                "total_claude_output_tokens": 0,
                "total_cost_usd": 0.0,
                "first_activity": session.created_at,
                "last_activity": session.last_message_at or session.updated_at,
            }

        data = clients_data[tag]
        data["total_sessions"] += 1
        data["total_apollo_credits"] += session.total_apollo_credits
        data["total_claude_input_tokens"] += session.total_claude_input_tokens
        data["total_claude_output_tokens"] += session.total_claude_output_tokens
        data["total_cost_usd"] += session.total_cost_usd

        # Track date range
        if session.created_at < data["first_activity"]:
            data["first_activity"] = session.created_at
        session_last = session.last_message_at or session.updated_at
        if session_last and (data["last_activity"] is None or session_last > data["last_activity"]):
            data["last_activity"] = session_last

    # Build response with cost breakdown
    clients = []
    grand_total_cost = 0.0
    grand_total_apollo = 0
    grand_total_claude_tokens = 0

    for tag, data in sorted(clients_data.items(), key=lambda x: x[1]["total_cost_usd"], reverse=True):
        apollo_cost = data["total_apollo_credits"] * 0.10
        claude_input_cost = (data["total_claude_input_tokens"] / 1_000_000) * 3.0
        claude_output_cost = (data["total_claude_output_tokens"] / 1_000_000) * 15.0
        claude_cost = claude_input_cost + claude_output_cost

        client = ClientCostSummary(
            client_tag=tag,
            total_sessions=data["total_sessions"],
            total_searches=search_counts.get(tag, 0),
            total_apollo_credits=data["total_apollo_credits"],
            total_claude_input_tokens=data["total_claude_input_tokens"],
            total_claude_output_tokens=data["total_claude_output_tokens"],
            cost_apollo_usd=round(apollo_cost, 4),
            cost_claude_usd=round(claude_cost, 4),
            total_cost_usd=round(data["total_cost_usd"], 4),
            first_activity=data["first_activity"],
            last_activity=data["last_activity"],
        )
        clients.append(client)

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
