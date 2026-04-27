"""MCP tools: email campaigns (synced with Instantly)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select

from app.mcp.session import db_session
from app.mcp.tools._common import campaign_to_dict
from app.models.campaign import Campaign, CampaignStatus

logger = logging.getLogger(__name__)


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_campaigns(
        status: Optional[str] = None,
        search: Optional[str] = None,
        icp_id: Optional[int] = None,
        include_deleted: bool = False,
    ) -> dict[str, Any]:
        """List campaigns. `status` must be one of: draft, active, paused, completed, scheduled, error."""
        async with db_session() as db:
            q = select(Campaign).order_by(Campaign.created_at.desc())
            if not include_deleted:
                q = q.where(Campaign.deleted_at.is_(None))
            if status:
                try:
                    q = q.where(Campaign.status == CampaignStatus(status))
                except ValueError:
                    return {"error": "invalid_status", "allowed": [s.value for s in CampaignStatus]}
            if icp_id is not None:
                q = q.where(Campaign.icp_id == icp_id)
            if search:
                q = q.where(Campaign.name.ilike(f"%{search}%"))
            rows = (await db.execute(q)).scalars().all()
        return {"campaigns": [campaign_to_dict(c) for c in rows], "total": len(rows)}

    @mcp.tool()
    async def get_campaign(campaign_id: int) -> dict[str, Any]:
        """Fetch a campaign by internal ID."""
        async with db_session() as db:
            c = await db.get(Campaign, campaign_id)
            if not c:
                return {"error": "not_found", "campaign_id": campaign_id}
            return campaign_to_dict(c)

    @mcp.tool()
    async def create_campaign(
        name: str,
        subject_lines: Optional[str] = None,
        email_templates: Optional[str] = None,
        icp_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """Create a new campaign (draft status). Use sync_with_instantly to push it to Instantly."""
        async with db_session() as db:
            c = Campaign(
                name=name,
                subject_lines=subject_lines,
                email_templates=email_templates,
                icp_id=icp_id,
            )
            db.add(c)
            await db.flush()
            await db.refresh(c)
            return campaign_to_dict(c)

    @mcp.tool()
    async def update_campaign(
        campaign_id: int,
        name: Optional[str] = None,
        subject_lines: Optional[str] = None,
        email_templates: Optional[str] = None,
        icp_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """Partial update on campaign fields."""
        async with db_session() as db:
            c = await db.get(Campaign, campaign_id)
            if not c:
                return {"error": "not_found", "campaign_id": campaign_id}
            if name is not None:
                c.name = name
            if subject_lines is not None:
                c.subject_lines = subject_lines
            if email_templates is not None:
                c.email_templates = email_templates
            if icp_id is not None:
                c.icp_id = icp_id
            await db.flush()
            await db.refresh(c)
            return campaign_to_dict(c)

    @mcp.tool()
    async def delete_campaign(campaign_id: int) -> dict[str, Any]:
        """Soft-delete a campaign (sets deleted_at)."""
        async with db_session() as db:
            c = await db.get(Campaign, campaign_id)
            if not c:
                return {"error": "not_found", "campaign_id": campaign_id}
            c.deleted_at = datetime.now(timezone.utc)
            return {"deleted": True, "campaign_id": campaign_id}

    @mcp.tool()
    async def activate_campaign(campaign_id: int) -> dict[str, Any]:
        """Activate a campaign on Instantly (must already be synced). Also flips DB status."""
        from app.services.instantly import instantly_service, InstantlyAPIError

        async with db_session() as db:
            c = await db.get(Campaign, campaign_id)
            if not c:
                return {"error": "not_found", "campaign_id": campaign_id}
            if not c.instantly_campaign_id:
                return {"error": "not_synced", "detail": "Campaign has no instantly_campaign_id"}

            try:
                result = await instantly_service.activate_campaign(c.instantly_campaign_id)
            except InstantlyAPIError as e:
                return {"error": "instantly_error", "status_code": e.status_code, "detail": e.detail}

            c.status = CampaignStatus.ACTIVE
            await db.flush()
            return {"activated": True, "campaign_id": campaign_id, "instantly_result": result}

    @mcp.tool()
    async def pause_campaign(campaign_id: int) -> dict[str, Any]:
        """Pause a campaign on Instantly and reflect status in DB."""
        from app.services.instantly import instantly_service, InstantlyAPIError

        async with db_session() as db:
            c = await db.get(Campaign, campaign_id)
            if not c:
                return {"error": "not_found", "campaign_id": campaign_id}
            if not c.instantly_campaign_id:
                return {"error": "not_synced"}
            try:
                result = await instantly_service.pause_campaign(c.instantly_campaign_id)
            except InstantlyAPIError as e:
                return {"error": "instantly_error", "status_code": e.status_code, "detail": e.detail}
            c.status = CampaignStatus.PAUSED
            await db.flush()
            return {"paused": True, "campaign_id": campaign_id, "instantly_result": result}

    @mcp.tool()
    async def push_people_to_campaign(
        campaign_id: int,
        person_ids: list[int],
    ) -> dict[str, Any]:
        """Upload selected people as leads into the Instantly campaign."""
        from app.models.person import Person
        from app.services.instantly import instantly_service, InstantlyAPIError

        if not person_ids:
            return {"uploaded": 0}

        async with db_session() as db:
            c = await db.get(Campaign, campaign_id)
            if not c:
                return {"error": "not_found", "campaign_id": campaign_id}
            if not c.instantly_campaign_id:
                return {"error": "not_synced", "detail": "Campaign has no instantly_campaign_id"}

            people = (await db.execute(select(Person).where(Person.id.in_(person_ids)))).scalars().all()

            leads = [{
                "email": p.email,
                "first_name": p.first_name,
                "last_name": p.last_name,
                "company_name": p.company_name or "",
                "phone": p.phone or "",
                "custom_variables": {
                    "title": p.title or "",
                    "industry": p.industry or "",
                    "location": p.location or "",
                    "linkedin_url": p.linkedin_url or "",
                },
            } for p in people if p.email]

            try:
                result = await instantly_service.add_leads_to_campaign(c.instantly_campaign_id, leads)
            except InstantlyAPIError as e:
                return {"error": "instantly_error", "status_code": e.status_code, "detail": e.detail}

        return {"uploaded": len(leads), "instantly_result": result}

    @mcp.tool()
    async def campaign_analytics(
        campaign_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """Fetch Instantly analytics for a campaign. Dates are YYYY-MM-DD."""
        from app.services.instantly import instantly_service, InstantlyAPIError

        async with db_session() as db:
            c = await db.get(Campaign, campaign_id)
            if not c or not c.instantly_campaign_id:
                return {"error": "not_synced"}
            try:
                overall = await instantly_service.get_campaign_analytics(
                    c.instantly_campaign_id, start_date=start_date, end_date=end_date
                )
                daily = await instantly_service.get_daily_campaign_analytics(
                    c.instantly_campaign_id, start_date=start_date, end_date=end_date
                )
            except InstantlyAPIError as e:
                return {"error": "instantly_error", "status_code": e.status_code, "detail": e.detail}
        return {"overall": overall, "daily": daily}

    @mcp.tool()
    async def generate_email_template(
        industry: Optional[str] = None,
        company_size: Optional[str] = None,
        job_titles: Optional[str] = None,
        geography: Optional[str] = None,
        revenue_range: Optional[str] = None,
        keywords: Optional[str] = None,
        description: Optional[str] = None,
        num_subject_lines: int = 3,
        num_steps: int = 3,
        additional_context: Optional[str] = None,
    ) -> dict[str, Any]:
        """Generate Instantly-ready email templates with Claude.

        Returns `{subject_lines: [...], email_steps: [{subject, body, delay_days}, ...]}`.
        """
        from app.services.email_generator import email_generator_service

        icp_data = {
            "industry": industry,
            "company_size": company_size,
            "job_titles": job_titles,
            "geography": geography,
            "revenue_range": revenue_range,
            "keywords": keywords,
            "description": description,
        }
        return await email_generator_service.generate_templates(
            icp_data=icp_data,
            num_subject_lines=num_subject_lines,
            num_steps=num_steps,
            additional_context=additional_context,
        )
