"""Lead Lists API - Manage lead lists, bulk operations, and exports."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.lead_list import (
    LeadListCreate,
    LeadListUpdate,
    LeadListResponse,
    LeadListListResponse,
    AddLeadsToListRequest,
    RemoveLeadsFromListRequest,
    BulkTagRequest,
    BulkOperationResponse,
)
from app.services.lead_list import LeadListService

logger = logging.getLogger(__name__)
router = APIRouter()


# ==============================================================================
# CRUD Operations
# ==============================================================================

@router.post("", response_model=LeadListResponse, status_code=201)
async def create_list(
    list_data: LeadListCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create new lead list for AI Agent."""
    service = LeadListService(db)
    lead_list = await service.create_list(
        name=list_data.name,
        ai_agent_id=list_data.ai_agent_id,
        client_tag=list_data.client_tag,
        description=list_data.description,
        filters_snapshot=list_data.filters_snapshot,
        person_ids=list_data.person_ids,
        company_ids=list_data.company_ids,
    )

    # Add calculated property
    lead_list.total_leads = lead_list.people_count + lead_list.companies_count

    return lead_list


@router.get("", response_model=LeadListListResponse)
async def list_all_lists(
    ai_agent_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List all lead lists with optional filtering by AI Agent."""
    service = LeadListService(db)
    lists = await service.list_all_lists(
        ai_agent_id=ai_agent_id,
        skip=skip,
        limit=limit,
    )

    # Add calculated properties
    for lead_list in lists:
        lead_list.total_leads = lead_list.people_count + lead_list.companies_count

    return LeadListListResponse(lists=lists, total=len(lists))


@router.get("/{list_id}", response_model=LeadListResponse)
async def get_list(
    list_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get lead list by ID."""
    service = LeadListService(db)
    lead_list = await service.get_list(list_id)
    if not lead_list:
        raise HTTPException(status_code=404, detail=f"Lead list {list_id} not found")

    # Add calculated property
    lead_list.total_leads = lead_list.people_count + lead_list.companies_count

    return lead_list


@router.put("/{list_id}", response_model=LeadListResponse)
async def update_list(
    list_id: int,
    list_data: LeadListUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update lead list name/description."""
    service = LeadListService(db)
    lead_list = await service.update_list(
        list_id=list_id,
        name=list_data.name,
        description=list_data.description,
    )
    if not lead_list:
        raise HTTPException(status_code=404, detail=f"Lead list {list_id} not found")

    # Add calculated property
    lead_list.total_leads = lead_list.people_count + lead_list.companies_count

    return lead_list


@router.delete("/{list_id}", status_code=204)
async def delete_list(
    list_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete lead list (sets list_id to NULL in people/companies)."""
    service = LeadListService(db)
    deleted = await service.delete_list(list_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Lead list {list_id} not found")


# ==============================================================================
# Lead Management
# ==============================================================================

@router.post("/{list_id}/leads", response_model=BulkOperationResponse)
async def add_leads_to_list(
    list_id: int,
    request: AddLeadsToListRequest,
    db: AsyncSession = Depends(get_db),
):
    """Bulk add leads to list."""
    service = LeadListService(db)

    try:
        result = await service.add_leads_to_list(
            list_id=list_id,
            person_ids=request.person_ids,
            company_ids=request.company_ids,
        )
        return BulkOperationResponse(
            people_affected=result["people_added"],
            companies_affected=result["companies_added"],
            message=f"Added {result['people_added']} people and {result['companies_added']} companies to list",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{list_id}/leads", response_model=BulkOperationResponse)
async def remove_leads_from_list(
    list_id: int,
    request: RemoveLeadsFromListRequest,
    db: AsyncSession = Depends(get_db),
):
    """Bulk remove leads from list."""
    service = LeadListService(db)

    result = await service.remove_leads_from_list(
        list_id=list_id,
        person_ids=request.person_ids,
        company_ids=request.company_ids,
    )
    return BulkOperationResponse(
        people_affected=result["people_removed"],
        companies_affected=result["companies_removed"],
        message=f"Removed {result['people_removed']} people and {result['companies_removed']} companies from list",
    )


@router.get("/{list_id}/leads")
async def get_list_leads(
    list_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Get people and companies in a lead list."""
    service = LeadListService(db)

    result = await service.get_list_leads(list_id=list_id, skip=skip, limit=limit)

    # Convert SQLAlchemy models to dicts for JSON response
    from app.schemas.person import PersonResponse
    from app.schemas.company import CompanyResponse

    people_responses = [PersonResponse.model_validate(p) for p in result["people"]]
    companies_responses = [CompanyResponse.model_validate(c) for c in result["companies"]]

    return {
        "people": people_responses,
        "companies": companies_responses,
        "total_people": result["total_people"],
        "total_companies": result["total_companies"],
    }


# ==============================================================================
# Bulk Operations
# ==============================================================================

@router.post("/bulk-tag", response_model=BulkOperationResponse)
async def bulk_tag_leads(
    request: BulkTagRequest,
    db: AsyncSession = Depends(get_db),
):
    """Bulk add/remove tags to leads."""
    service = LeadListService(db)

    result = await service.bulk_tag_leads(
        person_ids=request.person_ids,
        company_ids=request.company_ids,
        tags_to_add=request.tags_to_add,
        tags_to_remove=request.tags_to_remove,
    )

    return BulkOperationResponse(
        people_affected=result["people_tagged"],
        companies_affected=result["companies_tagged"],
        message=f"Tagged {result['people_tagged']} people and {result['companies_tagged']} companies",
    )


# ==============================================================================
# Export Operations
# ==============================================================================

@router.get("/{list_id}/export")
async def export_list_to_csv(
    list_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Export lead list to CSV file."""
    service = LeadListService(db)

    # Check if list exists
    lead_list = await service.get_list(list_id)
    if not lead_list:
        raise HTTPException(status_code=404, detail=f"Lead list {list_id} not found")

    try:
        csv_content = await service.export_list_to_csv(list_id)

        # Return CSV file
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=lead_list_{list_id}_{lead_list.name.replace(' ', '_')}.csv"
            },
        )
    except Exception as e:
        logger.error(f"CSV export error: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
