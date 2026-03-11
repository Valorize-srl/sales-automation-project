"""Pipeline Run model for tracking waterfall pipeline executions."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Float, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base


class PipelineRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    client_tag: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    ai_agent_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )
    icp_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # Step counters
    leads_raw_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    leads_filtered_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    leads_with_dm_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    leads_with_email_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    leads_verified_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    leads_scored_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # Score breakdown
    leads_score_a: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    leads_score_b: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    leads_score_c: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # Cost tracking
    cost_scraping_usd: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
    cost_linkedin_usd: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
    cost_email_finding_usd: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
    cost_zerobounce_usd: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
    cost_signals_usd: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
    cost_claude_usd: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
    cost_total_usd: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")

    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    leads: Mapped[list["PipelineLead"]] = relationship(
        "PipelineLead", back_populates="pipeline_run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PipelineRun(id={self.id}, run_id='{self.run_id}', status='{self.status}')>"
