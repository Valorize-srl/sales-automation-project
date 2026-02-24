from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Integer, Float, ForeignKey, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base


class ApolloSearchHistory(Base):
    """Track all Apollo.io searches with costs and metadata."""

    __tablename__ = "apollo_search_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    search_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "people" | "companies"
    search_query: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Original query if available
    filters_applied: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # All filters used
    results_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    apollo_credits_consumed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    claude_input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    claude_output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cost_apollo_usd: Mapped[float] = mapped_column(Float, default=0.0, server_default="0.0")
    cost_claude_usd: Mapped[float] = mapped_column(Float, default=0.0, server_default="0.0")
    cost_total_usd: Mapped[float] = mapped_column(Float, default=0.0, server_default="0.0")
    client_tag: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # Client/project tag
    icp_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("icps.id", ondelete="SET NULL"), nullable=True
    )  # Associated ICP if any
    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True
    )  # Associated chat session if any
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    icp: Mapped[Optional["ICP"]] = relationship(back_populates="apollo_searches")
    chat_session: Mapped[Optional["ChatSession"]] = relationship(back_populates="apollo_searches")
