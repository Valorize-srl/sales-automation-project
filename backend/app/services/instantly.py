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
        self, name: str, campaign_schedule: dict
    ) -> dict:
        """Create a new campaign on Instantly."""
        payload = {
            "name": name,
            "campaign_schedule": campaign_schedule,
        }
        return await self._request("POST", "/campaigns", json=payload)

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
        params: dict[str, Any] = {"campaign_id": campaign_id}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return await self._request(
            "GET", "/analytics/campaign/overview", params=params
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

    async def reply_to_email(self, reply_data: dict) -> dict:
        """Reply to an email (20 req/min limit)."""
        return await self._request("POST", "/emails/reply", json=reply_data)


instantly_service = InstantlyService()
