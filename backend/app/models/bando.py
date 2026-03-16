"""Bando model — tracks government grants/incentives from RSS feeds and web sources."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Text, Float, DateTime, JSON, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.database import Base


class BandoSource(str, enum.Enum):
    MIMIT = "mimit"
    INVITALIA = "invitalia"
    MASE = "mase"
    FASI = "fasi"
    UNIONCAMERE = "unioncamere"
    INCENTIVI_GOV = "incentivi_gov"


class BandoStatus(str, enum.Enum):
    NEW = "new"
    ANALYZED = "analyzed"
    EXPIRED = "expired"
    ARCHIVED = "archived"


class Bando(Base):
    __tablename__ = "bandi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Source info
    source: Mapped[BandoSource] = mapped_column(
        SAEnum(BandoSource, native_enum=False), nullable=False, index=True
    )
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    raw_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Status
    status: Mapped[BandoStatus] = mapped_column(
        SAEnum(BandoStatus, native_enum=False),
        default=BandoStatus.NEW,
        server_default="new",
        index=True,
    )

    # AI-extracted fields
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_companies: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ateco_codes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    amount_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    amount_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    funding_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    regions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    sectors: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    ai_analysis_raw: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Timestamps
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    analyzed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Bando(id={self.id}, source={self.source}, title={self.title[:40]})>"
