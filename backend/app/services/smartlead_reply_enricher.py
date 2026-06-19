"""Fetch the actual reply body + category from Smartlead and merge it into a
local EmailResponse row.

Smartlead's `EMAIL_REPLY` webhook payload is unreliable: the body field is
frequently missing (logged as empty) and `lead_category` arrives null because
Smartlead's AI categorization runs asynchronously after the webhook. The
fields ARE available through the REST API later, so we fetch:

  1. `GET /leads/?email=...`                                 → smartlead lead_id
  2. `GET /campaigns/{cid}/leads/{lid}/message-history`      → reply body / message_id
  3. `GET /campaigns/{cid}/statistics?email_status=replied`  → lead_category

…and patch the EmailResponse row that we just stored. Idempotent: re-running
on an already-complete row updates nothing.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_response import EmailResponse, Sentiment
from app.services.smartlead import SmartleadAPIError, smartlead_service
from app.services.smartlead_categories import category_to_sentiment

logger = logging.getLogger(__name__)


async def enrich_response(
    db: AsyncSession,
    response: EmailResponse,
    smartlead_campaign_id: str,
    lead_email: str,
) -> dict:
    """Patch `response` in-place with body/subject/lead_category fetched from
    Smartlead. Returns a dict describing what changed (useful for logging).

    Safe to call on an already-complete row — only fills what's missing.
    """
    changes: dict[str, bool] = {
        "body": False, "subject": False, "category": False,
        "thread_id": False, "message_id": False, "smartlead_lead_id": False,
        "stats_id": False, "sender_email": False,
    }

    needs_body = not (response.message_body or "").strip()
    needs_category = not (response.lead_category or "").strip()
    needs_smartlead_lead_id = not response.smartlead_lead_id
    needs_stats_id = not response.smartlead_message_stats_id
    needs_sender_email = not (response.sender_email or "").strip()

    if not (needs_body or needs_category or needs_smartlead_lead_id
            or needs_stats_id or needs_sender_email):
        return changes

    # 1. Resolve smartlead lead_id by email (if we don't already have it).
    sl_lead_id: Optional[str] = response.smartlead_lead_id
    if not sl_lead_id and lead_email:
        try:
            lead_data = await smartlead_service.fetch_lead_by_email(lead_email)
        except SmartleadAPIError as e:
            logger.warning("enrich_response: lead lookup failed for %s: %s", lead_email, e.detail)
            lead_data = None
        if isinstance(lead_data, dict):
            raw_id = lead_data.get("id")
            if raw_id is not None:
                sl_lead_id = str(raw_id)
                response.smartlead_lead_id = sl_lead_id
                changes["smartlead_lead_id"] = True

    # 2. Fetch message-history → fill body/subject/message_id/thread_id +
    #    stats_id (per il reply-email-thread) + sender_email (la nostra
    #    casella che ha inviato il messaggio originale = il SENT message).
    needs_history = (
        needs_body or not response.thread_id or not response.instantly_email_id
        or needs_stats_id or needs_sender_email
    )
    if sl_lead_id and needs_history:
        try:
            hist = await smartlead_service.get_lead_message_history(
                smartlead_campaign_id, sl_lead_id,
            )
        except SmartleadAPIError as e:
            logger.warning(
                "enrich_response: message-history failed for campaign=%s lead=%s: %s",
                smartlead_campaign_id, sl_lead_id, e.detail,
            )
            hist = {}
        messages = hist.get("history") if isinstance(hist, dict) else []
        # Pick the latest REPLY (= inbound from the lead).
        replies = [m for m in (messages or []) if (m.get("type") or "").upper() == "REPLY"]
        replies.sort(key=lambda m: m.get("time") or "", reverse=True)
        if replies:
            latest = replies[0]
            body_new = (latest.get("email_body") or latest.get("body") or "").strip()
            if needs_body and body_new:
                response.message_body = body_new
                changes["body"] = True
            subj_new = (latest.get("subject") or "").strip()
            if subj_new and not (response.subject or "").strip():
                response.subject = subj_new
                changes["subject"] = True
            mid_new = (latest.get("message_id") or "").strip() or None
            if mid_new and not response.instantly_email_id:
                response.instantly_email_id = mid_new
                changes["message_id"] = True
            stats_new = (latest.get("stats_id") or latest.get("email_stats_id") or "").strip() or None
            if needs_stats_id and stats_new:
                response.smartlead_message_stats_id = stats_new
                changes["stats_id"] = True

        # The latest SENT message = the outbound mail from our sender that
        # the lead replied to. Its `email_from_account` or `from_email` is
        # the sender we'll need to reply from.
        sent_msgs = [m for m in (messages or []) if (m.get("type") or "").upper() == "SENT"]
        sent_msgs.sort(key=lambda m: m.get("time") or "", reverse=True)
        if needs_sender_email and sent_msgs:
            latest_sent = sent_msgs[0]
            sender_new = (
                (latest_sent.get("email_from_account") or "").strip()
                or (latest_sent.get("from_email") or "").strip()
                or (latest_sent.get("email_from") or "").strip()
            )
            if sender_new:
                response.sender_email = sender_new.lower()
                changes["sender_email"] = True

    # 3. Fetch category from statistics if still missing.
    if needs_category:
        try:
            offset = 0
            cat_name: Optional[str] = None
            while True:
                page = await smartlead_service.get_campaign_statistics(
                    smartlead_campaign_id, email_status="replied",
                    offset=offset, limit=100,
                )
                rows = page.get("data") if isinstance(page, dict) else []
                if not rows:
                    break
                for r in rows:
                    em = (r.get("lead_email") or "").strip().lower()
                    if em == lead_email.lower():
                        cat_name = (r.get("lead_category") or "").strip() or None
                        break
                if cat_name or len(rows) < 100:
                    break
                offset += 100
            if cat_name:
                response.lead_category = cat_name
                sentiment = await category_to_sentiment(category_name=cat_name)
                if sentiment is not None:
                    response.sentiment = sentiment
                changes["category"] = True
        except SmartleadAPIError as e:
            logger.warning(
                "enrich_response: statistics failed for campaign=%s: %s",
                smartlead_campaign_id, e.detail,
            )

    return changes
