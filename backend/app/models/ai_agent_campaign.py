"""AI Agent Campaign association model for auto-reply configuration."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base


class AIAgentCampaign(Base):
    """
    AI Agent Campaign is a join table between AI Agents and Campaigns.

    It defines which campaigns use which AI Agent for auto-reply functionality.
    When an email response arrives for a campaign, the associated AI Agent's
    knowledge base is used to generate suggested replies.

    Example:
    - AI Agent "Cliente XYZ Wine Prospecting" → Campaign "XYZ Outreach 2024"
    - Email response received → AI generates reply using XYZ knowledge base
    - User approves → Email sent via Instantly
    """

    __tablename__ = "ai_agent_campaigns"

    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign Keys
    ai_agent_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ai_agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    campaign_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Configuration
    auto_reply_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    ai_agent: Mapped["AIAgent"] = relationship("AIAgent")
    campaign: Mapped["Campaign"] = relationship("Campaign")

    def __repr__(self) -> str:
        return f"<AIAgentCampaign(agent_id={self.ai_agent_id}, campaign_id={self.campaign_id}, auto_reply={self.auto_reply_enabled})>"
