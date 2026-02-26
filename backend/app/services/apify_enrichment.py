"""
Apify Waterfall Contact Enrichment service.
Fallback enrichment when Apollo credits are exhausted.
Uses actor ryanclinton/waterfall-contact-enrichment (~$0.005/lead).
"""
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

APIFY_BASE_URL = "https://api.apify.com/v2"
WATERFALL_ACTOR_ID = "kIEqeHJbKtCuBbkVE"


class ApifyEnrichmentError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Apify error {status_code}: {detail}")


class ApifyEnrichmentService:
    def __init__(self) -> None:
        self.api_token = settings.apify_api_token

    async def _get_token(self) -> str:
        """Get Apify token from env var or DB settings."""
        if self.api_token:
            return self.api_token
        # Try loading from DB settings
        try:
            from app.db.database import async_session_factory
            from app.models.settings import Setting
            from sqlalchemy import select
            async with async_session_factory() as db:
                result = await db.execute(select(Setting).where(Setting.key == "apify_api_token"))
                setting = result.scalar_one_or_none()
                if setting and setting.value:
                    return setting.value
        except Exception:
            pass
        raise ApifyEnrichmentError(
            401,
            "Apify API token not configured. Add APIFY_API_TOKEN to environment variables or set it in Settings.",
        )

    async def enrich_people(
        self,
        people: list[dict],
    ) -> dict[str, Any]:
        """Enrich people using Apify Waterfall Contact Enrichment.

        Args:
            people: List of dicts with keys: id, first_name, last_name, organization_name, domain (optional)

        Returns:
            Same format as Apollo enrich: {enriched: {id: {...}}, enriched_count, credits_consumed}
        """
        api_token = await self._get_token()

        # Build input for the Waterfall actor
        # It expects: firstName + lastName + domain, or fullName + domain
        contacts = []
        id_map: dict[int, str] = {}  # index -> original apollo_id

        for i, p in enumerate(people):
            first_name = p.get("first_name", "")
            last_name = p.get("last_name", "")
            company = p.get("organization_name", "")
            domain = p.get("domain", "")

            contact: dict[str, str] = {}
            if first_name:
                contact["firstName"] = first_name
            if last_name:
                contact["lastName"] = last_name
            if not first_name and not last_name:
                # Skip if no name at all
                continue
            if domain:
                contact["domain"] = domain
            elif company:
                # Use company name as fallback — the actor can sometimes resolve it
                contact["companyName"] = company

            contacts.append(contact)
            id_map[len(contacts) - 1] = p.get("id", str(i))

        if not contacts:
            return {"enriched": {}, "enriched_count": 0, "credits_consumed": 0}

        # Run the actor synchronously (waitForFinish)
        run_url = (
            f"{APIFY_BASE_URL}/acts/{WATERFALL_ACTOR_ID}/runs"
            f"?token={api_token}&waitForFinish=120"
        )

        actor_input = {
            "people": contacts,
            "scrapeCompanyWebsite": True,
            "detectEmailPattern": True,
        }

        logger.info(f"Apify Waterfall: enriching {len(contacts)} contacts")

        async with httpx.AsyncClient(timeout=180.0) as client:
            # Start the run and wait for it to finish
            response = await client.post(
                run_url,
                json=actor_input,
                headers={"Content-Type": "application/json"},
            )

        if response.status_code >= 400:
            detail = response.text[:500]
            try:
                detail = response.json().get("error", {}).get("message", detail)
            except Exception:
                pass
            raise ApifyEnrichmentError(response.status_code, detail)

        run_data = response.json().get("data", {})
        run_status = run_data.get("status")
        dataset_id = run_data.get("defaultDatasetId")

        if run_status not in ("SUCCEEDED", "RUNNING"):
            raise ApifyEnrichmentError(
                500, f"Apify run failed with status: {run_status}"
            )

        # If still running after waitForFinish, the dataset may be partial
        if not dataset_id:
            raise ApifyEnrichmentError(500, "No dataset returned from Apify run")

        # Fetch dataset items
        dataset_url = (
            f"{APIFY_BASE_URL}/datasets/{dataset_id}/items?token={api_token}"
        )

        async with httpx.AsyncClient(timeout=60.0) as client:
            ds_response = await client.get(dataset_url)

        if ds_response.status_code >= 400:
            raise ApifyEnrichmentError(ds_response.status_code, "Failed to fetch Apify dataset")

        items = ds_response.json() if isinstance(ds_response.json(), list) else []

        # Normalize output to match Apollo enrich format
        enriched: dict[str, dict] = {}
        for i, item in enumerate(items):
            original_id = id_map.get(i, str(i))

            # Extract email — Waterfall returns various email fields
            email = (
                item.get("email")
                or item.get("personalEmail")
                or item.get("workEmail")
                or item.get("businessEmail")
            )

            phone = (
                item.get("phone")
                or item.get("directPhone")
                or item.get("mobilePhone")
            )

            linkedin_url = item.get("linkedInUrl") or item.get("linkedin") or None

            enriched[original_id] = {
                "id": original_id,
                "email": email,
                "phone": phone,
                "direct_phone": item.get("directPhone"),
                "linkedin_url": linkedin_url,
                "first_name": item.get("firstName") or item.get("first_name"),
                "last_name": item.get("lastName") or item.get("last_name"),
                "city": item.get("city"),
                "state": item.get("state"),
                "country": item.get("country"),
            }

        # Estimate cost (~$0.005 per lead)
        estimated_cost = len(contacts) * 0.005

        # Get actual usage stats if available
        usage = run_data.get("usage", {})
        compute_units = usage.get("ACTOR_COMPUTE_UNITS", 0)

        logger.info(
            f"Apify Waterfall: enriched {len(enriched)}/{len(contacts)} contacts, "
            f"compute_units={compute_units}, est_cost=${estimated_cost:.3f}"
        )

        return {
            "enriched": enriched,
            "enriched_count": len(enriched),
            "credits_consumed": 0,  # No Apollo credits used
            "apify_cost_usd": round(estimated_cost, 4),
            "apify_compute_units": compute_units,
        }


apify_enrichment_service = ApifyEnrichmentService()
