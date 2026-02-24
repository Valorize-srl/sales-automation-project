"""
AI Replier Service - Generate AI-powered email replies using agent's knowledge base.

This service:
1. Takes an email response from a campaign
2. Uses the associated AI Agent's knowledge base as context
3. Generates a suggested reply using Claude
4. Allows human approval before sending via Instantly
"""
import logging
from typing import Optional

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.email_response import EmailResponse, ResponseStatus
from app.models.ai_agent import AIAgent
from app.models.person import Person
from app.services.instantly import instantly_service

logger = logging.getLogger(__name__)


# AI Reply generation system prompt
AI_REPLY_SYSTEM_PROMPT = """\
You are an AI email reply assistant for a B2B sales team. You will receive:
1. Context about the sender (company, role, previous interactions)
2. The original email they sent to us
3. A knowledge base about our company/offering

Your task is to generate a professional, helpful, personalized reply that:
- Addresses their questions or concerns
- Provides relevant information from the knowledge base
- Maintains a conversational, non-salesy tone
- Suggests next steps (call, demo, meeting)
- Is concise (under 200 words)

Use the generate_reply tool to return your suggested response."""

AI_REPLY_TOOL = {
    "name": "generate_reply",
    "description": "Generate an AI-suggested email reply",
    "input_schema": {
        "type": "object",
        "properties": {
            "subject": {
                "type": "string",
                "description": "Email subject line (usually Re: original subject)",
            },
            "body": {
                "type": "string",
                "description": "Email body text (plain text or light HTML)",
            },
            "tone": {
                "type": "string",
                "enum": ["professional", "friendly", "enthusiastic", "concise"],
                "description": "Tone of the reply",
            },
            "call_to_action": {
                "type": "string",
                "description": "Suggested next step (e.g., 'Schedule a 15-min call', 'Review pricing', etc.)",
            },
        },
        "required": ["subject", "body", "tone", "call_to_action"],
    },
}


class AIReplierService:
    """Service for generating AI-powered email replies using agent knowledge base."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    # ==============================================================================
    # AI Reply Generation
    # ==============================================================================

    async def generate_reply(
        self,
        email_response_id: int,
        ai_agent_id: Optional[int] = None,
    ) -> dict:
        """
        Generate AI-suggested reply using agent's knowledge base.

        Args:
            email_response_id: EmailResponse ID
            ai_agent_id: Optional AI Agent ID (if not set on email_response)

        Returns:
            dict with: subject, body, tone, call_to_action
        """
        # Get email response
        email_response = await self._get_email_response(email_response_id)
        if not email_response:
            raise ValueError(f"EmailResponse {email_response_id} not found")

        # Get AI Agent
        agent = None
        if ai_agent_id:
            agent = await self._get_agent(ai_agent_id)
        elif email_response.ai_agent_id:
            agent = await self._get_agent(email_response.ai_agent_id)
        elif email_response.campaign_id:
            # Try to find agent from campaign association
            agent = await self._get_agent_from_campaign(email_response.campaign_id)

        if not agent:
            raise ValueError("No AI Agent associated with this email response")

        # Get sender info (person)
        sender_info = await self._get_sender_info(email_response)

        # Build context message
        user_message = self._build_user_message(
            agent=agent,
            email_response=email_response,
            sender_info=sender_info,
        )

        # Call Claude with tool use
        response = await self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            system=AI_REPLY_SYSTEM_PROMPT,
            tools=[AI_REPLY_TOOL],
            messages=[
                {
                    "role": "user",
                    "content": user_message,
                }
            ],
        )

        # Extract tool use result
        reply_data = None
        for block in response.content:
            if block.type == "tool_use" and block.name == "generate_reply":
                reply_data = block.input
                break

        if not reply_data:
            # Fallback: extract text content
            text_content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text_content += block.text

            if text_content:
                reply_data = {
                    "subject": f"Re: {email_response.subject}",
                    "body": text_content,
                    "tone": "professional",
                    "call_to_action": "Let me know if you'd like to discuss further.",
                }
            else:
                raise ValueError("Claude did not return a valid reply")

        # Update email_response with AI suggestion
        email_response.ai_suggested_reply = reply_data["body"]
        email_response.ai_agent_id = agent.id
        email_response.status = ResponseStatus.AI_REPLIED
        await self.db.commit()

        logger.info(f"🤖 Generated AI reply for EmailResponse {email_response_id}")

        return reply_data

    def _build_user_message(
        self,
        agent: AIAgent,
        email_response: EmailResponse,
        sender_info: Optional[dict],
    ) -> str:
        """Build user message for Claude with all context."""
        kb_text = agent.knowledge_base_text or "No knowledge base available."

        # Truncate KB if too long (keep first 8000 chars)
        if len(kb_text) > 8000:
            kb_text = kb_text[:8000] + "\n\n[Knowledge base truncated for length]"

        sender_name = "Unknown"
        sender_company = "Unknown Company"
        sender_role = "Unknown"

        if sender_info:
            sender_name = f"{sender_info.get('first_name', '')} {sender_info.get('last_name', '')}".strip() or "Unknown"
            sender_company = sender_info.get('company_name') or "Unknown Company"
            sender_role = sender_info.get('title') or "Unknown"

        message = f"""**Sender Information:**
- Name: {sender_name}
- Company: {sender_company}
- Role: {sender_role}
- Email: {email_response.from_email or 'N/A'}

**Original Email:**
Subject: {email_response.subject}

{email_response.message_body or 'No message body'}

**Our Company Knowledge Base:**
{kb_text}

**Instructions:**
Generate a professional, helpful reply to {sender_name} from {sender_company}.
Use information from the knowledge base to answer their questions or provide value.
Keep the tone {agent.icp_config.get('preferred_tone', 'professional and friendly')}.
"""

        return message

    # ==============================================================================
    # Approve & Send Reply
    # ==============================================================================

    async def approve_and_send_reply(
        self,
        email_response_id: int,
        approved_body: str,
        approved_subject: Optional[str] = None,
        sender_email: Optional[str] = None,
    ) -> dict:
        """
        Approve AI-generated reply and send via Instantly.

        Args:
            email_response_id: EmailResponse ID
            approved_body: Human-approved reply text (can be edited)
            approved_subject: Optional subject (defaults to "Re: {original}")
            sender_email: Email account to send from (must be in campaign)

        Returns:
            dict with: status, message
        """
        # Get email response
        email_response = await self._get_email_response(email_response_id)
        if not email_response:
            raise ValueError(f"EmailResponse {email_response_id} not found")

        if not email_response.instantly_email_id:
            raise ValueError("EmailResponse has no instantly_email_id - cannot reply")

        # Use approved text
        email_response.human_approved_reply = approved_body

        # Default subject
        if not approved_subject:
            approved_subject = f"Re: {email_response.subject}" if email_response.subject else "Re: Your message"

        # Default sender email
        if not sender_email and email_response.sender_email:
            sender_email = email_response.sender_email

        if not sender_email:
            raise ValueError("No sender email specified for reply")

        # Prepare Instantly reply payload
        reply_payload = {
            "reply_to_uuid": email_response.instantly_email_id,
            "eaccount": sender_email,
            "subject": approved_subject,
            "body": {
                "html": f"<div>{approved_body.replace(chr(10), '<br>')}</div>",
                "text": approved_body,
            },
        }

        # Send via Instantly
        try:
            result = await instantly_service.reply_to_email(reply_payload)
            logger.info(f"✅ Sent email reply via Instantly: {result}")

            # Update status
            email_response.status = ResponseStatus.SENT
            await self.db.commit()

            return {
                "status": "sent",
                "message": "Reply sent successfully",
                "instantly_result": result,
            }

        except Exception as e:
            logger.error(f"❌ Failed to send reply via Instantly: {e}")
            email_response.status = ResponseStatus.HUMAN_APPROVED  # Mark as approved but not sent
            await self.db.commit()

            return {
                "status": "error",
                "message": f"Failed to send reply: {str(e)}",
            }

    async def approve_reply_without_sending(
        self,
        email_response_id: int,
        approved_body: str,
    ) -> EmailResponse:
        """
        Approve reply without sending (for manual sending later).

        Args:
            email_response_id: EmailResponse ID
            approved_body: Human-approved reply text

        Returns:
            Updated EmailResponse
        """
        email_response = await self._get_email_response(email_response_id)
        if not email_response:
            raise ValueError(f"EmailResponse {email_response_id} not found")

        email_response.human_approved_reply = approved_body
        email_response.status = ResponseStatus.HUMAN_APPROVED
        await self.db.commit()

        logger.info(f"✅ Approved reply for EmailResponse {email_response_id} (not sent)")

        return email_response

    async def ignore_response(self, email_response_id: int) -> EmailResponse:
        """Mark email response as ignored (no reply needed)."""
        email_response = await self._get_email_response(email_response_id)
        if not email_response:
            raise ValueError(f"EmailResponse {email_response_id} not found")

        email_response.status = ResponseStatus.IGNORED
        await self.db.commit()

        logger.info(f"🚫 Ignored EmailResponse {email_response_id}")

        return email_response

    # ==============================================================================
    # Helper Methods
    # ==============================================================================

    async def _get_email_response(self, email_response_id: int) -> Optional[EmailResponse]:
        """Get email response by ID."""
        result = await self.db.execute(
            select(EmailResponse).where(EmailResponse.id == email_response_id)
        )
        return result.scalar_one_or_none()

    async def _get_agent(self, agent_id: int) -> Optional[AIAgent]:
        """Get AI Agent by ID."""
        result = await self.db.execute(
            select(AIAgent).where(AIAgent.id == agent_id)
        )
        return result.scalar_one_or_none()

    async def _get_agent_from_campaign(self, campaign_id: int) -> Optional[AIAgent]:
        """Get AI Agent associated with a campaign."""
        from app.models.ai_agent_campaign import AIAgentCampaign

        result = await self.db.execute(
            select(AIAgent)
            .join(AIAgentCampaign, AIAgentCampaign.ai_agent_id == AIAgent.id)
            .where(AIAgentCampaign.campaign_id == campaign_id)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_sender_info(self, email_response: EmailResponse) -> Optional[dict]:
        """Get sender (person) information if available."""
        if not email_response.lead_id:
            return None

        result = await self.db.execute(
            select(Person).where(Person.id == email_response.lead_id)
        )
        person = result.scalar_one_or_none()

        if not person:
            return None

        return {
            "first_name": person.first_name,
            "last_name": person.last_name,
            "company_name": person.company_name,
            "title": person.title,
            "email": person.email,
            "linkedin_url": person.linkedin_url,
        }


# Dependency injection helper
async def get_ai_replier_service(db: AsyncSession) -> AIReplierService:
    """Dependency injection helper for FastAPI routes."""
    return AIReplierService(db)
