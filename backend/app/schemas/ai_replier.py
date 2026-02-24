"""Pydantic schemas for AI Replier API endpoints."""
from typing import Optional

from pydantic import BaseModel, Field


class GenerateReplyRequest(BaseModel):
    """Schema for generating AI reply."""
    email_response_id: int = Field(..., description="EmailResponse ID")
    ai_agent_id: Optional[int] = Field(None, description="Optional AI Agent ID override")


class GenerateReplyResponse(BaseModel):
    """Schema for generated AI reply."""
    subject: str
    body: str
    tone: str
    call_to_action: str


class ApproveAndSendReplyRequest(BaseModel):
    """Schema for approving and sending reply."""
    approved_body: str = Field(..., description="Human-approved reply text (can be edited)")
    approved_subject: Optional[str] = Field(None, description="Optional subject override")
    sender_email: Optional[str] = Field(None, description="Email account to send from")


class ApproveReplyRequest(BaseModel):
    """Schema for approving reply without sending."""
    approved_body: str = Field(..., description="Human-approved reply text")


class ReplyActionResponse(BaseModel):
    """Schema for reply action results."""
    status: str = Field(..., description="Status: sent, approved, ignored, error")
    message: str = Field(..., description="Human-readable message")
    instantly_result: Optional[dict] = Field(None, description="Instantly API response (if sent)")
