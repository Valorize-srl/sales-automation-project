"""
Email template generator - uses Claude to create personalized email sequences
for outreach campaigns based on ICP data.
"""
import anthropic

from app.config import settings

EMAIL_GENERATION_SYSTEM_PROMPT = """\
You are a B2B cold email copywriting expert. Generate professional, personalized \
email sequences for outreach campaigns.

You will be given an Ideal Customer Profile (ICP) describing the target audience, \
the number of subject line variations, and the number of email steps to generate.

Rules:
- Subject lines: short, curiosity-driven, no spam words
- Emails: concise (under 150 words), professional, conversational, non-salesy
- Use personalization placeholders: {{first_name}}, {{company}}, {{job_title}}
- Step 1 is the initial outreach, subsequent steps are follow-ups
- Follow-ups should reference the previous email and add new value
- wait_days: step 1 = 0, step 2 = 3, step 3 = 5, etc.

Use the save_templates tool to return the generated templates."""

EMAIL_TEMPLATE_TOOL = {
    "name": "save_templates",
    "description": "Save the generated email subject lines and sequence steps.",
    "input_schema": {
        "type": "object",
        "properties": {
            "subject_lines": {
                "type": "array",
                "items": {"type": "string"},
                "description": "A/B test subject line variations",
            },
            "email_steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "step": {"type": "integer"},
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                        "wait_days": {"type": "integer"},
                    },
                    "required": ["step", "subject", "body", "wait_days"],
                },
                "description": "Ordered email sequence steps",
            },
        },
        "required": ["subject_lines", "email_steps"],
    },
}


class EmailGeneratorService:
    def __init__(self) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def generate_templates(
        self,
        icp_data: dict,
        num_subject_lines: int = 3,
        num_steps: int = 3,
        additional_context: str | None = None,
    ) -> dict:
        """Generate email templates based on ICP data using Claude tool use."""
        user_message = f"""Generate email templates for this outreach campaign:

**Ideal Customer Profile:**
- Industry: {icp_data.get('industry', 'N/A')}
- Company Size: {icp_data.get('company_size', 'N/A')}
- Target Job Titles: {icp_data.get('job_titles', 'N/A')}
- Geography: {icp_data.get('geography', 'N/A')}
- Revenue Range: {icp_data.get('revenue_range', 'N/A')}
- Keywords/Technologies: {icp_data.get('keywords', 'N/A')}
- Description: {icp_data.get('description', 'N/A')}

**Requirements:**
- {num_subject_lines} subject line variations
- {num_steps} email steps in the sequence"""

        if additional_context:
            user_message += f"\n\n**Additional Instructions:**\n{additional_context}"

        message = await self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2048,
            system=EMAIL_GENERATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            tools=[EMAIL_TEMPLATE_TOOL],
        )

        for block in message.content:
            if block.type == "tool_use" and block.name == "save_templates":
                return block.input

        return {"subject_lines": [], "email_steps": []}


email_generator_service = EmailGeneratorService()
