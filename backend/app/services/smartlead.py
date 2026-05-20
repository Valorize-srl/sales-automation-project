"""Smartlead API v1 client.

Replaces the previous Instantly client. Smartlead's auth is via `?api_key=…`
query parameter on every request (not a header), and the API base is
`https://server.smartlead.ai/api/v1`.

Method names mirror the legacy InstantlyService where the operations overlap
(`list_campaigns`, `add_leads_to_campaign`, `activate_campaign`,
`pause_campaign`, `get_campaign_top_analytics`, etc.) so call sites stay
short. Where Smartlead semantics differ (e.g. status transitions via PATCH
/campaigns/{id}/status with body {status: START|PAUSED|STOPPED}, lead pause
via dedicated endpoints, lead-list batch max 400), the divergence is hidden
inside the client.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class SmartleadAPIError(Exception):
    """Raised when Smartlead returns a non-recoverable error."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Smartlead API error {status_code}: {detail}")


SMARTLEAD_BASE_URL = "https://server.smartlead.ai/api/v1"

# Smartlead campaign-create POST returns DRAFTED; status transitions use
# PATCH /campaigns/{id}/status body {"status": "START"|"PAUSED"|"STOPPED"}.
STATUS_START = "START"
STATUS_PAUSED = "PAUSED"
STATUS_STOPPED = "STOPPED"

# Smartlead limit on /campaigns/{id}/leads POST body lead_list size.
ADD_LEADS_BATCH_SIZE = 400


class SmartleadService:
    def __init__(self) -> None:
        self.base_url = SMARTLEAD_BASE_URL

    @property
    def api_key(self) -> str:
        # Re-read every time so test/dev can override settings at runtime.
        return settings.smartlead_api_key or ""

    def _params(self, extra: Optional[dict] = None) -> dict:
        """Inject api_key into every request's query string."""
        p: dict[str, Any] = {"api_key": self.api_key}
        if extra:
            p.update({k: v for k, v in extra.items() if v is not None})
        return p

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Any] = None,
        params: Optional[dict] = None,
        timeout: float = 30.0,
        _retries: int = 3,
    ) -> Any:
        """Generic request wrapper with rate-limit + 5xx retry. Returns the
        parsed JSON body, or `{}` for empty responses."""
        if not self.api_key:
            raise SmartleadAPIError(0, "SMARTLEAD_API_KEY not configured")

        url = f"{self.base_url}{path}"
        merged_params = self._params(params)

        last_error: Optional[SmartleadAPIError] = None
        for attempt in range(_retries):
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method, url,
                    params=merged_params,
                    json=json,
                    headers={"Content-Type": "application/json"} if json is not None else None,
                )
            logger.info(
                "Smartlead %s %s -> status=%s body=%s",
                method, path, response.status_code, response.text[:300],
            )

            if response.status_code == 429 or response.status_code >= 500:
                wait = (attempt + 1) * 2
                logger.warning(
                    "Smartlead %s on %s, retrying in %ss (attempt %s/%s)",
                    response.status_code, path, wait, attempt + 1, _retries,
                )
                last_error = SmartleadAPIError(response.status_code, response.text[:200])
                await asyncio.sleep(wait)
                continue

            if response.status_code >= 400:
                detail = response.text
                try:
                    j = response.json()
                    detail = j.get("message") or j.get("error") or response.text
                except Exception:
                    pass
                raise SmartleadAPIError(response.status_code, detail)

            if not response.text.strip():
                return {}
            try:
                return response.json()
            except ValueError:
                return {"_raw": response.text}

        raise last_error or SmartleadAPIError(429, "Rate limited after retries")

    # ---------------------------------------------------------------------
    # Campaigns
    # ---------------------------------------------------------------------

    async def list_campaigns(
        self,
        *,
        client_id: Optional[int] = None,
        include_tags: bool = False,
    ) -> list[dict]:
        params: dict[str, Any] = {}
        if client_id is not None:
            params["client_id"] = client_id
        if include_tags:
            params["include_tags"] = "true"
        result = await self._request("GET", "/campaigns/", params=params)
        # API ritorna array di campagne direttamente
        if isinstance(result, list):
            return result
        # alcuni endpoint v1 ritornano {data: [...]}
        return result.get("data") if isinstance(result, dict) else []

    async def get_campaign(self, campaign_id: str | int) -> dict:
        return await self._request("GET", f"/campaigns/{campaign_id}")

    async def create_campaign(self, name: str, *, client_id: Optional[int] = None) -> dict:
        """POST /campaigns/create — returns DRAFTED campaign. Status is
        transitioned via update_campaign_status() afterwards."""
        body: dict[str, Any] = {"name": name}
        if client_id is not None:
            body["client_id"] = client_id
        return await self._request("POST", "/campaigns/create", json=body)

    async def update_campaign_status(self, campaign_id: str | int, status: str) -> dict:
        """PATCH /campaigns/{id}/status — START | PAUSED | STOPPED."""
        return await self._request(
            "PATCH", f"/campaigns/{campaign_id}/status", json={"status": status},
        )

    async def update_campaign_schedule(
        self,
        campaign_id: str | int,
        *,
        timezone: str,
        days_of_the_week: list[int],
        start_hour: str,
        end_hour: str,
        min_time_btw_emails: Optional[int] = None,
        max_leads_per_day: Optional[int] = None,
    ) -> dict:
        body: dict[str, Any] = {
            "timezone": timezone,
            "days_of_the_week": days_of_the_week,
            "start_hour": start_hour,
            "end_hour": end_hour,
        }
        if min_time_btw_emails is not None:
            body["min_time_btw_emails"] = min_time_btw_emails
        if max_leads_per_day is not None:
            body["max_leads_per_day"] = max_leads_per_day
        return await self._request("POST", f"/campaigns/{campaign_id}/schedule", json=body)

    async def update_campaign_settings(self, campaign_id: str | int, **kwargs: Any) -> dict:
        body = {k: v for k, v in kwargs.items() if v is not None}
        return await self._request("POST", f"/campaigns/{campaign_id}/settings", json=body)

    async def save_campaign_sequences(
        self, campaign_id: str | int, sequences: list[dict]
    ) -> dict:
        return await self._request(
            "POST", f"/campaigns/{campaign_id}/sequences", json=sequences,
        )

    async def get_campaign_sequences(self, campaign_id: str | int) -> Any:
        return await self._request("GET", f"/campaigns/{campaign_id}/sequences")

    async def delete_campaign(self, campaign_id: str | int) -> dict:
        return await self._request("DELETE", f"/campaigns/{campaign_id}")

    # Convenience aliases — match the legacy call-site naming.
    async def activate_campaign(self, campaign_id: str | int) -> dict:
        return await self.update_campaign_status(campaign_id, STATUS_START)

    async def pause_campaign(self, campaign_id: str | int) -> dict:
        return await self.update_campaign_status(campaign_id, STATUS_PAUSED)

    # ---------------------------------------------------------------------
    # Campaign ↔ Email Accounts
    # ---------------------------------------------------------------------

    async def get_campaign_email_accounts(self, campaign_id: str | int) -> list[dict]:
        result = await self._request("GET", f"/campaigns/{campaign_id}/email-accounts")
        if isinstance(result, list):
            return result
        return result.get("data") if isinstance(result, dict) else []

    async def add_email_accounts_to_campaign(
        self, campaign_id: str | int, account_ids: list[int]
    ) -> dict:
        return await self._request(
            "POST",
            f"/campaigns/{campaign_id}/email-accounts",
            json={"email_account_ids": account_ids},
        )

    async def remove_email_accounts_from_campaign(
        self, campaign_id: str | int, account_ids: list[int]
    ) -> dict:
        return await self._request(
            "DELETE",
            f"/campaigns/{campaign_id}/email-accounts",
            json={"email_account_ids": account_ids},
        )

    # ---------------------------------------------------------------------
    # Leads
    # ---------------------------------------------------------------------

    async def add_leads_to_campaign(
        self,
        campaign_id: str | int,
        leads: list[dict],
        *,
        settings_overrides: Optional[dict] = None,
    ) -> dict:
        """POST /campaigns/{id}/leads — body {lead_list, settings}.

        Smartlead's hard cap is 400 leads per request. We batch transparently
        and aggregate the per-call results.
        """
        if not leads:
            return {"uploaded_count": 0, "duplicate_count": 0, "batches": 0}

        total_uploaded = 0
        total_duplicates = 0
        total_skipped = 0
        batches = 0
        last_resp: dict = {}

        for i in range(0, len(leads), ADD_LEADS_BATCH_SIZE):
            chunk = leads[i:i + ADD_LEADS_BATCH_SIZE]
            payload: dict[str, Any] = {"lead_list": chunk}
            if settings_overrides:
                payload["settings"] = settings_overrides
            resp = await self._request(
                "POST", f"/campaigns/{campaign_id}/leads", json=payload, timeout=120.0,
            )
            batches += 1
            if isinstance(resp, dict):
                total_uploaded += int(resp.get("upload_count") or resp.get("uploaded_count") or 0)
                total_duplicates += int(resp.get("already_added_to_campaign") or resp.get("duplicate_count") or 0)
                total_skipped += int(resp.get("invalid_email_count") or resp.get("blocklist_count") or 0)
                last_resp = resp

        return {
            "uploaded_count": total_uploaded,
            "duplicate_count": total_duplicates,
            "skipped_count": total_skipped,
            "batches": batches,
            "last_response": last_resp,
        }

    async def list_leads_in_campaign(
        self, campaign_id: str | int, *, offset: int = 0, limit: int = 100
    ) -> dict:
        return await self._request(
            "GET", f"/campaigns/{campaign_id}/leads",
            params={"offset": offset, "limit": limit},
        )

    async def fetch_lead_by_email(self, email: str) -> dict:
        return await self._request("GET", "/leads/", params={"email": email})

    async def update_lead(self, campaign_id: str | int, lead_id: str | int, payload: dict) -> dict:
        return await self._request(
            "POST", f"/campaigns/{campaign_id}/leads/{lead_id}", json=payload,
        )

    async def pause_lead(self, campaign_id: str | int, lead_id: str | int) -> dict:
        return await self._request("POST", f"/campaigns/{campaign_id}/leads/{lead_id}/pause")

    async def resume_lead(self, campaign_id: str | int, lead_id: str | int) -> dict:
        return await self._request("POST", f"/campaigns/{campaign_id}/leads/{lead_id}/resume")

    async def delete_lead_from_campaign(self, campaign_id: str | int, lead_id: str | int) -> dict:
        return await self._request("DELETE", f"/campaigns/{campaign_id}/leads/{lead_id}")

    async def unsubscribe_lead_from_campaign(
        self, campaign_id: str | int, lead_id: str | int
    ) -> dict:
        return await self._request(
            "POST", f"/campaigns/{campaign_id}/leads/{lead_id}/unsubscribe",
        )

    async def unsubscribe_lead_globally(self, lead_id: str | int) -> dict:
        return await self._request("POST", f"/leads/{lead_id}/unsubscribe")

    async def add_to_block_list(
        self, *, email: Optional[str] = None, domain: Optional[str] = None
    ) -> dict:
        body: dict[str, Any] = {}
        if email:
            body["email"] = email
        elif domain:
            body["domain"] = domain
        return await self._request("POST", "/leads/add-domain-block-list", json=body)

    async def fetch_categories(self) -> list[dict]:
        """GET /leads/fetch-categories — list of {id, name} category labels."""
        result = await self._request("GET", "/leads/fetch-categories")
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("data") or result.get("categories") or []
        return []

    async def get_lead_message_history(
        self, campaign_id: str | int, lead_id: str | int
    ) -> dict:
        return await self._request(
            "GET", f"/campaigns/{campaign_id}/leads/{lead_id}/message-history",
        )

    async def get_campaigns_for_lead(self, lead_id: str | int) -> list[dict]:
        result = await self._request("GET", f"/leads/{lead_id}/campaigns")
        if isinstance(result, list):
            return result
        return result.get("data") if isinstance(result, dict) else []

    # ---------------------------------------------------------------------
    # Reply to thread (master-inbox surrogate)
    # ---------------------------------------------------------------------

    async def reply_to_thread(
        self,
        campaign_id: str | int,
        *,
        lead_id: str | int,
        email_body: str,
        reply_message_id: str,
        reply_email_time: str,
    ) -> dict:
        """POST /campaigns/{id}/reply-email-thread.

        Smartlead delivers the reply through the same email account the
        original thread is on (no eaccount arg needed, unlike Instantly).
        """
        return await self._request(
            "POST", f"/campaigns/{campaign_id}/reply-email-thread",
            json={
                "lead_id": lead_id,
                "email_body": email_body,
                "reply_message_id": reply_message_id,
                "reply_email_time": reply_email_time,
            },
        )

    # ---------------------------------------------------------------------
    # Analytics
    # ---------------------------------------------------------------------

    async def get_campaign_top_analytics(self, campaign_id: str | int) -> dict:
        return await self._request("GET", f"/campaigns/{campaign_id}/analytics")

    async def get_campaign_statistics(
        self,
        campaign_id: str | int,
        *,
        email_sequence_number: Optional[int] = None,
        email_status: Optional[str] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> dict:
        params: dict[str, Any] = {"offset": offset, "limit": limit}
        if email_sequence_number is not None:
            params["email_sequence_number"] = email_sequence_number
        if email_status:
            params["email_status"] = email_status
        return await self._request(
            "GET", f"/campaigns/{campaign_id}/statistics", params=params,
        )

    async def get_campaign_analytics_by_date(
        self,
        campaign_id: str | int,
        *,
        start_date: str,
        end_date: str,
    ) -> dict:
        return await self._request(
            "GET", f"/campaigns/{campaign_id}/analytics-by-date",
            params={"start_date": start_date, "end_date": end_date},
        )

    async def get_global_analytics(self) -> dict:
        return await self._request("GET", "/analytics/overview")

    # ---------------------------------------------------------------------
    # Email accounts
    # ---------------------------------------------------------------------

    async def list_email_accounts(self, *, offset: int = 0, limit: int = 100) -> dict:
        return await self._request(
            "GET", "/email-accounts/", params={"offset": offset, "limit": limit},
        )

    async def get_email_account(self, account_id: str | int) -> dict:
        return await self._request("GET", f"/email-accounts/{account_id}/")

    async def save_email_account(self, payload: dict) -> dict:
        return await self._request("POST", "/email-accounts/save", json=payload)

    async def update_email_account(self, account_id: str | int, payload: dict) -> dict:
        return await self._request("POST", f"/email-accounts/{account_id}", json=payload)

    async def configure_warmup(self, account_id: str | int, payload: dict) -> dict:
        return await self._request(
            "POST", f"/email-accounts/{account_id}/warmup", json=payload,
        )

    async def fetch_warmup_stats(self, account_id: str | int) -> dict:
        return await self._request("GET", f"/email-accounts/{account_id}/warmup-stats")

    # ---------------------------------------------------------------------
    # Webhooks (programmatic registration — optional; manual via UI also OK)
    # ---------------------------------------------------------------------

    async def create_webhook(self, webhook_url: str, event_type: str) -> dict:
        return await self._request(
            "POST", "/webhooks",
            json={"webhook_url": webhook_url, "event_type": event_type},
        )

    async def list_webhooks(self) -> Any:
        return await self._request("GET", "/webhooks")

    async def delete_webhook(self, webhook_id: str | int) -> dict:
        return await self._request("DELETE", f"/webhooks/{webhook_id}")


smartlead_service = SmartleadService()
