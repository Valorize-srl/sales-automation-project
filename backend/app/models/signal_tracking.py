"""Signal Tracking model for detecting engagement and company events."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, DateTime, JSON, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base


class SignalType(str, enum.Enum):
    """Types of signals that can be tracked."""

    LINKEDIN_POST = "linkedin_post"  # Person posted on LinkedIn with keyword match
    LINKEDIN_COMMENT = "linkedin_comment"  # Person commented on LinkedIn with keyword match
    JOB_CHANGE = "job_change"  # Person changed job (new role, company)
    COMPANY_FUNDING = "company_funding"  # Company raised funding
    COMPANY_HIRING = "company_hiring"  # Company is actively hiring
    COMPANY_EXPANSION = "company_expansion"  # Company expanded to new location/market
    COMPANY_ACQUISITION = "company_acquisition"  # Company acquired/was acquired


class SignalTracking(Base):
    """
    Signal Tracking logs detected signals for leads.

    Signals are triggers that indicate buying intent or good timing for outreach:
    - LinkedIn engagement (posts, comments with keywords)
    - Job changes (new role, promotion)
    - Company events (funding, hiring, expansion)

    Initially a placeholder - will integrate with external APIs in Phase 2:
    - LinkedIn: Proxycurl, Phantombuster
    - Company data: Crunchbase, Clearbit
    """

    __tablename__ = "signal_trackings"

    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign Keys
    ai_agent_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ai_agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    person_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("people.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    company_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Signal Details
    signal_type: Mapped[SignalType] = mapped_column(
        SAEnum(SignalType, native_enum=False),
        nullable=False,
        index=True,
    )

    # Signal Data (JSON with type-specific fields)
    # LinkedIn post: {keyword_matched, post_url, post_text, engagement_count}
    # Job change: {old_title, new_title, old_company, new_company, change_date}
    # Funding: {round_type, amount_usd, investors, announcement_url}
    signal_data: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Metadata
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    ai_agent: Mapped["AIAgent"] = relationship(
        "AIAgent",
        back_populates="signal_trackings",
    )
    person: Mapped[Optional["Person"]] = relationship("Person")
    company: Mapped[Optional["Company"]] = relationship("Company")

    def __repr__(self) -> str:
        return f"<SignalTracking(id={self.id}, type={self.signal_type}, person_id={self.person_id}, company_id={self.company_id})>"
