from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest
from app.services.icp_parser import icp_parser_service
from app.services.file_parser import extract_text_from_file

router = APIRouter()


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """SSE streaming endpoint for chat with Claude."""
    return StreamingResponse(
        icp_parser_service.stream_chat(request.messages, request.file_content),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a document and extract its text content."""
    allowed_extensions = {".pdf", ".docx", ".txt"}
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in allowed_extensions:
        raise HTTPException(
            400,
            f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}",
        )

    if file.size and file.size > 10 * 1024 * 1024:
        raise HTTPException(400, "File too large. Maximum size is 10MB.")

    try:
        text = await extract_text_from_file(file)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {"filename": filename, "text": text, "length": len(text)}
