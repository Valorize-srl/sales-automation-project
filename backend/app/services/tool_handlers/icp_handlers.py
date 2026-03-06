"""ICP-related tool handlers: save_icp, update_icp_draft."""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.models.icp import ICP
from app.services.chat_session import ChatSessionService


async def handle_save_icp(
    db: AsyncSession, session_id: int, tool_input: dict, session_service: ChatSessionService
) -> tuple[dict, Optional[dict]]:
    """Save ICP to database."""
    icp = ICP(
        name=tool_input["name"],
        description=tool_input.get("description"),
        industry=tool_input.get("industry"),
        company_size=tool_input.get("company_size"),
        job_titles=tool_input.get("job_titles"),
        geography=tool_input.get("geography"),
        revenue_range=tool_input.get("revenue_range"),
        keywords=tool_input.get("keywords"),
        status="draft"
    )

    db.add(icp)
    await db.commit()
    await db.refresh(icp)

    # Link ICP to session
    session = await db.get(ChatSession, session_id)
    if session:
        session.icp_id = icp.id
        session.current_icp_draft = None
        await db.commit()

    return (
        {"summary": f"ICP '{icp.name}' saved successfully", "icp_id": icp.id},
        None
    )


async def handle_update_icp_draft(
    db: AsyncSession, session_id: int, tool_input: dict, session_service: ChatSessionService
) -> tuple[dict, Optional[dict]]:
    """Update ICP draft in session metadata."""
    session = await db.get(ChatSession, session_id)
    if not session:
        return ({"error": "Session not found"}, None)

    if session.current_icp_draft is None:
        session.current_icp_draft = {}

    session.current_icp_draft.update(tool_input["updates"])
    await db.commit()

    return (
        {"summary": "ICP draft updated", "current_draft": session.current_icp_draft},
        None
    )
