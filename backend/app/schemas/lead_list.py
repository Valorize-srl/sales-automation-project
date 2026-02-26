"""Pydantic schemas for Lead List API endpoints."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LeadListCreate(BaseModel):
    """Schema for creating a new lead list."""
    ai_agent_id: Optional[int] = Field(None, description="Parent AI Agent ID (optional)")
    name: str = Field(..., min_length=1, max_length=255, description="List name")
    description: Optional[str] = Field(None, description="Optional description")
    client_tag: Optional[str] = Field(None, description="Client/project tag")
    filters_snapshot: Optional[dict] = Field(None, description="Apollo filters used to create this list")
    person_ids: Optional[list[int]] = Field(None, description="People to add to list on creation")
    company_ids: Optional[list[int]] = Field(None, description="Companies to add to list on creation")


class LeadListUpdate(BaseModel):
    """Schema for updating a lead list."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


class LeadListResponse(BaseModel):
    """Schema for lead list response."""
    id: int
    ai_agent_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    client_tag: Optional[str] = None
    filters_snapshot: Optional[dict] = None
    people_count: int
    companies_count: int
    created_at: datetime
    updated_at: datetime

    # Calculated property
    total_leads: int = Field(default=0, description="Total leads (people + companies)")

    model_config = {"from_attributes": True}


class LeadListListResponse(BaseModel):
    """Schema for listing lead lists."""
    lists: list[LeadListResponse]
    total: int


class AddLeadsToListRequest(BaseModel):
    """Schema for adding leads to list."""
    person_ids: Optional[list[int]] = Field(None, description="List of person IDs")
    company_ids: Optional[list[int]] = Field(None, description="List of company IDs")


class RemoveLeadsFromListRequest(BaseModel):
    """Schema for removing leads from list."""
    person_ids: Optional[list[int]] = Field(None, description="List of person IDs")
    company_ids: Optional[list[int]] = Field(None, description="List of company IDs")


class BulkTagRequest(BaseModel):
    """Schema for bulk tagging leads."""
    person_ids: Optional[list[int]] = Field(None, description="List of person IDs")
    company_ids: Optional[list[int]] = Field(None, description="List of company IDs")
    tags_to_add: Optional[list[str]] = Field(None, description="Tags to add")
    tags_to_remove: Optional[list[str]] = Field(None, description="Tags to remove")


class BulkOperationResponse(BaseModel):
    """Schema for bulk operation results."""
    people_affected: int = Field(default=0, description="Number of people affected")
    companies_affected: int = Field(default=0, description="Number of companies affected")
    message: str = Field(default="Operation completed successfully")
