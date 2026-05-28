"""In-memory cache of the user's Smartlead sender (outbound) email accounts.

Smartlead's warmup feature sends emails between the user's own sender
accounts to build deliverability reputation. These warmup auto-replies get
delivered to our webhook as EMAIL_REPLY events with a `from_email` that's
actually one of OUR sending accounts. We need to filter them out so they
don't pollute /responses.

Refreshes from `GET /email-accounts/` (paginated). Refreshes lazily on first
use and on demand when an unknown email lands in the webhook (cheap insurance
against newly-added sender accounts).
"""
from __future__ import annotations

import asyncio
import logging

from app.services.smartlead import SmartleadAPIError, smartlead_service

logger = logging.getLogger(__name__)


class _SenderPool:
    def __init__(self) -> None:
        self._emails: set[str] = set()
        self._loaded: bool = False
        self._lock = asyncio.Lock()

    async def refresh(self) -> None:
        async with self._lock:
            try:
                offset = 0
                seen: set[str] = set()
                while True:
                    page = await smartlead_service.list_email_accounts(
                        offset=offset, limit=100,
                    )
                    items = page if isinstance(page, list) else (
                        page.get("data") or page.get("accounts") or page.get("items") or []
                    )
                    if not items:
                        break
                    for a in items:
                        em = (a.get("from_email") or a.get("email") or "").strip().lower()
                        if em:
                            seen.add(em)
                    if len(items) < 100:
                        break
                    offset += 100
                self._emails = seen
                self._loaded = True
                logger.info("Loaded %d Smartlead sender accounts", len(seen))
            except SmartleadAPIError as e:
                logger.warning("Could not load Smartlead sender pool: %s", e.detail)
                self._loaded = True  # avoid hammering on every webhook

    async def is_sender(self, email: str | None) -> bool:
        """True if `email` is one of our Smartlead sender accounts.

        First call lazy-loads the pool. If the lookup misses and the pool was
        loaded a while ago, refresh once — covers the case where the user
        just added a new sender on Smartlead.
        """
        if not email:
            return False
        em = email.strip().lower()
        if not self._loaded:
            await self.refresh()
        if em in self._emails:
            return True
        # Miss: try one refresh in case the pool is stale.
        # (Only fires when a webhook is being processed and the from_email
        # is unknown — so it's not free, but it's bounded.)
        before = len(self._emails)
        await self.refresh()
        if len(self._emails) > before:
            return em in self._emails
        return False


smartlead_sender_pool = _SenderPool()
