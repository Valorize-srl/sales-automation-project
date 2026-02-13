from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ScheduleDays(BaseModel):
    """Days of the week for campaign schedule (0=Sun, 1=Mon, ..., 6=Sat)."""
    d0: bool = Field(False, alias="0")  # Sunday
    d1: bool = Field(True, alias="1")   # Monday
    d2: bool = Field(True, alias="2")   # Tuesday
    d3: bool = Field(True, alias="3")   # Wednesday
    d4: bool = Field(True, alias="4")   # Thursday
    d5: bool = Field(True, alias="5")   # Friday
    d6: bool = Field(False, alias="6")  # Saturday

    model_config = {"populate_by_name": True}


class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    icp_id: Optional[int] = None
    create_on_instantly: bool = True
    # Schedule
    schedule_timezone: str = "Europe/Rome"
    schedule_from: str = "09:00"
    schedule_to: str = "17:00"
    schedule_days: Optional[ScheduleDays] = None
    # Email accounts
    email_accounts: list[str] = Field(default_factory=list)
    # Sending options
    daily_limit: Optional[int] = None
    email_gap: Optional[int] = None
    stop_on_reply: bool = True
    stop_on_auto_reply: bool = True
    link_tracking: bool = False
    open_tracking: bool = True
    text_only: bool = False


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


class EmailAccountOut(BaseModel):
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    status: Optional[int] = None


class EmailAccountListResponse(BaseModel):
    accounts: list[EmailAccountOut]
    total: int


class PushSequencesResponse(BaseModel):
    success: bool
    steps_pushed: int
    message: str
