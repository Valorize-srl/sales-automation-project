from typing import Optional
"""
AI reply generation service.
Uses Claude to generate a suggested reply for an inbound email.
Sentiment is imported from Instantly's ai_interest_value.
"""
import logging

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

REPLY_SYSTEM_PROMPT = """\
You are an expert B2B email reply writer. You will be given an inbound \
email response from a prospect in a cold outreach campaign, along with \
the detected sentiment.

Your job is to generate an appropriate reply.

Reply guidelines based on sentiment:
- For "interested": Enthusiastic but professional, propose a specific next step \
(meeting, call, demo)
- For "positive": Nurture the relationship, provide value, gently move toward a meeting
- For "neutral" or unknown: Polite follow-up, try to re-engage with a different value proposition
- For "negative": Do NOT generate a reply. Return null.

Keep replies concise (under 100 words), conversational, and non-salesy.
Use the generate_reply tool to return your result."""

REPLY_TOOL = {
    "name": "generate_reply",
    "description": "Save the generated reply for an email response.",
    "input_schema": {
        "type": "object",
        "properties": {
            "suggested_reply": {
                "type": ["string", "null"],
                "description": "Suggested reply text, or null for negative sentiment",
            },
        },
        "required": ["suggested_reply"],
    },
}


class ReplyService:
    def __init__(self) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def generate_reply(
        self,
        email_body: str,
        lead_name: Optional[str] = None,
        lead_company: Optional[str] = None,
        campaign_name: Optional[str] = None,
        sentiment: Optional[str] = None,
    ) -> Optional[str]:
        """Generate a reply suggestion using Claude."""
        user_message = f"""Generate a reply for this inbound email:

**Prospect Email:**
{email_body}"""

        if lead_name:
            user_message += f"\n\n**Prospect Name:** {lead_name}"
        if lead_company:
            user_message += f"\n**Prospect Company:** {lead_company}"
        if campaign_name:
            user_message += f"\n**Campaign:** {campaign_name}"
        if sentiment:
            user_message += f"\n**Detected Sentiment:** {sentiment}"

        try:
            message = await self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1024,
                system=REPLY_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
                tools=[REPLY_TOOL],
            )

            for block in message.content:
                if block.type == "tool_use" and block.name == "generate_reply":
                    return block.input.get("suggested_reply")

        except Exception as e:
            logger.error(f"Claude reply generation error: {e}")
            raise

        return None


reply_service = ReplyService()
