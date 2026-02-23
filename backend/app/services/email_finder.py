"""
Email finder service - Extract generic email addresses from company websites.

This service visits company websites and extracts contact emails like:
info@company.com, contact@company.com, sales@company.com, etc.
"""

import re
import logging
from typing import Optional
from dataclasses import dataclass, field
import httpx
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

# Generic email prefixes to look for
GENERIC_EMAIL_PREFIXES = [
    "info", "contact", "sales", "support", "hello",
    "team", "admin", "general", "office", "mail",
    "contatti", "vendite"  # Italian variants
]

# Common contact page paths to try
CONTACT_PATHS = [
    "/contact",
    "/contacts",
    "/contactus",
    "/contact-us",
    "/contatti",  # Italian
    "/chi-siamo",  # Italian "about us"
    "/about",
    "/about-us",
]


@dataclass
class EmailFinderResult:
    """Result of email finding operation."""
    emails: list[str] = field(default_factory=list)
    source_pages: dict[str, str] = field(default_factory=dict)  # email -> page URL
    confidence: dict[str, float] = field(default_factory=dict)  # email -> confidence score
    error: Optional[str] = None


class EmailFinder:
    """Extract generic emails from company websites."""

    def __init__(self):
        self.http_client = httpx.AsyncClient(
            timeout=10.0,  # 10 second timeout
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; EmailFinder/1.0; +http://example.com/bot)"
            }
        )
        # Email regex pattern
        self.email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        )

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()

    async def find_emails_on_website(self, website_url: str) -> EmailFinderResult:
        """
        Visit company website and extract generic contact emails.

        Steps:
        1. Normalize website URL
        2. Fetch homepage HTML
        3. Fetch common contact pages
        4. Extract all emails using regex
        5. Filter to keep only generic emails
        6. Assign confidence scores
        7. Return deduplicated list

        Args:
            website_url: Company website URL (e.g., "winery.com" or "https://winery.com")

        Returns:
            EmailFinderResult with found emails, sources, and confidence scores
        """
        result = EmailFinderResult()

        try:
            # Normalize URL
            website_url = self._normalize_url(website_url)
            if not website_url:
                result.error = "Invalid website URL"
                return result

            # Extract domain for filtering
            domain = self._extract_domain(website_url)
            if not domain:
                result.error = "Could not extract domain from URL"
                return result

            logger.info(f"Finding emails on {website_url} (domain: {domain})")

            # 1. Fetch homepage
            homepage_html = await self._fetch_page(website_url)
            if homepage_html:
                self._extract_and_add_emails(
                    homepage_html, domain, website_url, result, confidence=0.8
                )

            # 2. Try common contact pages
            for path in CONTACT_PATHS[:3]:  # Limit to first 3 to avoid too many requests
                contact_url = urljoin(website_url, path)
                contact_html = await self._fetch_page(contact_url)
                if contact_html:
                    self._extract_and_add_emails(
                        contact_html, domain, contact_url, result, confidence=1.0
                    )

            # Remove duplicates and sort by confidence
            if result.emails:
                logger.info(f"Found {len(result.emails)} generic emails on {website_url}")
            else:
                logger.info(f"No generic emails found on {website_url}")

        except Exception as e:
            logger.error(f"Error finding emails on {website_url}: {e}")
            result.error = str(e)

        return result

    def _normalize_url(self, url: str) -> Optional[str]:
        """
        Normalize website URL to include scheme.

        Examples:
            "winery.com" -> "https://winery.com"
            "http://winery.com" -> "http://winery.com"
            "https://winery.com/" -> "https://winery.com"
        """
        if not url:
            return None

        url = url.strip().rstrip('/')

        # Add https if no scheme
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'

        return url

    def _extract_domain(self, url: str) -> Optional[str]:
        """
        Extract domain from URL.

        Examples:
            "https://www.winery.com/about" -> "winery.com"
            "https://winery.it" -> "winery.it"
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc

            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]

            return domain.lower()
        except Exception:
            return None

    async def _fetch_page(self, url: str) -> Optional[str]:
        """
        Fetch HTML content with timeout and error handling.

        Args:
            url: Page URL to fetch

        Returns:
            HTML content as string, or None if fetch failed
        """
        try:
            response = await self.http_client.get(url)
            if response.status_code == 200:
                return response.text
            else:
                logger.debug(f"Page {url} returned status {response.status_code}")
                return None
        except httpx.TimeoutException:
            logger.debug(f"Timeout fetching {url}")
            return None
        except Exception as e:
            logger.debug(f"Error fetching {url}: {e}")
            return None

    def _extract_and_add_emails(
        self,
        html: str,
        domain: str,
        source_url: str,
        result: EmailFinderResult,
        confidence: float
    ):
        """
        Extract emails from HTML and add to result if generic.

        Args:
            html: HTML content
            domain: Company domain for filtering
            source_url: URL where emails were found
            result: EmailFinderResult to add emails to
            confidence: Confidence score for emails found on this page
        """
        emails = self._extract_emails_from_html(html, domain)

        for email in emails:
            if email not in result.emails:
                result.emails.append(email)
                result.source_pages[email] = source_url
                result.confidence[email] = confidence
            else:
                # Update confidence if higher
                if confidence > result.confidence.get(email, 0):
                    result.confidence[email] = confidence
                    result.source_pages[email] = source_url

    def _extract_emails_from_html(self, html: str, domain: str) -> list[str]:
        """
        Extract email addresses from HTML content using regex.

        Filters to only keep:
        1. Emails from the company's domain
        2. Emails with generic prefixes (info@, contact@, etc.)

        Args:
            html: HTML content
            domain: Company domain

        Returns:
            List of generic email addresses
        """
        # Find all email-like patterns
        all_emails = self.email_pattern.findall(html)

        generic_emails = []
        for email in all_emails:
            email = email.lower().strip()

            # Check if email is from company domain
            if not email.endswith(f'@{domain}'):
                continue

            # Check if email has generic prefix
            if self._is_generic_email(email, domain):
                generic_emails.append(email)

        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for email in generic_emails:
            if email not in seen:
                seen.add(email)
                deduped.append(email)

        return deduped

    def _is_generic_email(self, email: str, domain: str) -> bool:
        """
        Check if email matches generic patterns.

        Examples:
            info@winery.com -> True (generic prefix)
            john.smith@winery.com -> False (personal name)
            contact@winery.com -> True (generic prefix)

        Args:
            email: Email address to check
            domain: Company domain

        Returns:
            True if email appears to be generic (not personal)
        """
        # Extract prefix (part before @)
        prefix = email.split('@')[0].lower()

        # Check exact matches
        if prefix in GENERIC_EMAIL_PREFIXES:
            return True

        # Check if prefix contains generic keywords
        for generic_prefix in GENERIC_EMAIL_PREFIXES:
            if prefix.startswith(generic_prefix) or prefix.endswith(generic_prefix):
                return True

        return False
