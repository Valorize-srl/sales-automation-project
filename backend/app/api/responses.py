"""Email responses API routes - fetch, generate AI reply, approve, send, delete."""
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


def _score_to_sentiment(score: float | None) -> Sentiment | None:
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
    campaign_id: int | None = Query(None),
    campaign_ids: str | None = Query(None, description="Comma-separated campaign IDs"),
    status: str | None = Query(None),
    sentiment: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List email responses with optional filters."""
    query = (
        select(EmailResponse)
        .options(
            selectinload(EmailResponse.lead),
            selectinload(EmailResponse.campaign),
        )
        .where(EmailResponse.direction == MessageDirection.INBOUND)
        .order_by(
            sa_func.coalesce(EmailResponse.received_at, EmailResponse.created_at).desc()
        )
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

    result = await db.execute(query)
    responses = result.scalars().all()
    items = [_response_to_out(r) for r in responses]
    return EmailResponseListResponse(responses=items, total=len(items))


# --- Fetch Replies from Instantly ---


@router.post("/fetch", response_model=FetchRepliesResponse)
async def fetch_replies(
    data: FetchRepliesRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch new replies from Instantly for given campaigns.
    Imports emails with sentiment from Instantly's ai_interest_value.
    """
    fetched = 0
    skipped = 0
    errors = 0

    camp_result = await db.execute(
        select(Campaign).where(Campaign.id.in_(data.campaign_ids))
    )
    campaigns = camp_result.scalars().all()

    for campaign in campaigns:
        if not campaign.instantly_campaign_id:
            continue

        try:
            starting_after = None
            while True:
                email_data = await instantly_service.list_emails(
                    campaign_id=campaign.instantly_campaign_id,
                    email_type="received",
                    limit=50,
                    starting_after=starting_after,
                )
                items = email_data.get("items", [])
                if not items:
                    break

                for email_item in items:
                    instantly_id = email_item.get("id")
                    if not instantly_id:
                        continue

                    # Deduplication
                    existing = await db.execute(
                        select(EmailResponse.id).where(
                            EmailResponse.instantly_email_id == instantly_id
                        )
                    )
                    if existing.scalar_one_or_none() is not None:
                        skipped += 1
                        continue

                    # Match lead by sender email
                    from_email = email_item.get("from_address_email", "")
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
                        campaign_id=campaign.id,
                        lead_id=lead_id,
                        instantly_email_id=instantly_id,
                        from_email=from_email,
                        sender_email=email_item.get("eaccount"),
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
                    fetched += 1

                # Cursor pagination
                next_cursor = email_data.get("next_starting_after")
                if not next_cursor or len(items) < 50:
                    break
                starting_after = next_cursor

        except InstantlyAPIError as e:
            logger.error(
                f"Failed to fetch emails for campaign {campaign.id}: {e.detail}"
            )
            errors += 1

    return FetchRepliesResponse(
        fetched=fetched, skipped=skipped, errors=errors
    )


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
                "html": f"<p>{reply_text}</p>",
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
