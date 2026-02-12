"""
ICP Parser service - uses Claude API to extract structured ICP data
from natural language conversation via tool use and SSE streaming.
"""
import json
from typing import AsyncIterator

import anthropic

from app.config import settings
from app.schemas.chat import ChatMessage

ICP_SYSTEM_PROMPT = """You are an AI assistant helping a B2B sales professional define their \
Ideal Customer Profile (ICP). Your goal is to have a natural conversation to gather the \
following information:

1. **Industry/Sector**: What industry do their ideal customers operate in?
2. **Company Size**: How many employees? (e.g., 10-50, 50-200, 200-1000, 1000+)
3. **Job Titles**: What roles/titles should be targeted? (e.g., CTO, VP Engineering, Head of Sales)
4. **Geography**: What regions/countries are they targeting?
5. **Revenue Range**: What annual revenue range? (e.g., $1M-$10M, $10M-$50M)
6. **Keywords**: Specific technologies, pain points, or characteristics
7. **Description**: A brief summary of the ideal customer

Start by asking what their business does and who they typically sell to. Ask follow-up \
questions naturally. Don't ask all questions at once -- be conversational.

When you have gathered enough information (at minimum: industry, job titles, and one of \
company_size/geography/revenue_range), use the save_icp tool to propose the structured ICP. \
Include a conversational message confirming what you've captured and asking if they want \
to adjust anything.

If the user uploads a document, analyze it to extract ICP-relevant information and propose \
an ICP based on what you find, asking for confirmation or adjustments.

Always respond in the same language the user writes in."""

ICP_TOOL = {
    "name": "save_icp",
    "description": "Save the structured ICP data extracted from the conversation. "
    "Call this when you have gathered enough information about the ideal customer profile.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "A short descriptive name for this ICP",
            },
            "description": {
                "type": "string",
                "description": "Brief description of the ideal customer",
            },
            "industry": {
                "type": "string",
                "description": "Target industry/sector",
            },
            "company_size": {
                "type": "string",
                "description": "Company size range (employees)",
            },
            "job_titles": {
                "type": "string",
                "description": "Comma-separated target job titles",
            },
            "geography": {
                "type": "string",
                "description": "Target geographic regions",
            },
            "revenue_range": {
                "type": "string",
                "description": "Annual revenue range",
            },
            "keywords": {
                "type": "string",
                "description": "Comma-separated relevant keywords, technologies, or characteristics",
            },
        },
        "required": ["name", "industry", "job_titles"],
    },
}


class ICPParserService:
    def __init__(self) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        file_content: str | None = None,
    ) -> AsyncIterator[str]:
        """
        Stream a chat response from Claude via SSE.

        Yields SSE-formatted strings with events:
        - {"type": "text", "content": "..."} -- text chunks
        - {"type": "icp_extracted", "data": {...}} -- when tool is called
        - {"type": "done"} -- stream complete
        """
        api_messages = []
        for msg in messages:
            content = msg.content
            # Append file content to the last user message
            if msg.role == "user" and file_content and msg is messages[-1]:
                content = f"{content}\n\n---\nUploaded document content:\n{file_content}"
            api_messages.append({"role": msg.role, "content": content})

        try:
            async with self.client.messages.stream(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1024,
                system=ICP_SYSTEM_PROMPT,
                messages=api_messages,
                tools=[ICP_TOOL],
            ) as stream:
                async for event in stream:
                    if event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            yield f"data: {json.dumps({'type': 'text', 'content': event.delta.text})}\n\n"

                # After stream ends, check for tool use in final message
                final_message = await stream.get_final_message()
                for block in final_message.content:
                    if block.type == "tool_use" and block.name == "save_icp":
                        yield f"data: {json.dumps({'type': 'icp_extracted', 'data': block.input})}\n\n"

        except anthropic.APIError as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"


icp_parser_service = ICPParserService()
