"""Tool orchestrator for multi-turn tool execution in conversational chat."""

import json
import time
from typing import AsyncIterator, Optional

from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.models.tool_execution import ToolExecution
from app.models.apollo_search_history import ApolloSearchHistory
from app.models.company import Company
from app.models.icp import ICP
from app.config import settings as app_settings
from app.services.chat_session import ChatSessionService
from app.services.enrichment import CompanyEnrichmentService
from app.services.apollo import apollo_service


# Tool definitions
SAVE_ICP_TOOL = {
    "name": "save_icp",
    "description": "Save the ICP that has been collaboratively defined through conversation. "
                   "Use this when the user confirms the ICP is complete or asks to save it.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Descriptive name for this ICP"},
            "description": {"type": "string"},
            "industry": {"type": "string"},
            "company_size": {"type": "string"},
            "job_titles": {"type": "string"},
            "geography": {"type": "string"},
            "revenue_range": {"type": "string"},
            "keywords": {"type": "string"},
        },
        "required": ["name", "industry", "job_titles"],
    },
}

SEARCH_APOLLO_TOOL = {
    "name": "search_apollo",
    "description": "Search Apollo.io for people or companies. Use this when user asks to find, "
                   "search, or look for leads. After getting results, suggest next steps like enrichment.",
    "input_schema": {
        "type": "object",
        "properties": {
            "search_type": {
                "type": "string",
                "enum": ["people", "companies"],
                "description": "Type of search"
            },
            "person_titles": {
                "type": ["array", "null"],
                "items": {"type": "string"},
                "description": "Job titles to search for (for people search)"
            },
            "person_locations": {
                "type": ["array", "null"],
                "items": {"type": "string"}
            },
            "person_seniorities": {
                "type": ["array", "null"],
                "items": {"type": "string"}
            },
            "organization_locations": {
                "type": ["array", "null"],
                "items": {"type": "string"}
            },
            "organization_keywords": {
                "type": ["array", "null"],
                "items": {"type": "string"}
            },
            "organization_sizes": {
                "type": ["array", "null"],
                "items": {"type": "string"}
            },
            "technologies": {
                "type": ["array", "null"],
                "items": {"type": "string"}
            },
            "keywords": {
                "type": ["string", "null"]
            },
            "per_page": {
                "type": "integer",
                "default": 25
            }
        },
        "required": ["search_type"]
    }
}

ENRICH_COMPANIES_TOOL = {
    "name": "enrich_companies",
    "description": "Enrich companies from last Apollo search with contact emails from their websites. "
                   "Use when user asks to 'find emails', 'get contacts', or 'enrich companies'. "
                   "Scrapes generic emails like info@, contact@, sales@.",
    "input_schema": {
        "type": "object",
        "properties": {
            "company_ids": {
                "type": ["array", "string"],
                "description": "Company IDs to enrich. Use 'all' for all from last search.",
                "items": {"type": "integer"}
            },
            "max_concurrent": {
                "type": "integer",
                "default": 3
            },
            "force": {
                "type": "boolean",
                "default": False
            }
        },
        "required": ["company_ids"]
    }
}

VERIFY_EMAILS_TOOL = {
    "name": "verify_emails",
    "description": "Verify email deliverability for people from last search. "
                   "Checks for catch-all domains, invalid addresses, deliverability.",
    "input_schema": {
        "type": "object",
        "properties": {
            "person_ids": {
                "type": "array",
                "items": {"type": "integer"}
            },
            "min_confidence": {
                "type": "number",
                "default": 0.7
            }
        },
        "required": ["person_ids"]
    }
}

GET_SESSION_CONTEXT_TOOL = {
    "name": "get_session_context",
    "description": "Get current session state: ICP draft, last search results, stats. "
                   "Use when user asks 'what did we search for?' or 'where are we?'",
    "input_schema": {
        "type": "object",
        "properties": {
            "include_history": {
                "type": "boolean",
                "default": False
            }
        }
    }
}

UPDATE_ICP_DRAFT_TOOL = {
    "name": "update_icp_draft",
    "description": "Update ICP draft incrementally as user provides details. "
                   "Does NOT save to database - only builds draft in session. "
                   "Use save_icp when complete.",
    "input_schema": {
        "type": "object",
        "properties": {
            "updates": {
                "type": "object",
                "properties": {
                    "industry": {"type": "string"},
                    "company_size": {"type": "string"},
                    "job_titles": {"type": "string"},
                    "geography": {"type": "string"},
                    "revenue_range": {"type": "string"},
                    "keywords": {"type": "string"}
                }
            }
        },
        "required": ["updates"]
    }
}

ALL_TOOLS = [
    SAVE_ICP_TOOL,
    SEARCH_APOLLO_TOOL,
    ENRICH_COMPANIES_TOOL,
    VERIFY_EMAILS_TOOL,
    GET_SESSION_CONTEXT_TOOL,
    UPDATE_ICP_DRAFT_TOOL,
]

PROSPECTING_TOOLS = [
    SAVE_ICP_TOOL,
    SEARCH_APOLLO_TOOL,
    GET_SESSION_CONTEXT_TOOL,
    UPDATE_ICP_DRAFT_TOOL,
]


class ToolOrchestrator:
    """
    Orchestrator for multi-turn tool execution with streaming.

    Manages Claude tool use, execution, and multi-turn loops.
    """

    def __init__(self, db: AsyncSession, session_id: int, anthropic_api_key: str = "", tools_mode: str = "all"):
        self.db = db
        self.session_id = session_id
        api_key = anthropic_api_key or app_settings.anthropic_api_key
        self.client = AsyncAnthropic(api_key=api_key)
        self.session_service = ChatSessionService(db)
        self.tools = PROSPECTING_TOOLS if tools_mode == "prospecting" else ALL_TOOLS
        self._pending_apollo_results: Optional[dict] = None

    async def execute_and_continue(
        self,
        messages: list[dict],
        system_prompt: str,
        max_iterations: int = 5
    ) -> AsyncIterator[str]:
        """
        Multi-turn tool execution loop with streaming.

        Flow:
        1. Call Claude with messages + tools
        2. Stream text chunks as SSE
        3. If tool_use blocks in final_message:
           a. Execute tools
           b. Yield tool progress SSE events
           c. Add tool results to messages
           d. Call Claude again (loop to step 1)
        4. If no tool_use or max iterations: done

        Args:
            messages: Conversation history
            system_prompt: System prompt with context
            max_iterations: Max tool execution loops

        Yields:
            SSE events (text, tool_start, tool_complete, done)
        """
        iteration = 0
        current_messages = messages.copy()
        total_input_tokens = 0
        total_output_tokens = 0

        while iteration < max_iterations:
            iteration += 1
            tool_uses = []
            assistant_content_blocks = []

            # Stream Claude response
            try:
                async with self.client.messages.stream(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=2048,
                    system=system_prompt,
                    messages=current_messages,
                    tools=self.tools,
                ) as stream:
                    # Stream text chunks
                    async for event in stream:
                        if event.type == "content_block_delta":
                            if hasattr(event.delta, "text"):
                                yield f"data: {json.dumps({'type': 'text', 'content': event.delta.text})}\n\n"

                    # Get final message with tool uses
                    final_message = await stream.get_final_message()
                    assistant_content_blocks = final_message.content

                    # Capture token usage from Claude API response
                    if final_message.usage:
                        total_input_tokens += final_message.usage.input_tokens
                        total_output_tokens += final_message.usage.output_tokens

                    # Extract tool uses
                    for block in final_message.content:
                        if block.type == "tool_use":
                            tool_uses.append(block)

            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
                break

            # No tools? Done — emit usage data before done event
            if not tool_uses:
                yield f"data: {json.dumps({'type': 'usage', 'input_tokens': total_input_tokens, 'output_tokens': total_output_tokens})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break

            # Execute tools
            tool_results = []
            for tool_use in tool_uses:
                # Yield tool start event
                yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_use.name, 'input': tool_use.input})}\n\n"

                try:
                    # Execute tool
                    result = await self.execute_tool(tool_use.name, tool_use.input, tool_use.id)

                    # Add to tool results for Claude
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(result)
                    })

                    # Yield tool complete event
                    yield f"data: {json.dumps({'type': 'tool_complete', 'tool': tool_use.name, 'summary': result.get('summary', 'Completed')})}\n\n"

                    # Emit apollo_results SSE event if search_apollo produced results
                    if tool_use.name == "search_apollo" and self._pending_apollo_results:
                        yield f"data: {json.dumps({'type': 'apollo_results', 'data': self._pending_apollo_results})}\n\n"
                        self._pending_apollo_results = None

                except Exception as e:
                    # Tool execution failed
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps({"error": str(e)}),
                        "is_error": True
                    })
                    yield f"data: {json.dumps({'type': 'tool_error', 'tool': tool_use.name, 'error': str(e)})}\n\n"

            # Add assistant message with tool uses
            current_messages.append({
                "role": "assistant",
                "content": assistant_content_blocks
            })

            # Add tool results as user message
            current_messages.append({
                "role": "user",
                "content": tool_results
            })

            # Continue loop - Claude will process tool results

        if iteration >= max_iterations:
            yield f"data: {json.dumps({'type': 'usage', 'input_tokens': total_input_tokens, 'output_tokens': total_output_tokens})}\n\n"
            yield f"data: {json.dumps({'type': 'error', 'content': 'Max iterations reached'})}\n\n"

    async def execute_tool(
        self,
        tool_name: str,
        tool_input: dict,
        tool_call_id: str
    ) -> dict:
        """
        Execute a single tool and log execution.

        Args:
            tool_name: Name of tool to execute
            tool_input: Tool input parameters
            tool_call_id: Claude's tool use ID

        Returns:
            Tool output dict

        Raises:
            Exception if tool execution fails
        """
        start_time = time.time()

        try:
            # Dispatch to appropriate tool handler
            if tool_name == "save_icp":
                result = await self._save_icp(tool_input)
            elif tool_name == "search_apollo":
                result = await self._search_apollo(tool_input)
            elif tool_name == "enrich_companies":
                result = await self._enrich_companies(tool_input)
            elif tool_name == "verify_emails":
                result = await self._verify_emails(tool_input)
            elif tool_name == "get_session_context":
                result = await self._get_session_context(tool_input)
            elif tool_name == "update_icp_draft":
                result = await self._update_icp_draft(tool_input)
            else:
                raise ValueError(f"Unknown tool: {tool_name}")

            # Log successful execution
            execution_time_ms = int((time.time() - start_time) * 1000)
            await self._log_tool_execution(
                tool_name,
                tool_call_id,
                tool_input,
                result,
                "success",
                execution_time_ms
            )

            return result

        except Exception as e:
            # Log failed execution
            execution_time_ms = int((time.time() - start_time) * 1000)
            await self._log_tool_execution(
                tool_name,
                tool_call_id,
                tool_input,
                {"error": str(e)},
                "error",
                execution_time_ms,
                error_message=str(e)
            )
            raise

    async def _log_tool_execution(
        self,
        tool_name: str,
        tool_call_id: str,
        tool_input: dict,
        tool_output: dict,
        status: str,
        execution_time_ms: int,
        error_message: Optional[str] = None
    ):
        """Log tool execution to database."""
        execution = ToolExecution(
            session_id=self.session_id,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            tool_input=tool_input,
            tool_output=tool_output,
            status=status,
            execution_time_ms=execution_time_ms,
            error_message=error_message,
            credits_consumed=tool_output.get("credits_consumed", 0),
            cost_usd=tool_output.get("cost_usd", 0.0)
        )

        self.db.add(execution)
        await self.db.commit()

    # Tool implementation methods

    async def _save_icp(self, tool_input: dict) -> dict:
        """Save ICP to database."""
        icp = ICP(
            name=tool_input["name"],
            description=tool_input.get("description"),
            industry=tool_input.get("industry"),
            company_size=tool_input.get("company_size"),
            job_titles=tool_input.get("job_titles"),
            geography=tool_input.get("geography"),
            revenue_range=tool_input.get("revenue_range"),
            keywords=tool_input.get("keywords"),
            status="draft"
        )

        self.db.add(icp)
        await self.db.commit()
        await self.db.refresh(icp)

        # Link ICP to session
        session = await self.db.get(ChatSession, self.session_id)
        if session:
            session.icp_id = icp.id
            session.current_icp_draft = None  # Clear draft
            await self.db.commit()

        return {
            "summary": f"ICP '{icp.name}' saved successfully",
            "icp_id": icp.id
        }

    def _infer_industry_from_context(self, tool_input: dict, search_type: str) -> str | None:
        """Infer industry from search parameters when Apollo doesn't provide it."""
        # organization_keywords usually indicate the industry/sector
        org_keywords = tool_input.get("organization_keywords", [])
        if org_keywords:
            return ", ".join(org_keywords[:2])

        # Fallback to general keywords
        keywords = tool_input.get("keywords", "")
        if keywords:
            return keywords

        return None

    async def _search_apollo(self, tool_input: dict) -> dict:
        """
        Search Apollo backend-side and return summary to Claude.

        Full results are stored in self._pending_apollo_results
        and emitted as an SSE event for the frontend.
        """
        import logging
        logger = logging.getLogger(__name__)

        search_type = tool_input.get("search_type", "people")
        per_page = min(tool_input.get("per_page", 25), 100)

        try:
            if search_type == "people":
                raw = await apollo_service.search_people(
                    person_titles=tool_input.get("person_titles"),
                    person_locations=tool_input.get("person_locations"),
                    person_seniorities=tool_input.get("person_seniorities"),
                    organization_keywords=tool_input.get("organization_keywords"),
                    organization_sizes=tool_input.get("organization_sizes"),
                    keywords=tool_input.get("keywords"),
                    per_page=per_page,
                    auto_enrich=False,  # Never auto-enrich from chat
                )
                results = apollo_service.format_people_results(raw)
                # Inject fallback location
                person_locations = tool_input.get("person_locations")
                if person_locations:
                    fallback_location = ", ".join(person_locations)
                    for r in results:
                        if not r.get("location"):
                            r["location"] = fallback_location
                total = raw.get("pagination", {}).get("total_entries", len(results))
            elif search_type == "companies":
                raw = await apollo_service.search_organizations(
                    organization_locations=tool_input.get("organization_locations"),
                    organization_keywords=tool_input.get("organization_keywords"),
                    organization_sizes=tool_input.get("organization_sizes"),
                    technologies=tool_input.get("technologies"),
                    keywords=tool_input.get("keywords"),
                    per_page=per_page,
                )
                results = apollo_service.format_org_results(raw)
                total = raw.get("pagination", {}).get("total_entries", len(results))
            else:
                return {"error": f"Unknown search_type: {search_type}", "summary": "Invalid search type"}

            # Infer industry for results missing it (Apollo often doesn't return it)
            results_missing_industry = [r for r in results if not r.get("industry")]
            if results_missing_industry and len(results_missing_industry) > len(results) * 0.3:
                inferred_industry = self._infer_industry_from_context(tool_input, search_type)
                if inferred_industry:
                    for r in results_missing_industry:
                        r["industry"] = inferred_industry

            # Store full results for SSE emission
            self._pending_apollo_results = {
                "results": results,
                "total": total,
                "search_type": search_type,
                "returned": len(results),
                "search_params": tool_input,
            }

            # Update session metadata
            await self.session_service.update_session_metadata(self.session_id, {
                "last_apollo_search": {
                    "type": search_type,
                    "count": total,
                    "returned": len(results),
                    "params": tool_input,
                }
            })

            # Build compact summary for Claude (~200 tokens)
            summary_parts = [f"Found {total} {search_type} total, showing {len(results)}."]
            if search_type == "people" and results:
                titles = {}
                companies = {}
                for r in results[:25]:
                    t = r.get("title", "Unknown")
                    c = r.get("company", "Unknown")
                    titles[t] = titles.get(t, 0) + 1
                    companies[c] = companies.get(c, 0) + 1
                top_titles = sorted(titles.items(), key=lambda x: -x[1])[:5]
                top_companies = sorted(companies.items(), key=lambda x: -x[1])[:5]
                summary_parts.append(f"Top titles: {', '.join(f'{t} ({n})' for t, n in top_titles)}")
                summary_parts.append(f"Top companies: {', '.join(f'{c} ({n})' for c, n in top_companies)}")
            elif search_type == "companies" and results:
                industries = {}
                for r in results[:25]:
                    ind = r.get("industry", "Unknown")
                    industries[ind] = industries.get(ind, 0) + 1
                top_industries = sorted(industries.items(), key=lambda x: -x[1])[:5]
                summary_parts.append(f"Top industries: {', '.join(f'{i} ({n})' for i, n in top_industries)}")

            # Create ApolloSearchHistory record so it appears in Usage page
            session = await self.db.get(ChatSession, self.session_id)
            search_history = ApolloSearchHistory(
                search_type=search_type,
                search_query=tool_input.get("keywords"),
                filters_applied=tool_input,
                results_count=len(results),
                apollo_credits_consumed=0,  # Search is free
                claude_input_tokens=0,
                claude_output_tokens=0,
                cost_apollo_usd=0.0,
                cost_claude_usd=0.0,
                cost_total_usd=0.0,
                client_tag=session.client_tag if session else None,
                session_id=self.session_id,
            )
            self.db.add(search_history)
            await self.db.commit()

            return {
                "summary": " ".join(summary_parts),
                "total": total,
                "returned": len(results),
                "search_type": search_type,
            }

        except Exception as e:
            logger.error(f"Apollo search error: {e}")
            return {"error": str(e), "summary": f"Apollo search failed: {e}"}

    async def _enrich_companies(self, tool_input: dict) -> dict:
        """Enrich companies from last search."""
        session = await self.db.get(ChatSession, self.session_id)
        if not session:
            return {"error": "Session not found", "count": 0}

        # Get company IDs
        if tool_input["company_ids"] == "all":
            # Get from last search metadata
            last_search = session.session_metadata.get("last_apollo_search", {}) if session.session_metadata else {}
            company_ids = last_search.get("company_ids", [])
        else:
            company_ids = tool_input["company_ids"]

        if not company_ids:
            return {"error": "No companies to enrich", "count": 0}

        # Load companies
        result = await self.db.execute(
            select(Company).where(Company.id.in_(company_ids))
        )
        companies = result.scalars().all()

        if not companies:
            return {"error": "Companies not found", "count": 0}

        # Enrich using existing service
        enrichment_service = CompanyEnrichmentService(self.db)
        results = await enrichment_service.enrich_companies_batch(
            companies,
            max_concurrent=tool_input.get("max_concurrent", 3),
            force=tool_input.get("force", False)
        )

        # Commit enrichment updates
        await self.db.commit()

        # Update session metadata
        completed = sum(1 for r in results if r.status == "completed")
        emails_found = sum(len(r.emails_found) for r in results)

        await self.session_service.update_session_metadata(self.session_id, {
            "last_enrichment": {
                "company_ids": [r.company_id for r in results if r.status == "completed"],
                "emails_found": emails_found,
                "completed": completed
            }
        })

        return {
            "summary": f"Enriched {completed}/{len(companies)} companies, found {emails_found} emails",
            "completed": completed,
            "failed": sum(1 for r in results if r.status == "failed"),
            "skipped": len(companies) - completed - sum(1 for r in results if r.status == "failed"),
            "total_emails": emails_found
        }

    async def _verify_emails(self, tool_input: dict) -> dict:
        """Verify emails - placeholder for future implementation."""
        return {
            "summary": "Email verification not yet implemented",
            "verified": 0,
            "invalid": 0,
            "risky": 0
        }

    async def _get_session_context(self, tool_input: dict) -> dict:
        """Return current session state."""
        session = await self.db.get(ChatSession, self.session_id)
        if not session:
            return {"error": "Session not found"}

        return {
            "icp_draft": session.current_icp_draft,
            "last_search": session.session_metadata.get("last_apollo_search") if session.session_metadata else None,
            "last_enrichment": session.session_metadata.get("last_enrichment") if session.session_metadata else None,
            "total_cost_usd": round(session.total_cost_usd, 4),
            "summary": "Session context retrieved"
        }

    async def _update_icp_draft(self, tool_input: dict) -> dict:
        """Update ICP draft in session metadata."""
        session = await self.db.get(ChatSession, self.session_id)
        if not session:
            return {"error": "Session not found"}

        # Merge updates into current draft
        if session.current_icp_draft is None:
            session.current_icp_draft = {}

        session.current_icp_draft.update(tool_input["updates"])

        await self.db.commit()

        return {
            "summary": "ICP draft updated",
            "current_draft": session.current_icp_draft
        }
