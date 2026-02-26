"""Many-to-many association between Campaign and LeadList."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.database import Base


class CampaignLeadList(Base):
    """
    Associates a LeadList with a Campaign.

    Tracks whether the leads in this list have been pushed to Instantly.
    """

    __tablename__ = "campaign_lead_lists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_list_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("lead_lists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pushed_to_instantly: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    pushed_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<CampaignLeadList(campaign={self.campaign_id}, list={self.lead_list_id})>"
