"""
CSV mapper service - parses CSV files and uses Claude to map columns
to lead database fields via tool use. Unmapped columns are saved as custom_fields.
"""
import csv
import io
import json

import anthropic

from app.config import settings

# All known lead fields that Claude can map to
KNOWN_FIELDS = [
    "first_name", "last_name", "email", "company", "job_title",
    "industry", "linkedin_url", "phone", "address", "city", "state",
    "zip_code", "country", "website",
]

CSV_MAPPING_SYSTEM_PROMPT = """You are a data mapping assistant. You receive CSV column headers \
and sample data, and must map them to lead database fields.

Lead fields to map:
- first_name: The person's first/given name
- last_name: The person's last/family/surname
- email: Email address
- company: Company/organization name
- job_title: Job title/role/position
- industry: Industry sector or category (e.g., Technology, Healthcare, Finance)
- linkedin_url: LinkedIn profile URL
- phone: Phone/telephone number
- address: Street address
- city: City name
- state: State/province/region
- zip_code: ZIP/postal code
- country: Country name
- website: Company or personal website URL

Rules:
- Map each CSV column to the most appropriate lead field
- If a CSV has a single "name" or "full_name" column, map it to first_name and set last_name to null
- If a column clearly does not match any lead field, set it to null - it will be saved as a custom field
- The email field is the most important - always try to identify it
- Use the map_columns tool to return your mapping"""

CSV_MAPPING_TOOL = {
    "name": "map_columns",
    "description": "Map CSV column headers to lead database fields",
    "input_schema": {
        "type": "object",
        "properties": {
            field: {
                "type": ["string", "null"],
                "description": f"CSV column name that maps to {field}",
            }
            for field in KNOWN_FIELDS
        },
        "required": KNOWN_FIELDS,
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

        return {field: None for field in KNOWN_FIELDS}

    def get_unmapped_headers(self, headers: list[str], mapping: dict) -> list[str]:
        """Return CSV headers that are not mapped to any known field."""
        mapped_columns = {v for v in mapping.values() if v}
        return [h for h in headers if h not in mapped_columns]


csv_mapper_service = CSVMapperService()
