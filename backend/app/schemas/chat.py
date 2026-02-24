from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    file_content: Optional[str] = None


# Session-based chat schemas
class CreateSessionRequest(BaseModel):
    client_tag: Optional[str] = None
    title: Optional[str] = None


class ChatStreamRequest(BaseModel):
    message: str
    file_content: Optional[str] = None


class SessionResponse(BaseModel):
    session_uuid: str
    title: Optional[str] = None
    status: str
    client_tag: Optional[str] = None
    created_at: datetime
    last_message_at: Optional[datetime] = None
    total_cost_usd: float
    total_claude_input_tokens: int
    total_claude_output_tokens: int
    total_apollo_credits: int

    class Config:
        from_attributes = True
