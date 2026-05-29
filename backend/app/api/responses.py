from typing import Optional
"""Email responses API routes - list, generate AI reply, approve, send, delete.

Replies arrive via the Smartlead webhook (see `app/api/webhooks.py`) and are
persisted as `EmailResponse` rows directly. The legacy `/responses/fetch`
polling endpoint is retained as a no-op stub so any frontend code still
calling it during the migration window doesn't 404 — it will be removed
together with its UI button in Phase 4.
"""
import html
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.email_response import (
    EmailResponse,
    MessageDirection,
    ResponseStatus,
)
from app.schemas.response import (
    EmailResponseOut,
    EmailResponseListResponse,
    FetchRepliesRequest,
    FetchRepliesResponse,
    ApproveReplyRequest,
    SendReplyResponse,
)
from app.services.smartlead import smartlead_service, SmartleadAPIError
from app.services.sentiment import reply_service

logger = logging.getLogger(__name__)
router = APIRouter()


def _response_to_out(resp: EmailResponse) -> EmailResponseOut:
    """Convert ORM model to schema, populating joined fields."""
    out = EmailResponseOut.model_validate(resp)
    if resp.lead:
        out.lead_name = f"{resp.lead.first_name} {resp.lead.last_name}"
        out.lead_email = resp.lead.email
        out.lead_company = resp.lead.company
    elif resp.from_email:
        out.lead_email = resp.from_email
    if resp.campaign:
        out.campaign_name = resp.campaign.name
    return out


# --- List Responses ---


@router.get("", response_model=EmailResponseListResponse)
async def list_responses(
    campaign_id: Optional[int] = Query(None),
    campaign_ids: Optional[str] = Query(None, description="Comma-separated campaign IDs"),
    status: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    """List email responses with optional filters."""
    date_col = sa_func.coalesce(EmailResponse.received_at, EmailResponse.created_at)
    query = (
        select(EmailResponse)
        .options(
            selectinload(EmailResponse.lead),
            selectinload(EmailResponse.campaign),
        )
        .where(EmailResponse.direction == MessageDirection.INBOUND)
        .order_by(date_col.desc())
    )
    if campaign_ids:
        ids = [int(x.strip()) for x in campaign_ids.split(",") if x.strip()]
        if ids:
            query = query.where(EmailResponse.campaign_id.in_(ids))
    elif campaign_id is not None:
        query = query.where(EmailResponse.campaign_id == campaign_id)
    if status:
        query = query.where(EmailResponse.status == status)
    if sentiment:
        query = query.where(EmailResponse.sentiment == sentiment)
    if date_from:
        from_dt = datetime.fromisoformat(date_from)
        query = query.where(date_col >= from_dt)
    if date_to:
        to_dt = datetime.fromisoformat(date_to + "T23:59:59")
        query = query.where(date_col <= to_dt)

    result = await db.execute(query)
    responses = result.scalars().all()

    # Group by conversation: (campaign_id, lower(from_email)) — keep only the
    # most recent message per thread and attach a count so the UI can show a
    # "+N more" badge for back-and-forth conversations. Smartlead doesn't
    # currently populate `thread_id` in its EMAIL_REPLY webhook payload, so
    # we approximate the thread by `campaign + lead email`. Rows are already
    # date_col.desc()-ordered, so the first occurrence of each key is the
    # latest.
    threads: dict[tuple[int, str], EmailResponse] = {}
    thread_counts: dict[tuple[int, str], int] = {}
    for r in responses:
        em = (r.from_email or "").strip().lower()
        if not em:
            # Without a `from_email` we can't group — keep as its own row.
            threads[("__noaddr__", str(r.id))] = r
            thread_counts[("__noaddr__", str(r.id))] = 1
            continue
        key = (r.campaign_id, em)
        thread_counts[key] = thread_counts.get(key, 0) + 1
        if key not in threads:
            threads[key] = r

    items = []
    for key, r in threads.items():
        out = _response_to_out(r)
        out.thread_count = thread_counts[key]
        items.append(out)
    return EmailResponseListResponse(responses=items, total=len(items))


@router.get("/{response_id}/thread", response_model=EmailResponseListResponse)
async def get_response_thread(
    response_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Return every inbound message in the same conversation as `response_id`.

    Two messages belong to the same thread when they share the same
    `campaign_id` AND the same `from_email` (case-insensitive). Sorted
    oldest-first so the detail dialog can render the conversation
    chronologically. Smartlead's webhook payload doesn't include a stable
    thread_id, hence the (campaign, lead-email) heuristic.
    """
    anchor = await db.execute(
        select(EmailResponse).where(EmailResponse.id == response_id)
    )
    base = anchor.scalar_one_or_none()
    if not base:
        raise HTTPException(404, "Response not found")
    em = (base.from_email or "").strip().lower()
    if not em:
        # No address to group by → return just the anchor.
        return EmailResponseListResponse(responses=[_response_to_out(base)], total=1)

    date_col = sa_func.coalesce(EmailResponse.received_at, EmailResponse.created_at)
    result = await db.execute(
        select(EmailResponse)
        .options(
            selectinload(EmailResponse.lead),
            selectinload(EmailResponse.campaign),
        )
        .where(
            EmailResponse.direction == MessageDirection.INBOUND,
            EmailResponse.campaign_id == base.campaign_id,
            sa_func.lower(EmailResponse.from_email) == em,
        )
        .order_by(date_col.asc())
    )
    rows = result.scalars().all()
    return EmailResponseListResponse(
        responses=[_response_to_out(r) for r in rows],
        total=len(rows),
    )


# --- Fetch Replies (no-op stub) ---
#
# Replies are now pushed in by Smartlead via webhook (`/api/webhooks/smartlead`)
# the moment they arrive. This endpoint is kept as a no-op so any frontend
# button still calling it during the migration doesn't 404; it is removed
# together with its UI in Phase 4.


@router.post("/fetch", response_model=FetchRepliesResponse, deprecated=True)
async def fetch_replies(
    data: FetchRepliesRequest,
    db: AsyncSession = Depends(get_db),
):
    logger.info(
        "/responses/fetch called for campaign_ids=%s — no-op (replies arrive via Smartlead webhook)",
        data.campaign_ids,
    )
    return FetchRepliesResponse(fetched=0, skipped=0, errors=0)


# --- Response Stats ---


@router.get("/stats")
async def get_response_stats(
    campaign_ids: Optional[str] = Query(None, description="Comma-separated campaign IDs"),
    date_from: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    """Get response counts grouped by sentiment and status."""
    date_col = sa_func.coalesce(EmailResponse.received_at, EmailResponse.created_at)
    base_filter = [EmailResponse.direction == MessageDirection.INBOUND]

    if campaign_ids:
        ids = [int(x.strip()) for x in campaign_ids.split(",") if x.strip()]
        if ids:
            base_filter.append(EmailResponse.campaign_id.in_(ids))
    if date_from:
        base_filter.append(date_col >= datetime.fromisoformat(date_from))
    if date_to:
        base_filter.append(date_col <= datetime.fromisoformat(date_to + "T23:59:59"))

    # Count by sentiment
    sentiment_result = await db.execute(
        select(EmailResponse.sentiment, sa_func.count())
        .where(*base_filter)
        .group_by(EmailResponse.sentiment)
    )
    by_sentiment: dict[str, int] = {
        "interested": 0, "positive": 0, "neutral": 0, "negative": 0, "unknown": 0
    }
    total = 0
    for row in sentiment_result.all():
        val, count = row
        key = val.value if val else "unknown"
        by_sentiment[key] = count
        total += count

    # Count by status
    status_result = await db.execute(
        select(EmailResponse.status, sa_func.count())
        .where(*base_filter)
        .group_by(EmailResponse.status)
    )
    by_status: dict[str, int] = {}
    for row in status_result.all():
        val, count = row
        by_status[val.value if val else "unknown"] = count

    # Daily chart data grouped by sentiment
    chart_result = await db.execute(
        select(
            sa_func.date(date_col).label("day"),
            EmailResponse.sentiment,
            sa_func.count().label("cnt"),
        )
        .where(*base_filter)
        .group_by("day", EmailResponse.sentiment)
        .order_by(sa_func.date(date_col).asc())
    )
    chart_map: dict[str, dict[str, int]] = {}
    for row in chart_result.all():
        day_str = str(row.day)
        if day_str not in chart_map:
            chart_map[day_str] = {"interested": 0, "positive": 0, "neutral": 0, "negative": 0}
        key = row.sentiment.value if row.sentiment else "neutral"
        chart_map[day_str][key] = row.cnt

    chart_data = [{"date": day, **counts} for day, counts in chart_map.items()]

    return {
        "total": total,
        "by_sentiment": by_sentiment,
        "by_status": by_status,
        "chart_data": chart_data,
    }


# --- Generate AI Reply ---


@router.post("/{response_id}/generate-reply", response_model=EmailResponseOut)
async def generate_reply(
    response_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Generate an AI reply suggestion using Claude for a single response."""
    result = await db.execute(
        select(EmailResponse)
        .options(
            selectinload(EmailResponse.lead),
            selectinload(EmailResponse.campaign),
        )
        .where(EmailResponse.id == response_id)
    )
    resp = result.scalar_one_or_none()
    if not resp:
        raise HTTPException(404, "Response not found")

    try:
        lead_name = None
        lead_company = None
        if resp.lead:
            lead_name = f"{resp.lead.first_name} {resp.lead.last_name}"
            lead_company = resp.lead.company

        suggested_reply = await reply_service.generate_reply(
            email_body=resp.message_body or "",
            lead_name=lead_name,
            lead_company=lead_company,
            campaign_name=resp.campaign.name if resp.campaign else None,
            sentiment=resp.sentiment.value if resp.sentiment else None,
        )

        resp.ai_suggested_reply = suggested_reply
        if suggested_reply:
            resp.status = ResponseStatus.AI_REPLIED
        await db.flush()
        await db.refresh(resp, attribute_names=["lead", "campaign"])
    except Exception as e:
        logger.error(f"Failed to generate reply for response {response_id}: {e}")
        raise HTTPException(502, f"Reply generation failed: {str(e)}")

    return _response_to_out(resp)


# --- Approve Reply ---


@router.post("/{response_id}/approve", response_model=EmailResponseOut)
async def approve_reply(
    response_id: int,
    data: ApproveReplyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Approve an AI-suggested reply, optionally with edits."""
    result = await db.execute(
        select(EmailResponse)
        .options(
            selectinload(EmailResponse.lead),
            selectinload(EmailResponse.campaign),
        )
        .where(EmailResponse.id == response_id)
    )
    resp = result.scalar_one_or_none()
    if not resp:
        raise HTTPException(404, "Response not found")

    if data.edited_reply:
        resp.human_approved_reply = data.edited_reply
    else:
        resp.human_approved_reply = resp.ai_suggested_reply

    if not resp.human_approved_reply:
        raise HTTPException(400, "No reply text to approve")

    resp.status = ResponseStatus.HUMAN_APPROVED
    await db.flush()
    await db.refresh(resp, attribute_names=["lead", "campaign"])
    return _response_to_out(resp)


# --- Send Reply ---


@router.post("/{response_id}/send", response_model=SendReplyResponse)
async def send_reply(
    response_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Send an approved reply via Smartlead's reply-to-thread endpoint.

    Smartlead delivers the reply through the same email account the original
    thread is on (no per-call eaccount needed), and identifies the thread by
    the original message_id we stored on EmailResponse plus the Smartlead
    lead_id captured from the webhook payload.
    """
    from datetime import timezone

    result = await db.execute(
        select(EmailResponse)
        .options(
            selectinload(EmailResponse.lead),
            selectinload(EmailResponse.campaign),
        )
        .where(EmailResponse.id == response_id)
    )
    resp = result.scalar_one_or_none()
    if not resp:
        raise HTTPException(404, "Response not found")

    if resp.status not in (ResponseStatus.HUMAN_APPROVED, ResponseStatus.AI_REPLIED):
        raise HTTPException(
            400,
            f"Response must be approved before sending. Current status: {resp.status.value}",
        )

    reply_text = resp.human_approved_reply or resp.ai_suggested_reply
    if not reply_text:
        raise HTTPException(400, "No reply text available")

    # `instantly_email_id` is the legacy column name; it stores the Smartlead
    # message_id of the original inbound email captured by the webhook.
    if not resp.instantly_email_id:
        raise HTTPException(400, "No Smartlead message id on this response — cannot reply")
    if not resp.smartlead_lead_id:
        raise HTTPException(400, "No Smartlead lead id on this response — cannot reply")
    if not resp.campaign or not resp.campaign.instantly_campaign_id:
        raise HTTPException(400, "Linked campaign has no Smartlead id — cannot reply")

    email_html = "<div>{}</div>".format(
        html.escape(reply_text).replace("\r\n", "<br>").replace("\n", "<br>")
    )

    try:
        logger.info(
            "Sending Smartlead reply for response %s in campaign smartlead_id=%s lead_id=%s",
            response_id, resp.campaign.instantly_campaign_id, resp.smartlead_lead_id,
        )
        await smartlead_service.reply_to_thread(
            resp.campaign.instantly_campaign_id,
            lead_id=resp.smartlead_lead_id,
            email_body=email_html,
            reply_message_id=resp.instantly_email_id,
            reply_email_time=datetime.now(timezone.utc).isoformat(),
        )
        resp.status = ResponseStatus.SENT
        await db.flush()
        return SendReplyResponse(success=True, message="Reply sent successfully")
    except SmartleadAPIError as e:
        logger.error("Smartlead reply failed for response %s: %s", response_id, e.detail)
        raise HTTPException(502, f"Failed to send reply via Smartlead: {e.detail}")
    except Exception as e:
        logger.error("Unexpected error sending response %s: %s", response_id, e)
        raise HTTPException(500, f"Internal server error while sending reply: {e}")


# --- Ignore Response ---


@router.post("/{response_id}/ignore", response_model=EmailResponseOut)
async def ignore_response(
    response_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Mark a response as ignored."""
    result = await db.execute(
        select(EmailResponse)
        .options(
            selectinload(EmailResponse.lead),
            selectinload(EmailResponse.campaign),
        )
        .where(EmailResponse.id == response_id)
    )
    resp = result.scalar_one_or_none()
    if not resp:
        raise HTTPException(404, "Response not found")

    resp.status = ResponseStatus.IGNORED
    await db.flush()
    await db.refresh(resp, attribute_names=["lead", "campaign"])
    return _response_to_out(resp)


# --- Delete Response ---


@router.delete("/{response_id}")
async def delete_response(
    response_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a response from the database (does not affect Instantly)."""
    result = await db.execute(
        select(EmailResponse).where(EmailResponse.id == response_id)
    )
    resp = result.scalar_one_or_none()
    if not resp:
        raise HTTPException(404, "Response not found")

    await db.delete(resp)
    await db.flush()
    return {"success": True}


# --- Bulk Delete Responses ---


@router.post("/bulk-delete")
async def bulk_delete_responses(
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple responses from the database."""
    ids = data.get("ids", [])
    if not ids:
        raise HTTPException(400, "No IDs provided")

    result = await db.execute(
        select(EmailResponse).where(EmailResponse.id.in_(ids))
    )
    responses = result.scalars().all()
    for resp in responses:
        await db.delete(resp)
    await db.flush()
    return {"deleted": len(responses)}


