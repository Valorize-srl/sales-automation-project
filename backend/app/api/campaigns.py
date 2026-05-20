"""Campaign management API routes.

All call sites in this module use the Smartlead client now. The legacy
`instantly_campaign_id` column is reused to store Smartlead campaign ids
(integers cast to str) — see migration 033 and the Phase 1 README. Other
column names with `instantly_` in them are likewise kept to avoid rippling
into the leads section.
"""
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
from app.models.lead import Lead
from app.models.lead_list import LeadList
from app.models.person import Person
from app.models.company import Company
from app.models.campaign_lead_list import CampaignLeadList
from app.services.smartlead import smartlead_service, SmartleadAPIError, ADD_LEADS_BATCH_SIZE
from app.schemas.campaign import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    CampaignListResponse,
    InstantlySyncResponse,
    LeadUploadRequest,
    LeadUploadResponse,
    EmailAccountListResponse,
    EmailAccountOut,
    PushSequencesResponse,
)


# Smartlead campaign status strings → our internal CampaignStatus enum.
# Used by the sync endpoints to keep DB campaign.status in sync with whatever
# the user does in the Smartlead UI.
_SMARTLEAD_STATUS_MAP: dict[str, CampaignStatus] = {
    "DRAFTED": CampaignStatus.DRAFT,
    "ACTIVE": CampaignStatus.ACTIVE,
    "PAUSED": CampaignStatus.PAUSED,
    "STOPPED": CampaignStatus.PAUSED,
    "COMPLETED": CampaignStatus.COMPLETED,
    "ARCHIVED": CampaignStatus.COMPLETED,
}


def _map_smartlead_status(status_value) -> CampaignStatus:
    if isinstance(status_value, str):
        return _SMARTLEAD_STATUS_MAP.get(status_value.upper(), CampaignStatus.DRAFT)
    return CampaignStatus.DRAFT


def _smartlead_analytics_to_metrics(analytics: dict) -> tuple[int, int, int]:
    """Pull (sent, opened, replied) from a Smartlead /analytics response.

    Smartlead's field naming varies between endpoints (`total_sent_count`
    vs `emails_sent_count` vs nested objects). Be defensive.
    """
    def _grab(*keys):
        for k in keys:
            v = analytics.get(k)
            if v is not None:
                try:
                    return int(v)
                except (TypeError, ValueError):
                    pass
        return 0
    sent = _grab("sent_count", "total_sent_count", "emails_sent_count", "sent")
    opened = _grab("open_count", "unique_open_count", "opens", "opened")
    replied = _grab("reply_count", "unique_reply_count", "replies", "replied")
    return sent, opened, replied


async def _resolve_email_account_id(email: str) -> Optional[int]:
    """Find a Smartlead email_account_id given the email address. Smartlead
    addresses email accounts by integer id; the legacy `/instantly/accounts/{email}`
    endpoints take email as the path param so we walk the account list once."""
    offset = 0
    while True:
        page = await smartlead_service.list_email_accounts(offset=offset, limit=100)
        items = page if isinstance(page, list) else (
            page.get("data") or page.get("accounts") or page.get("items") or []
        )
        if not items:
            return None
        for acct in items:
            acct_email = (acct.get("from_email") or acct.get("email") or "").lower()
            if acct_email == email.lower():
                aid = acct.get("id")
                try:
                    return int(aid) if aid is not None else None
                except (TypeError, ValueError):
                    return None
        if len(items) < 100:
            return None
        offset += 100

logger = logging.getLogger(__name__)
router = APIRouter()


async def _campaign_to_response(campaign: Campaign, db: AsyncSession) -> CampaignResponse:
    return CampaignResponse.model_validate(campaign)


# --- CRUD ---


@router.get("", response_model=CampaignListResponse)
async def list_campaigns(
    search: Optional[str] = Query(None, description="Search campaigns by name"),
    status: Optional[CampaignStatus] = Query(None, description="Filter by campaign status"),
    include_deleted: bool = Query(False, description="Include soft-deleted campaigns"),
    db: AsyncSession = Depends(get_db),
):
    """List campaigns with optional filters."""
    query = (
        select(Campaign)
        .order_by(Campaign.created_at.desc())
    )
    if not include_deleted:
        query = query.where(Campaign.deleted_at.is_(None))
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
    """Create a new campaign locally and (optionally) on Smartlead.

    Smartlead requires the campaign to be created first (DRAFTED) and then
    schedule + settings + sequences updated in separate calls.
    """
    smartlead_campaign_id: Optional[str] = None
    if data.create_on_instantly:  # legacy field name — still means "create externally"
        try:
            created = await smartlead_service.create_campaign(data.name)
            sid = created.get("id") or created.get("campaign_id") or (created.get("data") or {}).get("id")
            if sid is None:
                raise HTTPException(502, f"Smartlead create_campaign returned no id: {created}")
            smartlead_campaign_id = str(sid)

            # Schedule: translate ScheduleDays → list[int] (0=Sun..6=Sat)
            days = data.schedule_days
            days_list = [
                i for i, present in enumerate([
                    days.d0 if days else False,
                    days.d1 if days else True,
                    days.d2 if days else True,
                    days.d3 if days else True,
                    days.d4 if days else True,
                    days.d5 if days else True,
                    days.d6 if days else False,
                ]) if present
            ]
            try:
                await smartlead_service.update_campaign_schedule(
                    smartlead_campaign_id,
                    timezone=data.schedule_timezone,
                    days_of_the_week=days_list,
                    start_hour=data.schedule_from,
                    end_hour=data.schedule_to,
                    min_time_btw_emails=data.email_gap,
                    max_leads_per_day=data.daily_limit,
                )
            except SmartleadAPIError as e:
                logger.warning("Smartlead schedule update failed: %s", e.detail)

            # Settings: track_settings + stop conditions
            track_settings: list[str] = []
            if not data.link_tracking:
                track_settings.append("DONT_LINK_CLICK")
            if not data.open_tracking:
                track_settings.append("DONT_EMAIL_OPEN")
            stop_lead = "REPLY_TO_AN_EMAIL" if data.stop_on_reply else "NEVER"
            try:
                await smartlead_service.update_campaign_settings(
                    smartlead_campaign_id,
                    track_settings=track_settings,
                    stop_lead_settings=stop_lead,
                    send_as_plain_text=data.text_only,
                )
            except SmartleadAPIError as e:
                logger.warning("Smartlead settings update failed: %s", e.detail)

            # Email accounts: resolve emails → Smartlead account ids, then attach
            if data.email_accounts:
                account_ids: list[int] = []
                for em in data.email_accounts:
                    aid = await _resolve_email_account_id(em)
                    if aid:
                        account_ids.append(aid)
                if account_ids:
                    try:
                        await smartlead_service.add_email_accounts_to_campaign(
                            smartlead_campaign_id, account_ids,
                        )
                    except SmartleadAPIError as e:
                        logger.warning("Smartlead account attach failed: %s", e.detail)
        except SmartleadAPIError as e:
            raise HTTPException(
                502, f"Failed to create campaign on Smartlead: {e.detail}"
            )

    # Save email steps locally as JSON + push to Smartlead as sequences
    email_templates_json = None
    if data.email_steps:
        steps_data = [s.model_dump() for s in data.email_steps]
        email_templates_json = json.dumps(steps_data)

        if smartlead_campaign_id:
            sl_sequences = []
            for idx, step in enumerate(steps_data, start=1):
                sl_sequences.append({
                    "seq_number": idx,
                    "seq_delay_details": {"delay_in_days": int(step.get("wait_days", 0) or 0)},
                    "variant_distribution_type": "MANUALLY_EQUAL",
                    "variants": [{
                        "subject": step.get("subject", "") or "",
                        "email_body": step.get("body", "") or "",
                        "variant_label": "A",
                    }],
                })
            try:
                await smartlead_service.save_campaign_sequences(
                    smartlead_campaign_id, sl_sequences,
                )
            except SmartleadAPIError as e:
                logger.warning("Failed to push sequences during creation: %s", e.detail)

    campaign = Campaign(
        name=data.name,
        instantly_campaign_id=smartlead_campaign_id,  # legacy column name
        email_templates=email_templates_json,
        status=CampaignStatus.DRAFT,
    )
    db.add(campaign)
    await db.flush()
    return await _campaign_to_response(campaign, db)


# NOTE: /instantly/accounts MUST be registered before /{campaign_id}.
# URL kept as `/instantly/accounts` for frontend compat — internally hits Smartlead.
@router.get("/instantly/accounts", response_model=EmailAccountListResponse)
async def list_instantly_accounts():
    """List sender email accounts from Smartlead."""
    try:
        all_accounts: list[dict] = []
        offset = 0
        while True:
            data = await smartlead_service.list_email_accounts(offset=offset, limit=100)
            items = data if isinstance(data, list) else (
                data.get("data") or data.get("accounts") or data.get("items") or []
            )
            if not items:
                break
            all_accounts.extend(items)
            if len(items) < 100:
                break
            offset += 100

        def _map_status(s: Optional[str]) -> Optional[int]:
            # The legacy schema (EmailAccountOut.status: Optional[int]) expected
            # an integer enum from Instantly. Smartlead reports textual statuses;
            # we coerce to a stable int so the frontend doesn't break.
            if not s:
                return None
            mapping = {"ACTIVE": 1, "PAUSED": 2, "DISABLED": 0, "WARMING_UP": 3}
            return mapping.get(str(s).upper(), None)

        accounts = [
            EmailAccountOut(
                email=(a.get("from_email") or a.get("email") or ""),
                first_name=a.get("from_name", "").split(" ", 1)[0] if a.get("from_name") else None,
                last_name=" ".join(a.get("from_name", "").split(" ")[1:]) or None if a.get("from_name") else None,
                status=_map_status(a.get("status")),
            )
            for a in all_accounts
        ]
        return EmailAccountListResponse(accounts=accounts, total=len(accounts))
    except SmartleadAPIError as e:
        raise HTTPException(502, f"Failed to list email accounts from Smartlead: {e.detail}")


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single campaign by ID."""
    result = await db.execute(
        select(Campaign)
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


# --- Smartlead Sync ---


@router.post("/sync", response_model=InstantlySyncResponse)
async def sync_campaigns(db: AsyncSession = Depends(get_db)):
    """Import/update campaigns from Smartlead. Manual trigger."""
    imported = 0
    updated = 0
    errors = 0

    try:
        # /campaigns/ ritorna direttamente l'array completo (no cursor pagination).
        all_smartlead = await smartlead_service.list_campaigns()
        logger.info("Smartlead returned %d campaigns", len(all_smartlead))

        existing_result = await db.execute(
            select(Campaign.instantly_campaign_id).where(
                Campaign.instantly_campaign_id.isnot(None)
            )
        )
        existing_ids = {row[0] for row in existing_result.all() if row[0]}

        for sc in all_smartlead:
            sc_id = sc.get("id")
            if sc_id is None:
                continue
            sc_id_str = str(sc_id)
            sc_name = sc.get("name") or "Unnamed Campaign"

            try:
                if sc_id_str in existing_ids:
                    result = await db.execute(
                        select(Campaign).where(
                            Campaign.instantly_campaign_id == sc_id_str
                        )
                    )
                    campaign = result.scalar_one_or_none()
                    if campaign:
                        campaign.status = _map_smartlead_status(sc.get("status"))
                        try:
                            analytics = await smartlead_service.get_campaign_top_analytics(sc_id_str)
                            sent, opened, replied = _smartlead_analytics_to_metrics(analytics)
                            campaign.total_sent = sent or campaign.total_sent
                            campaign.total_opened = opened or campaign.total_opened
                            campaign.total_replied = replied or campaign.total_replied
                        except SmartleadAPIError:
                            pass
                        updated += 1
                else:
                    new_campaign = Campaign(
                        name=sc_name,
                        instantly_campaign_id=sc_id_str,
                        status=_map_smartlead_status(sc.get("status")),
                    )
                    db.add(new_campaign)
                    imported += 1

            except Exception as e:
                logger.warning(f"Error syncing Smartlead campaign {sc_id}: {e}")
                errors += 1

        await db.flush()

    except SmartleadAPIError as e:
        raise HTTPException(502, f"Failed to sync with Smartlead: {e.detail}")

    return InstantlySyncResponse(imported=imported, updated=updated, errors=errors)


@router.post("/{campaign_id}/sync-metrics", response_model=CampaignResponse)
async def sync_campaign_metrics(
    campaign_id: int, db: AsyncSession = Depends(get_db)
):
    """Pull latest metrics from Smartlead for a single campaign."""
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if not campaign.instantly_campaign_id:
        raise HTTPException(400, "Campaign is not linked to Smartlead")

    try:
        analytics = await smartlead_service.get_campaign_top_analytics(
            campaign.instantly_campaign_id
        )
        sent, opened, replied = _smartlead_analytics_to_metrics(analytics)
        campaign.total_sent = sent or campaign.total_sent
        campaign.total_opened = opened or campaign.total_opened
        campaign.total_replied = replied or campaign.total_replied

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

    except SmartleadAPIError as e:
        raise HTTPException(
            502, f"Failed to get analytics from Smartlead: {e.detail}"
        )

    return await _campaign_to_response(campaign, db)


@router.post("/sync-all-metrics")
async def sync_all_campaign_metrics(db: AsyncSession = Depends(get_db)):
    """Bulk sync metrics from Smartlead for all linked campaigns. Used by auto-polling."""
    result = await db.execute(
        select(Campaign).where(
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
            analytics = await smartlead_service.get_campaign_top_analytics(
                campaign.instantly_campaign_id
            )
            sent, opened, replied = _smartlead_analytics_to_metrics(analytics)
            campaign.total_sent = sent or campaign.total_sent
            campaign.total_opened = opened or campaign.total_opened
            campaign.total_replied = replied or campaign.total_replied

            # Also refresh status from Smartlead
            try:
                sl_data = await smartlead_service.get_campaign(campaign.instantly_campaign_id)
                if isinstance(sl_data, dict):
                    campaign.status = _map_smartlead_status(sl_data.get("status"))
            except SmartleadAPIError:
                pass  # keep existing if Smartlead errors

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

            synced += 1
        except SmartleadAPIError as e:
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
    """Activate campaign on Smartlead."""
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if not campaign.instantly_campaign_id:
        raise HTTPException(400, "Campaign is not linked to Smartlead")

    try:
        await smartlead_service.activate_campaign(campaign.instantly_campaign_id)
        campaign.status = CampaignStatus.ACTIVE
        await db.flush()
    except SmartleadAPIError as e:
        raise HTTPException(
            502, f"Failed to activate campaign on Smartlead: {e.detail}"
        )

    return await _campaign_to_response(campaign, db)


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    campaign_id: int, db: AsyncSession = Depends(get_db)
):
    """Pause campaign on Smartlead."""
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if not campaign.instantly_campaign_id:
        raise HTTPException(400, "Campaign is not linked to Smartlead")

    try:
        await smartlead_service.pause_campaign(campaign.instantly_campaign_id)
        campaign.status = CampaignStatus.PAUSED
        await db.flush()
    except SmartleadAPIError as e:
        raise HTTPException(
            502, f"Failed to pause campaign on Smartlead: {e.detail}"
        )

    return await _campaign_to_response(campaign, db)


# --- Lead Lists ---


@router.post("/{campaign_id}/add-list")
async def add_list_to_campaign(
    campaign_id: int,
    lead_list_id: int = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
):
    """Associate a lead list with a campaign and push its people to Smartlead."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if not campaign.instantly_campaign_id:
        raise HTTPException(400, "Campaign is not linked to Smartlead")

    # Verify lead list exists
    list_result = await db.execute(select(LeadList).where(LeadList.id == lead_list_id))
    lead_list = list_result.scalar_one_or_none()
    if not lead_list:
        raise HTTPException(404, "Lead list not found")

    # Check if already associated (allow re-push, update record)
    existing_result = await db.execute(
        select(CampaignLeadList).where(
            CampaignLeadList.campaign_id == campaign_id,
            CampaignLeadList.lead_list_id == lead_list_id,
        )
    )
    existing_assoc = existing_result.scalar_one_or_none()

    # Get all people in this list
    people_result = await db.execute(
        select(Person).where(Person.list_id == lead_list_id)
    )
    people = people_result.scalars().all()

    # Get all companies in this list (companies with email can also be pushed)
    companies_result = await db.execute(
        select(Company).where(Company.list_id == lead_list_id)
    )
    companies = companies_result.scalars().all()

    # Build leads for Instantly from both people and companies
    import re
    email_regex = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

    instantly_leads = []
    skipped_invalid = 0
    seen_global = set()

    for person in people:
        if not person.email:
            continue
        email = person.email.strip().lower()
        if not email_regex.match(email) or email in seen_global:
            skipped_invalid += 1
            continue
        seen_global.add(email)
        instantly_leads.append({
            "email": email,
            "first_name": person.first_name or "",
            "last_name": person.last_name or "",
            "company_name": person.company_name or "",
        })

    for company in companies:
        # Collect all available emails: primary email + generic_emails
        company_emails = []
        if company.email:
            company_emails.append(company.email)
        if company.generic_emails:
            try:
                parsed = json.loads(company.generic_emails) if isinstance(company.generic_emails, str) else []
                if isinstance(parsed, list):
                    company_emails.extend(parsed)
            except (json.JSONDecodeError, TypeError):
                pass
        for raw_email in company_emails:
            if not raw_email or not isinstance(raw_email, str):
                continue
            email = raw_email.strip().lower()
            if not email_regex.match(email) or email in seen_global:
                skipped_invalid += 1
                continue
            seen_global.add(email)
            instantly_leads.append({
                "email": email,
                "first_name": "",
                "last_name": "",
                "company_name": company.name or "",
            })

    logger.info(f"Prepared {len(instantly_leads)} valid leads for Smartlead (skipped {skipped_invalid} invalid/duplicate)")

    # Push to Smartlead (the client handles 400-per-request batching internally)
    pushed = 0
    errors_count = 0
    error_details = []
    api_responses: list[dict] = []
    logger.info(f"Pushing to Smartlead campaign_id: {campaign.instantly_campaign_id}")
    if instantly_leads:
        # Translate our internal lead shape to Smartlead's lead_list entries.
        # Smartlead accepts {email, first_name, last_name, company_name, ...}.
        for i in range(0, len(instantly_leads), ADD_LEADS_BATCH_SIZE):
            batch = instantly_leads[i:i + ADD_LEADS_BATCH_SIZE]
            try:
                resp = await smartlead_service.add_leads_to_campaign(
                    campaign.instantly_campaign_id, batch,
                )
                logger.info(f"Batch {i//ADD_LEADS_BATCH_SIZE + 1} response: {resp}")
                if len(api_responses) < 2:
                    api_responses.append(resp)
                pushed += int(resp.get("uploaded_count") or len(batch))
            except SmartleadAPIError as e:
                logger.error(
                    f"Failed to push lead batch {i//ADD_LEADS_BATCH_SIZE + 1} to Smartlead "
                    f"(status={e.status_code}): {e.detail}"
                )
                errors_count += len(batch)
                if len(error_details) < 3:
                    error_details.append(
                        f"Batch {i//ADD_LEADS_BATCH_SIZE + 1}: {e.status_code} - {e.detail[:200]}"
                    )
            except Exception as e:
                logger.error(f"Unexpected error pushing batch {i//ADD_LEADS_BATCH_SIZE + 1}: {e}")
                errors_count += len(batch)
                if len(error_details) < 3:
                    error_details.append(f"Batch {i//ADD_LEADS_BATCH_SIZE + 1}: {str(e)[:200]}")

    # Create or update association record (legacy column name kept).
    if existing_assoc:
        existing_assoc.pushed_to_instantly = pushed > 0
        existing_assoc.pushed_count = (existing_assoc.pushed_count or 0) + pushed
    else:
        assoc = CampaignLeadList(
            campaign_id=campaign_id,
            lead_list_id=lead_list_id,
            pushed_to_instantly=pushed > 0,
            pushed_count=pushed,
        )
        db.add(assoc)
    await db.commit()

    message = f"Pushed {pushed} leads to Smartlead."
    if skipped_invalid:
        message += f" Skipped {skipped_invalid} invalid/duplicate emails."
    if error_details:
        message += f" Errors: {'; '.join(error_details)}"
    if pushed > 0:
        message += " Le lead possono impiegare qualche minuto per apparire su Smartlead."

    first_lead_sample = instantly_leads[0] if instantly_leads else None
    logger.info(f"First lead sample: {first_lead_sample}")
    logger.info(f"Campaign Smartlead ID: {campaign.instantly_campaign_id}")

    return {
        "campaign_id": campaign_id,
        "lead_list_id": lead_list_id,
        "lead_list_name": lead_list.name,
        "instantly_campaign_id": campaign.instantly_campaign_id,
        "people_in_list": len(people) + len(companies),
        "valid_leads": len(instantly_leads),
        "pushed_to_instantly": pushed,
        "errors": errors_count,
        "skipped_invalid": skipped_invalid,
        "error_details": error_details,
        "api_responses": api_responses,
        "message": message,
    }


@router.get("/{campaign_id}/lists")
async def get_campaign_lists(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get all lead lists associated with a campaign."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    assoc_result = await db.execute(
        select(CampaignLeadList, LeadList)
        .join(LeadList, CampaignLeadList.lead_list_id == LeadList.id)
        .where(CampaignLeadList.campaign_id == campaign_id)
        .order_by(CampaignLeadList.added_at.desc())
    )
    rows = assoc_result.all()

    lists = []
    for assoc, lead_list in rows:
        lists.append({
            "id": lead_list.id,
            "name": lead_list.name,
            "client_tag": lead_list.client_tag,
            "people_count": lead_list.people_count,
            "companies_count": lead_list.companies_count,
            "pushed_to_instantly": assoc.pushed_to_instantly,
            "pushed_count": assoc.pushed_count,
            "added_at": assoc.added_at.isoformat() if assoc.added_at else None,
        })

    return {"campaign_id": campaign_id, "lists": lists, "total": len(lists)}


@router.delete("/{campaign_id}/lists/{list_id}", status_code=204)
async def remove_list_from_campaign(
    campaign_id: int,
    list_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Remove a lead list association from a campaign."""
    result = await db.execute(
        select(CampaignLeadList).where(
            CampaignLeadList.campaign_id == campaign_id,
            CampaignLeadList.lead_list_id == list_id,
        )
    )
    assoc = result.scalar_one_or_none()
    if not assoc:
        raise HTTPException(404, "Lead list association not found")
    await db.delete(assoc)
    await db.commit()


# --- Lead Upload ---


@router.post("/{campaign_id}/upload-leads", response_model=LeadUploadResponse)
async def upload_leads_to_campaign(
    campaign_id: int,
    data: LeadUploadRequest,
    db: AsyncSession = Depends(get_db),
):
    """Push selected leads from our DB to a Smartlead campaign.

    Supports both legacy Lead model (lead_ids) and new Person model (person_ids).
    """
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if not campaign.instantly_campaign_id:
        raise HTTPException(400, "Campaign is not linked to Smartlead")

    instantly_leads = []

    # Handle Person model (new flow)
    if data.person_ids:
        person_result = await db.execute(
            select(Person).where(Person.id.in_(data.person_ids))
        )
        people = person_result.scalars().all()
        for person in people:
            if not person.email:
                continue
            instantly_leads.append({
                "email": person.email,
                "first_name": person.first_name or "",
                "last_name": person.last_name or "",
                "company_name": person.company_name or "",
                "personalization": "",
            })

    # Handle legacy Lead model (backward compatibility)
    if data.lead_ids:
        lead_result = await db.execute(
            select(Lead).where(Lead.id.in_(data.lead_ids))
        )
        leads = lead_result.scalars().all()
        for lead in leads:
            instantly_leads.append({
                "email": lead.email,
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "company_name": lead.company or "",
                "personalization": lead.job_title or "",
            })

    if not instantly_leads:
        raise HTTPException(400, "No valid leads found")

    pushed = 0
    errors_count = 0
    for i in range(0, len(instantly_leads), ADD_LEADS_BATCH_SIZE):
        batch = instantly_leads[i:i + ADD_LEADS_BATCH_SIZE]
        try:
            resp = await smartlead_service.add_leads_to_campaign(
                campaign.instantly_campaign_id, batch,
            )
            pushed += int(resp.get("uploaded_count") or len(batch))
        except SmartleadAPIError as e:
            logger.error(f"Failed to push lead batch to Smartlead: {e.detail}")
            errors_count += len(batch)

    return LeadUploadResponse(pushed=pushed, errors=errors_count)


# --- Push Sequences to Smartlead ---


@router.post(
    "/{campaign_id}/push-sequences",
    response_model=PushSequencesResponse,
)
async def push_sequences_to_instantly(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Push email templates from DB to Smartlead as campaign sequences."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if not campaign.instantly_campaign_id:
        raise HTTPException(400, "Campaign is not linked to Smartlead")
    if not campaign.email_templates:
        raise HTTPException(400, "No email templates to push")

    try:
        steps_data = json.loads(campaign.email_templates)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(400, "Invalid email templates data")

    sl_sequences = []
    for idx, step in enumerate(steps_data, start=1):
        sl_sequences.append({
            "seq_number": idx,
            "seq_delay_details": {"delay_in_days": int(step.get("wait_days", 0) or 0)},
            "variant_distribution_type": "MANUALLY_EQUAL",
            "variants": [{
                "subject": step.get("subject", "") or "",
                "email_body": step.get("body", "") or "",
                "variant_label": "A",
            }],
        })

    try:
        await smartlead_service.save_campaign_sequences(
            campaign.instantly_campaign_id, sl_sequences,
        )
    except SmartleadAPIError as e:
        raise HTTPException(
            502, f"Failed to push sequences to Smartlead: {e.detail}"
        )

    return PushSequencesResponse(
        success=True,
        steps_pushed=len(sl_sequences),
        message=f"Pushed {len(sl_sequences)} steps to Smartlead",
    )


# (The old /webhooks/instantly handler was removed — Smartlead replies are
# now handled by /api/webhooks/smartlead in app/api/webhooks.py)


# --- Sync Leads FROM Instantly ---


@router.post("/{campaign_id}/sync-leads")
async def sync_leads_from_instantly(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Pull leads FROM Smartlead campaign back to local DB."""
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if not campaign.instantly_campaign_id:
        raise HTTPException(400, "Campaign is not linked to Smartlead")

    imported = 0
    skipped = 0
    errors = 0

    try:
        offset = 0
        while True:
            data = await smartlead_service.list_leads_in_campaign(
                campaign.instantly_campaign_id, offset=offset, limit=100,
            )
            items = data if isinstance(data, list) else (
                data.get("data") or data.get("leads") or data.get("items") or []
            )
            if not items:
                break

            for lead_data in items:
                # Smartlead nests the lead under .lead in some responses
                lead_obj = lead_data.get("lead") if isinstance(lead_data.get("lead"), dict) else lead_data
                email = (lead_obj.get("email", "") or "").lower().strip()
                if not email:
                    continue

                existing = await db.execute(
                    select(Lead).where(Lead.email == email)
                )
                if existing.scalar_one_or_none() is not None:
                    skipped += 1
                    continue

                try:
                    new_lead = Lead(
                        email=email,
                        first_name=lead_obj.get("first_name", ""),
                        last_name=lead_obj.get("last_name", ""),
                        company=lead_obj.get("company_name", ""),
                        source="smartlead",
                    )
                    db.add(new_lead)
                    await db.flush()
                    imported += 1
                except Exception as e:
                    logger.warning(f"Error importing lead {email}: {e}")
                    errors += 1

            if len(items) < 100:
                break
            offset += 100

    except SmartleadAPIError as e:
        raise HTTPException(502, f"Failed to fetch leads from Smartlead: {e.detail}")

    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "message": f"Imported {imported} leads, {skipped} already existed, {errors} errors",
    }


# --- Daily Analytics from Smartlead ---


@router.get("/{campaign_id}/daily-analytics")
async def get_campaign_daily_analytics(
    campaign_id: int,
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    """Get day-by-day analytics from Smartlead for a campaign.

    Smartlead's `/analytics-by-date` requires both start_date and end_date and
    rejects ranges larger than 30 days. Defaults to the last 30 days when
    parameters are not supplied.
    """
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if not campaign.instantly_campaign_id:
        raise HTTPException(400, "Campaign is not linked to Smartlead")

    from datetime import timedelta
    today = date.today()
    if not end_date:
        end_date = today.isoformat()
    if not start_date:
        start_date = (today - timedelta(days=30)).isoformat()

    try:
        analytics = await smartlead_service.get_campaign_analytics_by_date(
            campaign.instantly_campaign_id,
            start_date=start_date,
            end_date=end_date,
        )
        return analytics
    except SmartleadAPIError as e:
        raise HTTPException(502, f"Failed to get daily analytics: {e.detail}")


# --- Email Account & Warmup Management (Smartlead) ---
# URLs preserved as `/instantly/accounts/...` so any frontend code that
# referenced them keeps working. Internally we resolve email → Smartlead
# account id and call the appropriate Smartlead endpoints.


@router.get("/instantly/accounts/{email}")
async def get_instantly_account(email: str):
    """Get details for a specific email account (Smartlead)."""
    try:
        aid = await _resolve_email_account_id(email)
        if aid is None:
            raise HTTPException(404, f"Email account {email} not found on Smartlead")
        return await smartlead_service.get_email_account(aid)
    except SmartleadAPIError as e:
        raise HTTPException(502, f"Failed to get account: {e.detail}")


@router.patch("/instantly/accounts/{email}")
async def update_instantly_account(email: str, request: Request):
    """Update email account settings on Smartlead (daily limit, warmup, etc.)."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON payload")

    try:
        aid = await _resolve_email_account_id(email)
        if aid is None:
            raise HTTPException(404, f"Email account {email} not found on Smartlead")
        return await smartlead_service.update_email_account(aid, payload)
    except SmartleadAPIError as e:
        raise HTTPException(502, f"Failed to update account: {e.detail}")


@router.post("/instantly/accounts/{email}/{action}")
async def manage_instantly_account(email: str, action: str):
    """Account state actions. Smartlead exposes warmup config (POST
    /email-accounts/{id}/warmup body {warmup_enabled, ...}) but not the
    granular pause/resume/test_vitals actions Instantly had — for those
    return 501 with a hint to use the Smartlead UI."""
    if action in ("enable_warmup", "disable_warmup"):
        aid = await _resolve_email_account_id(email)
        if aid is None:
            raise HTTPException(404, f"Email account {email} not found on Smartlead")
        try:
            return await smartlead_service.configure_warmup(
                aid, {"warmup_enabled": action == "enable_warmup"},
            )
        except SmartleadAPIError as e:
            raise HTTPException(502, f"Failed to {action}: {e.detail}")
    raise HTTPException(
        501,
        f"Action '{action}' is not exposed by Smartlead's API. Manage it from the Smartlead dashboard.",
    )


@router.get("/instantly/accounts/{email}/warmup-analytics")
async def get_account_warmup_analytics(
    email: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """Warmup stats for a single email account. Smartlead returns the last
    7 days of warmup metrics regardless of start/end (those args are ignored
    here but kept for API compat)."""
    try:
        aid = await _resolve_email_account_id(email)
        if aid is None:
            raise HTTPException(404, f"Email account {email} not found on Smartlead")
        return await smartlead_service.fetch_warmup_stats(aid)
    except SmartleadAPIError as e:
        raise HTTPException(502, f"Failed to get warmup analytics: {e.detail}")


@router.post("/bulk-delete")
async def bulk_delete_campaigns(
    campaign_ids: list[int] = Body(..., embed=True),
    db: AsyncSession = Depends(get_db)
):
    """
    Soft delete multiple campaigns (mark as deleted_at).

    Also deletes campaigns from Smartlead if they have a linked id. Smartlead
    delete is irreversible — proceed with the local soft-delete even if the
    remote call returns 404 (already gone).
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
    remote_deleted = 0
    errors = []

    for campaign in campaigns:
        try:
            if campaign.instantly_campaign_id:
                logger.info(
                    f"Deleting campaign {campaign.id} from Smartlead: {campaign.instantly_campaign_id}",
                )
                await smartlead_service.delete_campaign(campaign.instantly_campaign_id)
                remote_deleted += 1
                logger.info(f"Successfully deleted campaign {campaign.id} from Smartlead")
        except SmartleadAPIError as e:
            if e.status_code == 404 or "not found" in (e.detail or "").lower():
                logger.info(f"Campaign {campaign.id} not found on Smartlead (already gone), proceeding")
                remote_deleted += 1
            else:
                error_msg = f"Failed to delete campaign {campaign.id} ('{campaign.name}') from Smartlead: {e.detail}"
                logger.error(error_msg)
                errors.append(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error deleting campaign {campaign.id} from Smartlead: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

    now = datetime.utcnow()
    for campaign in campaigns:
        campaign.deleted_at = now
        deleted_count += 1

    await db.commit()

    logger.info(f"Successfully soft-deleted {deleted_count} campaigns, {remote_deleted} from Smartlead")

    return {
        "deleted": deleted_count,
        # Key kept as `instantly_deleted` for frontend compat (legacy naming).
        "instantly_deleted": remote_deleted,
        "errors": errors,
        "message": f"Successfully deleted {deleted_count} campaigns",
    }
