"""
CSV mapper service - parses CSV files and uses Claude to map columns
to lead database fields via tool use.
"""
import csv
import io
import json

import anthropic

from app.config import settings

CSV_MAPPING_SYSTEM_PROMPT = """You are a data mapping assistant. You receive CSV column headers \
and sample data, and must map them to lead database fields.

Lead fields to map:
- first_name: The person's first/given name
- last_name: The person's last/family/surname
- email: Email address
- company: Company/organization name
- job_title: Job title/role/position
- linkedin_url: LinkedIn profile URL
- phone: Phone/telephone number

Rules:
- Map each CSV column to the most appropriate lead field
- If a CSV has a single "name" or "full_name" column, map it to first_name and set last_name to null
- If a column clearly does not match any lead field, do not map it
- The email field is the most important - always try to identify it
- Use the map_columns tool to return your mapping"""

CSV_MAPPING_TOOL = {
    "name": "map_columns",
    "description": "Map CSV column headers to lead database fields",
    "input_schema": {
        "type": "object",
        "properties": {
            "first_name": {
                "type": ["string", "null"],
                "description": "CSV column name that maps to first_name",
            },
            "last_name": {
                "type": ["string", "null"],
                "description": "CSV column name that maps to last_name",
            },
            "email": {
                "type": ["string", "null"],
                "description": "CSV column name that maps to email",
            },
            "company": {
                "type": ["string", "null"],
                "description": "CSV column name that maps to company",
            },
            "job_title": {
                "type": ["string", "null"],
                "description": "CSV column name that maps to job_title",
            },
            "linkedin_url": {
                "type": ["string", "null"],
                "description": "CSV column name that maps to linkedin_url",
            },
            "phone": {
                "type": ["string", "null"],
                "description": "CSV column name that maps to phone",
            },
        },
        "required": [
            "first_name",
            "last_name",
            "email",
            "company",
            "job_title",
            "linkedin_url",
            "phone",
        ],
    },
}


class CSVMapperService:
    def __init__(self) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    def parse_csv(self, content: bytes) -> tuple[list[str], list[dict]]:
        """Parse CSV bytes into (headers, rows_as_dicts)."""
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("latin-1")

        reader = csv.DictReader(io.StringIO(text))
        headers = reader.fieldnames or []
        rows = list(reader)
        return headers, rows

    async def map_columns(
        self, headers: list[str], sample_rows: list[dict]
    ) -> dict:
        """Use Claude to map CSV headers to lead fields."""
        sample_text = f"CSV Headers: {headers}\n\nSample data (first 3 rows):\n"
        for i, row in enumerate(sample_rows[:3]):
            sample_text += f"Row {i + 1}: {json.dumps(row)}\n"

        message = await self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=512,
            system=CSV_MAPPING_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": sample_text}],
            tools=[CSV_MAPPING_TOOL],
        )

        for block in message.content:
            if block.type == "tool_use" and block.name == "map_columns":
                return block.input

        return {
            "first_name": None,
            "last_name": None,
            "email": None,
            "company": None,
            "job_title": None,
            "linkedin_url": None,
            "phone": None,
        }


csv_mapper_service = CSVMapperService()
