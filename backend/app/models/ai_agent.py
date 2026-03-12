"""AI Agent model for client-specific prospecting and auto-reply."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Integer, String, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base


class AIAgent(Base):
    """
    AI Agent represents a client-specific configuration for:
    1. ICP definition (industry, company size, job titles, etc.)
    2. Signals tracking (LinkedIn keywords, company triggers)
    3. Knowledge base for AI auto-replies
    4. Budget tracking (Apollo credits allocation/consumption)
    """

    __tablename__ = "ai_agents"

    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Basic Info
    name: Mapped[str] = mapped_column(String(255), nullable=False)  # "Cliente XYZ Wine Prospecting"
    client_tag: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # "cliente_xyz"
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ICP Configuration (JSON)
    # Example: {"industry": "Wine Production", "company_size": "10-50", "job_titles": "CEO, Founder", ...}
    icp_config: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Signals Configuration (JSON)
    # Example: {"linkedin_keywords": ["innovation", "digital"], "company_triggers": ["funding"], ...}
    signals_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Knowledge Base for AI Replier
    knowledge_base_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Extracted text
    knowledge_base_source: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # "upload" | "url" | "manual"
    knowledge_base_files: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # [{filename, upload_date, size}]

    # Budget & Usage Tracking (Apollo credits)
    apollo_credits_allocated: Mapped[int] = mapped_column(Integer, default=1000, server_default="1000")
    apollo_credits_consumed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_credits_reset: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # FK to users if multi-tenancy

    # Relationships
    lead_lists: Mapped[list["LeadList"]] = relationship(
        "LeadList",
        back_populates="ai_agent",
        cascade="all, delete-orphan",
    )
    agent_campaigns: Mapped[list["AIAgentCampaign"]] = relationship(
        "AIAgentCampaign",
        back_populates="ai_agent",
    )
    signal_trackings: Mapped[list["SignalTracking"]] = relationship(
        "SignalTracking",
        back_populates="ai_agent",
    )

    def __repr__(self) -> str:
        return f"<AIAgent(id={self.id}, name='{self.name}', client_tag='{self.client_tag}')>"

    @property
    def credits_remaining(self) -> int:
        """Calculate remaining Apollo credits."""
        return self.apollo_credits_allocated - self.apollo_credits_consumed

    @property
    def credits_percentage_used(self) -> float:
        """Calculate percentage of credits consumed."""
        if self.apollo_credits_allocated == 0:
            return 0.0
        return (self.apollo_credits_consumed / self.apollo_credits_allocated) * 100
