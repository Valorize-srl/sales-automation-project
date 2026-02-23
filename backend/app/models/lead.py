from __future__ import annotations

import enum
from datetime import datetime

from typing import Optional
from sqlalchemy import String, Text, Boolean, Float, ForeignKey, DateTime, Enum as SAEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base


class LeadSource(str, enum.Enum):
    CSV = "csv"
    APOLLO = "apollo"
    MANUAL = "manual"


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    icp_id: Mapped[int] = mapped_column(ForeignKey("icps.id", ondelete="CASCADE"), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    zip_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    custom_fields: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    source: Mapped[LeadSource] = mapped_column(
        SAEnum(LeadSource, native_enum=False),
        default=LeadSource.MANUAL,
        server_default="manual",
    )
    verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    icp: Mapped["ICP"] = relationship(back_populates="leads")
    email_responses: Mapped[list["EmailResponse"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
