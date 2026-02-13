"""Campaign management API routes."""
import json
import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.campaign import Campaign, CampaignStatus
from app.models.analytics import Analytics
from app.models.email_response import EmailResponse, MessageDirection, ResponseStatus
from app.models.icp import ICP
from app.models.lead import Lead
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
)
from app.services.instantly import instantly_service, InstantlyAPIError
from app.services.email_generator import email_generator_service

logger = logging.getLogger(__name__)
router = APIRouter()


def _campaign_to_response(campaign: Campaign) -> CampaignResponse:
    resp = CampaignResponse.model_validate(campaign)
    resp.icp_name = campaign.icp.name if campaign.icp else None
    return resp


# --- CRUD ---


@router.get("", response_model=CampaignListResponse)
async def list_campaigns(
    icp_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all campaigns, optionally filtered by ICP."""
    query = (
        select(Campaign)
        .options(selectinload(Campaign.icp))
        .order_by(Campaign.created_at.desc())
    )
    if icp_id is not None:
        query = query.where(Campaign.icp_id == icp_id)
    result = await db.execute(query)
    campaigns = result.scalars().all()
    items = [_campaign_to_response(c) for c in campaigns]
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
            default_schedule = {
                "schedules": [{
                    "name": "Default",
                    "timing": {"from": "09:00", "to": "17:00"},
                    "days": {
                        "1": True, "2": True, "3": True,
                        "4": True, "5": True, "6": False, "0": False,
                    },
                    "timezone": "Etc/UTC",
                }]
            }
            result = await instantly_service.create_campaign(
                data.name, default_schedule
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
    return _campaign_to_response(campaign)


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
    return _campaign_to_response(campaign)


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
    return _campaign_to_response(campaign)


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(campaign_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a campaign."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    await db.delete(campaign)


# --- Instantly Sync ---


def _map_instantly_status(status_value) -> CampaignStatus:
    """Map Instantly status integer to our CampaignStatus enum."""
    mapping = {
        0: CampaignStatus.PAUSED,
        1: CampaignStatus.ACTIVE,
        2: CampaignStatus.COMPLETED,
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
            items = data.get("data", data.get("items", []))
            if not items:
                break
            all_instantly.extend(items)
            if len(items) < 100:
                break
            starting_after = items[-1].get("id")

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
                                "total_emails_sent", campaign.total_sent
                            )
                            campaign.total_opened = analytics.get(
                                "total_opened", campaign.total_opened
                            )
                            campaign.total_replied = analytics.get(
                                "total_replied", campaign.total_replied
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
        campaign.total_sent = analytics.get("total_emails_sent", campaign.total_sent)
        campaign.total_opened = analytics.get("total_opened", campaign.total_opened)
        campaign.total_replied = analytics.get("total_replied", campaign.total_replied)

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

    return _campaign_to_response(campaign)


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
        lead_email = event_data.get("lead_email", event_data.get("email"))
        if lead_email:
            lead_result = await db.execute(
                select(Lead).where(Lead.email == lead_email.lower())
            )
            lead = lead_result.scalar_one_or_none()
            if lead:
                db.add(EmailResponse(
                    campaign_id=campaign.id,
                    lead_id=lead.id,
                    message_body=event_data.get("text", event_data.get("body", "")),
                    direction=MessageDirection.INBOUND,
                    status=ResponseStatus.PENDING,
                ))

    await db.flush()
    return {"status": "ok"}
