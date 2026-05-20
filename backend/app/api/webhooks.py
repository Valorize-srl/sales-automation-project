"""Inbound webhooks from external providers (currently: Smartlead).

The Smartlead webhook is the live-sync mechanism replacing the legacy
`/responses/fetch` polling endpoint. Smartlead POSTs here when a reply is
received, when a lead is unsubscribed/bounced, or when a campaign's status
changes; we authenticate the request via HMAC-SHA256 against the configured
`SMARTLEAD_WEBHOOK_SECRET`, then persist or update DB rows accordingly.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_db
from app.models.campaign import Campaign, CampaignStatus
from app.models.email_response import (
    EmailResponse,
    MessageDirection,
    ResponseStatus,
)
from app.models.lead import Lead
from app.services.smartlead_categories import category_to_sentiment

logger = logging.getLogger(__name__)
router = APIRouter()


SMARTLEAD_TO_CAMPAIGN_STATUS: dict[str, CampaignStatus] = {
    "DRAFTED": CampaignStatus.DRAFT,
    "ACTIVE": CampaignStatus.ACTIVE,
    "PAUSED": CampaignStatus.PAUSED,
    # Smartlead's "STOPPED" is a hard stop; our UI doesn't distinguish from
    # PAUSED, so map it there to keep the campaign list display sensible.
    "STOPPED": CampaignStatus.PAUSED,
    "COMPLETED": CampaignStatus.COMPLETED,
    "ARCHIVED": CampaignStatus.COMPLETED,
}


# ----------------------------------------------------------------------
# HMAC verification
# ----------------------------------------------------------------------


def _verify_hmac(raw_body: bytes, signature: Optional[str], secret: str) -> bool:
    """Validate an HMAC-SHA256 signature header against the raw body bytes.

    Fail-closed: if either signature or secret is missing, returns False so
    the request is rejected. Tolerates a leading `sha256=` prefix that some
    webhook providers add to the header value.
    """
    if not signature or not secret:
        return False
    sig = signature.split("=", 1)[-1].strip()
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


# ----------------------------------------------------------------------
# Helpers — find local records that correspond to the webhook payload
# ----------------------------------------------------------------------


async def _find_campaign(db: AsyncSession, smartlead_campaign_id: Any) -> Optional[Campaign]:
    """Resolve a Smartlead campaign id to our local `Campaign` row.

    The DB column is still named `instantly_campaign_id` (deferred rename —
    see migration 033) but stores Smartlead values going forward.
    """
    if smartlead_campaign_id is None:
        return None
    sid = str(smartlead_campaign_id)
    result = await db.execute(
        select(Campaign).where(Campaign.instantly_campaign_id == sid)
    )
    return result.scalar_one_or_none()


async def _find_lead_by_email(db: AsyncSession, email: Optional[str]) -> Optional[Lead]:
    if not email:
        return None
    result = await db.execute(
        select(Lead).where(Lead.email == email.strip().lower())
    )
    return result.scalar_one_or_none()


# ----------------------------------------------------------------------
# Event handlers
# ----------------------------------------------------------------------


async def _handle_reply(payload: dict, db: AsyncSession) -> str:
    """Persist an inbound reply event as an `EmailResponse` row.

    Returns a one-word status for the response body: "stored" / "dup" /
    "no_campaign" / "no_message_id".
    """
    smartlead_campaign_id = (
        payload.get("campaign_id")
        or payload.get("smartlead_campaign_id")
    )
    campaign = await _find_campaign(db, smartlead_campaign_id)
    if not campaign:
        logger.warning(
            "Smartlead reply for unknown campaign smartlead_id=%s",
            smartlead_campaign_id,
        )
        return "no_campaign"

    message_id = (
        payload.get("message_id")
        or payload.get("reply_message_id")
        or payload.get("email_id")
        or ""
    )
    if not message_id:
        logger.warning("Smartlead reply missing message_id: %s", payload)
        return "no_message_id"

    # Dedup on message_id (stored in the legacy column `instantly_email_id`).
    existing = await db.execute(
        select(EmailResponse.id).where(
            EmailResponse.instantly_email_id == str(message_id)
        )
    )
    if existing.scalar_one_or_none() is not None:
        return "dup"

    lead_email = (
        payload.get("from_email")
        or payload.get("lead_email")
        or payload.get("reply_email")
        or ""
    ).strip().lower() or None
    lead = await _find_lead_by_email(db, lead_email)

    # Category → Sentiment. Smartlead webhooks may include either the id, the
    # name, or both. Our cache resolves both.
    cat_id_raw = (
        payload.get("lead_category_id")
        or payload.get("category_id")
    )
    try:
        cat_id_int = int(cat_id_raw) if cat_id_raw is not None else None
    except (TypeError, ValueError):
        cat_id_int = None
    cat_name = payload.get("lead_category") or payload.get("category")
    sentiment = await category_to_sentiment(
        category_id=cat_id_int, category_name=cat_name,
    )

    # Parse receive timestamp
    received_at: Optional[datetime] = None
    ts_raw = (
        payload.get("received_at")
        or payload.get("timestamp")
        or payload.get("time_replied")
        or payload.get("reply_time")
    )
    if ts_raw:
        try:
            received_at = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            received_at = None

    body_text = payload.get("body_text") or payload.get("text") or ""
    body_html = payload.get("body_html") or payload.get("html") or ""
    body = body_text or body_html or ""

    sender_email = (
        payload.get("eaccount")
        or payload.get("sender_email")
        or payload.get("to_email")
    )

    smartlead_lead_id = payload.get("lead_id") or payload.get("smartlead_lead_id")

    record = EmailResponse(
        campaign_id=campaign.id,
        lead_id=lead.id if lead else None,
        instantly_email_id=str(message_id),  # column reused for Smartlead message_id
        smartlead_lead_id=str(smartlead_lead_id) if smartlead_lead_id is not None else None,
        from_email=lead_email,
        sender_email=str(sender_email).lower() if sender_email else None,
        thread_id=payload.get("thread_id"),
        subject=payload.get("subject"),
        message_body=body,
        direction=MessageDirection.INBOUND,
        status=ResponseStatus.PENDING,
        received_at=received_at,
        sentiment=sentiment,
    )
    db.add(record)
    await db.flush()
    logger.info(
        "Smartlead reply stored: campaign=%s lead=%s message_id=%s sentiment=%s",
        campaign.id, lead.id if lead else None, message_id, sentiment,
    )
    return "stored"


async def _handle_status_change(payload: dict, db: AsyncSession) -> str:
    smartlead_campaign_id = payload.get("campaign_id") or payload.get("smartlead_campaign_id")
    campaign = await _find_campaign(db, smartlead_campaign_id)
    if not campaign:
        return "no_campaign"
    new_status_raw = (
        payload.get("new_status")
        or payload.get("status")
        or payload.get("campaign_status")
        or ""
    ).upper()
    mapped = SMARTLEAD_TO_CAMPAIGN_STATUS.get(new_status_raw)
    if not mapped:
        logger.warning("Smartlead status_change: unmapped status '%s'", new_status_raw)
        return "unmapped_status"
    campaign.status = mapped
    await db.flush()
    logger.info(
        "Smartlead campaign %s (smartlead_id=%s) status → %s",
        campaign.id, smartlead_campaign_id, mapped,
    )
    return "updated"


async def _handle_bounce(payload: dict, db: AsyncSession) -> str:
    # Logged-only for now. Future: flip a "bounced" flag on the Lead row.
    logger.info("Smartlead EMAIL_BOUNCE payload: %s", payload)
    return "logged"


async def _handle_unsubscribe(payload: dict, db: AsyncSession) -> str:
    logger.info("Smartlead LEAD_UNSUBSCRIBED payload: %s", payload)
    return "logged"


# ----------------------------------------------------------------------
# Route
# ----------------------------------------------------------------------


@router.post("/smartlead")
async def smartlead_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive a Smartlead webhook event.

    Smartlead may sign the request with HMAC-SHA256 — we accept the signature
    from any of `X-Smartlead-Signature`, `X-Signature`, or
    `Smartlead-Signature` (varies by account). If `SMARTLEAD_WEBHOOK_SECRET`
    is unset on the server, all requests are rejected with 401.
    """
    raw_body = await request.body()
    signature = (
        request.headers.get("x-smartlead-signature")
        or request.headers.get("x-signature")
        or request.headers.get("smartlead-signature")
    )
    if not _verify_hmac(raw_body, signature, settings.smartlead_webhook_secret):
        logger.warning("Smartlead webhook rejected — bad/missing signature")
        raise HTTPException(401, "Invalid webhook signature")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")
    if not isinstance(payload, dict):
        raise HTTPException(400, "Payload must be an object")

    event = (
        payload.get("event_type")
        or payload.get("event")
        or payload.get("type")
        or ""
    ).upper()
    logger.info("Smartlead webhook event=%s", event)

    if event in ("EMAIL_REPLY", "EMAIL_REPLY_RECEIVED", "REPLY_RECEIVED"):
        result = await _handle_reply(payload, db)
    elif event in ("EMAIL_BOUNCE", "EMAIL_BOUNCED"):
        result = await _handle_bounce(payload, db)
    elif event in ("LEAD_UNSUBSCRIBED", "EMAIL_UNSUBSCRIBED"):
        result = await _handle_unsubscribe(payload, db)
    elif event in ("CAMPAIGN_STATUS_CHANGED", "CAMPAIGN_STATUS_CHANGE"):
        result = await _handle_status_change(payload, db)
    else:
        logger.info("Smartlead webhook unknown event=%s payload=%s", event, payload)
        result = "ignored"

    return {"ok": True, "event": event or "unknown", "result": result}
