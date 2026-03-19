from typing import Any, Optional
"""Email responses API routes - fetch, generate AI reply, approve, send, delete."""
import asyncio
import html
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.campaign import Campaign
from app.models.email_response import (
    EmailResponse,
    MessageDirection,
    ResponseStatus,
    Sentiment,
)
from app.models.lead import Lead
from app.schemas.response import (
    EmailResponseOut,
    EmailResponseListResponse,
    FetchRepliesRequest,
    FetchRepliesResponse,
    ApproveReplyRequest,
    SendReplyResponse,
)
from app.services.instantly import instantly_service, InstantlyAPIError
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


def _score_to_sentiment(score: Optional[float]) -> Optional[Sentiment]:
    """Map Instantly ai_interest_value (0-1) to our Sentiment enum."""
    if score is None:
        return None
    if score >= 0.7:
        return Sentiment.INTERESTED
    if score >= 0.4:
        return Sentiment.POSITIVE
    if score >= 0.2:
        return Sentiment.NEUTRAL
    return Sentiment.NEGATIVE


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
    items = [_response_to_out(r) for r in responses]
    return EmailResponseListResponse(responses=items, total=len(items))


# --- Fetch Replies from Instantly ---


async def _process_email_item(
    email_item: dict,
    campaign_id: int,
    db: AsyncSession,
    our_accounts: set[str],
) -> str:
    """Process a single email item from Instantly. Returns 'fetched', 'skipped', or 'skip_outbound'."""
    instantly_id = email_item.get("id")
    if not instantly_id:
        return "skipped"

    # Deduplication
    existing = await db.execute(
        select(EmailResponse.id).where(
            EmailResponse.instantly_email_id == instantly_id
        )
    )
    if existing.scalar_one_or_none() is not None:
        return "skipped"

    # Determine direction: if from_address_email is one of our sending accounts, it's outbound
    from_email = email_item.get("from_address_email", "")
    eaccount = email_item.get("eaccount", "")
    if from_email and from_email.lower() in our_accounts:
        return "skip_outbound"

    # Match lead by sender email
    lead_id = None
    if from_email:
        lead_result = await db.execute(
            select(Lead).where(Lead.email == from_email.lower())
        )
        lead = lead_result.scalar_one_or_none()
        if lead:
            lead_id = lead.id

    # Extract body text
    body_raw = email_item.get("body", "")
    if isinstance(body_raw, dict):
        body_text = body_raw.get("text", "") or body_raw.get("html", "")
    else:
        body_text = str(body_raw)

    # Parse actual email timestamp from Instantly
    received_at = None
    ts_raw = email_item.get("timestamp_email")
    if ts_raw:
        try:
            received_at = datetime.fromisoformat(
                ts_raw.replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            pass

    # Extract sentiment from Instantly's AI interest score
    ai_interest = email_item.get("ai_interest_value")
    sentiment_score = None
    sentiment_val = None
    if ai_interest is not None:
        try:
            sentiment_score = float(ai_interest)
            sentiment_val = _score_to_sentiment(sentiment_score)
        except (ValueError, TypeError):
            pass

    # Create record
    email_response = EmailResponse(
        campaign_id=campaign_id,
        lead_id=lead_id,
        instantly_email_id=instantly_id,
        from_email=from_email,
        sender_email=eaccount,
        thread_id=email_item.get("thread_id"),
        subject=email_item.get("subject", ""),
        message_body=body_text,
        direction=MessageDirection.INBOUND,
        status=ResponseStatus.PENDING,
        received_at=received_at,
        sentiment=sentiment_val,
        sentiment_score=sentiment_score,
    )
    db.add(email_response)
    await db.flush()
    return "fetched"


async def _paginated_fetch(
    campaign_instantly_id: str,
    campaign_id: int,
    db: AsyncSession,
    our_accounts: set[str],
    email_type: Optional[str] = None,
    lead_email: Optional[str] = None,
) -> tuple[int, int]:
    """Fetch emails from Instantly with pagination. Returns (fetched, skipped)."""
    fetched = 0
    skipped = 0
    starting_after = None

    while True:
        kwargs: dict[str, Any] = {
            "campaign_id": campaign_instantly_id,
            "limit": 50,
            "starting_after": starting_after,
        }
        if email_type:
            kwargs["email_type"] = email_type
        if lead_email:
            kwargs["lead"] = lead_email
        email_data = await instantly_service.list_emails(**kwargs)

        # Try different response structures (Instantly API format varies)
        items = (
            email_data.get("items") or
            email_data.get("data") or
            email_data.get("emails") or
            []
        )
        if not items:
            logger.info(f"No email items found. Response keys: {[k for k in email_data.keys() if k != '_status_code']}")
            break

        for email_item in items:
            result = await _process_email_item(email_item, campaign_id, db, our_accounts)
            if result == "fetched":
                fetched += 1
            elif result == "skipped":
                skipped += 1

        # Cursor pagination — check both top-level and nested pagination object
        pagination = email_data.get("pagination", {})
        next_cursor = (
            email_data.get("next_starting_after") or
            pagination.get("next_starting_after")
        )
        if not next_cursor or len(items) < 50:
            break
        starting_after = next_cursor
        await asyncio.sleep(0.5)  # Rate limit between pagination calls

    return fetched, skipped


@router.post("/fetch", response_model=FetchRepliesResponse)
async def fetch_replies(
    data: FetchRepliesRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch new replies from Instantly for given campaigns.
    Imports inbound emails with sentiment from Instantly's ai_interest_value.
    Outbound emails are filtered via our_accounts detection (DB + Instantly API).
    Includes retry with backoff on rate limits and inter-campaign throttling.
    """
    fetched = 0
    skipped = 0
    errors = 0

    # Collect our sending accounts to distinguish inbound vs outbound
    # 1) From existing records in DB
    acct_result = await db.execute(
        select(EmailResponse.sender_email)
        .where(EmailResponse.sender_email.isnot(None))
        .distinct()
    )
    our_accounts = {row[0].lower() for row in acct_result.all() if row[0]}
    # 2) Also fetch accounts from Instantly API for reliable detection
    try:
        acct_data = await instantly_service.list_accounts(limit=100)
        api_accounts = acct_data.get("items") or acct_data.get("data") or acct_data.get("accounts") or []
        for acct in api_accounts:
            email = acct.get("email", "")
            if email:
                our_accounts.add(email.lower())
    except Exception as e:
        logger.warning(f"Could not fetch Instantly accounts for outbound detection: {e}")

    camp_result = await db.execute(
        select(Campaign).where(Campaign.id.in_(data.campaign_ids))
    )
    campaigns = camp_result.scalars().all()
    logger.info(
        f"Fetch replies: {len(campaigns)} campaigns loaded, "
        f"our_accounts={our_accounts}, "
        f"requested_ids={data.campaign_ids}"
    )

    for campaign in campaigns:
        if not campaign.instantly_campaign_id:
            logger.warning(f"Campaign {campaign.id} ({campaign.name}) has no instantly_campaign_id, skipping")
            continue
        logger.info(f"Fetching replies for campaign {campaign.id} ({campaign.name}), instantly_id={campaign.instantly_campaign_id}")

        try:
            # Fetch all emails for this campaign (no email_type filter to get everything)
            f, s = await _paginated_fetch(
                campaign.instantly_campaign_id,
                campaign.id,
                db,
                our_accounts,
            )
            fetched += f
            skipped += s
            logger.info(f"Campaign {campaign.id}: fetched={f}, skipped={s}")

        except InstantlyAPIError as e:
            logger.error(
                f"Failed to fetch emails for campaign {campaign.id}: {e.detail}"
            )
            errors += 1

        # Brief pause between campaigns to avoid rate limits
        await asyncio.sleep(0.5)

    return FetchRepliesResponse(
        fetched=fetched, skipped=skipped, errors=errors
    )


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
    """Send an approved reply via Instantly."""
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

    if not resp.instantly_email_id:
        raise HTTPException(400, "No Instantly email ID - cannot send reply")

    if not resp.sender_email:
        raise HTTPException(400, "No sender email account (eaccount) - cannot send reply")

    try:
        logger.info(f"Sending reply for response {response_id} from {resp.sender_email} to {resp.from_email}")
        reply_data = {
            "reply_to_uuid": resp.instantly_email_id,
            "eaccount": resp.sender_email,
            "subject": f"Re: {resp.subject}" if resp.subject else "Re: ",
            "body": {
                "text": reply_text,
                "html": "<div>{}</div>".format(
                    html.escape(reply_text).replace("\r\n", "<br>").replace("\n", "<br>")
                ),
            },
        }
        result = await instantly_service.reply_to_email(reply_data)
        logger.info(f"Reply sent successfully for response {response_id}: {result}")
        resp.status = ResponseStatus.SENT
        await db.flush()
        return SendReplyResponse(success=True, message="Reply sent successfully")
    except InstantlyAPIError as e:
        logger.error(f"Instantly API error for response {response_id}: {e.detail}")
        raise HTTPException(
            502, f"Failed to send reply via Instantly: {e.detail}"
        )
    except Exception as e:
        logger.error(f"Unexpected error sending response {response_id}: {str(e)}")
        raise HTTPException(500, f"Internal server error while sending reply: {str(e)}")


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


# ==============================================================================
# AI Reply Operations
# ==============================================================================

@router.post("/{response_id}/generate-ai-reply")
async def generate_ai_reply(
    response_id: int,
    ai_agent_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Generate AI-suggested reply using agent's knowledge base."""
    from app.services.ai_replier import AIReplierService

    service = AIReplierService(db)

    try:
        reply_data = await service.generate_reply(
            email_response_id=response_id,
            ai_agent_id=ai_agent_id,
        )
        return reply_data
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"AI reply generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate reply: {str(e)}")


@router.post("/{response_id}/approve-and-send")
async def approve_and_send_reply(
    response_id: int,
    approved_body: str,
    approved_subject: Optional[str] = None,
    sender_email: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Approve AI-generated reply and send via Instantly."""
    from app.services.ai_replier import AIReplierService

    service = AIReplierService(db)

    try:
        result = await service.approve_and_send_reply(
            email_response_id=response_id,
            approved_body=approved_body,
            approved_subject=approved_subject,
            sender_email=sender_email,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Reply send error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send reply: {str(e)}")


@router.post("/{response_id}/approve-only")
async def approve_reply_without_sending(
    response_id: int,
    approved_body: str,
    db: AsyncSession = Depends(get_db),
):
    """Approve AI reply without sending (for manual sending later)."""
    from app.services.ai_replier import AIReplierService

    service = AIReplierService(db)

    try:
        email_response = await service.approve_reply_without_sending(
            email_response_id=response_id,
            approved_body=approved_body,
        )
        return {
            "status": "approved",
            "message": "Reply approved (not sent)",
            "response_id": email_response.id,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{response_id}/ignore-ai")
async def ignore_response_ai(
    response_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Mark email response as ignored via AI agent service (no reply needed)."""
    from app.services.ai_replier import AIReplierService

    service = AIReplierService(db)

    try:
        email_response = await service.ignore_response(response_id)
        return {
            "status": "ignored",
            "message": "Email response marked as ignored",
            "response_id": email_response.id,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
