from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    icp_id: Optional[int] = None
    create_on_instantly: bool = True


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    icp_id: Optional[int] = None
    status: Optional[str] = None
    subject_lines: Optional[str] = None
    email_templates: Optional[str] = None


class CampaignResponse(BaseModel):
    id: int
    icp_id: Optional[int] = None
    icp_name: Optional[str] = None
    instantly_campaign_id: Optional[str] = None
    name: str
    status: str
    subject_lines: Optional[str] = None
    email_templates: Optional[str] = None
    total_sent: int
    total_opened: int
    total_replied: int
    created_at: datetime

    model_config = {"from_attributes": True}


class CampaignListResponse(BaseModel):
    campaigns: list[CampaignResponse]
    total: int


class InstantlySyncResponse(BaseModel):
    imported: int
    updated: int
    errors: int


class LeadUploadRequest(BaseModel):
    lead_ids: list[int]


class LeadUploadResponse(BaseModel):
    pushed: int
    errors: int


class EmailTemplateGenerateRequest(BaseModel):
    icp_id: Optional[int] = None
    additional_context: Optional[str] = None
    num_subject_lines: int = Field(default=3, ge=1, le=10)
    num_steps: int = Field(default=3, ge=1, le=5)


class EmailTemplateGenerateResponse(BaseModel):
    subject_lines: list[str]
    email_steps: list[dict[str, Any]]
