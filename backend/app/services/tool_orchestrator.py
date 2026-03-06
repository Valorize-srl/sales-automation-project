"""Tool orchestrator for multi-turn tool execution in conversational chat."""

import json
import time
import logging
from typing import AsyncIterator, Optional

from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_execution import ToolExecution
from app.config import settings as app_settings
from app.services.chat_session import ChatSessionService
from app.services.tool_definitions import get_tools_for_mode
from app.services.tool_handlers import TOOL_HANDLERS

logger = logging.getLogger(__name__)


class ToolOrchestrator:
    """
    Orchestrator for multi-turn tool execution with streaming.

    Manages Claude tool use, execution, and multi-turn loops.
    Dispatches tool calls to handlers via TOOL_HANDLERS registry.
    """

    def __init__(self, db: AsyncSession, session_id: int, anthropic_api_key: str = "", tools_mode: str = "all"):
        self.db = db
        self.session_id = session_id
        api_key = anthropic_api_key or app_settings.anthropic_api_key
        self.client = AsyncAnthropic(api_key=api_key)
        self.session_service = ChatSessionService(db)
        self.tools = get_tools_for_mode(tools_mode)

    async def execute_and_continue(
        self,
        messages: list[dict],
        system_prompt: str,
        max_iterations: int = 10
    ) -> AsyncIterator[str]:
        """
        Multi-turn tool execution loop with streaming.

        Flow:
        1. Call Claude with messages + tools
        2. Stream text chunks as SSE
        3. If tool_use blocks in response:
           a. Execute tools via handler registry
           b. Yield tool progress + extra SSE events
           c. Add tool results to messages
           d. Loop back to step 1
        4. If no tool_use or max iterations: done

        Yields:
            SSE events (text, tool_start, tool_complete, search_results, csv_ready, import_complete, done)
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
                    async for event in stream:
                        if event.type == "content_block_delta":
                            if hasattr(event.delta, "text"):
                                yield f"data: {json.dumps({'type': 'text', 'content': event.delta.text})}\n\n"

                    final_message = await stream.get_final_message()
                    assistant_content_blocks = final_message.content

                    if final_message.usage:
                        total_input_tokens += final_message.usage.input_tokens
                        total_output_tokens += final_message.usage.output_tokens

                    for block in final_message.content:
                        if block.type == "tool_use":
                            tool_uses.append(block)

            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
                break

            # No tools? Done
            if not tool_uses:
                yield f"data: {json.dumps({'type': 'usage', 'input_tokens': total_input_tokens, 'output_tokens': total_output_tokens})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break

            # Execute tools
            tool_results = []
            for tool_use in tool_uses:
                yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_use.name, 'input': tool_use.input})}\n\n"

                try:
                    result, sse_extra = await self.execute_tool(tool_use.name, tool_use.input, tool_use.id)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(result)
                    })

                    yield f"data: {json.dumps({'type': 'tool_complete', 'tool': tool_use.name, 'summary': result.get('summary', 'Completed')})}\n\n"

                    # Emit extra SSE event if handler returned one
                    if sse_extra:
                        yield f"data: {json.dumps(sse_extra)}\n\n"

                except Exception as e:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps({"error": str(e)}),
                        "is_error": True
                    })
                    yield f"data: {json.dumps({'type': 'tool_error', 'tool': tool_use.name, 'error': str(e)})}\n\n"

            # Add assistant message + tool results to conversation
            current_messages.append({
                "role": "assistant",
                "content": assistant_content_blocks
            })
            current_messages.append({
                "role": "user",
                "content": tool_results
            })

        if iteration >= max_iterations:
            yield f"data: {json.dumps({'type': 'usage', 'input_tokens': total_input_tokens, 'output_tokens': total_output_tokens})}\n\n"
            yield f"data: {json.dumps({'type': 'error', 'content': 'Max iterations reached'})}\n\n"

    async def execute_tool(
        self,
        tool_name: str,
        tool_input: dict,
        tool_call_id: str
    ) -> tuple[dict, Optional[dict]]:
        """
        Execute a single tool via handler registry and log execution.

        Returns:
            (result_for_claude, optional_sse_extra_event)
        """
        start_time = time.time()

        try:
            handler = TOOL_HANDLERS.get(tool_name)
            if not handler:
                raise ValueError(f"Unknown tool: {tool_name}")

            result, sse_extra = await handler(self.db, self.session_id, tool_input, self.session_service)

            execution_time_ms = int((time.time() - start_time) * 1000)
            await self._log_tool_execution(
                tool_name, tool_call_id, tool_input, result, "success", execution_time_ms
            )

            return result, sse_extra

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            await self._log_tool_execution(
                tool_name, tool_call_id, tool_input, {"error": str(e)}, "error",
                execution_time_ms, error_message=str(e)
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
