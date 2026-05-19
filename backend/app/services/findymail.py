"""Findymail API client.

Two endpoints we use:
  POST https://app.findymail.com/api/search/linkedin
       body: {"linkedin_url": "..."}
  POST https://app.findymail.com/api/search/name
       body: {"name": "Mario Rossi", "domain": "acme.com"}

Both return: {"contact": {id, name, email, domain, company, linkedin_url,
job_title, company_city, company_region, company_country, city, region,
country}} when found. Cost: 1 credit per successful match.

Auth: Authorization: Bearer <FINDYMAIL_API_KEY>
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class FindymailError(Exception):
    """Raised when Findymail returns a non-2xx that we can't recover from."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Findymail {status_code}: {detail}")


class FindymailService:
    BASE_URL = "https://app.findymail.com/api"
    TIMEOUT_SECONDS = 30

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.findymail_api_key
        if not self.api_key:
            raise RuntimeError("FINDYMAIL_API_KEY not configured")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _post(self, path: str, body: dict) -> Optional[dict]:
        """POST to Findymail and return the `contact` dict if found, else None.

        Returns None for 404 (no email found) or empty contact. Raises
        FindymailError on auth/rate-limit/credit errors that the caller should
        surface to the user.
        """
        url = f"{self.BASE_URL}{path}"
        async with httpx.AsyncClient(timeout=self.TIMEOUT_SECONDS) as client:
            try:
                resp = await client.post(url, headers=self._headers(), json=body)
            except httpx.RequestError as e:
                raise FindymailError(0, f"network error: {e}") from e

        if resp.status_code == 404:
            return None
        if resp.status_code in (401, 403):
            raise FindymailError(resp.status_code, "Findymail API key invalid or unauthorised")
        if resp.status_code == 402:
            raise FindymailError(402, "Findymail credit balance exhausted")
        if resp.status_code == 429:
            raise FindymailError(429, "Findymail rate limit exceeded")
        if resp.status_code >= 400:
            raise FindymailError(resp.status_code, resp.text[:300])

        try:
            data = resp.json()
        except ValueError:
            return None

        contact = data.get("contact") if isinstance(data, dict) else None
        if not contact or not isinstance(contact, dict) or not contact.get("email"):
            return None
        return contact

    async def find_email_by_linkedin(self, linkedin_url: str) -> Optional[dict]:
        """Look up a person's professional email from their public LinkedIn URL.

        Returns the full `contact` dict (with `email`, `name`, `job_title`,
        `domain`, `company`, location fields) or None if Findymail can't
        resolve an email.
        """
        if not linkedin_url:
            return None
        return await self._post("/search/linkedin", {"linkedin_url": linkedin_url})

    async def find_email_by_name(self, name: str, domain: str) -> Optional[dict]:
        """Look up an email by full name + company domain. Used as a fallback
        when we have a Person's name and the company's email_domain but no
        LinkedIn URL.
        """
        if not name or not domain:
            return None
        return await self._post("/search/name", {"name": name, "domain": domain})

    async def lookup_company_info(self, *, linkedin_url: Optional[str] = None,
                                  website: Optional[str] = None,
                                  name: Optional[str] = None,
                                  domain: Optional[str] = None) -> Optional[dict]:
        """Look up a company via Findymail's /search/company.

        Accepts any of {linkedin_url, website, name, domain}. Returns the
        full `{name, domain, linkedin_url, company_size, industry,
        description, city, region, country}` dict or None.
        """
        body: dict = {}
        if linkedin_url:
            body["linkedin_url"] = linkedin_url
        elif website:
            body["website"] = website
        elif domain:
            body["domain"] = domain
        elif name:
            body["name"] = name
        else:
            return None
        url = f"{self.BASE_URL}/search/company"
        async with httpx.AsyncClient(timeout=self.TIMEOUT_SECONDS) as client:
            try:
                resp = await client.post(url, headers=self._headers(), json=body)
            except httpx.RequestError as e:
                raise FindymailError(0, f"network error: {e}") from e
        if resp.status_code == 404:
            return None
        if resp.status_code in (401, 403):
            raise FindymailError(resp.status_code, "Findymail API key invalid or unauthorised")
        if resp.status_code == 402:
            raise FindymailError(402, "Findymail credit balance exhausted")
        if resp.status_code == 429:
            raise FindymailError(429, "Findymail rate limit exceeded")
        if resp.status_code >= 400:
            return None
        try:
            data = resp.json()
        except ValueError:
            return None
        if not isinstance(data, dict):
            return None
        return data

    async def lookup_company_domain(self, *, linkedin_url: Optional[str] = None,
                                    website: Optional[str] = None,
                                    name: Optional[str] = None) -> Optional[str]:
        """Thin wrapper around lookup_company_info that returns just the domain.
        Kept for backwards compat with the LinkedIn-find-DM endpoint."""
        info = await self.lookup_company_info(
            linkedin_url=linkedin_url, website=website, name=name,
        )
        if not info:
            return None
        domain = (info.get("domain") or "").strip().lower()
        return domain or None

    async def find_contacts_by_domain_and_roles(
        self, domain: str, roles: list[str]
    ) -> list[dict]:
        """Find decision makers AT a company matching the given job titles.

        Findymail's `/search/domain` returns each contact with name +
        first_name + email + domain. Costs 1 credit per contact returned.

        Returns the full `contacts` list (possibly empty). Raises
        FindymailError on auth/credit/rate errors.
        """
        if not domain or not roles:
            return []
        url = f"{self.BASE_URL}/search/domain"
        async with httpx.AsyncClient(timeout=self.TIMEOUT_SECONDS) as client:
            try:
                resp = await client.post(
                    url,
                    headers=self._headers(),
                    json={"domain": domain, "roles": roles},
                )
            except httpx.RequestError as e:
                raise FindymailError(0, f"network error: {e}") from e

        if resp.status_code == 404:
            return []
        if resp.status_code in (401, 403):
            raise FindymailError(resp.status_code, "Findymail API key invalid or unauthorised")
        if resp.status_code == 402:
            raise FindymailError(402, "Findymail credit balance exhausted")
        if resp.status_code == 429:
            raise FindymailError(429, "Findymail rate limit exceeded")
        if resp.status_code >= 400:
            raise FindymailError(resp.status_code, resp.text[:300])

        try:
            data = resp.json()
        except ValueError:
            return []
        contacts = data.get("contacts") if isinstance(data, dict) else None
        if not isinstance(contacts, list):
            return []
        return [c for c in contacts if isinstance(c, dict) and c.get("email")]
