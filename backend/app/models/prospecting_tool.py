"""ProspectingTool model — tool cards stored in DB, injected into Claude system prompt."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Boolean, Integer, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.database import Base


class ProspectingTool(Base):
    __tablename__ = "prospecting_tools"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    when_to_use: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cost_info: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sectors_strong: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    sectors_weak: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    apify_actor_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    output_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
