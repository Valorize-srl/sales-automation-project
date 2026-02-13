"""
Combined sentiment analysis + reply generation service.
Uses a single Claude tool-use call per email to analyze sentiment
AND generate a suggested reply.
"""
import logging

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

SENTIMENT_REPLY_SYSTEM_PROMPT = """\
You are an expert B2B email analyst and reply writer. You will be given an inbound \
email response from a prospect in a cold outreach campaign.

Your job:
1. Analyze the sentiment of the email
2. Generate an appropriate reply suggestion

Sentiment categories:
- "interested": Prospect shows genuine interest, asks questions, wants to learn more, \
requests a meeting/call, or engages positively with the offer
- "positive": Friendly but non-committal, polite acknowledgment, warm response but \
no clear buying signal
- "neutral": Automated replies, out-of-office, forwarded to someone else, \
ambiguous responses
- "negative": Explicit rejection, unsubscribe request, hostile tone, "not interested", \
"remove me from your list"

Sentiment score: 0.0 (most negative) to 1.0 (most positive/interested)

Reply guidelines:
- For "interested": Enthusiastic but professional, propose a specific next step \
(meeting, call, demo)
- For "positive": Nurture the relationship, provide value, gently move toward a meeting
- For "neutral": Polite follow-up, try to re-engage with a different value proposition
- For "negative": Do NOT generate a reply. Set suggested_reply to null.

Keep replies concise (under 100 words), conversational, and non-salesy.
Use the analyze_and_reply tool to return your analysis."""

SENTIMENT_REPLY_TOOL = {
    "name": "analyze_and_reply",
    "description": "Save the sentiment analysis and suggested reply for an email response.",
    "input_schema": {
        "type": "object",
        "properties": {
            "sentiment": {
                "type": "string",
                "enum": ["interested", "positive", "neutral", "negative"],
                "description": "The sentiment category of the prospect's email",
            },
            "sentiment_score": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Sentiment score from 0.0 (negative) to 1.0 (interested)",
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of why this sentiment was assigned",
            },
            "suggested_reply": {
                "type": ["string", "null"],
                "description": "Suggested reply text, or null for negative sentiment",
            },
        },
        "required": ["sentiment", "sentiment_score", "reasoning", "suggested_reply"],
    },
}


class SentimentReplyService:
    def __init__(self) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def analyze_and_generate_reply(
        self,
        email_body: str,
        lead_name: str | None = None,
        lead_company: str | None = None,
        campaign_name: str | None = None,
    ) -> dict:
        """Analyze sentiment and generate a reply suggestion in one Claude call."""
        user_message = f"""Analyze this inbound email response and generate a reply suggestion:

**Prospect Email:**
{email_body}"""

        if lead_name:
            user_message += f"\n\n**Prospect Name:** {lead_name}"
        if lead_company:
            user_message += f"\n**Prospect Company:** {lead_company}"
        if campaign_name:
            user_message += f"\n**Campaign:** {campaign_name}"

        try:
            message = await self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1024,
                system=SENTIMENT_REPLY_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
                tools=[SENTIMENT_REPLY_TOOL],
            )

            for block in message.content:
                if block.type == "tool_use" and block.name == "analyze_and_reply":
                    return block.input

        except Exception as e:
            logger.error(f"Claude sentiment/reply error: {e}")

        return {
            "sentiment": "neutral",
            "sentiment_score": 0.5,
            "reasoning": "Analysis failed - defaulted to neutral",
            "suggested_reply": None,
        }


sentiment_reply_service = SentimentReplyService()
