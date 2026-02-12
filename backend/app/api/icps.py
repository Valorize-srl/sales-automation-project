from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.icp import ICP, ICPStatus
from app.schemas.icp import ICPCreate, ICPUpdate, ICPResponse, ICPListResponse

router = APIRouter()


@router.get("/", response_model=ICPListResponse)
async def list_icps(db: AsyncSession = Depends(get_db)):
    """List all ICPs."""
    result = await db.execute(select(ICP).order_by(ICP.created_at.desc()))
    icps = result.scalars().all()
    return ICPListResponse(icps=icps, total=len(icps))


@router.post("/", response_model=ICPResponse, status_code=201)
async def create_icp(data: ICPCreate, db: AsyncSession = Depends(get_db)):
    """Create a new ICP."""
    icp = ICP(**data.model_dump(), status=ICPStatus.DRAFT)
    db.add(icp)
    await db.flush()
    await db.refresh(icp)
    return icp


@router.get("/{icp_id}", response_model=ICPResponse)
async def get_icp(icp_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single ICP by ID."""
    result = await db.execute(select(ICP).where(ICP.id == icp_id))
    icp = result.scalar_one_or_none()
    if not icp:
        raise HTTPException(404, "ICP not found")
    return icp


@router.put("/{icp_id}", response_model=ICPResponse)
async def update_icp(
    icp_id: int, data: ICPUpdate, db: AsyncSession = Depends(get_db)
):
    """Update an ICP."""
    result = await db.execute(select(ICP).where(ICP.id == icp_id))
    icp = result.scalar_one_or_none()
    if not icp:
        raise HTTPException(404, "ICP not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "status":
            setattr(icp, key, ICPStatus(value))
        else:
            setattr(icp, key, value)

    await db.flush()
    await db.refresh(icp)
    return icp


@router.delete("/{icp_id}", status_code=204)
async def delete_icp(icp_id: int, db: AsyncSession = Depends(get_db)):
    """Delete an ICP."""
    result = await db.execute(select(ICP).where(ICP.id == icp_id))
    icp = result.scalar_one_or_none()
    if not icp:
        raise HTTPException(404, "ICP not found")
    await db.delete(icp)
