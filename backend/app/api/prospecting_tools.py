"""API endpoints for managing prospecting tool cards."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.prospecting_tool import ProspectingTool
from app.schemas.prospecting_tool import (
    ProspectingToolOut,
    ProspectingToolUpdate,
    ProspectingToolListResponse,
)

router = APIRouter()


@router.get("", response_model=ProspectingToolListResponse)
async def list_prospecting_tools(db: AsyncSession = Depends(get_db)):
    """List all prospecting tools ordered by sort_order."""
    result = await db.execute(
        select(ProspectingTool).order_by(ProspectingTool.sort_order)
    )
    tools = result.scalars().all()
    return ProspectingToolListResponse(
        tools=[ProspectingToolOut.model_validate(t) for t in tools],
        total=len(tools),
    )


@router.put("/{tool_id}", response_model=ProspectingToolOut)
async def update_prospecting_tool(
    tool_id: int,
    data: ProspectingToolUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a prospecting tool card."""
    tool = await db.get(ProspectingTool, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(tool, field, value)

    await db.commit()
    await db.refresh(tool)
    return ProspectingToolOut.model_validate(tool)
