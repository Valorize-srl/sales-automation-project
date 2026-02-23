from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EmailResponseOut(BaseModel):
    """Single email response with all fields for display."""

    id: int
    campaign_id: int
    lead_id: Optional[int] = None
    instantly_email_id: Optional[str] = None
    from_email: Optional[str] = None
    sender_email: Optional[str] = None
    subject: Optional[str] = None
    thread_id: Optional[str] = None
    message_body: Optional[str] = None
    direction: str
    sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None
    ai_suggested_reply: Optional[str] = None
    human_approved_reply: Optional[str] = None
    status: str
    received_at: Optional[datetime] = None
    created_at: datetime
    # Joined fields
    lead_name: Optional[str] = None
    lead_email: Optional[str] = None
    lead_company: Optional[str] = None
    campaign_name: Optional[str] = None

    model_config = {"from_attributes": True}


class EmailResponseListResponse(BaseModel):
    responses: list[EmailResponseOut]
    total: int


class FetchRepliesRequest(BaseModel):
    campaign_ids: list[int] = Field(..., min_items=1)


class FetchRepliesResponse(BaseModel):
    fetched: int
    skipped: int
    errors: int


class ApproveReplyRequest(BaseModel):
    edited_reply: Optional[str] = None


class SendReplyResponse(BaseModel):
    success: bool
    message: str
