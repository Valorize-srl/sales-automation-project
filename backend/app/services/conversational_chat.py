"""Conversational chat service with RAG capabilities."""

import json
from typing import Optional, AsyncIterator
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.chat_session import ChatSessionService
from app.services.tool_orchestrator import ToolOrchestrator
from app.models.chat_session import ChatSession


# Conversational system prompt with RAG capabilities
CONVERSATIONAL_SYSTEM_PROMPT = """You are an AI sales assistant helping B2B professionals find and qualify leads through conversation.

**Personality:**
- Proactive and helpful
- Ask clarifying questions
- Suggest next logical steps
- Speak naturally in user's language (Italian/English)
- Concise but friendly

**Capabilities:**

1. **ICP Definition** - Help define Ideal Customer Profile:
   - Use `update_icp_draft` to build incrementally
   - When complete, use `save_icp`

2. **Lead Search** - Search Apollo.io:
   - When user says "find X", call `search_apollo`
   - After search, summarize and suggest next steps
   - Proactively offer: "Want me to enrich with contact emails?"

3. **Data Enrichment** - Enrich companies with website emails:
   - When user says "find their emails" or "enrich", call `enrich_companies`
   - Use company_ids from session metadata (last search)
   - Report success rate

4. **Email Verification** - Validate deliverability:
   - Call `verify_emails` when user wants validation
   - Explain confidence scores

5. **Session Awareness** - Remember context:
   - Reference previous searches
   - Build on existing ICP drafts
   - Use `get_session_context` if needed

**Behavior:**
- Be PROACTIVE: After tool completion, suggest next steps
- Ask before destructive actions: "Should I save this ICP?"
- Summarize tool results in natural language
- Multi-step workflows: Guide through search → enrich → verify → import

**Example Flow:**
User: "Sto cercando aziende vinicole in Toscana"
You: [call update_icp_draft] [call search_apollo]
     "Ho trovato 45 aziende vinicole in Toscana con 10-50 dipendenti.
      Vuoi che cerchi le loro email di contatto?"

User: "Sì"
You: [call enrich_companies with company_ids from session]
     "Ho arricchito 45 aziende, trovato 120 email generiche.
      Vuoi importarle o preferisci verificare prima la deliverability?"
"""


class ConversationalChatService:
    """Main orchestrator for conversational chat with RAG capabilities."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.session_service = ChatSessionService(db)

    async def stream_chat(
        self,
        session_uuid: str,
        user_message: str,
        file_content: Optional[str] = None
    ) -> AsyncIterator[str]:
        """
        Main entry point for conversational chat with streaming.

        Args:
            session_uuid: Session UUID
            user_message: User's message
            file_content: Optional file content uploaded by user

        Yields:
            SSE events: text chunks, tool progress, completion
        """
        # Get or create session
        session = await self.session_service.get_session(session_uuid)
        if not session:
            # Create new session if doesn't exist
            session = await self.session_service.create_session()

        # Add user message to DB
        message_metadata = {}
        if file_content:
            message_metadata["has_file_attachment"] = True

        await self.session_service.add_message(
            session_id=session.id,
            role="user",
            content=user_message,
            message_metadata=message_metadata if message_metadata else None
        )

        # Build conversation context (last 20 messages)
        messages = await self.session_service.get_conversation_context(
            session_id=session.id,
            max_messages=20
        )

        # Add file content to last user message if present
        if file_content and messages:
            last_message = messages[-1]
            if last_message["role"] == "user":
                last_message["content"] += f"\n\nUploaded document:\n{file_content}"

        # Build dynamic system prompt with session context
        system_prompt = self._build_system_prompt(session)

        # Initialize tool orchestrator and stream with multi-turn orchestration
        orchestrator = ToolOrchestrator(self.db, session.id)

        try:
            async for event in orchestrator.execute_and_continue(
                messages=messages,
                system_prompt=system_prompt,
                max_iterations=5
            ):
                yield event

        except Exception as e:
            # Yield error event
            error_event = {
                "type": "error",
                "error": str(e),
                "message": "An error occurred during conversation processing"
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    def _build_system_prompt(self, session: ChatSession) -> str:
        """
        Build context-aware system prompt with session metadata.

        Args:
            session: ChatSession instance

        Returns:
            System prompt string with context
        """
        prompt = CONVERSATIONAL_SYSTEM_PROMPT

        # Add current ICP draft if exists
        if session.current_icp_draft:
            icp_draft_str = json.dumps(session.current_icp_draft, indent=2)
            prompt += f"\n\n**Current ICP Draft:**\n{icp_draft_str}"
            prompt += "\n\nYou can reference or update this draft using `update_icp_draft` tool."

        # Add last search context if exists
        if session.session_metadata and session.session_metadata.get("last_apollo_search"):
            search = session.session_metadata["last_apollo_search"]
            prompt += f"\n\n**Last Search Results:**"
            prompt += f"\n- Type: {search.get('type', 'unknown')}"
            prompt += f"\n- Count: {search.get('count', 0)} results found"

            # Include company IDs for enrichment
            if search.get("company_ids"):
                company_ids = search["company_ids"]
                if len(company_ids) > 10:
                    prompt += f"\n- Company IDs available: {company_ids[:10]}... (total: {len(company_ids)})"
                else:
                    prompt += f"\n- Company IDs available: {company_ids}"

                prompt += f"\n\nWhen user asks to 'enrich' or 'find contacts', use these company_ids with `enrich_companies` tool."

        # Add last enrichment context if exists
        if session.session_metadata and session.session_metadata.get("last_enrichment"):
            enrichment = session.session_metadata["last_enrichment"]
            prompt += f"\n\n**Last Enrichment:**"
            prompt += f"\n- Companies enriched: {enrichment.get('completed', 0)}"
            prompt += f"\n- Emails found: {enrichment.get('emails_found', 0)}"

        # Add session stats for context
        prompt += f"\n\n**Session Stats:**"
        prompt += f"\n- Total cost so far: ${session.total_cost_usd:.4f}"
        prompt += f"\n- Apollo credits used: {session.total_apollo_credits}"
        prompt += f"\n- Messages in conversation: {len(session.messages)}"

        return prompt

    async def create_session(
        self,
        client_tag: Optional[str] = None,
        title: Optional[str] = None
    ) -> ChatSession:
        """
        Create new chat session.

        Args:
            client_tag: Optional client/project tag
            title: Optional session title

        Returns:
            Created ChatSession
        """
        return await self.session_service.create_session(
            client_tag=client_tag,
            title=title
        )

    async def get_session(self, session_uuid: str) -> Optional[ChatSession]:
        """
        Get session by UUID.

        Args:
            session_uuid: Session UUID

        Returns:
            ChatSession or None if not found
        """
        return await self.session_service.get_session(session_uuid)

    async def get_session_summary(self, session_uuid: str) -> dict:
        """
        Get session statistics and summary.

        Args:
            session_uuid: Session UUID

        Returns:
            Dict with stats: message_count, tools_used, costs, etc.
        """
        session = await self.session_service.get_session(session_uuid)
        if not session:
            return {}

        return await self.session_service.get_session_summary(session.id)

    async def list_sessions(
        self,
        client_tag: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> list[ChatSession]:
        """
        List sessions with pagination.

        Args:
            client_tag: Filter by client tag
            status: Filter by status
            limit: Max sessions to return
            offset: Offset for pagination

        Returns:
            List of ChatSession
        """
        return await self.session_service.list_sessions(
            client_tag=client_tag,
            status=status,
            limit=limit,
            offset=offset
        )

    async def archive_session(self, session_uuid: str):
        """
        Mark session as archived.

        Args:
            session_uuid: Session UUID
        """
        await self.session_service.archive_session(session_uuid)
