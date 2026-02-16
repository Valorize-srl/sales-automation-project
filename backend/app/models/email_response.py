import enum
from datetime import datetime

from sqlalchemy import String, Text, Float, ForeignKey, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base


class MessageDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class Sentiment(str, enum.Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    INTERESTED = "interested"


class ResponseStatus(str, enum.Enum):
    PENDING = "pending"
    AI_REPLIED = "ai_replied"
    HUMAN_APPROVED = "human_approved"
    SENT = "sent"
    IGNORED = "ignored"


class EmailResponse(Base):
    __tablename__ = "email_responses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=True)
    instantly_email_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    from_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    direction: Mapped[MessageDirection] = mapped_column(
        SAEnum(MessageDirection, native_enum=False),
        nullable=False,
    )
    sentiment: Mapped[Sentiment | None] = mapped_column(
        SAEnum(Sentiment, native_enum=False),
        nullable=True,
    )
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_suggested_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_approved_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ResponseStatus] = mapped_column(
        SAEnum(ResponseStatus, native_enum=False),
        default=ResponseStatus.PENDING,
        server_default="pending",
    )
    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    campaign: Mapped["Campaign"] = relationship(back_populates="email_responses")
    lead: Mapped["Lead | None"] = relationship(back_populates="email_responses")
