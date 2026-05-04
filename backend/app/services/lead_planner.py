"""Lead Planner & Scorer — runs Claude over (ICP, companies) batches and parses
the strict JSON output described in the system prompt.

Public entry point: ``LeadPlannerService.score_companies(icp, companies)``.
Companies are split into chunks of ``CHUNK_SIZE`` and processed concurrently.
``target_temp_id`` values returned by Claude (1-indexed within each chunk) are
remapped to global indices in the merged result so the API layer can resolve
them back to real Company.id values.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Optional

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-5-20250929"
CHUNK_SIZE = 50
MAX_OUTPUT_TOKENS = 8192
MAX_PARALLEL_REQUESTS = 5

SYSTEM_PROMPT = """RUOLO
Sei un "Lead Planner & Scorer" per una piattaforma B2B (dash.Miriade) che organizza e qualifica lead
a partire da:
- un ICP gia' strutturato in JSON
- una lista di aziende con pochi campi base (nome, fatturato, organico, url)

Il tuo compito NON e' chiamare API ma:
1) Normalizzare i dati aziendali in un formato coerente con il nostro schema "accounts".
2) Calcolare se ogni azienda e' in ICP o no (icp_match).
3) Assegnare un icp_score 0-100 usando le regole implicite nell'ICP.
4) Assegnare un priority_tier ("A" / "B" / "C") e un lifecycle_stage iniziale.
5) Decidere se ha senso creare enrichment_tasks per funding, hiring, tech stack, contact discovery.

DEVI SEMPRE restituire SOLO JSON valido che rispetta ESATTAMENTE lo schema sotto.
Nessun testo fuori dal JSON, nessun commento.


SCHEMA INPUT (che riceverai nel messaggio utente)
L'input sara' un JSON con questa forma:

{
  "icp": { ... },          // ICP strutturato
  "companies": [           // aziende grezze dalla lista
    {
      "raw_company_name": "string",
      "raw_website_url": "string | null",
      "raw_revenue": "string | number | null",
      "raw_employee_count": "string | number | null",
      "raw_country": "string | null",
      "raw_city": "string | null",
      "source": "string"   // es. "csv_upload", "apollo_export"
    }
  ]
}


SCHEMA OUTPUT (che devi produrre)
Devi restituire un singolo oggetto JSON:

{
  "schema_version": "v1",
  "accounts": [
    {
      "company_name": "string",
      "domain": "string",
      "website_url": "string | null",

      "revenue_band": "string | null",
      "employee_count_band": "string | null",
      "country": "string | null",
      "city": "string | null",

      "industry_raw": "string | null",
      "industry_standardized": "string | null",

      "source": "string",
      "icp_match": true | false,
      "icp_score": 0-100,
      "priority_tier": "A" | "B" | "C",
      "lifecycle_stage": "new" | "enriched" | "ready_for_outreach",
      "reason_summary": "string",
      "notes": "string | null"
    }
  ],
  "enrichment_tasks": [
    {
      "target_type": "account",
      "target_temp_id": "string",
      "task_type": "firmographic_base" | "hiring_scrape" | "funding_lookup" | "techstack_lookup" | "contact_discovery",
      "priority": 1 | 2 | 3 | 4 | 5,
      "reason": "string"
    }
  ]
}


LINEE GUIDA DI DECISIONE

1) Normalizzazione company_name e domain
- Pulisci company_name togliendo suffix inutili ("srl", "spa", "ltd") quando non servono al senso.
- Per domain estrai dal raw_website_url o inferisci dal nome solo se chiarissimo, altrimenti null.

2) revenue_band: 0-1M, 1-5M, 5-10M, 10-50M, 50M+
   employee_count_band: 1-10, 11-50, 51-200, 201-500, 500+

3) icp_score:
   - 70-100 se industry+size+country tutti positivi
   - 40-69 se match parziale
   - <40 se chiaramente fuori target
   - icp_match = true se score >= 60

4) priority_tier:
   - "A" se icp_match=true e icp_score>=80
   - "B" se icp_match=true e icp_score 60-79
   - "C" altrimenti
   lifecycle_stage="new" sempre in prima importazione.

5) enrichment_tasks SOLO per A/B:
   - SEMPRE "firmographic_base" se mancano industry/geo
   - "hiring_scrape" se ICP valorizza scale-up
   - "funding_lookup" se ICP parla di startup/funding
   - "techstack_lookup" se ICP cita tech specifiche
   - "contact_discovery" SOLO per priority_tier "A"
   - Usa target_temp_id "temp-account-1", "temp-account-2", ecc. nell'ordine delle companies in input.

6) reason_summary: 1-2 frasi brevi.
   reason: frase secca senza fluff.


REGOLE
- Mantieni l'ordine degli "accounts" identico all'ordine delle companies in input (1-indexed).
- NON inventare industry/revenue/employees: limita il lavoro a normalizzare.
- Se non hai abbastanza dati, metti campi a null ma compila comunque icp_score.
- Restituisci sempre almeno array vuoti per "accounts" o "enrichment_tasks" se non ci sono.
- Nessun testo fuori dal JSON finale."""


class LeadPlannerError(Exception):
    pass


class LeadPlannerService:
    def __init__(self) -> None:
        if not settings.anthropic_api_key:
            raise LeadPlannerError("ANTHROPIC_API_KEY not configured")
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def score_companies(
        self,
        icp: dict,
        companies: list[dict],
    ) -> dict:
        """Score the full company list, chunked + parallel.

        Returns the merged ``{schema_version, accounts, enrichment_tasks}`` plus
        ``_usage`` (input/output token totals across chunks).
        """
        if not companies:
            return {
                "schema_version": "v1",
                "accounts": [],
                "enrichment_tasks": [],
                "_usage": {"input_tokens": 0, "output_tokens": 0, "chunks": 0},
            }

        # Build (offset, chunk) tuples so we can remap target_temp_id later.
        chunks: list[tuple[int, list[dict]]] = []
        for i in range(0, len(companies), CHUNK_SIZE):
            chunks.append((i, companies[i : i + CHUNK_SIZE]))

        sem = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)

        async def run_chunk(offset: int, chunk: list[dict]):
            async with sem:
                return await self._score_chunk(icp, chunk, offset)

        results = await asyncio.gather(*(run_chunk(off, ck) for off, ck in chunks))

        merged_accounts: list[dict] = []
        merged_tasks: list[dict] = []
        total_in = 0
        total_out = 0
        for (offset, chunk), result in zip(chunks, results):
            accounts = result.get("accounts") or []
            tasks = result.get("enrichment_tasks") or []
            merged_accounts.extend(accounts)
            for t in tasks:
                local_id = self._parse_temp_id(t.get("target_temp_id"))
                if local_id is None:
                    continue
                # local_id is 1-indexed within the chunk
                global_id = offset + local_id  # also 1-indexed
                t["target_temp_id"] = f"temp-account-{global_id}"
                merged_tasks.append(t)
            usage = result.get("_usage") or {}
            total_in += usage.get("input_tokens", 0)
            total_out += usage.get("output_tokens", 0)

        return {
            "schema_version": "v1",
            "accounts": merged_accounts,
            "enrichment_tasks": merged_tasks,
            "_usage": {
                "input_tokens": total_in,
                "output_tokens": total_out,
                "chunks": len(chunks),
            },
        }

    async def _score_chunk(self, icp: dict, companies: list[dict], offset: int) -> dict:
        payload = {"icp": icp, "companies": companies}
        user_message = json.dumps(payload, ensure_ascii=False)

        try:
            response = await self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=MAX_OUTPUT_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
        except anthropic.APIError as e:
            logger.error("Claude API error scoring chunk offset=%d: %s", offset, e)
            return {
                "schema_version": "v1",
                "accounts": [],
                "enrichment_tasks": [],
                "_usage": {"input_tokens": 0, "output_tokens": 0},
            }

        text_blocks = [b.text for b in response.content if getattr(b, "type", "") == "text"]
        raw = "".join(text_blocks).strip()

        parsed = self._parse_json(raw)
        if parsed is None:
            logger.warning(
                "Failed to parse JSON from Claude (chunk offset=%d, %d companies). Raw head: %s",
                offset, len(companies), raw[:300],
            )
            return {
                "schema_version": "v1",
                "accounts": [],
                "enrichment_tasks": [],
                "_usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            }

        parsed["_usage"] = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        return parsed

    @staticmethod
    def _parse_json(raw: str) -> Optional[dict]:
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        # Try to extract the first {...} JSON object even if surrounded by text.
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
        return None

    @staticmethod
    def _parse_temp_id(value: Optional[str]) -> Optional[int]:
        if not value:
            return None
        m = re.search(r"(\d+)$", str(value))
        if not m:
            return None
        try:
            return int(m.group(1))
        except ValueError:
            return None


lead_planner_service: Optional[LeadPlannerService] = None


def get_lead_planner_service() -> LeadPlannerService:
    global lead_planner_service
    if lead_planner_service is None:
        lead_planner_service = LeadPlannerService()
    return lead_planner_service
