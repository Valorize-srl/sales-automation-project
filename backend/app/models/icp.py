from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base


class ICPStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class ICP(Base):
    __tablename__ = "icps"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company_size: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    job_titles: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    geography: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    revenue_range: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_input: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[ICPStatus] = mapped_column(
        SAEnum(ICPStatus, native_enum=False),
        default=ICPStatus.DRAFT,
        server_default="draft",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    leads: Mapped[list["Lead"]] = relationship(back_populates="icp", cascade="all, delete-orphan")
    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="icp")
    apollo_searches: Mapped[list["ApolloSearchHistory"]] = relationship(back_populates="icp")
