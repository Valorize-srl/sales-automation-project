from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.lead import Lead
from app.models.icp import ICP
from app.schemas.lead import (
    LeadCreate,
    LeadResponse,
    LeadListResponse,
    CSVColumnMapping,
    CSVUploadResponse,
    CSVImportRequest,
    CSVImportResponse,
)
from app.services.csv_mapper import csv_mapper_service
from app.services.lead_import import import_leads_from_csv

router = APIRouter()


@router.get("", response_model=LeadListResponse)
async def list_leads(
    icp_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all leads, optionally filtered by ICP."""
    query = select(Lead).order_by(Lead.created_at.desc())
    if icp_id is not None:
        query = query.where(Lead.icp_id == icp_id)
    result = await db.execute(query)
    leads = result.scalars().all()
    return LeadListResponse(leads=leads, total=len(leads))


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single lead by ID."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(404, "Lead not found")
    return lead


@router.post("", response_model=LeadResponse, status_code=201)
async def create_lead(data: LeadCreate, db: AsyncSession = Depends(get_db)):
    """Create a single lead manually."""
    icp_result = await db.execute(select(ICP).where(ICP.id == data.icp_id))
    if not icp_result.scalar_one_or_none():
        raise HTTPException(404, "ICP not found")

    lead = Lead(**data.model_dump(), source="manual")
    db.add(lead)
    await db.flush()
    await db.refresh(lead)
    return lead


@router.delete("/{lead_id}", status_code=204)
async def delete_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a lead."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(404, "Lead not found")
    await db.delete(lead)


@router.post("/csv/upload", response_model=CSVUploadResponse)
async def upload_csv(file: UploadFile = File(...)):
    """Upload a CSV file, parse it, and auto-map columns with Claude."""
    filename = file.filename or ""
    if not filename.lower().endswith(".csv"):
        raise HTTPException(400, "Only CSV files are supported")

    if file.size and file.size > 5 * 1024 * 1024:
        raise HTTPException(400, "File too large. Maximum size is 5MB.")

    content = await file.read()
    headers, rows = csv_mapper_service.parse_csv(content)

    if not headers or not rows:
        raise HTTPException(400, "CSV file is empty or has no data rows")

    mapping = await csv_mapper_service.map_columns(headers, rows[:3])
    unmapped = csv_mapper_service.get_unmapped_headers(headers, mapping)

    return CSVUploadResponse(
        headers=headers,
        mapping=CSVColumnMapping(**mapping),
        rows=rows,
        preview_rows=rows[:5],
        total_rows=len(rows),
        unmapped_headers=unmapped,
    )


@router.post("/csv/import", response_model=CSVImportResponse)
async def import_csv(
    data: CSVImportRequest,
    db: AsyncSession = Depends(get_db),
):
    """Import leads from CSV with confirmed column mapping."""
    icp_result = await db.execute(select(ICP).where(ICP.id == data.icp_id))
    if not icp_result.scalar_one_or_none():
        raise HTTPException(404, "ICP not found")

    if not data.mapping.email:
        raise HTTPException(400, "Email column mapping is required")

    result = await import_leads_from_csv(
        db=db,
        icp_id=data.icp_id,
        mapping=data.mapping.model_dump(),
        rows=data.rows,
    )
    return CSVImportResponse(**result)
