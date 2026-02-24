"""Pydantic schemas for AI Agent API endpoints."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AIAgentCreate(BaseModel):
    """Schema for creating a new AI Agent."""
    name: str = Field(..., min_length=1, max_length=255, description="Agent display name")
    client_tag: str = Field(..., min_length=1, max_length=100, description="Unique client tag for lead tagging")
    description: Optional[str] = Field(None, description="Optional detailed description")
    icp_config: dict = Field(..., description="ICP configuration (industry, size, titles, etc.)")
    signals_config: Optional[dict] = Field(None, description="Signals tracking configuration")
    apollo_credits_allocated: int = Field(1000, ge=0, description="Monthly Apollo credits budget")


class AIAgentUpdate(BaseModel):
    """Schema for updating an AI Agent."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    client_tag: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    icp_config: Optional[dict] = None
    signals_config: Optional[dict] = None
    apollo_credits_allocated: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class AIAgentResponse(BaseModel):
    """Schema for AI Agent response."""
    id: int
    name: str
    client_tag: str
    description: Optional[str] = None
    icp_config: dict
    signals_config: Optional[dict] = None
    knowledge_base_text: Optional[str] = None
    knowledge_base_source: Optional[str] = None
    knowledge_base_files: Optional[list] = None
    apollo_credits_allocated: int
    apollo_credits_consumed: int
    last_credits_reset: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int] = None

    # Calculated properties
    credits_remaining: int = Field(default=0, description="Calculated: allocated - consumed")
    credits_percentage_used: float = Field(default=0.0, description="Calculated: percentage of credits used")

    model_config = {"from_attributes": True}


class AIAgentListResponse(BaseModel):
    """Schema for listing AI Agents."""
    agents: list[AIAgentResponse]
    total: int


class AIAgentStatsResponse(BaseModel):
    """Schema for AI Agent statistics."""
    agent_id: int
    agent_name: str
    client_tag: str
    total_leads: int
    total_people: int
    total_companies: int
    apollo_credits_allocated: int
    apollo_credits_consumed: int
    apollo_credits_remaining: int
    apollo_credits_percentage_used: float
    lists_created: int
    campaigns_connected: int
    signals_detected: int


class ApolloSearchRequest(BaseModel):
    """Schema for executing Apollo search."""
    per_page: int = Field(100, ge=1, le=100, description="Results per page (max 100)")
    auto_create_list: bool = Field(True, description="Auto-create lead list for results")
    list_name: Optional[str] = Field(None, description="Custom list name (auto-generated if not provided)")


class ApolloSearchResponse(BaseModel):
    """Schema for Apollo search results."""
    list_id: Optional[int] = None
    list_name: Optional[str] = None
    results_count: int
    people_count: int
    companies_count: int
    credits_consumed: int
    credits_remaining: int


class EnrichLeadsRequest(BaseModel):
    """Schema for bulk enriching leads."""
    person_ids: Optional[list[int]] = Field(None, description="List of person IDs to enrich")
    company_ids: Optional[list[int]] = Field(None, description="List of company IDs to enrich")


class EnrichEstimateResponse(BaseModel):
    """Schema for enrichment cost estimate."""
    total_leads: int
    apollo_credits_needed: int
    estimated_cost_usd: float


class EnrichLeadsResponse(BaseModel):
    """Schema for enrichment results."""
    enriched_count: int
    credits_consumed: int
    credits_remaining: int


class KnowledgeBaseUpload(BaseModel):
    """Schema for uploading knowledge base."""
    source_type: str = Field(..., description="upload, url, or manual")
    content: str = Field(..., description="Extracted text content")
    files_metadata: Optional[list[dict]] = Field(None, description="Optional file metadata")


class CampaignAssociation(BaseModel):
    """Schema for associating agent with campaigns."""
    campaign_ids: list[int] = Field(..., description="List of campaign IDs to associate")
