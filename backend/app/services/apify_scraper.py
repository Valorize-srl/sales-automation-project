"""Generic Apify scraper service.

Calls any Apify actor and returns results with cost tracking.
Pattern based on existing apify_enrichment.py.
"""

import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

APIFY_BASE_URL = "https://api.apify.com/v2"
# Apify pricing: ~$0.25 per compute unit (CU) on pay-as-you-go
APIFY_COST_PER_CU = 0.25


class ApifyScraperService:
    """Generic service for running Apify actors."""

    def __init__(self, apify_token: str):
        self.token = apify_token
        if not self.token:
            raise ValueError("Apify API token not configured")

    async def run_actor(
        self,
        actor_id: str,
        input_data: dict,
        timeout: int = 180,
    ) -> dict:
        """
        Run an Apify actor synchronously and return results + cost.

        Args:
            actor_id: Apify actor ID (e.g. "compass/crawler-google-places")
            input_data: Input for the actor
            timeout: Max wait time in seconds

        Returns:
            {"results": [...], "run_id": str, "cost_usd": float, "compute_units": float}
        """
        async with httpx.AsyncClient(timeout=timeout + 30) as client:
            # Start the actor run and wait for it to finish
            # Apify API uses ~ separator between username and actor name
            api_actor_id = actor_id.replace("/", "~")
            run_url = f"{APIFY_BASE_URL}/acts/{api_actor_id}/runs"
            params = {
                "token": self.token,
                "waitForFinish": timeout,
            }

            logger.info(f"Starting Apify actor {actor_id} with timeout={timeout}s")

            response = await client.post(
                run_url,
                params=params,
                json=input_data,
            )

            if response.status_code not in (200, 201):
                logger.error(f"Apify actor start failed: {response.status_code} {response.text[:500]}")
                raise Exception(f"Apify actor {actor_id} failed to start: HTTP {response.status_code}")

            run_data = response.json().get("data", {})
            run_id = run_data.get("id", "")
            status = run_data.get("status", "")
            dataset_id = run_data.get("defaultDatasetId", "")

            if status not in ("SUCCEEDED", "RUNNING"):
                logger.warning(f"Apify run {run_id} status: {status}")

            # If still running, the waitForFinish should have handled it
            # but let's check status
            if status == "RUNNING":
                logger.warning(f"Apify run {run_id} still running after {timeout}s wait")

            # Fetch results from dataset
            results = []
            if dataset_id:
                dataset_url = f"{APIFY_BASE_URL}/datasets/{dataset_id}/items"
                dataset_response = await client.get(
                    dataset_url,
                    params={"token": self.token, "limit": 500},
                )

                if dataset_response.status_code == 200:
                    results = dataset_response.json()
                    if not isinstance(results, list):
                        results = []
                else:
                    logger.error(f"Failed to fetch dataset: {dataset_response.status_code}")

            # Calculate cost
            compute_units = 0.0
            cost_usd = 0.0
            stats = run_data.get("stats", {})
            if stats:
                compute_units = stats.get("computeUnits", 0.0)
                cost_usd = compute_units * APIFY_COST_PER_CU

            # If no stats yet (run may still be finishing), estimate from usage
            usage = run_data.get("usage", {})
            if not compute_units and usage:
                # Usage is in USD directly in newer API versions
                cost_usd = sum(v for v in usage.values() if isinstance(v, (int, float)))

            logger.info(
                f"Apify actor {actor_id} completed: "
                f"{len(results)} results, {compute_units:.4f} CU, ${cost_usd:.4f}"
            )

            return {
                "results": results,
                "run_id": run_id,
                "cost_usd": round(cost_usd, 4),
                "compute_units": round(compute_units, 4),
            }

    async def get_run_cost(self, run_id: str) -> Optional[float]:
        """Get the actual cost of a completed run."""
        async with httpx.AsyncClient(timeout=30) as client:
            url = f"{APIFY_BASE_URL}/actor-runs/{run_id}"
            response = await client.get(url, params={"token": self.token})

            if response.status_code != 200:
                return None

            data = response.json().get("data", {})
            stats = data.get("stats", {})
            compute_units = stats.get("computeUnits", 0.0)
            return round(compute_units * APIFY_COST_PER_CU, 4)
