"""Chat message model for conversational AI assistant."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Text, DateTime, JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class ChatMessage(Base):
    """
    Individual message in a chat session.

    Stores message content, tool calls, and token usage.
    """
    __tablename__ = "chat_messages"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to session
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        index=True
    )

    # Message content
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="user, assistant, or tool_result"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Tool tracking
    tool_calls: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        comment="Claude's tool_use blocks from this message"
    )
    tool_results: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        comment="Results for tool_result messages"
    )

    # Token usage for this message
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)

    # Metadata
    message_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="File attachments, sources, etc."
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True
    )

    # Relationships
    session: Mapped["ChatSession"] = relationship(
        "ChatSession",
        back_populates="messages"
    )

    def __repr__(self) -> str:
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<ChatMessage(id={self.id}, role={self.role}, content='{content_preview}')>"
