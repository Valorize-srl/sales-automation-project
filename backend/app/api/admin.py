"""
Admin endpoints for maintenance and inspection.

The previous /backfill-sender-emails endpoint was Instantly-specific and
relied on `instantly_service.list_emails`, which doesn't exist on Smartlead.
After the Phase 3 wipe of historical Instantly data it had no rows to operate
on anyway, so it was removed. /check-sender-emails is generic and still
useful for inspection.
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.email_response import EmailResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/check-sender-emails")
async def check_sender_emails(db: AsyncSession = Depends(get_db)):
    """Check status of sender_email field for all responses."""
    result_with = await db.execute(
        select(EmailResponse.id, EmailResponse.campaign_id, EmailResponse.sender_email)
        .where(EmailResponse.sender_email.isnot(None))
        .order_by(EmailResponse.id)
    )
    responses_with = result_with.all()

    result_without = await db.execute(
        select(EmailResponse.id, EmailResponse.campaign_id, EmailResponse.instantly_email_id)
        .where(
            EmailResponse.sender_email.is_(None),
            EmailResponse.instantly_email_id.isnot(None),
        )
        .order_by(EmailResponse.id)
    )
    responses_without = result_without.all()

    return {
        "with_sender_email": {
            "count": len(responses_with),
            "response_ids": [r.id for r in responses_with],
            "details": [
                {
                    "id": r.id,
                    "campaign_id": r.campaign_id,
                    "sender_email": r.sender_email,
                }
                for r in responses_with[:20]
            ],
        },
        "without_sender_email": {
            "count": len(responses_without),
            "response_ids": [r.id for r in responses_without],
            "details": [
                {
                    "id": r.id,
                    "campaign_id": r.campaign_id,
                    "instantly_email_id": r.instantly_email_id,
                }
                for r in responses_without[:20]
            ],
        },
    }
