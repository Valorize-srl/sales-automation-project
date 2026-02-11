import enum
from datetime import datetime

from sqlalchemy import String, Text, Integer, ForeignKey, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    icp_id: Mapped[int] = mapped_column(ForeignKey("icps.id", ondelete="CASCADE"), nullable=False)
    instantly_campaign_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[CampaignStatus] = mapped_column(
        SAEnum(CampaignStatus, native_enum=False),
        default=CampaignStatus.DRAFT,
        server_default="draft",
    )
    subject_lines: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_templates: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_sent: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    total_opened: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    total_replied: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    icp: Mapped["ICP"] = relationship(back_populates="campaigns")
    email_responses: Mapped[list["EmailResponse"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")
    analytics_entries: Mapped[list["Analytics"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")
