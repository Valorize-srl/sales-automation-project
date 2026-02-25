"""
Instantly API v2 client - manages campaigns, leads, analytics, and webhooks.
"""
import logging
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

INSTANTLY_BASE_URL = "https://api.instantly.ai/api/v2"


class InstantlyAPIError(Exception):
    """Raised when Instantly API returns an error."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Instantly API error {status_code}: {detail}")


class InstantlyService:
    def __init__(self) -> None:
        self.api_key = settings.instantly_api_key
        self.base_url = INSTANTLY_BASE_URL

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Generic request wrapper with error handling."""
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method, url,
                headers=self._headers(),
                json=json,
                params=params,
            )
        if response.status_code >= 400:
            detail = response.text
            try:
                detail = response.json().get("message", response.text)
            except Exception:
                pass
            raise InstantlyAPIError(response.status_code, detail)
        return response.json()

    # --- Campaign Methods ---

    async def list_campaigns(
        self, limit: int = 100, starting_after: Optional[str] = None
    ) -> dict:
        """List all campaigns, paginated."""
        params: dict[str, Any] = {"limit": limit}
        if starting_after:
            params["starting_after"] = starting_after
        return await self._request("GET", "/campaigns", params=params)

    async def get_campaign(self, campaign_id: str) -> dict:
        """Get single campaign details."""
        return await self._request("GET", f"/campaigns/{campaign_id}")

    async def create_campaign(
        self,
        name: str,
        campaign_schedule: dict,
        *,
        sequences: Optional[list[dict]] = None,
        email_list: Optional[list[str]] = None,
        daily_limit: Optional[int] = None,
        email_gap: Optional[int] = None,
        stop_on_reply: Optional[bool] = None,
        stop_on_auto_reply: Optional[bool] = None,
        link_tracking: Optional[bool] = None,
        open_tracking: Optional[bool] = None,
        text_only: Optional[bool] = None,
    ) -> dict:
        """Create a new campaign on Instantly with full options."""
        payload: dict[str, Any] = {
            "name": name,
            "campaign_schedule": campaign_schedule,
        }
        if sequences is not None:
            payload["sequences"] = sequences
        if email_list is not None:
            payload["email_list"] = email_list
        if daily_limit is not None:
            payload["daily_limit"] = daily_limit
        if email_gap is not None:
            payload["email_gap"] = email_gap
        if stop_on_reply is not None:
            payload["stop_on_reply"] = stop_on_reply
        if stop_on_auto_reply is not None:
            payload["stop_on_auto_reply"] = stop_on_auto_reply
        if link_tracking is not None:
            payload["link_tracking"] = link_tracking
        if open_tracking is not None:
            payload["open_tracking"] = open_tracking
        if text_only is not None:
            payload["text_only"] = text_only
        return await self._request("POST", "/campaigns", json=payload)

    async def update_campaign(self, campaign_id: str, payload: dict) -> dict:
        """Update an existing campaign via PATCH."""
        return await self._request("PATCH", f"/campaigns/{campaign_id}", json=payload)

    async def activate_campaign(self, campaign_id: str) -> dict:
        """Activate a campaign."""
        return await self._request("POST", f"/campaigns/{campaign_id}/activate")

    async def pause_campaign(self, campaign_id: str) -> dict:
        """Pause a campaign."""
        return await self._request("POST", f"/campaigns/{campaign_id}/pause")

    async def delete_campaign(self, campaign_id: str) -> dict:
        """Delete a campaign permanently from Instantly."""
        return await self._request("DELETE", f"/campaigns/{campaign_id}")

    # --- Account Methods ---

    async def list_accounts(
        self, limit: int = 100, starting_after: Optional[str] = None
    ) -> dict:
        """List email accounts in the workspace."""
        params: dict[str, Any] = {"limit": limit}
        if starting_after:
            params["starting_after"] = starting_after
        return await self._request("GET", "/accounts", params=params)

    async def get_account(self, email: str) -> dict:
        """Get account details, warmup status, and campaign eligibility."""
        return await self._request("GET", f"/accounts/{email}")

    async def update_account(self, email: str, payload: dict) -> dict:
        """Update account settings (warmup, daily_limit, sending_gap, etc.)."""
        return await self._request("PATCH", f"/accounts/{email}", json=payload)

    async def manage_account_state(self, email: str, action: str) -> dict:
        """Manage account state: pause, resume, enable_warmup, disable_warmup, test_vitals."""
        return await self._request("POST", f"/accounts/{email}/{action}")

    # --- Lead Methods ---

    async def add_leads_to_campaign(
        self, campaign_id: str, leads: list[dict]
    ) -> dict:
        """Bulk add leads to a campaign."""
        payload = {
            "campaign_id": campaign_id,
            "leads": leads,
        }
        return await self._request("POST", "/leads/batch", json=payload)

    async def list_leads(
        self,
        campaign_id: Optional[str] = None,
        list_id: Optional[str] = None,
        limit: int = 100,
        starting_after: Optional[str] = None,
        search: Optional[str] = None,
        filter_status: Optional[str] = None,
    ) -> dict:
        """List leads with filters and pagination."""
        params: dict[str, Any] = {"limit": limit}
        if campaign_id:
            params["campaign"] = campaign_id
        if list_id:
            params["list_id"] = list_id
        if starting_after:
            params["starting_after"] = starting_after
        if search:
            params["search"] = search
        if filter_status:
            params["filter"] = filter_status
        return await self._request("GET", "/leads", params=params)

    async def get_lead(self, lead_id: str) -> dict:
        """Get lead details by ID."""
        return await self._request("GET", f"/leads/{lead_id}")

    async def update_lead(self, lead_id: str, payload: dict) -> dict:
        """Update lead data."""
        return await self._request("PATCH", f"/leads/{lead_id}", json=payload)

    async def delete_lead(self, lead_id: str) -> dict:
        """Delete a lead permanently."""
        return await self._request("DELETE", f"/leads/{lead_id}")

    async def move_leads(self, payload: dict) -> dict:
        """Move or copy leads between campaigns/lists."""
        return await self._request("POST", "/leads/move", json=payload)

    # --- Lead List Methods ---

    async def list_lead_lists(
        self, limit: int = 100, starting_after: Optional[str] = None
    ) -> dict:
        """List all lead lists."""
        params: dict[str, Any] = {"limit": limit}
        if starting_after:
            params["starting_after"] = starting_after
        return await self._request("GET", "/lead-lists", params=params)

    async def create_lead_list(self, name: str) -> dict:
        """Create a lead list."""
        return await self._request("POST", "/lead-lists", json={"name": name})

    async def delete_lead_list(self, list_id: str) -> dict:
        """Delete a lead list permanently."""
        return await self._request("DELETE", f"/lead-lists/{list_id}")

    # --- Analytics Methods ---

    async def get_campaign_analytics(
        self,
        campaign_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        """Retrieve overview metrics for a campaign."""
        params: dict[str, Any] = {"id": campaign_id}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return await self._request(
            "GET", "/campaigns/analytics/overview", params=params
        )

    async def get_daily_campaign_analytics(
        self,
        campaign_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        """Get day-by-day campaign performance analytics."""
        params: dict[str, Any] = {}
        if campaign_id:
            params["campaign_id"] = campaign_id
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return await self._request(
            "GET", "/campaigns/analytics/daily", params=params
        )

    async def get_warmup_analytics(
        self,
        emails: list[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        """Get warmup metrics for email account(s)."""
        payload: dict[str, Any] = {"emails": emails}
        if start_date:
            payload["start_date"] = start_date
        if end_date:
            payload["end_date"] = end_date
        return await self._request("POST", "/accounts/warmup/analytics", json=payload)

    # --- Webhook Methods ---

    async def create_webhook(self, webhook_url: str, event_type: str) -> dict:
        """Register a webhook for an event type."""
        payload = {
            "webhook_url": webhook_url,
            "event_type": event_type,
        }
        return await self._request("POST", "/webhooks", json=payload)

    async def list_webhooks(self) -> dict:
        """List registered webhooks."""
        return await self._request("GET", "/webhooks")

    async def delete_webhook(self, webhook_id: str) -> dict:
        """Delete a webhook."""
        return await self._request("DELETE", f"/webhooks/{webhook_id}")

    # --- Email Methods ---

    async def list_emails(
        self,
        campaign_id: Optional[str] = None,
        email_type: str = "received",
        limit: int = 50,
        starting_after: Optional[str] = None,
        lead: Optional[str] = None,
    ) -> dict:
        """Fetch emails, paginated with cursor."""
        params: dict[str, Any] = {
            "email_type": email_type,
            "limit": limit,
        }
        if campaign_id:
            params["campaign_id"] = campaign_id
        if starting_after:
            params["starting_after"] = starting_after
        if lead:
            params["lead"] = lead
        return await self._request("GET", "/emails", params=params)

    async def get_email(self, email_id: str) -> dict:
        """Get email details by ID."""
        return await self._request("GET", f"/emails/{email_id}")

    async def count_unread_emails(self) -> dict:
        """Count unread emails in inbox."""
        return await self._request("GET", "/emails/unread/count")

    async def mark_thread_as_read(self, thread_id: str) -> dict:
        """Mark an email thread as read."""
        return await self._request(
            "POST", f"/emails/threads/{thread_id}/read"
        )

    async def reply_to_email(self, reply_data: dict) -> dict:
        """Reply to an email (20 req/min limit)."""
        return await self._request("POST", "/emails/reply", json=reply_data)

    # --- Email Verification ---

    async def verify_email(self, email: str) -> dict:
        """Verify email deliverability."""
        return await self._request("POST", "/email-verification", json={"email": email})

    # --- Search ---

    async def search_campaigns_by_contact(self, contact_email: str) -> dict:
        """Find all campaigns that a contact is part of."""
        return await self._request(
            "GET", "/campaigns/search/by-contact",
            params={"contact_email": contact_email},
        )


instantly_service = InstantlyService()
