"""Pipeline Lead model for tracking leads through the waterfall pipeline."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Float, Boolean, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base


class PipelineLeadStatus(str, enum.Enum):
    RAW = "raw"
    FILTERED = "filtered"
    LINKEDIN_SEARCHED = "linkedin_searched"
    DM_SEARCHED = "dm_searched"
    EMAIL_FOUND = "email_found"
    EMAIL_VERIFIED = "email_verified"
    SIGNALS_COLLECTED = "signals_collected"
    SCORED = "scored"
    APPROVED = "approved"
    SENT = "sent"
    DISCARDED_INVALID_EMAIL = "discarded_invalid_email"
    DISCARDED_MANUAL = "discarded_manual"
    REVIEW_POSTPONED = "review_postponed"


class PipelineLead(Base):
    __tablename__ = "pipeline_leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pipeline_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False, index=True)

    # Italian company registry
    ragione_sociale: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    partita_iva: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    codice_ateco: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    forma_giuridica: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    fatturato_range: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    dipendenti_range: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    indirizzo: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    provincia: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    anno_costituzione: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sito_web: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source_portal: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Pipeline status
    pipeline_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="raw", index=True)

    # LinkedIn company
    linkedin_company_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    linkedin_industry: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    linkedin_employees_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    linkedin_followers: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    linkedin_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Decision maker
    dm_first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    dm_last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    dm_job_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    dm_linkedin_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    dm_headline: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    dm_found: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Email
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    email_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    email_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    email_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email_catchall: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    email_unknown: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Signals + Scoring
    signals_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    icp_score: Mapped[Optional[str]] = mapped_column(String(5), nullable=True, index=True)
    score_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approach_angle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    first_line_email: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    relevant_products: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Flags
    no_website: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    exclude_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    exclude_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Timestamps + tenancy
    pipeline_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    pipeline_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    client_tag: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Relationships
    pipeline_run: Mapped["PipelineRun"] = relationship("PipelineRun", back_populates="leads")

    def __repr__(self) -> str:
        return f"<PipelineLead(id={self.id}, ragione_sociale='{self.ragione_sociale}', status='{self.pipeline_status}')>"
