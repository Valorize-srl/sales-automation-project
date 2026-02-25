"""Chat session model for conversational AI assistant."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class ChatSession(Base):
    """
    Chat session for conversational AI assistant.

    Stores conversation history, ICP drafts, search results, and cost tracking.
    """
    __tablename__ = "chat_sessions"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_uuid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        default=lambda: str(uuid.uuid4())
    )

    # Session info
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Context tracking
    icp_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("icps.id", ondelete="SET NULL"),
        nullable=True
    )
    current_icp_draft: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="ICP being built incrementally through conversation"
    )
    session_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Last search results, enrichment state, etc."
    )

    # Cost tracking
    total_claude_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_claude_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_apollo_credits: Mapped[int] = mapped_column(Integer, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    # Organization
    client_tag: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        server_default="active",
        comment="active, archived, completed"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationships
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at"
    )
    tool_executions: Mapped[list["ToolExecution"]] = relationship(
        "ToolExecution",
        back_populates="session",
        cascade="all, delete-orphan"
    )
    apollo_searches: Mapped[list["ApolloSearchHistory"]] = relationship(
        "ApolloSearchHistory",
        back_populates="chat_session"
    )
    icp: Mapped[Optional["ICP"]] = relationship(
        "ICP",
        back_populates="chat_sessions",
        foreign_keys="[ChatSession.icp_id]"
    )

    def __repr__(self) -> str:
        return f"<ChatSession(id={self.id}, uuid={self.session_uuid}, status={self.status})>"
