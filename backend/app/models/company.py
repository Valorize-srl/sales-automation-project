from __future__ import annotations

from datetime import datetime

from typing import Optional
from sqlalchemy import String, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base


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
    signals: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    client_tag: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # Enrichment tracking fields
    generic_emails: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    enrichment_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    enrichment_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    enrichment_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    people: Mapped[list["Person"]] = relationship(
        back_populates="company",
        passive_deletes=True,
    )
