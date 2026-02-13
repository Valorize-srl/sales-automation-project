"""
Instantly API v2 client - manages campaigns, leads, analytics, and webhooks.
"""
import logging
from typing import Any

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
        json: dict | None = None,
        params: dict | None = None,
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
        self, limit: int = 100, starting_after: str | None = None
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
        sequences: list[dict] | None = None,
        email_list: list[str] | None = None,
        daily_limit: int | None = None,
        email_gap: int | None = None,
        stop_on_reply: bool | None = None,
        stop_on_auto_reply: bool | None = None,
        link_tracking: bool | None = None,
        open_tracking: bool | None = None,
        text_only: bool | None = None,
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

    # --- Account Methods ---

    async def list_accounts(
        self, limit: int = 100, starting_after: str | None = None
    ) -> dict:
        """List email accounts in the workspace."""
        params: dict[str, Any] = {"limit": limit}
        if starting_after:
            params["starting_after"] = starting_after
        return await self._request("GET", "/accounts", params=params)

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

    # --- Analytics Methods ---

    async def get_campaign_analytics(
        self,
        campaign_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """Retrieve metrics for a campaign."""
        params: dict[str, Any] = {"id": campaign_id}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return await self._request(
            "GET", "/campaigns/analytics/overview", params=params
        )

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
        campaign_id: str,
        email_type: str = "received",
        limit: int = 50,
        starting_after: str | None = None,
    ) -> dict:
        """Fetch emails for a campaign, paginated with cursor."""
        params: dict[str, Any] = {
            "campaign_id": campaign_id,
            "email_type": email_type,
            "limit": limit,
        }
        if starting_after:
            params["starting_after"] = starting_after
        return await self._request("GET", "/emails", params=params)

    async def reply_to_email(self, reply_data: dict) -> dict:
        """Reply to an email (20 req/min limit)."""
        return await self._request("POST", "/emails/reply", json=reply_data)


instantly_service = InstantlyService()
