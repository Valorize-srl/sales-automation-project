"""Schemas for ProspectingTool API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ProspectingToolOut(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str] = None
    when_to_use: Optional[str] = None
    cost_info: Optional[str] = None
    sectors_strong: Optional[list] = None
    sectors_weak: Optional[list] = None
    apify_actor_id: Optional[str] = None
    output_type: Optional[str] = None
    is_enabled: bool = True
    sort_order: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ProspectingToolUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    when_to_use: Optional[str] = None
    cost_info: Optional[str] = None
    sectors_strong: Optional[list] = None
    sectors_weak: Optional[list] = None
    apify_actor_id: Optional[str] = None
    output_type: Optional[str] = None
    is_enabled: Optional[bool] = None
    sort_order: Optional[int] = None


class ProspectingToolListResponse(BaseModel):
    tools: list[ProspectingToolOut]
    total: int
