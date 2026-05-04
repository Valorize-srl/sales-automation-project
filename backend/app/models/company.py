from __future__ import annotations

from datetime import datetime

from typing import Optional
from sqlalchemy import String, Text, DateTime, Index, JSON, ForeignKey, Integer, BigInteger, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base


# Association table for the many-to-many Company <-> LeadList relationship.
# Declared at module scope so SQLAlchemy can resolve it before either side
# imports the other.
company_lead_list = Table(
    "company_lead_list",
    Base.metadata,
    Column("company_id", Integer, ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True),
    Column("lead_list_id", Integer, ForeignKey("lead_lists.id", ondelete="CASCADE"), primary_key=True),
    Column("added_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_domain: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    province: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    signals: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    client_tag: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Raw firmographics (used by Clay-style dashboard + Lead Planner)
    revenue: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    employee_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # User-defined columns; key→value (anything serialisable)
    custom_fields: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # AI Agents integration
    list_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("lead_lists.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tags: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)  # ["cliente_xyz", "wine_industry"]
    enriched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)  # Apollo enrich date

    # Enrichment tracking fields (web scraping)
    generic_emails: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enrichment_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    enrichment_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    enrichment_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # ICP-based scoring (populated by the Lead Planner & Scorer)
    icp_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    priority_tier: Mapped[Optional[str]] = mapped_column(String(1), nullable=True)  # 'A' | 'B' | 'C'
    lifecycle_stage: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="new")
    revenue_band: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    employee_count_band: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    industry_standardized: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reason_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_scored_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    scored_with_icp_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("icps.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    people: Mapped[list["Person"]] = relationship(
        back_populates="company",
        passive_deletes=True,
    )
    lead_list: Mapped[Optional["LeadList"]] = relationship(
        "LeadList", foreign_keys=[list_id]
    )
    # Multi-list membership (Clay-style multi-tag)
    lists: Mapped[list["LeadList"]] = relationship(
        "LeadList",
        secondary=company_lead_list,
        backref="companies",
    )
