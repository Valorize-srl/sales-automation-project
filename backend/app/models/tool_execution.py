"""Tool execution model for auditing tool calls."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Float, Text, DateTime, JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class ToolExecution(Base):
    """
    Audit log for tool executions in chat sessions.

    Tracks tool calls, inputs, outputs, status, and costs.
    """
    __tablename__ = "tool_executions"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        index=True
    )
    message_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True
    )

    # Tool details
    tool_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="search_apollo, enrich_companies, etc."
    )
    tool_call_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Claude's tool use ID"
    )
    tool_input: Mapped[dict] = mapped_column(JSON, nullable=False)
    tool_output: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Execution tracking
    status: Mapped[str] = mapped_column(
        String(20),
        default="success",
        server_default="success",
        comment="success, error, partial"
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Execution time in milliseconds"
    )

    # Cost tracking (for tools that consume resources)
    credits_consumed: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Apollo credits or other API credits"
    )
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # Relationships
    session: Mapped["ChatSession"] = relationship(
        "ChatSession",
        back_populates="tool_executions"
    )

    def __repr__(self) -> str:
        return f"<ToolExecution(id={self.id}, tool={self.tool_name}, status={self.status})>"
