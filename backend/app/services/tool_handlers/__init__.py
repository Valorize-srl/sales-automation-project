"""Tool handler registry.

Each handler is an async function:
    async def handle_X(db, session_id, tool_input, session_service) -> tuple[dict, Optional[dict]]

Returns:
    (result_for_claude, optional_sse_extra_event)
"""

from typing import Callable, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.chat_session import ChatSessionService

# Type alias for handler functions
HandlerFunc = Callable[
    [AsyncSession, int, dict, ChatSessionService],
    tuple[dict, Optional[dict]]
]

# Import all handlers
from app.services.tool_handlers.icp_handlers import handle_save_icp, handle_update_icp_draft
from app.services.tool_handlers.search_handlers import (
    handle_search_apollo,
    handle_search_google_maps,
    handle_search_linkedin_companies,
    handle_search_linkedin_people,
)
from app.services.tool_handlers.scraping_handlers import handle_scrape_websites
from app.services.tool_handlers.enrichment_handlers import handle_enrich_companies, handle_verify_emails
from app.services.tool_handlers.session_handlers import handle_get_session_context, handle_import_leads
from app.services.tool_handlers.output_handlers import handle_generate_csv

# Handler registry: tool_name -> handler function
TOOL_HANDLERS: dict[str, HandlerFunc] = {
    "save_icp": handle_save_icp,
    "update_icp_draft": handle_update_icp_draft,
    "search_apollo": handle_search_apollo,
    "search_google_maps": handle_search_google_maps,
    "scrape_websites": handle_scrape_websites,
    "search_linkedin_companies": handle_search_linkedin_companies,
    "search_linkedin_people": handle_search_linkedin_people,
    "enrich_companies": handle_enrich_companies,
    "verify_emails": handle_verify_emails,
    "get_session_context": handle_get_session_context,
    "import_leads": handle_import_leads,
    "generate_csv": handle_generate_csv,
}
