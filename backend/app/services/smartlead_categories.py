"""In-memory cache of Smartlead lead categories.

Smartlead exposes `GET /leads/fetch-categories` which returns the per-account
list of category labels (defaults + custom). When a reply event arrives via
webhook, the payload includes the category by id and/or name; we map it onto
our internal `Sentiment` enum at ingestion time.

Loaded lazily on first call so app startup never blocks on Smartlead.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.models.email_response import Sentiment
from app.services.smartlead import SmartleadAPIError, smartlead_service

logger = logging.getLogger(__name__)


# Default mapping covering the Smartlead defaults plus common custom labels.
# All keys are lowercased; lookup is case-insensitive.
_DEFAULT_CATEGORY_TO_SENTIMENT: dict[str, Sentiment] = {
    "interested": Sentiment.INTERESTED,
    "meeting request": Sentiment.INTERESTED,
    "meeting_request": Sentiment.INTERESTED,
    "booked meeting": Sentiment.INTERESTED,
    # "Information Request" is treated as Interested per product
    # decision (2026-06-16): chiedere informazioni è un'intent
    # forte e va in pari livello di priorità con le meeting request.
    "information request": Sentiment.INTERESTED,
    "info request": Sentiment.INTERESTED,
    "requested info": Sentiment.INTERESTED,
    "positive": Sentiment.POSITIVE,
    "not now": Sentiment.NEUTRAL,
    "not_now": Sentiment.NEUTRAL,
    "out of office": Sentiment.NEUTRAL,
    "out_of_office": Sentiment.NEUTRAL,
    "ooo": Sentiment.NEUTRAL,
    "objection": Sentiment.NEGATIVE,
    "not interested": Sentiment.NEGATIVE,
    "not_interested": Sentiment.NEGATIVE,
    "wrong person": Sentiment.NEGATIVE,
    "wrong_person": Sentiment.NEGATIVE,
    "do not contact": Sentiment.NEGATIVE,
    "do_not_contact": Sentiment.NEGATIVE,
    "dnc": Sentiment.NEGATIVE,
    "unsubscribe": Sentiment.NEGATIVE,
    "unsubscribed": Sentiment.NEGATIVE,
    "negative": Sentiment.NEGATIVE,
}


class _CategoryCache:
    """Holds {category_id: (name, sentiment)} keyed by Smartlead's int IDs.

    Refreshed lazily; webhook handler can call `refresh()` if it receives an
    unknown id (suggests a new custom category in Smartlead).

    Resolution priority for each category:
      1. The Smartlead API itself returns `sentiment_type` per category
         ("positive" | "negative" | null). When present, use it.
      2. Otherwise, look up the name in `_DEFAULT_CATEGORY_TO_SENTIMENT` —
         catches a few labels that Smartlead leaves untagged but that have a
         clear conceptual lean (e.g. "Wrong Person" → NEGATIVE).
      3. Else fall back to NEUTRAL.
    """

    def __init__(self) -> None:
        self._by_id: dict[int, tuple[str, Sentiment]] = {}
        self._loaded: bool = False
        self._lock = asyncio.Lock()

    def _name_to_sentiment(self, name: str) -> Sentiment:
        key = (name or "").strip().lower()
        return _DEFAULT_CATEGORY_TO_SENTIMENT.get(key, Sentiment.NEUTRAL)

    def _resolve(self, name: str, sentiment_type: Optional[str]) -> Sentiment:
        st = (sentiment_type or "").strip().lower()
        if st == "positive":
            # Smartlead "positive" covers both raw interest ("Interested",
            # "Meeting Request") and informational ("Information Request").
            # Per product decision (2026-06-16) Info Request is now treated
            # as Interested, joining Meeting Request and Booked Meeting.
            key = (name or "").strip().lower()
            if key in {
                "interested", "meeting request", "booked meeting",
                "information request", "info request", "requested info",
            }:
                return Sentiment.INTERESTED
            return Sentiment.POSITIVE
        if st == "negative":
            return Sentiment.NEGATIVE
        # Smartlead sentiment_type is null → use name-based fallback.
        return self._name_to_sentiment(name)

    async def refresh(self) -> None:
        async with self._lock:
            try:
                rows = await smartlead_service.fetch_categories()
            except SmartleadAPIError as e:
                logger.warning("Could not load Smartlead categories: %s", e.detail)
                self._loaded = True  # avoid hammering
                return
            mapping: dict[int, tuple[str, Sentiment]] = {}
            for row in rows or []:
                if not isinstance(row, dict):
                    continue
                cid = row.get("id")
                cname = row.get("name") or row.get("category_name") or ""
                if cid is None or not cname:
                    continue
                try:
                    cid_int = int(cid)
                except (TypeError, ValueError):
                    continue
                mapping[cid_int] = (
                    str(cname),
                    self._resolve(str(cname), row.get("sentiment_type")),
                )
            self._by_id = mapping
            self._loaded = True
            logger.info("Loaded %d Smartlead categories", len(mapping))

    async def _ensure_loaded(self) -> None:
        if not self._loaded:
            await self.refresh()

    async def sentiment_for_id(self, category_id: Optional[int]) -> Optional[Sentiment]:
        if category_id is None:
            return None
        await self._ensure_loaded()
        hit = self._by_id.get(int(category_id))
        if hit is None:
            # Could be a freshly-added custom category — refresh once.
            await self.refresh()
            hit = self._by_id.get(int(category_id))
        return hit[1] if hit else Sentiment.NEUTRAL

    async def name_for_id(self, category_id: Optional[int]) -> Optional[str]:
        if category_id is None:
            return None
        await self._ensure_loaded()
        hit = self._by_id.get(int(category_id))
        if hit is None:
            await self.refresh()
            hit = self._by_id.get(int(category_id))
        return hit[0] if hit else None

    def sentiment_for_name(self, category_name: Optional[str]) -> Optional[Sentiment]:
        if not category_name:
            return None
        return self._name_to_sentiment(category_name)


smartlead_categories = _CategoryCache()


async def category_to_sentiment(
    *,
    category_id: Optional[int] = None,
    category_name: Optional[str] = None,
) -> Optional[Sentiment]:
    """Resolve a Smartlead category to our Sentiment enum.

    Prefers id lookup (handles custom categories); falls back to name matching
    against the default keyword set. Returns `Sentiment.NEUTRAL` for unknown
    custom labels, `None` only when both inputs are missing.
    """
    if category_id is not None:
        return await smartlead_categories.sentiment_for_id(category_id)
    return smartlead_categories.sentiment_for_name(category_name)
