"""Campaign management API routes."""
from typing import Optional
import json
import logging
from datetime import date, datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.campaign import Campaign, CampaignStatus
from app.models.analytics import Analytics
from app.models.email_response import EmailResponse, MessageDirection, ResponseStatus
from app.models.icp import ICP
from app.models.lead import Lead
from app.models.ai_agent_campaign import AIAgentCampaign
from app.models.ai_agent import AIAgent
from app.services.instantly import instantly_service, InstantlyAPIError
from app.schemas.campaign import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    CampaignListResponse,
    InstantlySyncResponse,
    LeadUploadRequest,
    LeadUploadResponse,
    EmailTemplateGenerateRequest,
    EmailTemplateGenerateResponse,
    EmailAccountListResponse,
    EmailAccountOut,
    PushSequencesResponse,
)
from app.services.email_generator import email_generator_service

logger = logging.getLogger(__name__)
router = APIRouter()


async def _campaign_to_response(campaign: Campaign, db: AsyncSession) -> CampaignResponse:
    resp = CampaignResponse.model_validate(campaign)
    resp.icp_name = campaign.icp.name if campaign.icp else None

    # Load AI agent info if campaign has one associated
    agent_assoc_result = await db.execute(
        select(AIAgentCampaign, AIAgent)
        .join(AIAgent, AIAgentCampaign.ai_agent_id == AIAgent.id)
        .where(AIAgentCampaign.campaign_id == campaign.id)
        .limit(1)
    )
    agent_assoc = agent_assoc_result.first()
    if agent_assoc:
        _, agent = agent_assoc
        resp.ai_agent_id = agent.id
        resp.ai_agent_name = agent.name

    return resp


# --- CRUD ---


@router.get("", response_model=CampaignListResponse)
async def list_campaigns(
    icp_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None, description="Search campaigns by name"),
    status: Optional[CampaignStatus] = Query(None, description="Filter by campaign status"),
    db: AsyncSession = Depends(get_db),
):
    """List all non-deleted campaigns with optional filters."""
    query = (
        select(Campaign)
        .options(selectinload(Campaign.icp))
        .where(Campaign.deleted_at.is_(None))  # Exclude soft-deleted campaigns
        .order_by(Campaign.created_at.desc())
    )
    if icp_id is not None:
        query = query.where(Campaign.icp_id == icp_id)
    if search:
        query = query.where(Campaign.name.ilike(f"%{search}%"))
    if status is not None:
        query = query.where(Campaign.status == status)
    result = await db.execute(query)
    campaigns = result.scalars().all()
    items = []
    for c in campaigns:
        items.append(await _campaign_to_response(c, db))
    return CampaignListResponse(campaigns=items, total=len(items))


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    data: CampaignCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new campaign locally and optionally on Instantly."""
    if data.icp_id:
        icp_result = await db.execute(select(ICP).where(ICP.id == data.icp_id))
        if not icp_result.scalar_one_or_none():
            raise HTTPException(404, "ICP not found")

    instantly_campaign_id = None
    if data.create_on_instantly:
        try:
            # Build schedule from frontend data
            days = data.schedule_days
            days_dict = {
                "0": days.d0 if days else False,
                "1": days.d1 if days else True,
                "2": days.d2 if days else True,
                "3": days.d3 if days else True,
                "4": days.d4 if days else True,
                "5": days.d5 if days else True,
                "6": days.d6 if days else False,
            }
            campaign_schedule = {
                "schedules": [{
                    "name": "Default",
                    "timing": {
                        "from": data.schedule_from,
                        "to": data.schedule_to,
                    },
                    "days": days_dict,
                    "timezone": data.schedule_timezone,
                }]
            }
            result = await instantly_service.create_campaign(
                data.name,
                campaign_schedule,
                email_list=data.email_accounts if data.email_accounts else None,
                daily_limit=data.daily_limit,
                email_gap=data.email_gap,
                stop_on_reply=data.stop_on_reply,
                stop_on_auto_reply=data.stop_on_auto_reply,
                link_tracking=data.link_tracking,
                open_tracking=data.open_tracking,
                text_only=data.text_only,
            )
            instantly_campaign_id = result.get("id")
        except InstantlyAPIError as e:
            raise HTTPException(
                502, f"Failed to create campaign on Instantly: {e.detail}"
            )

    campaign = Campaign(
        name=data.name,
        icp_id=data.icp_id,
        instantly_campaign_id=instantly_campaign_id,
        status=CampaignStatus.DRAFT,
    )
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign, attribute_names=["icp"])
    return await _campaign_to_response(campaign, db)


# NOTE: /instantly/accounts MUST be registered before /{campaign_id}
@router.get("/instantly/accounts", response_model=EmailAccountListResponse)
async def list_instantly_accounts():
    """List email accounts from Instantly workspace."""
    try:
        all_accounts: list[dict] = []
        starting_after = None
        while True:
            data = await instantly_service.list_accounts(
                limit=100, starting_after=starting_after
            )

            # Try different response structures
            items = (
                data.get("accounts") or
                data.get("data") or
                data.get("items") or
                (data if isinstance(data, list) else [])
            )

            if not items:
                break

            all_accounts.extend(items)

            # Check pagination using the pagination object
            pagination = data.get("pagination", {})
            starting_after = pagination.get("next_starting_after")

            if not starting_after:
                break

        accounts = [
            EmailAccountOut(
                email=a.get("email", ""),
                first_name=a.get("first_name"),
                last_name=a.get("last_name"),
                status=a.get("status"),
            )
            for a in all_accounts
        ]
        return EmailAccountListResponse(accounts=accounts, total=len(accounts))
    except InstantlyAPIError as e:
        raise HTTPException(502, f"Failed to list accounts: {e.detail}")


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single campaign by ID."""
    result = await db.execute(
        select(Campaign)
        .options(selectinload(Campaign.icp))
        .where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    return await _campaign_to_response(campaign, db)


@router.put("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: int,
    data: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a campaign."""
    result = await db.execute(
        select(Campaign)
        .options(selectinload(Campaign.icp))
        .where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "status":
            setattr(campaign, key, CampaignStatus(value))
        else:
            setattr(campaign, key, value)

    await db.flush()
    await db.refresh(campaign, attribute_names=["icp"])
    return await _campaign_to_response(campaign, db)


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(campaign_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a campaign."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    await db.delete(campaign)
    await db.commit()


# --- Instantly Sync ---


def _map_instantly_status(status_value) -> CampaignStatus:
    """Map Instantly status integer to our CampaignStatus enum.

    Instantly statuses: 0=Draft, 1=Active, 2=Paused, 3=Completed, 4=Scheduled, -1=Error, -2=Deleted
    """
    mapping = {
        0: CampaignStatus.DRAFT,
        1: CampaignStatus.ACTIVE,
        2: CampaignStatus.PAUSED,
        3: CampaignStatus.COMPLETED,
        4: CampaignStatus.SCHEDULED,
        -1: CampaignStatus.ERROR,
        -2: CampaignStatus.ERROR,  # Deleted on Instantly = error state locally
    }
    return mapping.get(status_value, CampaignStatus.DRAFT)


@router.post("/sync", response_model=InstantlySyncResponse)
async def sync_campaigns(db: AsyncSession = Depends(get_db)):
    """Import/update campaigns from Instantly. Manual trigger."""
    imported = 0
    updated = 0
    errors = 0

    try:
        all_instantly = []
        starting_after = None
        while True:
            data = await instantly_service.list_campaigns(
                limit=100, starting_after=starting_after
            )

            # Log the response structure for debugging
            logger.info(f"Instantly API response keys: {list(data.keys())}")

            # Try different response structures
            items = (
                data.get("campaigns") or
                data.get("data") or
                data.get("items") or
                (data if isinstance(data, list) else [])
            )

            if not items:
                logger.warning(f"No campaigns found in response. Keys: {list(data.keys())}")
                break

            logger.info(f"Found {len(items)} campaigns in this batch")
            all_instantly.extend(items)

            # Check pagination using the pagination object (as per Instantly docs)
            pagination = data.get("pagination", {})
            starting_after = pagination.get("next_starting_after")

            if not starting_after:
                logger.info("No more pages (pagination.next_starting_after is null)")
                break

        existing_result = await db.execute(
            select(Campaign.instantly_campaign_id).where(
                Campaign.instantly_campaign_id.isnot(None)
            )
        )
        existing_ids = {row[0] for row in existing_result.all()}

        for ic in all_instantly:
            ic_id = ic.get("id")
            ic_name = ic.get("name", "Unnamed Campaign")

            try:
                if ic_id in existing_ids:
                    result = await db.execute(
                        select(Campaign).where(
                            Campaign.instantly_campaign_id == ic_id
                        )
                    )
                    campaign = result.scalar_one_or_none()
                    if campaign:
                        campaign.status = _map_instantly_status(ic.get("status"))
                        try:
                            analytics = await instantly_service.get_campaign_analytics(ic_id)
                            campaign.total_sent = analytics.get(
                                "emails_sent_count", campaign.total_sent
                            )
                            campaign.total_opened = analytics.get(
                                "open_count", campaign.total_opened
                            )
                            campaign.total_replied = analytics.get(
                                "reply_count", campaign.total_replied
                            )
                        except InstantlyAPIError:
                            pass
                        updated += 1
                else:
                    new_campaign = Campaign(
                        name=ic_name,
                        instantly_campaign_id=ic_id,
                        icp_id=None,
                        status=_map_instantly_status(ic.get("status")),
                    )
                    db.add(new_campaign)
                    imported += 1

            except Exception as e:
                logger.warning(f"Error syncing campaign {ic_id}: {e}")
                errors += 1

        await db.flush()

    except InstantlyAPIError as e:
        raise HTTPException(502, f"Failed to sync with Instantly: {e.detail}")

    return InstantlySyncResponse(imported=imported, updated=updated, errors=errors)


@router.post("/{campaign_id}/sync-metrics", response_model=CampaignResponse)
async def sync_campaign_metrics(
    campaign_id: int, db: AsyncSession = Depends(get_db)
):
    """Pull latest metrics from Instantly for a single campaign."""
    result = await db.execute(
        select(Campaign)
        .options(selectinload(Campaign.icp))
        .where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if not campaign.instantly_campaign_id:
        raise HTTPException(400, "Campaign is not linked to Instantly")

    try:
        analytics = await instantly_service.get_campaign_analytics(
            campaign.instantly_campaign_id
        )
        campaign.total_sent = analytics.get("emails_sent_count", campaign.total_sent)
        campaign.total_opened = analytics.get("open_count", campaign.total_opened)
        campaign.total_replied = analytics.get("reply_count", campaign.total_replied)

        today = date.today()
        existing = await db.execute(
            select(Analytics).where(
                Analytics.campaign_id == campaign.id,
                Analytics.date == today,
            )
        )
        entry = existing.scalar_one_or_none()
        if entry:
            entry.emails_sent = campaign.total_sent
            entry.opens = campaign.total_opened
            entry.replies = campaign.total_replied
        else:
            db.add(Analytics(
                campaign_id=campaign.id,
                date=today,
                emails_sent=campaign.total_sent,
                opens=campaign.total_opened,
                replies=campaign.total_replied,
            ))

        await db.flush()
        await db.refresh(campaign, attribute_names=["icp"])

    except InstantlyAPIError as e:
        raise HTTPException(
            502, f"Failed to get analytics from Instantly: {e.detail}"
        )

    return await _campaign_to_response(campaign, db)


@router.post("/sync-all-metrics")
async def sync_all_campaign_metrics(db: AsyncSession = Depends(get_db)):
    """Bulk sync metrics from Instantly for all active/linked campaigns. Used by auto-polling."""
    result = await db.execute(
        select(Campaign)
        .options(selectinload(Campaign.icp))
        .where(
            Campaign.instantly_campaign_id.isnot(None),
            Campaign.deleted_at.is_(None),
            Campaign.status.in_([CampaignStatus.ACTIVE, CampaignStatus.PAUSED, CampaignStatus.SCHEDULED]),
        )
    )
    campaigns = result.scalars().all()

    synced = 0
    errors = 0
    for campaign in campaigns:
        try:
            analytics = await instantly_service.get_campaign_analytics(
                campaign.instantly_campaign_id
            )
            campaign.total_sent = analytics.get("emails_sent_count", campaign.total_sent)
            campaign.total_opened = analytics.get("open_count", campaign.total_opened)
            campaign.total_replied = analytics.get("reply_count", campaign.total_replied)

            # Also update Instantly status
            try:
                instantly_data = await instantly_service.get_campaign(campaign.instantly_campaign_id)
                new_status = _map_instantly_status(instantly_data.get("status"))
                campaign.status = new_status
            except InstantlyAPIError:
                pass  # Keep existing status if we can't fetch it

            synced += 1
        except InstantlyAPIError as e:
            logger.warning(f"Failed to sync metrics for campaign {campaign.id}: {e.detail}")
            errors += 1
        except Exception as e:
            logger.warning(f"Unexpected error syncing campaign {campaign.id}: {e}")
            errors += 1

    await db.flush()

    return {
        "synced": synced,
        "errors": errors,
        "total_campaigns": len(campaigns),
        "message": f"Synced metrics for {synced}/{len(campaigns)} campaigns",
    }


@router.post("/{campaign_id}/activate", response_model=CampaignResponse)
async def activate_campaign(
    campaign_id: int, db: AsyncSession = Depends(get_db)
):
    """Activate campaign on Instantly."""
    result = await db.execute(
        select(Campaign)
        .options(selectinload(Campaign.icp))
        .where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if not campaign.instantly_campaign_id:
        raise HTTPException(400, "Campaign is not linked to Instantly")

    try:
        await instantly_service.activate_campaign(campaign.instantly_campaign_id)
        campaign.status = CampaignStatus.ACTIVE
        await db.flush()
        await db.refresh(campaign, attribute_names=["icp"])
    except InstantlyAPIError as e:
        raise HTTPException(
            502, f"Failed to activate campaign on Instantly: {e.detail}"
        )

    return await _campaign_to_response(campaign, db)


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    campaign_id: int, db: AsyncSession = Depends(get_db)
):
    """Pause campaign on Instantly."""
    result = await db.execute(
        select(Campaign)
        .options(selectinload(Campaign.icp))
        .where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if not campaign.instantly_campaign_id:
        raise HTTPException(400, "Campaign is not linked to Instantly")

    try:
        await instantly_service.pause_campaign(campaign.instantly_campaign_id)
        campaign.status = CampaignStatus.PAUSED
        await db.flush()
        await db.refresh(campaign, attribute_names=["icp"])
    except InstantlyAPIError as e:
        raise HTTPException(
            502, f"Failed to pause campaign on Instantly: {e.detail}"
        )

    return await _campaign_to_response(campaign, db)


# --- Lead Upload ---


@router.post("/{campaign_id}/upload-leads", response_model=LeadUploadResponse)
async def upload_leads_to_campaign(
    campaign_id: int,
    data: LeadUploadRequest,
    db: AsyncSession = Depends(get_db),
):
    """Push selected leads from our DB to an Instantly campaign."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if not campaign.instantly_campaign_id:
        raise HTTPException(400, "Campaign is not linked to Instantly")

    lead_result = await db.execute(
        select(Lead).where(Lead.id.in_(data.lead_ids))
    )
    leads = lead_result.scalars().all()
    if not leads:
        raise HTTPException(400, "No valid leads found")

    instantly_leads = []
    for lead in leads:
        instantly_leads.append({
            "email": lead.email,
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "company_name": lead.company or "",
            "personalization": lead.job_title or "",
        })

    pushed = 0
    errors_count = 0
    batch_size = 1000
    for i in range(0, len(instantly_leads), batch_size):
        batch = instantly_leads[i:i + batch_size]
        try:
            await instantly_service.add_leads_to_campaign(
                campaign.instantly_campaign_id, batch
            )
            pushed += len(batch)
        except InstantlyAPIError as e:
            logger.error(f"Failed to push lead batch: {e.detail}")
            errors_count += len(batch)

    return LeadUploadResponse(pushed=pushed, errors=errors_count)


# --- Push Sequences to Instantly ---


@router.post(
    "/{campaign_id}/push-sequences",
    response_model=PushSequencesResponse,
)
async def push_sequences_to_instantly(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Push email templates from DB to Instantly as campaign sequences."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if not campaign.instantly_campaign_id:
        raise HTTPException(400, "Campaign is not linked to Instantly")
    if not campaign.email_templates:
        raise HTTPException(400, "No email templates to push")

    try:
        steps_data = json.loads(campaign.email_templates)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(400, "Invalid email templates data")

    # Map internal format to Instantly sequences format
    instantly_steps = []
    for step in steps_data:
        instantly_steps.append({
            "type": "email",
            "delay": step.get("wait_days", 0),
            "delay_unit": "day",
            "variants": [{
                "subject": step.get("subject", ""),
                "body": step.get("body", ""),
            }],
        })

    try:
        await instantly_service.update_campaign(
            campaign.instantly_campaign_id,
            {"sequences": [{"steps": instantly_steps}]},
        )
    except InstantlyAPIError as e:
        raise HTTPException(
            502, f"Failed to push sequences to Instantly: {e.detail}"
        )

    return PushSequencesResponse(
        success=True,
        steps_pushed=len(instantly_steps),
        message=f"Pushed {len(instantly_steps)} steps to Instantly",
    )


# --- Email Template Generation ---


@router.post(
    "/{campaign_id}/generate-templates",
    response_model=EmailTemplateGenerateResponse,
)
async def generate_email_templates(
    campaign_id: int,
    data: EmailTemplateGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Use Claude to generate email templates based on ICP data."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    icp_id = data.icp_id or campaign.icp_id
    icp_data = {}
    if icp_id:
        icp_result = await db.execute(select(ICP).where(ICP.id == icp_id))
        icp = icp_result.scalar_one_or_none()
        if icp:
            icp_data = {
                "industry": icp.industry,
                "company_size": icp.company_size,
                "job_titles": icp.job_titles,
                "geography": icp.geography,
                "revenue_range": icp.revenue_range,
                "keywords": icp.keywords,
                "description": icp.description,
            }

    if not icp_data:
        raise HTTPException(
            400, "No ICP found. Please specify an ICP for template generation."
        )

    templates = await email_generator_service.generate_templates(
        icp_data=icp_data,
        num_subject_lines=data.num_subject_lines,
        num_steps=data.num_steps,
        additional_context=data.additional_context,
    )

    campaign.subject_lines = json.dumps(templates.get("subject_lines", []))
    campaign.email_templates = json.dumps(templates.get("email_steps", []))
    await db.flush()

    return EmailTemplateGenerateResponse(
        subject_lines=templates.get("subject_lines", []),
        email_steps=templates.get("email_steps", []),
    )


# --- Webhooks ---


@router.post("/webhooks/instantly")
async def instantly_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive webhook events from Instantly."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON payload")

    event_type = payload.get("event_type", "")
    event_data = payload.get("data", payload)
    logger.info(f"Instantly webhook: {event_type}")

    campaign_id_str = event_data.get("campaign_id")
    if not campaign_id_str:
        return {"status": "ignored", "reason": "no campaign_id"}

    result = await db.execute(
        select(Campaign).where(Campaign.instantly_campaign_id == campaign_id_str)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        return {"status": "ignored", "reason": "unknown campaign"}

    if event_type == "email_sent":
        campaign.total_sent = (campaign.total_sent or 0) + 1

    elif event_type == "email_opened":
        campaign.total_opened = (campaign.total_opened or 0) + 1

    elif event_type == "reply_received":
        campaign.total_replied = (campaign.total_replied or 0) + 1
        # NOTE: Webhook handler for reply_received is disabled because Instantly webhooks
        # don't provide critical fields (instantly_email_id, sender_email, thread_id) needed
        # to reply to emails. Use POST /responses/fetch instead which has complete data.
        # Keeping total_replied counter update for metrics.
        #
        # lead_email = event_data.get("lead_email", event_data.get("email"))
        # if lead_email:
        #     lead_result = await db.execute(
        #         select(Lead).where(Lead.email == lead_email.lower())
        #     )
        #     lead = lead_result.scalar_one_or_none()
        #     if lead:
        #         db.add(EmailResponse(
        #             campaign_id=campaign.id,
        #             lead_id=lead.id,
        #             message_body=event_data.get("text", event_data.get("body", "")),
        #             direction=MessageDirection.INBOUND,
        #             status=ResponseStatus.PENDING,
        #         ))

    await db.flush()
    return {"status": "ok"}


# --- Sync Leads FROM Instantly ---


@router.post("/{campaign_id}/sync-leads")
async def sync_leads_from_instantly(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Pull leads FROM Instantly campaign back to local DB."""
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if not campaign.instantly_campaign_id:
        raise HTTPException(400, "Campaign is not linked to Instantly")

    imported = 0
    skipped = 0
    errors = 0

    try:
        starting_after = None
        while True:
            data = await instantly_service.list_leads(
                campaign_id=campaign.instantly_campaign_id,
                limit=100,
                starting_after=starting_after,
            )
            items = data.get("items", [])
            if not items:
                break

            for lead_data in items:
                email = (lead_data.get("email", "") or "").lower().strip()
                if not email:
                    continue

                # Check if lead already exists
                existing = await db.execute(
                    select(Lead).where(Lead.email == email)
                )
                if existing.scalar_one_or_none() is not None:
                    skipped += 1
                    continue

                try:
                    new_lead = Lead(
                        email=email,
                        first_name=lead_data.get("first_name", ""),
                        last_name=lead_data.get("last_name", ""),
                        company=lead_data.get("company_name", ""),
                        source="instantly",
                        icp_id=campaign.icp_id,
                    )
                    db.add(new_lead)
                    await db.flush()
                    imported += 1
                except Exception as e:
                    logger.warning(f"Error importing lead {email}: {e}")
                    errors += 1

            # Cursor pagination
            pagination = data.get("pagination", {})
            starting_after = pagination.get("next_starting_after")
            if not starting_after:
                break

    except InstantlyAPIError as e:
        raise HTTPException(502, f"Failed to fetch leads from Instantly: {e.detail}")

    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "message": f"Imported {imported} leads, {skipped} already existed, {errors} errors",
    }


# --- Daily Analytics from Instantly ---


@router.get("/{campaign_id}/daily-analytics")
async def get_campaign_daily_analytics(
    campaign_id: int,
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    """Get day-by-day analytics from Instantly for a campaign."""
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if not campaign.instantly_campaign_id:
        raise HTTPException(400, "Campaign is not linked to Instantly")

    try:
        analytics = await instantly_service.get_daily_campaign_analytics(
            campaign_id=campaign.instantly_campaign_id,
            start_date=start_date,
            end_date=end_date,
        )
        return analytics
    except InstantlyAPIError as e:
        raise HTTPException(502, f"Failed to get daily analytics: {e.detail}")


# --- Instantly Account & Warmup Management ---


@router.get("/instantly/accounts/{email}")
async def get_instantly_account(email: str):
    """Get details for a specific Instantly email account including warmup status."""
    try:
        return await instantly_service.get_account(email)
    except InstantlyAPIError as e:
        raise HTTPException(502, f"Failed to get account: {e.detail}")


@router.patch("/instantly/accounts/{email}")
async def update_instantly_account(email: str, request: Request):
    """Update Instantly account settings (warmup config, daily limit, etc.)."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON payload")

    try:
        return await instantly_service.update_account(email, payload)
    except InstantlyAPIError as e:
        raise HTTPException(502, f"Failed to update account: {e.detail}")


@router.post("/instantly/accounts/{email}/{action}")
async def manage_instantly_account(email: str, action: str):
    """Manage Instantly account state: pause, resume, enable_warmup, disable_warmup, test_vitals."""
    valid_actions = {"pause", "resume", "enable_warmup", "disable_warmup", "test_vitals"}
    if action not in valid_actions:
        raise HTTPException(400, f"Invalid action. Must be one of: {', '.join(valid_actions)}")

    try:
        return await instantly_service.manage_account_state(email, action)
    except InstantlyAPIError as e:
        raise HTTPException(502, f"Failed to {action} account: {e.detail}")


@router.get("/instantly/accounts/{email}/warmup-analytics")
async def get_account_warmup_analytics(
    email: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """Get warmup analytics for a specific email account."""
    try:
        return await instantly_service.get_warmup_analytics(
            emails=[email],
            start_date=start_date,
            end_date=end_date,
        )
    except InstantlyAPIError as e:
        raise HTTPException(502, f"Failed to get warmup analytics: {e.detail}")


@router.post("/bulk-delete")
async def bulk_delete_campaigns(
    campaign_ids: list[int] = Body(..., embed=True),
    db: AsyncSession = Depends(get_db)
):
    """
    Soft delete multiple campaigns (mark as deleted_at).

    Also deletes campaigns from Instantly if they have instantly_campaign_id.
    If any Instantly deletion fails, the entire transaction is rolled back.
    """
    if not campaign_ids:
        raise HTTPException(400, "No campaign IDs provided")

    logger.info(f"Attempting to delete {len(campaign_ids)} campaigns: {campaign_ids}")

    # Fetch all campaigns to delete
    result = await db.execute(
        select(Campaign).where(Campaign.id.in_(campaign_ids))
    )
    campaigns = result.scalars().all()

    if not campaigns:
        raise HTTPException(404, "No campaigns found with provided IDs")

    deleted_count = 0
    instantly_deleted = 0
    errors = []

    # Try to delete from Instantly first (before committing to DB)
    for campaign in campaigns:
        try:
            if campaign.instantly_campaign_id:
                logger.info(f"Deleting campaign {campaign.id} from Instantly: {campaign.instantly_campaign_id}")
                await instantly_service.delete_campaign(campaign.instantly_campaign_id)
                instantly_deleted += 1
                logger.info(f"Successfully deleted campaign {campaign.id} from Instantly")
        except InstantlyAPIError as e:
            error_msg = f"Failed to delete campaign {campaign.id} ('{campaign.name}') from Instantly: {e.detail}"
            logger.error(error_msg)
            errors.append(error_msg)
            # Rollback the transaction - don't delete anything if Instantly fails
            await db.rollback()
            raise HTTPException(
                502,
                f"Failed to delete from Instantly: {e.detail}. No campaigns were deleted."
            )
        except Exception as e:
            error_msg = f"Unexpected error deleting campaign {campaign.id} from Instantly: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            await db.rollback()
            raise HTTPException(
                500,
                f"Unexpected error: {str(e)}. No campaigns were deleted."
            )

    # If all Instantly deletions succeeded (or no instantly_campaign_id), mark as deleted in DB
    now = datetime.utcnow()
    for campaign in campaigns:
        campaign.deleted_at = now
        deleted_count += 1

    await db.commit()

    logger.info(f"Successfully soft-deleted {deleted_count} campaigns, {instantly_deleted} from Instantly")

    return {
        "deleted": deleted_count,
        "instantly_deleted": instantly_deleted,
        "errors": errors,
        "message": f"Successfully deleted {deleted_count} campaigns"
    }
