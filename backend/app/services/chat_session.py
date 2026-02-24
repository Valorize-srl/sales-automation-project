"""Chat session service for managing conversational sessions."""

import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage
from app.models.tool_execution import ToolExecution


class ChatSessionService:
    """Service for managing chat sessions and conversation context."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(
        self,
        client_tag: Optional[str] = None,
        title: Optional[str] = None
    ) -> ChatSession:
        """
        Create new chat session with UUID.

        Args:
            client_tag: Optional client/project tag
            title: Optional session title

        Returns:
            Created ChatSession
        """
        session = ChatSession(
            session_uuid=str(uuid.uuid4()),
            title=title,
            client_tag=client_tag,
            status="active",
            session_metadata={}
        )

        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        return session

    async def get_session(self, session_uuid: str) -> Optional[ChatSession]:
        """
        Get session by UUID with messages loaded.

        Args:
            session_uuid: Session UUID

        Returns:
            ChatSession or None if not found
        """
        result = await self.db.execute(
            select(ChatSession)
            .options(selectinload(ChatSession.messages))
            .where(ChatSession.session_uuid == session_uuid)
        )
        return result.scalar_one_or_none()

    async def add_message(
        self,
        session_id: int,
        role: str,
        content: str,
        tool_calls: Optional[list] = None,
        tool_results: Optional[list] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        message_metadata: Optional[dict] = None
    ) -> ChatMessage:
        """
        Add message to session and update session stats.

        Args:
            session_id: Session ID
            role: Message role (user, assistant, tool_result)
            content: Message content
            tool_calls: Optional tool_use blocks from Claude
            tool_results: Optional tool results
            input_tokens: Claude input tokens for this message
            output_tokens: Claude output tokens for this message
            message_metadata: Optional metadata (file attachments, etc.)

        Returns:
            Created ChatMessage
        """
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_results=tool_results,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            message_metadata=message_metadata
        )

        self.db.add(message)

        # Update session stats
        session = await self.db.get(ChatSession, session_id)
        if session:
            session.total_claude_input_tokens += input_tokens
            session.total_claude_output_tokens += output_tokens
            session.last_message_at = datetime.utcnow()

            # Calculate cost (Claude Sonnet 4.5 pricing: $3/M input, $15/M output)
            claude_input_cost = (input_tokens / 1_000_000) * 3.0
            claude_output_cost = (output_tokens / 1_000_000) * 15.0
            session.total_cost_usd += claude_input_cost + claude_output_cost

        await self.db.commit()
        await self.db.refresh(message)

        return message

    async def get_conversation_context(
        self,
        session_id: int,
        max_messages: int = 20,
        max_tokens: int = 8000
    ) -> list[dict]:
        """
        Build API-ready message list with context window management.

        Strategy:
        - Always include first message (sets context)
        - Include last N messages
        - Summarize middle messages if needed
        - Always include tool calls/results

        Args:
            session_id: Session ID
            max_messages: Max messages to include
            max_tokens: Approximate max tokens (for future token counting)

        Returns:
            List of message dicts ready for Claude API
        """
        # Get all messages ordered by creation
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
        all_messages = result.scalars().all()

        if not all_messages:
            return []

        # If total messages <= max_messages, return all
        if len(all_messages) <= max_messages:
            return [self._format_message(m) for m in all_messages]

        # Otherwise: first + last (max_messages - 1) + summary
        first_message = all_messages[0]
        recent_messages = all_messages[-(max_messages - 1):]
        middle_count = len(all_messages) - max_messages

        # Build context
        context = [self._format_message(first_message)]

        # Add summary of middle messages
        if middle_count > 0:
            summary_message = {
                "role": "assistant",
                "content": f"[Previous conversation: {middle_count} messages about ICP definition and lead search]"
            }
            context.append(summary_message)

        # Add recent messages
        context.extend([self._format_message(m) for m in recent_messages])

        return context

    def _format_message(self, message: ChatMessage) -> dict:
        """
        Format ChatMessage for Claude API.

        Args:
            message: ChatMessage instance

        Returns:
            Dict in Claude API format
        """
        # Basic message format
        msg_dict = {
            "role": message.role,
            "content": message.content
        }

        # If tool_calls present, format as Claude expects
        if message.tool_calls:
            msg_dict["content"] = message.tool_calls

        # If tool_results present, format as tool result message
        if message.tool_results:
            msg_dict["content"] = message.tool_results

        return msg_dict

    async def update_session_metadata(
        self,
        session_id: int,
        metadata_updates: dict
    ):
        """
        Merge updates into session.session_metadata.

        Args:
            session_id: Session ID
            metadata_updates: Dict of updates to merge
        """
        session = await self.db.get(ChatSession, session_id)
        if not session:
            return

        # Merge metadata
        if session.session_metadata is None:
            session.session_metadata = {}

        session.session_metadata.update(metadata_updates)

        await self.db.commit()

    async def get_session_summary(self, session_id: int) -> dict:
        """
        Get session statistics.

        Args:
            session_id: Session ID

        Returns:
            Dict with stats: message_count, tools_used, costs, etc.
        """
        session = await self.db.get(ChatSession, session_id)
        if not session:
            return {}

        # Count messages
        message_count_result = await self.db.execute(
            select(func.count(ChatMessage.id))
            .where(ChatMessage.session_id == session_id)
        )
        message_count = message_count_result.scalar()

        # Count tool executions by type
        tool_stats_result = await self.db.execute(
            select(
                ToolExecution.tool_name,
                func.count(ToolExecution.id).label("count")
            )
            .where(ToolExecution.session_id == session_id)
            .group_by(ToolExecution.tool_name)
        )
        tool_stats = {row.tool_name: row.count for row in tool_stats_result}

        return {
            "session_id": session_id,
            "session_uuid": session.session_uuid,
            "message_count": message_count,
            "tool_stats": tool_stats,
            "total_claude_input_tokens": session.total_claude_input_tokens,
            "total_claude_output_tokens": session.total_claude_output_tokens,
            "total_apollo_credits": session.total_apollo_credits,
            "total_cost_usd": round(session.total_cost_usd, 4),
            "status": session.status,
            "created_at": session.created_at.isoformat(),
            "last_message_at": session.last_message_at.isoformat() if session.last_message_at else None
        }

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
        query = select(ChatSession).order_by(desc(ChatSession.updated_at))

        if client_tag:
            query = query.where(ChatSession.client_tag == client_tag)
        if status:
            query = query.where(ChatSession.status == status)

        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def archive_session(self, session_uuid: str):
        """
        Mark session as archived.

        Args:
            session_uuid: Session UUID
        """
        session = await self.get_session(session_uuid)
        if session:
            session.status = "archived"
            await self.db.commit()
