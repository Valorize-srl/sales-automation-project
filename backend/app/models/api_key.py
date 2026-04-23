"""API Key model for MCP server authentication."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Integer, String, DateTime, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.database import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    last_four: Mapped[str] = mapped_column(String(4), nullable=False)
    scopes: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    client_tag: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_api_keys_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<ApiKey id={self.id} name={self.name!r} prefix={self.prefix}>"
