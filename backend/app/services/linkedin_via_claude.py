"""Find LinkedIn profiles of decision makers at a company using Claude's
built-in `web_search` tool — no LinkedIn auth, no SERP API key needed.

Strategy: Google dorking. Claude is asked to run searches like
    site:linkedin.com/in/ "Acme Srl"
    site:linkedin.com/in/ "Acme Srl" "CEO"
parse the SERP entries (title format `Name - Role - Company | LinkedIn`),
filter by user-supplied target titles, and return a JSON array.

This is the right fit for the EU market where Apollo coverage is thin.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

import anthropic
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)


class LinkedInCandidate(BaseModel):
    first_name: str
    last_name: str
    title: Optional[str] = None
    linkedin_url: str = Field(..., min_length=10)
    location: Optional[str] = None


def _clean_linkedin_url(url: str) -> Optional[str]:
    """Normalise to https://www.linkedin.com/in/<slug> form, drop tracking params."""
    if not url or "/in/" not in url:
        return None
    # Strip query/fragment
    url = url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    # Force https + canonical host
    m = re.search(r"linkedin\.com/in/([A-Za-z0-9\-_%\.]+)", url)
    if not m:
        return None
    slug = m.group(1)
    return f"https://www.linkedin.com/in/{slug}"


def _parse_json_array(text: str) -> list[dict]:
    """Pull a JSON array out of Claude's text response, tolerating ```json fences and prose."""
    text = text.strip()
    # Try direct parse
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        pass
    # Try fenced block
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Last resort: any [ ... ] block
    m = re.search(r"(\[.*\])", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return []
    return []


async def find_company_employees_via_linkedin(
    company_name: str,
    target_titles: list[str],
    max_results: int = 5,
    company_linkedin_url: Optional[str] = None,
    max_searches: int = 2,
) -> list[LinkedInCandidate]:
    """Ask Claude (with web_search) to find LinkedIn profiles of people working at
    `company_name` whose role matches one of `target_titles`. No LinkedIn auth.

    Returns up to `max_results` deduplicated candidates.
    """
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")
    if not target_titles:
        raise ValueError("target_titles must not be empty")

    titles_str = ", ".join(t.strip() for t in target_titles if t.strip())
    li_hint = f"\nKnown company LinkedIn page: {company_linkedin_url}" if company_linkedin_url else ""

    or_clause = " OR ".join(f'"{t}"' for t in target_titles[:3])
    prompt = f"""Run ONE web_search with the query:
  site:linkedin.com/in/ "{company_name}" ({or_clause})

Hard cap: {max_searches} total web_search calls.{li_hint}

Each SERP entry for linkedin.com/in/<slug> has a title like
"First Last - Role - Company | LinkedIn". From each result extract:
  - first_name, last_name, title (the role, NOT the company), linkedin_url, location

Include only profiles clearly at "{company_name}". Skip near-duplicates and similar-but-different companies. Cap at {max_results} matches.

Output ONLY a raw JSON array (no prose, no fences):
[{{"first_name":"...","last_name":"...","title":"...","linkedin_url":"https://www.linkedin.com/in/...","location":"..."}}]

If nothing useful, output [].
"""

    # Haiku 4.5 does NOT support web_search_20260209 (returns 400) — must
    # stay on Sonnet for this flow.
    # max_retries=0: SDK retries on 429 burn through Railway edge timeout.
    # httpx timeout=55s: Railway hobby tier proxies cap around 60s; clean
    # client-side timeout is better than a gateway-truncated 5xx.
    client = anthropic.AsyncAnthropic(
        api_key=settings.anthropic_api_key,
        max_retries=0,
        timeout=55.0,
    )
    try:
        response = await client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1200,
            tools=[{
                "type": "web_search_20260209",
                "name": "web_search",
                "max_uses": max_searches,
            }],
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.RateLimitError as e:
        logger.warning("Anthropic rate limit during LinkedIn discovery: %s", e)
        raise
    except anthropic.APIError as e:
        logger.error("Anthropic API error during LinkedIn discovery: %s", e)
        raise

    # Concatenate all text blocks (final answer comes after web_search tool calls)
    text = "\n".join(b.text for b in response.content if getattr(b, "type", None) == "text").strip()

    raw_items = _parse_json_array(text)
    candidates: list[LinkedInCandidate] = []
    seen_urls: set[str] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        first = (item.get("first_name") or "").strip()
        last = (item.get("last_name") or "").strip()
        url = _clean_linkedin_url(item.get("linkedin_url") or "")
        if not (first and last and url):
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        candidates.append(LinkedInCandidate(
            first_name=first[:100],
            last_name=last[:100],
            title=(item.get("title") or "").strip()[:255] or None,
            linkedin_url=url,
            location=(item.get("location") or "").strip()[:255] or None,
        ))
        if len(candidates) >= max_results:
            break

    logger.info("LinkedIn-via-Claude: company=%r found=%d", company_name, len(candidates))
    return candidates
