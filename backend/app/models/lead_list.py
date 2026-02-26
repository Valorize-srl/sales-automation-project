"""Lead List model for organizing leads."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base


class LeadList(Base):
    """
    Lead List represents a collection of leads (people/companies).

    Can be created manually from the Leads page or automatically by an AI Agent.
    Lists help organize leads by project/client/search criteria.
    """

    __tablename__ = "lead_lists"

    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign Key to AI Agent (optional — lists can exist independently)
    ai_agent_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("ai_agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Basic Info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    client_tag: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Filter Snapshot - Apollo filters used to create this list
    filters_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Stats (cached counts, updated on lead add/remove)
    people_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    companies_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    ai_agent: Mapped[Optional["AIAgent"]] = relationship(
        "AIAgent",
        back_populates="lead_lists",
    )

    def __repr__(self) -> str:
        return f"<LeadList(id={self.id}, name='{self.name}')>"

    @property
    def total_leads(self) -> int:
        """Total leads (people + companies) in this list."""
        return self.people_count + self.companies_count
