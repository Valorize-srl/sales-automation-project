"""
Admin endpoints for maintenance and inspection.

The previous /backfill-sender-emails endpoint was Instantly-specific and
relied on `instantly_service.list_emails`, which doesn't exist on Smartlead.
After the Phase 3 wipe of historical Instantly data it had no rows to operate
on anyway, so it was removed. /check-sender-emails is generic and still
useful for inspection.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import delete as sql_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.campaign import Campaign
from app.models.email_response import EmailResponse, Sentiment
from app.services.smartlead import SmartleadAPIError, smartlead_service
from app.services.smartlead_categories import (
    category_to_sentiment,
    smartlead_categories,
)
from app.services.smartlead_sender_pool import smartlead_sender_pool

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/sync-smartlead-categories")
async def sync_smartlead_categories(db: AsyncSession = Depends(get_db)):
    """Backfill `lead_category` (and derived `sentiment`) on EmailResponse rows
    where Smartlead has since categorized the reply but our webhook stored a
    null category because the AI categorization is asynchronous.

    Flow: for every campaign with a Smartlead id, page through
    `/campaigns/{id}/statistics?email_status=replied` and for each row whose
    `lead_category` is populated, find the matching EmailResponse by
    (campaign, lead_email) and update both columns.

    Idempotent; returns counts so a second run on a no-change DB returns 0.
    """
    await smartlead_categories.refresh()

    campaigns_result = await db.execute(
        select(Campaign).where(Campaign.instantly_campaign_id.isnot(None))
    )
    campaigns = campaigns_result.scalars().all()

    updated = 0
    fetched = 0
    no_match = 0
    errors = 0

    for camp in campaigns:
        sid = camp.instantly_campaign_id
        offset = 0
        try:
            while True:
                page = await smartlead_service.get_campaign_statistics(
                    sid, email_status="replied", offset=offset, limit=100,
                )
                rows = page.get("data") if isinstance(page, dict) else []
                if not rows:
                    break
                fetched += len(rows)
                for row in rows:
                    cat_name = (row.get("lead_category") or "").strip() or None
                    if not cat_name:
                        continue
                    em = (row.get("lead_email") or "").strip().lower() or None
                    if not em:
                        continue
                    # Pick the EmailResponse row(s) for this campaign + lead
                    # whose category is currently null.
                    target_result = await db.execute(
                        select(EmailResponse).where(
                            EmailResponse.campaign_id == camp.id,
                            EmailResponse.lead_category.is_(None),
                            EmailResponse.from_email == em,
                        )
                    )
                    targets = list(target_result.scalars().all())
                    if not targets:
                        no_match += 1
                        continue
                    sentiment = await category_to_sentiment(category_name=cat_name)
                    for t in targets:
                        t.lead_category = cat_name
                        if sentiment is not None:
                            t.sentiment = sentiment
                        updated += 1
                if len(rows) < 100:
                    break
                offset += 100
        except SmartleadAPIError as e:
            logger.warning("Smartlead stats fetch failed for campaign %s: %s", sid, e.detail)
            errors += 1
            continue

    await db.commit()
    return {
        "campaigns": len(campaigns),
        "fetched_from_smartlead": fetched,
        "updated": updated,
        "no_local_match": no_match,
        "errors": errors,
    }


@router.post("/cleanup-warmup-replies")
async def cleanup_warmup_replies(db: AsyncSession = Depends(get_db)):
    """Delete EmailResponse rows whose `from_email` matches one of our
    Smartlead sender accounts.

    These are warmup auto-replies (Smartlead's senders ping each other to
    build deliverability reputation) that the webhook persisted before we
    added the outbound-filter. One-shot cleanup; idempotent — safe to call
    again, just returns 0 next time.
    """
    # Force-refresh the sender pool from Smartlead so the deletion criterion
    # is up-to-date (covers recently-added accounts).
    await smartlead_sender_pool.refresh()
    sender_emails = sorted(smartlead_sender_pool._emails)  # noqa: SLF001

    if not sender_emails:
        return {"deleted": 0, "message": "no sender accounts known — refresh failed?"}

    # Pull matching rows so we can report what was removed.
    matching = await db.execute(
        select(EmailResponse.id, EmailResponse.from_email)
        .where(EmailResponse.from_email.in_(sender_emails))
    )
    rows = matching.all()
    ids = [r.id for r in rows]

    if ids:
        await db.execute(
            sql_delete(EmailResponse).where(EmailResponse.id.in_(ids))
        )
        await db.commit()

    return {
        "deleted": len(ids),
        "deleted_ids": ids,
        "examples": [{"id": r.id, "from_email": r.from_email} for r in rows[:10]],
        "sender_pool_size": len(sender_emails),
    }


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
