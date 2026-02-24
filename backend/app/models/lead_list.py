"""Lead List model for organizing leads by AI Agent."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base


class LeadList(Base):
    """
    Lead List represents a collection of leads (people/companies) created by an AI Agent.

    Each AI Agent search creates a new list automatically, tagged with the agent's client_tag.
    Lists help organize leads by project/client/search criteria.
    """

    __tablename__ = "lead_lists"

    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign Key to AI Agent
    ai_agent_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ai_agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Basic Info
    name: Mapped[str] = mapped_column(String(255), nullable=False)  # "Cliente XYZ - Wine Leads - 2024-02-24"
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Filter Snapshot - Apollo filters used to create this list
    # Example: {"search_type": "companies", "filters": {"organization_locations": ["Tuscany"]}}
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
    ai_agent: Mapped["AIAgent"] = relationship(
        "AIAgent",
        back_populates="lead_lists",
    )

    # Note: Person and Company have list_id FK, but we don't define reverse relationship here
    # to avoid circular dependencies. Query via Person.query.filter_by(list_id=X) instead.

    def __repr__(self) -> str:
        return f"<LeadList(id={self.id}, name='{self.name}', agent_id={self.ai_agent_id})>"

    @property
    def total_leads(self) -> int:
        """Total leads (people + companies) in this list."""
        return self.people_count + self.companies_count
