"""Output tool handlers: generate_csv."""

import csv
import io
import base64
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.services.chat_session import ChatSessionService

logger = logging.getLogger(__name__)


async def handle_generate_csv(
    db: AsyncSession, session_id: int, tool_input: dict, session_service: ChatSessionService
) -> tuple[dict, Optional[dict]]:
    """Generate a downloadable CSV from structured data."""
    data = tool_input["data"]
    filename = tool_input.get("filename", "prospecting_results")

    if not data:
        return ({"error": "No data to generate CSV", "summary": "Nessun dato per il CSV."}, None)

    try:
        # Get all column headers from the data
        all_keys = []
        seen = set()
        for row in data:
            for key in row.keys():
                if key not in seen:
                    all_keys.append(key)
                    seen.add(key)

        # Generate CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        for row in data:
            writer.writerow(row)

        csv_content = output.getvalue()
        csv_base64 = base64.b64encode(csv_content.encode("utf-8")).decode("utf-8")

        # Store in session metadata for download
        session = await db.get(ChatSession, session_id)
        if session:
            metadata = session.session_metadata or {}
            metadata["generated_csv"] = {
                "filename": f"{filename}.csv",
                "content_base64": csv_base64,
                "rows": len(data),
                "columns": all_keys,
            }
            session.session_metadata = metadata
            await db.commit()

        # SSE event for frontend to show download button
        sse_data = {
            "type": "csv_ready",
            "data": {
                "filename": f"{filename}.csv",
                "rows": len(data),
                "columns": all_keys,
                "content_base64": csv_base64,
            }
        }

        summary = f"CSV '{filename}.csv' generato con {len(data)} righe e {len(all_keys)} colonne."
        return ({"summary": summary, "rows": len(data), "columns": len(all_keys)}, sse_data)

    except Exception as e:
        logger.error(f"CSV generation error: {e}")
        return ({"error": str(e), "summary": f"CSV generation failed: {e}"}, None)
