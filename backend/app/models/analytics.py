from datetime import date

from sqlalchemy import Integer, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Analytics(Base):
    __tablename__ = "analytics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    emails_sent: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    opens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    replies: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    positive_replies: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    meetings_booked: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # Relationships
    campaign: Mapped["Campaign"] = relationship(back_populates="analytics_entries")
