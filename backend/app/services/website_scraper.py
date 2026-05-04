"""
Native website scraper: extracts contact emails and LinkedIn company page URL.

Strategy:
1. Fetch homepage, parse all internal links.
2. Prioritize pages whose URL/text matches contact/about keywords.
3. Visit up to MAX_PAGES pages (BFS), collect emails and LinkedIn URLs.
4. Return deduplicated results sorted by relevance.
"""

import asyncio
import logging
import re
from urllib.parse import urljoin, urlparse, urlunparse
from typing import Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)
LINKEDIN_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/company/[A-Za-z0-9\-_%\.]+/?",
    re.IGNORECASE,
)

# Keywords that indicate a page likely contains contact info
CONTACT_KEYWORDS = {
    "contatti", "contatto", "contact", "contacts", "contact-us", "contactus",
    "chi-siamo", "chi_siamo", "about", "about-us", "aboutus", "team",
    "info", "write-us", "scrivici", "raggiungici", "dove-siamo",
}

# Emails to discard (noise)
BLACKLIST_DOMAINS = {"example.com", "sentry.io", "wixpress.com", "squarespace.com"}
BLACKLIST_PREFIXES = {"noreply", "no-reply", "donotreply", "do-not-reply", "mailer", "bounce"}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}

MAX_PAGES = 8
TIMEOUT = 15
MAX_REDIRECTS = 5


def _normalize_url(url: str, base: str) -> Optional[str]:
    """Resolve relative URL and strip fragment/query noise."""
    try:
        full = urljoin(base, url)
        p = urlparse(full)
        if p.scheme not in ("http", "https"):
            return None
        # Drop fragment; keep path + query as-is
        return urlunparse((p.scheme, p.netloc, p.path.rstrip("/") or "/", "", "", ""))
    except Exception:
        return None


def _same_origin(url: str, base_netloc: str) -> bool:
    try:
        return urlparse(url).netloc == base_netloc
    except Exception:
        return False


def _is_contact_page(url: str, link_text: str) -> bool:
    parts = url.lower() + " " + link_text.lower()
    return any(kw in parts for kw in CONTACT_KEYWORDS)


def _filter_email(email: str) -> bool:
    """Return True if the email looks like a real contact address."""
    email = email.lower()
    local, _, domain = email.partition("@")
    if domain in BLACKLIST_DOMAINS:
        return False
    if any(email.startswith(p) for p in BLACKLIST_PREFIXES):
        return False
    # Skip image/file extensions accidentally matched
    if any(email.endswith(ext) for ext in (".png", ".jpg", ".gif", ".svg", ".webp", ".css", ".js")):
        return False
    return True


def _extract_from_soup(soup: BeautifulSoup, page_url: str) -> tuple[set[str], set[str]]:
    """Return (emails, linkedin_urls) found in a parsed page."""
    emails: set[str] = set()
    linkedin_urls: set[str] = set()

    # 1. mailto: links — most reliable
    for tag in soup.find_all("a", href=True):
        href: str = tag["href"]
        if href.lower().startswith("mailto:"):
            addr = href[7:].split("?")[0].strip().lower()
            if EMAIL_RE.match(addr) and _filter_email(addr):
                emails.add(addr)
        # LinkedIn links
        match = LINKEDIN_RE.search(href)
        if match:
            linkedin_urls.add(match.group(0).rstrip("/"))

    # 2. Full-text regex scan (catches obfuscated addresses in plain text)
    text = soup.get_text(separator=" ")
    for addr in EMAIL_RE.findall(text):
        addr = addr.lower()
        if _filter_email(addr):
            emails.add(addr)

    # 3. LinkedIn in all href attributes
    for tag in soup.find_all(href=True):
        match = LINKEDIN_RE.search(tag["href"])
        if match:
            linkedin_urls.add(match.group(0).rstrip("/"))

    # 4. LinkedIn in visible text / data attributes
    raw_html = str(soup)
    for match in LINKEDIN_RE.finditer(raw_html):
        linkedin_urls.add(match.group(0).rstrip("/"))

    return emails, linkedin_urls


async def scrape_website(url: str) -> dict:
    """
    Scrape a website and return found emails and LinkedIn company page URL.

    Returns:
        {
            "url": str,
            "emails": list[str],
            "linkedin_url": str | None,
            "pages_visited": int,
            "error": str | None,
        }
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed_base = urlparse(url)
    base_netloc = parsed_base.netloc

    all_emails: set[str] = set()
    all_linkedin: set[str] = set()
    visited: set[str] = set()
    # Queue: (url, priority) — lower = higher priority
    queue: list[tuple[str, int]] = [(url, 0)]

    async with httpx.AsyncClient(
        headers=HEADERS,
        timeout=TIMEOUT,
        max_redirects=MAX_REDIRECTS,
        follow_redirects=True,
    ) as client:
        while queue and len(visited) < MAX_PAGES:
            # Sort so contact pages come first
            queue.sort(key=lambda x: x[1])
            page_url, _ = queue.pop(0)

            norm = _normalize_url(page_url, page_url) or page_url
            if norm in visited:
                continue
            visited.add(norm)

            try:
                resp = await client.get(page_url)
                if resp.status_code >= 400:
                    continue
                content_type = resp.headers.get("content-type", "")
                if "html" not in content_type:
                    continue
            except Exception as e:
                logger.debug(f"Failed to fetch {page_url}: {e}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            emails, linkedin_urls = _extract_from_soup(soup, page_url)
            all_emails.update(emails)
            all_linkedin.update(linkedin_urls)

            # Only discover sub-links from homepage and first-level pages
            if len(visited) <= 3:
                for tag in soup.find_all("a", href=True):
                    href = tag.get("href", "")
                    link_text = tag.get_text(strip=True)
                    child_url = _normalize_url(href, page_url)
                    if not child_url:
                        continue
                    if not _same_origin(child_url, base_netloc):
                        continue
                    if child_url in visited:
                        continue
                    priority = 0 if _is_contact_page(child_url, link_text) else 1
                    queue.append((child_url, priority))

    # Pick best LinkedIn: prefer /company/ URLs, shortest path = most canonical
    linkedin_url: Optional[str] = None
    company_links = [u for u in all_linkedin if "/company/" in u.lower()]
    if company_links:
        linkedin_url = min(company_links, key=lambda u: len(u))

    return {
        "url": url,
        "emails": sorted(all_emails),
        "linkedin_url": linkedin_url,
        "pages_visited": len(visited),
        "error": None,
    }


async def scrape_websites_bulk(urls: list[str], concurrency: int = 5) -> list[dict]:
    """Scrape multiple websites concurrently."""
    sem = asyncio.Semaphore(concurrency)

    async def _limited(url: str) -> dict:
        async with sem:
            try:
                return await scrape_website(url)
            except Exception as e:
                logger.error(f"Scrape error for {url}: {e}")
                return {"url": url, "emails": [], "linkedin_url": None, "pages_visited": 0, "error": str(e)}

    return await asyncio.gather(*[_limited(u) for u in urls])
