"""Compatibility shim: re-exports Smartlead under the legacy `instantly_service`
name so call sites in the leads section that import this module (notably
`app/api/companies.py`) keep working without being modified.

Background: this codebase was previously wired to Instantly; we replaced
the provider with Smartlead in Phase 3 of the migration. Most call sites
were swapped directly, but the leads section is off-limits by user
directive — to keep its imports valid without rippling changes we expose
the Smartlead singleton (and exception class) under the old names here.

This file should NOT be expanded — add new functionality to
`app/services/smartlead.py` directly.
"""
from app.services.smartlead import (
    SmartleadAPIError as InstantlyAPIError,  # noqa: F401  (legacy alias)
    smartlead_service as instantly_service,  # noqa: F401  (legacy alias)
)


__all__ = ["instantly_service", "InstantlyAPIError"]
