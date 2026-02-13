from datetime import datetime

from pydantic import BaseModel, Field


class EmailResponseOut(BaseModel):
    """Single email response with all fields for display."""

    id: int
    campaign_id: int
    lead_id: int | None = None
    instantly_email_id: str | None = None
    from_email: str | None = None
    subject: str | None = None
    thread_id: str | None = None
    message_body: str | None = None
    direction: str
    sentiment: str | None = None
    sentiment_score: float | None = None
    ai_suggested_reply: str | None = None
    human_approved_reply: str | None = None
    status: str
    received_at: datetime | None = None
    created_at: datetime
    # Joined fields
    lead_name: str | None = None
    lead_email: str | None = None
    lead_company: str | None = None
    campaign_name: str | None = None

    model_config = {"from_attributes": True}


class EmailResponseListResponse(BaseModel):
    responses: list[EmailResponseOut]
    total: int


class FetchRepliesRequest(BaseModel):
    campaign_ids: list[int] = Field(..., min_length=1)


class FetchRepliesResponse(BaseModel):
    fetched: int
    skipped: int
    errors: int


class ApproveReplyRequest(BaseModel):
    edited_reply: str | None = None


class SendReplyResponse(BaseModel):
    success: bool
    message: str
