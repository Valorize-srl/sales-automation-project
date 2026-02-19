"""
ICP Parser service - uses Claude API to extract structured ICP data
from natural language conversation via tool use and SSE streaming.
Also handles Apollo lead search intent detection.
"""
import json
from typing import AsyncIterator

import anthropic

from app.config import settings
from app.schemas.chat import ChatMessage

ICP_SYSTEM_PROMPT = """You are an AI assistant helping a B2B sales professional define their \
Ideal Customer Profile (ICP) and find leads.

You have two modes:

**Mode 1 – ICP Definition**
Help the user define their Ideal Customer Profile by gathering:
1. Industry/Sector
2. Company Size (employees)
3. Job Titles to target
4. Geography
5. Revenue Range
6. Keywords/technologies
7. Description

Ask follow-up questions naturally. When you have enough info (at minimum: industry, job titles, \
and one of company_size/geography/revenue_range), use the save_icp tool.

**Mode 2 – Lead Search**
If the user asks to search, find, or look for people or companies (e.g. "trova gli SEO specialist \
in Italia", "find marketing directors in Germany", "search for SaaS companies in Milan"), \
use the search_apollo tool immediately with the extracted parameters. \
Do NOT ask clarifying questions — extract what you can from the user's message and search.

For search_type:
- Use "people" if they want contacts/persons/people/professionals
- Use "companies" if they want organizations/aziende/companies/firms

For person_seniorities use only: senior, manager, director, vp, c_suite, entry, intern

For organization_sizes use only the formats: "1-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000", "5001+"

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

APOLLO_SEARCH_TOOL = {
    "name": "search_apollo",
    "description": "Search Apollo.io for people or companies matching the specified criteria. "
    "Use this when the user asks to find, search for, or look for leads, contacts, people, or companies.",
    "input_schema": {
        "type": "object",
        "properties": {
            "search_type": {
                "type": "string",
                "enum": ["people", "companies"],
                "description": "Whether to search for people (contacts) or companies (organizations)",
            },
            "person_titles": {
                "type": ["array", "null"],
                "items": {"type": "string"},
                "description": "Job titles to search for (e.g. ['SEO Specialist', 'SEO Manager'])",
            },
            "person_locations": {
                "type": ["array", "null"],
                "items": {"type": "string"},
                "description": "Geographic locations for people (e.g. ['Italy', 'Milan, Italy'])",
            },
            "person_seniorities": {
                "type": ["array", "null"],
                "items": {"type": "string", "enum": ["senior", "manager", "director", "vp", "c_suite", "entry", "intern"]},
                "description": "Seniority levels to filter by",
            },
            "organization_locations": {
                "type": ["array", "null"],
                "items": {"type": "string"},
                "description": "Geographic locations for companies (e.g. ['Italy', 'Germany'])",
            },
            "organization_keywords": {
                "type": ["array", "null"],
                "items": {"type": "string"},
                "description": "Keywords, industries, or sectors to filter organizations. Include industry when mentioned (e.g. ['hospitality', 'technology', 'healthcare', 'finance', 'digital agency'])",
            },
            "organization_sizes": {
                "type": ["array", "null"],
                "items": {"type": "string", "enum": ["1-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000", "5001+"]},
                "description": "Company size ranges",
            },
            "keywords": {
                "type": ["string", "null"],
                "description": "General keyword search",
            },
            "per_page": {
                "type": "integer",
                "description": "Number of results to return (default 25, max 100)",
                "default": 25,
            },
        },
        "required": ["search_type"],
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
        - {"type": "icp_extracted", "data": {...}} -- when save_icp tool is called
        - {"type": "apollo_search_params", "data": {...}} -- when search_apollo tool is called
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
                tools=[ICP_TOOL, APOLLO_SEARCH_TOOL],
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
                    elif block.type == "tool_use" and block.name == "search_apollo":
                        yield f"data: {json.dumps({'type': 'apollo_search_params', 'data': block.input})}\n\n"

        except anthropic.APIError as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"


icp_parser_service = ICPParserService()
