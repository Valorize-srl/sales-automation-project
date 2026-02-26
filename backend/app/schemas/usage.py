from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SearchHistoryOut(BaseModel):
    """Schema for Apollo search history response."""

    id: int
    search_type: str
    search_query: Optional[str] = None
    filters_applied: Optional[dict] = None
    results_count: int
    apollo_credits_consumed: int
    claude_input_tokens: int
    claude_output_tokens: int
    cost_apollo_usd: float
    cost_claude_usd: float
    cost_total_usd: float
    client_tag: Optional[str] = None
    icp_id: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchHistoryListResponse(BaseModel):
    """List of search history entries."""

    history: list[SearchHistoryOut]
    total: int


class UsageStats(BaseModel):
    """Aggregate usage statistics."""

    total_searches: int = Field(..., description="Total number of searches")
    total_results: int = Field(..., description="Total results returned")
    total_apollo_credits: int = Field(..., description="Total Apollo credits consumed")
    total_claude_input_tokens: int = Field(..., description="Total Claude input tokens")
    total_claude_output_tokens: int = Field(..., description="Total Claude output tokens")
    total_cost_usd: float = Field(..., description="Total cost in USD")
    cost_breakdown: dict = Field(..., description="Cost breakdown by service")
    searches_by_day: list[dict] = Field(..., description="Daily search statistics")


class UsageStatsResponse(BaseModel):
    """Response wrapper for usage statistics."""

    stats: UsageStats
    date_range: dict = Field(..., description="Date range for statistics")


class ClientCostSummary(BaseModel):
    """Cost summary for a single client/project tag."""

    client_tag: str
    total_sessions: int = Field(..., description="Number of chat sessions")
    total_searches: int = Field(..., description="Number of Apollo searches")
    total_apollo_credits: int = Field(..., description="Apollo credits consumed")
    total_claude_input_tokens: int = Field(..., description="Claude input tokens")
    total_claude_output_tokens: int = Field(..., description="Claude output tokens")
    cost_apollo_usd: float = Field(..., description="Apollo cost in USD")
    cost_claude_usd: float = Field(..., description="Claude cost in USD")
    total_cost_usd: float = Field(..., description="Total cost in USD")
    first_activity: Optional[datetime] = Field(None, description="First session date")
    last_activity: Optional[datetime] = Field(None, description="Last activity date")


class ClientSummaryResponse(BaseModel):
    """Response for client cost summary."""

    clients: list[ClientCostSummary]
    totals: dict = Field(..., description="Grand totals across all clients")
