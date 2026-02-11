from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def chat_placeholder():
    """Placeholder for chat endpoint - to be implemented in Step 2."""
    return {"message": "Chat endpoint - coming soon"}
