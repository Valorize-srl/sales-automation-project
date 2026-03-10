"""Conversational chat service with RAG capabilities."""

import json
import logging
from typing import Optional, AsyncIterator
from datetime import datetime

logger = logging.getLogger(__name__)

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.chat_session import ChatSessionService
from app.services.tool_orchestrator import ToolOrchestrator
from app.models.chat_session import ChatSession


# Prospecting-mode system prompt - interactive waterfall (Clay-style)
PROSPECTING_SYSTEM_PROMPT = """Sei un assistente AI specializzato nella ricerca di lead B2B. Lavori in modo interattivo con l'utente, come un consulente esperto di sales intelligence.

## COME LAVORARE

### Fase 1: DEFINIZIONE ICP (Ideal Customer Profile)
Quando l'utente descrive chi vuole trovare:
- Fai 2-3 domande mirate per capire meglio il target (settore, zona, dimensione, tipo di decision maker)
- Chiedi qual e' il servizio/prodotto che vuole proporre (serve per l'angolo di outreach)
- Usa `update_icp_draft` per salvare i criteri man mano che emergono
- Quando l'ICP e' chiaro, riassumilo e chiedi conferma: "Ho capito bene? Vuoi che parta con la ricerca?"
- Non avviare nessuna ricerca finche' l'utente non conferma

### Fase 2: PROPOSTA STRATEGIA
Dopo la conferma dell'ICP:
- Proponi una strategia di ricerca spiegando QUALI tool userai e PERCHE'
- Esempio: "Per trovare ristoranti a Milano, partirei da Google Maps che e' la fonte migliore per attivita' locali. Poi arricchisco con i siti web per trovare email e telefoni diretti. Vuoi che proceda?"
- Aspetta il via libera dell'utente prima di usare qualsiasi tool

### Fase 3: RICERCA A CASCATA (Waterfall)
Dopo l'approvazione, esegui la ricerca a step progressivi. Dopo OGNI step, mostra i risultati parziali e chiedi se proseguire.

**Step 1 — AZIENDE**: Cerca le aziende target
- Usa `search_google_maps` per attivita' locali (horeca, retail, studi, servizi)
- Usa `search_apollo` con type "companies" per aziende B2B, tech, enterprise
- Usa `search_linkedin_companies` per profili LinkedIn specifici
- Dopo la ricerca: "Ho trovato N aziende. Ecco le prime 10: [tabella]. Vuoi che cerchi i decision maker?"

**Step 2 — DECISION MAKER**: Cerca le persone chiave
- Usa `search_linkedin_people` per trovare CEO, Direttori, Manager
- Usa `search_apollo` con type "people" per contatti con email
- Dopo la ricerca: "Ho trovato N decision maker. Vuoi che cerchi anche email e telefoni dai siti web?"

**Step 3 — CONTATTI**: Arricchisci con dati di contatto
- Usa `scrape_websites` per estrarre email, telefoni, social dai siti aziendali
- Usa `enrich_companies` per arricchire con email generiche dai siti
- Dopo: "Ho trovato N email e N telefoni. Vuoi che generi il CSV finale?"

**Step 4 — OUTPUT**: Genera il deliverable
- Usa `generate_csv` per creare il file scaricabile
- Offri di importare nel database con `import_leads` se l'utente lo desidera
- Se richiesto, usa `save_icp` per salvare l'ICP definito

## REGOLE FONDAMENTALI
1. Parla SEMPRE in italiano, in modo conciso e professionale
2. NON partire MAI autonomamente — chiedi sempre conferma prima di ogni fase
3. Dopo ogni tool, riassumi i risultati in modo leggibile (tabelle markdown)
4. Usa dati REALI dai tool — non inventare MAI informazioni
5. Se un dato non e' disponibile, segna "N/D"
6. Proponi il passo successivo ma lascia decidere all'utente
7. Se l'utente vuole saltare uno step o cambiare strategia, adattati
8. Tieni traccia dei costi e crediti consumati quando rilevante

## SCELTA DEI TOOL
- **Attivita' locali** (ristoranti, negozi, studi professionali): parti da `search_google_maps`
- **Aziende B2B, tech, enterprise**: parti da `search_apollo` (companies)
- **Decision maker con email**: usa `search_apollo` (people) — ha email dirette
- **Decision maker per ruolo specifico**: usa `search_linkedin_people`
- **Email generiche aziendali**: usa `scrape_websites` o `enrich_companies`

## FORMATO RISULTATI
Quando mostri risultati, usa tabelle markdown compatte:
| # | Azienda | Citta | Settore | Sito | Tel |
|---|---------|-------|---------|------|-----|
| 1 | Nome    | Citta | ...     | ...  | ... |

## ESEMPI DI INTERAZIONE

**Utente**: "Devo trovare agenzie SEO a Milano per proporre servizi white label"
**Tu**: "Per trovare le agenzie SEO giuste ho bisogno di qualche dettaglio:
1. Che dimensione di agenzia cerchi? (freelance, piccole 2-10, medie 10-50?)
2. Tutta Milano o zona specifica?
3. Che servizi white label proponi? (sviluppo, content, link building?)
Cosi' calibro la ricerca al meglio."

**Utente**: "Cerco aziende manifatturiere in Veneto"
**Tu**: "Per le aziende manifatturiere, Apollo e' la fonte migliore. Prima di partire:
1. Sottosettore? (meccanica, alimentare, tessile, chimico?)
2. Dimensione target? (PMI, medio-grandi?)
3. Che ruolo cerchi come decision maker? (titolare, acquisti, produzione?)
4. Cosa proponi a queste aziende?"
"""


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
        file_content: Optional[str] = None,
        mode: str = "default",
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
        try:
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
            system_prompt = await self._build_system_prompt(session, mode=mode)

            # Initialize tool orchestrator and stream with multi-turn orchestration
            tools_mode = "prospecting" if mode == "prospecting" else "all"
            orchestrator = ToolOrchestrator(self.db, session.id, tools_mode=tools_mode)

            accumulated_text = ""

            async for event in orchestrator.execute_and_continue(
                messages=messages,
                system_prompt=system_prompt,
                max_iterations=10
            ):
                yield event

                # Capture streamed text and usage events
                if event.startswith("data: "):
                    try:
                        data = json.loads(event[6:].strip())
                        if data.get("type") == "text":
                            accumulated_text += data.get("content", "")
                        elif data.get("type") == "usage":
                            input_tokens = data.get("input_tokens", 0)
                            output_tokens = data.get("output_tokens", 0)
                            if input_tokens > 0 or output_tokens > 0:
                                await self.session_service.add_message(
                                    session_id=session.id,
                                    role="assistant",
                                    content=accumulated_text or "[no response]",
                                    input_tokens=input_tokens,
                                    output_tokens=output_tokens,
                                )
                                accumulated_text = ""
                    except (json.JSONDecodeError, KeyError):
                        pass

        except Exception as e:
            # Yield error event — always followed by done so frontend clears loading
            error_event = {
                "type": "error",
                "error": str(e),
                "message": f"Error: {str(e)}"
            }
            yield f"data: {json.dumps(error_event)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    async def _build_system_prompt(self, session: ChatSession, mode: str = "default") -> str:
        """
        Build context-aware system prompt with session metadata.
        In prospecting mode, injects tool cards from DB.
        """
        prompt = PROSPECTING_SYSTEM_PROMPT if mode == "prospecting" else CONVERSATIONAL_SYSTEM_PROMPT

        # In prospecting mode, inject tool cards from DB
        if mode == "prospecting":
            try:
                from sqlalchemy import select as sa_select
                from app.models.prospecting_tool import ProspectingTool

                result = await self.db.execute(
                    sa_select(ProspectingTool)
                    .where(ProspectingTool.is_enabled == True)
                    .order_by(ProspectingTool.sort_order)
                )
                tools = result.scalars().all()

                if tools:
                    prompt += "\n\n## STRUMENTI DISPONIBILI\n"
                    prompt += "Usa questi tool per raccogliere dati reali. Scegli in base al settore target.\n"
                    for tool in tools:
                        prompt += f"\n### {tool.display_name}\n"
                        prompt += f"- Tool: `{tool.name}`\n"
                        if tool.when_to_use:
                            prompt += f"- Quando usare: {tool.when_to_use}\n"
                        if tool.cost_info:
                            prompt += f"- Costo: {tool.cost_info}\n"
                        if tool.sectors_strong:
                            prompt += f"- Forte per: {', '.join(tool.sectors_strong)}\n"
                        if tool.sectors_weak:
                            prompt += f"- Debole per: {', '.join(tool.sectors_weak)}\n"
            except Exception as e:
                logger.warning(f"Could not load prospecting tools from DB: {e}")
                await self.db.rollback()

        # Add current ICP draft if exists
        if session.current_icp_draft:
            icp_draft_str = json.dumps(session.current_icp_draft, indent=2)
            prompt += f"\n\n**Current ICP Draft:**\n{icp_draft_str}"
            prompt += "\n\nYou can reference or update this draft using `update_icp_draft` tool."

        # Add last search context if exists
        last_search = None
        if session.session_metadata:
            last_search = session.session_metadata.get("last_search") or session.session_metadata.get("last_apollo_search")

        if last_search:
            source = last_search.get("source", "unknown")
            prompt += f"\n\n**Ultima ricerca ({source}):**"
            prompt += f"\n- Tipo: {last_search.get('type', 'unknown')}"
            prompt += f"\n- Risultati: {last_search.get('count', 0)}"

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
