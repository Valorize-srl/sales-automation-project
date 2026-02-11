from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_leads():
    """Placeholder for leads list - to be implemented."""
    return {"message": "Leads endpoint - coming soon"}
