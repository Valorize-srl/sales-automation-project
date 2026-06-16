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
from app.services.smartlead_reply_enricher import enrich_response
from app.services.smartlead_sender_pool import smartlead_sender_pool

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/enrich-responses")
async def enrich_responses(db: AsyncSession = Depends(get_db)):
    """Backfill missing body / lead_category / smartlead_lead_id on
    EmailResponse rows by fetching message-history + statistics from
    Smartlead. Idempotent; safe to re-run.

    Use after the webhook handler stored partial rows (Smartlead's
    EMAIL_REPLY payload often arrives without body and without category).
    """
    # All inbound rows that look incomplete (no body OR no category).
    from sqlalchemy import func as sa_func, or_
    incomplete_result = await db.execute(
        select(EmailResponse, Campaign)
        .join(Campaign, EmailResponse.campaign_id == Campaign.id)
        .where(
            or_(
                EmailResponse.message_body.is_(None),
                sa_func.length(EmailResponse.message_body) == 0,
                EmailResponse.lead_category.is_(None),
            )
        )
    )
    rows = incomplete_result.all()
    logger.info("enrich_responses: %d incomplete rows", len(rows))

    enriched = 0
    skipped_no_email = 0
    skipped_no_campaign_id = 0
    failed = 0

    for resp, camp in rows:
        em = (resp.from_email or "").strip().lower()
        if not em:
            skipped_no_email += 1
            continue
        if not camp.instantly_campaign_id:
            skipped_no_campaign_id += 1
            continue
        try:
            changes = await enrich_response(
                db, resp,
                smartlead_campaign_id=str(camp.instantly_campaign_id),
                lead_email=em,
            )
            if any(changes.values()):
                enriched += 1
        except Exception as e:
            logger.warning("enrich_responses row id=%s failed: %s", resp.id, e)
            failed += 1

    await db.commit()
    return {
        "scanned": len(rows),
        "enriched": enriched,
        "skipped_no_email": skipped_no_email,
        "skipped_no_campaign_id": skipped_no_campaign_id,
        "failed": failed,
    }


@router.post("/remap-info-request-to-interested")
async def remap_info_request_to_interested(db: AsyncSession = Depends(get_db)):
    """One-shot backfill: rows whose `lead_category` is a variant of
    "Information Request" stop being POSITIVE and become INTERESTED.

    Aligns with the product decision (2026-06-16) that requests for
    information are a strong-intent signal and belong in the Interested
    bucket. The ingestion-time mapping in `smartlead_categories.py` is
    already updated for new webhooks; this handles the historical rows.
    """
    from sqlalchemy import update, func as sa_func

    info_keys = {
        "information request", "info request", "requested info",
    }
    stmt = (
        update(EmailResponse)
        .where(
            sa_func.lower(EmailResponse.lead_category).in_(info_keys),
            EmailResponse.sentiment != Sentiment.INTERESTED,
        )
        .values(sentiment=Sentiment.INTERESTED)
    )
    result = await db.execute(stmt)
    await db.commit()
    return {"updated": int(result.rowcount or 0)}


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


@router.post("/cleanup-noreply-replies")
async def cleanup_noreply_replies(db: AsyncSession = Depends(get_db)):
    """Delete EmailResponse rows whose `from_email` is a no-reply / auto-ack
    address (sub-addressed `+noreply@`, or starting with `noreply@` /
    `no-reply@` / `do-not-reply@`).

    These are auto-acknowledgements from corporate notification systems
    (e.g. car dealerships, insurance complaint mailboxes) — no human
    content, never categorized by Smartlead. The webhook handler now
    skips them on arrival; this endpoint removes the ones that landed
    before the filter was added.
    """
    from sqlalchemy import or_
    result = await db.execute(
        select(EmailResponse).where(
            or_(
                EmailResponse.from_email.ilike("%+noreply@%"),
                EmailResponse.from_email.ilike("%+no-reply@%"),
                EmailResponse.from_email.ilike("noreply@%"),
                EmailResponse.from_email.ilike("no-reply@%"),
                EmailResponse.from_email.ilike("do-not-reply@%"),
                EmailResponse.from_email.ilike("donotreply@%"),
            )
        )
    )
    rows = list(result.scalars().all())
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
