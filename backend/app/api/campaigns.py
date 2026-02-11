from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_campaigns():
    """Placeholder for campaigns list - to be implemented."""
    return {"message": "Campaigns endpoint - coming soon"}
