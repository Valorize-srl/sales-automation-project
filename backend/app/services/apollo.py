"""
Apollo.io API service – search people and organizations for lead prospecting.
Supports both natural-language (via Claude tool) and structured form searches.
"""
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

APOLLO_BASE_URL = "https://api.apollo.io/api/v1"

SENIORITY_MAP = {
    "senior": "senior",
    "manager": "manager",
    "director": "director",
    "vp": "vp",
    "c_suite": "c_suite",
    "entry": "entry",
    "intern": "intern",
}

SIZE_RANGES = {
    "1-10": "1,10",
    "11-50": "11,50",
    "51-200": "51,200",
    "201-500": "201,500",
    "501-1000": "501,1000",
    "1001-5000": "1001,5000",
    "5001+": "5001,10000",
}


class ApolloAPIError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Apollo API error {status_code}: {detail}")


class ApolloService:
    def __init__(self) -> None:
        self.api_key = settings.apollo_api_key
        self.base_url = APOLLO_BASE_URL

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.api_key,
        }

    def _check_key(self) -> None:
        if not self.api_key:
            raise ApolloAPIError(401, "Apollo API key not configured. Add APOLLO_API_KEY to environment variables.")

    async def _post(self, path: str, payload: dict) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=self._headers(), json=payload)
        if response.status_code >= 400:
            detail = response.text
            try:
                detail = response.json().get("error", response.text)
            except Exception:
                pass
            raise ApolloAPIError(response.status_code, detail)
        return response.json()

    # -------------------------------------------------------------------
    # Credits status
    # -------------------------------------------------------------------

    async def get_credits_status(self) -> dict[str, Any]:
        """Get Apollo credits status (email credits remaining, etc.)."""
        self._check_key()
        url = f"{self.base_url}/auth/health"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers())
        if response.status_code >= 400:
            detail = response.text
            try:
                detail = response.json().get("error", response.text)
            except Exception:
                pass
            raise ApolloAPIError(response.status_code, detail)
        return response.json()

    # -------------------------------------------------------------------
    # People enrichment
    # -------------------------------------------------------------------

    async def enrich_people(
        self,
        people: list[dict],
    ) -> dict[str, Any]:
        """Enrich people with email, phone, LinkedIn via /people/bulk_match.
        Max 10 people per call. Costs 1 credit per person if reveal_personal_emails=True.

        Args:
            people: List of person dicts with at least: id, first_name, last_name, organization_name
        """
        self._check_key()

        # Build details array with required fields
        details = []
        for p in people[:10]:  # API limit: max 10
            detail = {}
            if p.get("id"):
                detail["id"] = p["id"]
            if p.get("first_name"):
                detail["first_name"] = p["first_name"]
            if p.get("last_name"):
                detail["last_name"] = p["last_name"]
            if p.get("organization_name"):
                detail["organization_name"] = p["organization_name"]
            if p.get("linkedin_url"):
                detail["linkedin_url"] = p["linkedin_url"]

            if detail:  # Only add if we have some data
                details.append(detail)

        payload = {"details": details}

        # Add query parameters for reveal options
        # Note: reveal_phone_number requires a webhook_url, so we skip it for now
        url = f"{self.base_url}/people/bulk_match?reveal_personal_emails=true"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=self._headers(), json=payload)

        if response.status_code >= 400:
            detail = response.text
            try:
                detail = response.json().get("error", response.text)
            except Exception:
                pass
            raise ApolloAPIError(response.status_code, detail)

        return response.json()

    # -------------------------------------------------------------------
    # People search
    # -------------------------------------------------------------------

    async def search_people(
        self,
        person_titles: list[str] | None = None,
        person_locations: list[str] | None = None,
        person_seniorities: list[str] | None = None,
        organization_keywords: list[str] | None = None,
        organization_sizes: list[str] | None = None,
        keywords: str | None = None,
        per_page: int = 25,
    ) -> dict[str, Any]:
        """Search Apollo people with automatic enrichment. Returns raw API response with enriched data."""
        self._check_key()

        payload: dict[str, Any] = {"per_page": min(per_page, 100), "page": 1}

        if person_titles:
            payload["person_titles"] = person_titles
        if person_locations:
            payload["person_locations"] = person_locations
        if person_seniorities:
            payload["person_seniorities"] = [
                SENIORITY_MAP.get(s.lower(), s.lower()) for s in person_seniorities
            ]
        if organization_keywords:
            payload["q_organization_keyword_tags"] = organization_keywords
        if organization_sizes:
            ranges = [SIZE_RANGES.get(s, s) for s in organization_sizes]
            payload["organization_num_employees_ranges"] = ranges
        if keywords:
            payload["q_keywords"] = keywords

        # 1. Base search
        raw = await self._post("/mixed_people/api_search", payload)

        # 2. Extract people to enrich (only those with potential email/phone data)
        people = raw.get("people", [])
        people_to_enrich = [
            p for p in people
            if p.get("id") and (p.get("has_email") or p.get("linkedin_url"))
        ]

        # 3. Enrichment in batches of 10
        enriched_data = {}
        total_credits_consumed = 0
        for i in range(0, len(people_to_enrich), 10):
            batch = people_to_enrich[i:i+10]
            try:
                result = await self.enrich_people(batch)
                # Track credits consumed from this batch
                credits_consumed = result.get("credits_consumed", 0)
                total_credits_consumed += credits_consumed

                for match in result.get("matches", []):
                    if match.get("id"):
                        enriched_data[match["id"]] = match
            except ApolloAPIError as e:
                if e.status_code == 402:
                    logger.warning("Apollo credits exhausted, returning results without enrichment")
                    break  # Stop enrichment but return what we have
                else:
                    logger.error(f"Apollo enrichment error: {e}")
                    # Continue with next batch

        # 4. Merge enriched data back into search results
        for person in people:
            person_id = person.get("id")
            if person_id and person_id in enriched_data:
                enriched = enriched_data[person_id]
                # Merge enriched fields
                if enriched.get("first_name"):
                    person["first_name"] = enriched["first_name"]
                if enriched.get("last_name"):
                    person["last_name"] = enriched["last_name"]
                if enriched.get("email"):
                    person["email"] = enriched["email"]
                if enriched.get("phone"):
                    person["phone"] = enriched["phone"]
                if enriched.get("direct_phone"):
                    person["direct_phone"] = enriched["direct_phone"]
                if enriched.get("linkedin_url"):
                    person["linkedin_url"] = enriched["linkedin_url"]

        raw["people"] = people
        raw["enriched_count"] = len(enriched_data)  # Track how many were enriched
        raw["credits_consumed"] = total_credits_consumed  # Track credits used for enrichment
        return raw

    def format_people_results(self, raw: dict) -> list[dict]:
        """Normalize Apollo people response to our preview format."""
        people = raw.get("people", [])
        results = []
        for p in people:
            org = p.get("organization") or {}
            location_parts = filter(None, [
                p.get("city"), p.get("state"), p.get("country")
            ])

            # Handle name parsing - Apollo might return "name" or separate first/last
            first_name = p.get("first_name") or ""
            last_name = p.get("last_name") or ""

            # If we don't have first/last but have a "name" field, split it
            if not first_name and not last_name and p.get("name"):
                name_parts = p.get("name", "").strip().split(None, 1)  # Split on first space
                first_name = name_parts[0] if len(name_parts) > 0 else ""
                last_name = name_parts[1] if len(name_parts) > 1 else ""

            results.append({
                "first_name": first_name,
                "last_name": last_name,
                "title": p.get("title"),
                "company": org.get("name") or p.get("organization_name"),
                "linkedin_url": p.get("linkedin_url"),
                "location": ", ".join(location_parts) or None,
                "email": p.get("email"),  # enriched
                "phone": p.get("phone") or p.get("direct_phone"),  # enriched
                "website": org.get("website_url"),
                "industry": org.get("industry"),
            })
        return results

    # -------------------------------------------------------------------
    # Organizations search
    # -------------------------------------------------------------------

    async def search_organizations(
        self,
        organization_locations: list[str] | None = None,
        organization_keywords: list[str] | None = None,
        organization_sizes: list[str] | None = None,
        technologies: list[str] | None = None,
        keywords: str | None = None,
        per_page: int = 25,
    ) -> dict[str, Any]:
        """Search Apollo organizations. Returns raw API response."""
        self._check_key()

        payload: dict[str, Any] = {"per_page": min(per_page, 100), "page": 1}

        if organization_locations:
            payload["organization_locations"] = organization_locations
        if organization_keywords:
            payload["q_organization_keyword_tags"] = organization_keywords
        if organization_sizes:
            ranges = [SIZE_RANGES.get(s, s) for s in organization_sizes]
            payload["organization_num_employees_ranges"] = ranges
        if technologies:
            payload["currently_using_any_of_technology_uids"] = technologies
        if keywords:
            payload["q_keywords"] = keywords

        return await self._post("/mixed_companies/api_search", payload)

    def format_org_results(self, raw: dict) -> list[dict]:
        """Normalize Apollo organizations response to our preview format."""
        orgs = raw.get("organizations", [])
        results = []
        for o in orgs:
            size_min = o.get("estimated_num_employees_min")
            size_max = o.get("estimated_num_employees_max")
            size = None
            if size_min is not None and size_max is not None:
                size = f"{size_min}–{size_max}"
            elif o.get("estimated_num_employees"):
                size = str(o["estimated_num_employees"])

            location_parts = filter(None, [o.get("city"), o.get("country")])
            results.append({
                "name": o.get("name") or "",
                "industry": o.get("industry"),
                "size": size,
                "website": o.get("website_url") or o.get("primary_domain"),
                "linkedin_url": o.get("linkedin_url"),
                "location": ", ".join(location_parts) or None,
                "email": o.get("email"),
                "phone": o.get("phone"),
                "signals": None,
            })
        return results


apollo_service = ApolloService()
