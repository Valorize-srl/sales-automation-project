"""Conversational chat service — Claude as strategic advisor (no tool orchestration)."""

import json
import logging
from typing import Optional, AsyncIterator

import anthropic

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.chat_session import ChatSessionService
from app.models.chat_session import ChatSession

logger = logging.getLogger(__name__)


ADVISOR_SYSTEM_PROMPT = """Sei un consulente esperto di vendite B2B e sales intelligence. Aiuti l'utente a definire strategie di prospecting, ICP (Ideal Customer Profile) e a scegliere gli strumenti giusti.

## IL TUO RUOLO
NON esegui ricerche ne' azioni dirette. L'utente ha a disposizione dei tool dedicati (Apollo Search, Google Maps, Website Scraper, Apollo Enrich) nella pagina Prospecting. Tu lo consigli su:

1. **Strategia di ricerca** — Quale tool usare e perche', in che ordine
2. **Definizione ICP** — Aiuti a definire il profilo cliente ideale (settore, dimensione, ruoli, zona)
3. **Qualificazione lead** — Come valutare e prioritizzare i risultati
4. **Outreach** — Consigli su approccio, messaging, personalizzazione

## TOOL DISPONIBILI (l'utente li usa dalla UI)
- **Apollo Search People**: cerca decision maker per titolo, location, seniority. Trova email dirette. 1 credito/contatto.
- **Apollo Search Companies**: cerca aziende per settore, dimensione, tecnologie. Gratuito.
- **Apollo Enrich**: arricchisce lead gia' importate con email, telefono, LinkedIn. 1 credito/contatto.
- **Google Maps Search**: cerca attivita' locali (ristoranti, negozi, studi). Ideale per horeca/retail/servizi.
- **Website Scraper**: estrae email, telefoni, social dai siti web aziendali.

## SCELTA DEI TOOL — CONSIGLI
- **Attivita' locali** (ristoranti, negozi, studi professionali): Google Maps → poi Website Scraper per email
- **Aziende B2B, tech, enterprise**: Apollo Search Companies → poi Apollo Search People per decision maker
- **Decision maker con email dirette**: Apollo Search People (ha email verificate)
- **Email generiche aziendali**: Website Scraper sui siti delle aziende trovate

## REGOLE
1. Parla SEMPRE in italiano, in modo conciso e professionale
2. NON fingere di eseguire ricerche — indirizza l'utente al tool giusto
3. Fai domande mirate per capire il target prima di consigliare
4. Suggerisci un approccio step-by-step: prima aziende, poi decision maker, poi arricchimento
5. Se l'utente chiede qualcosa che non puoi fare, spiega quale tool usare dalla UI

## ESEMPIO
Utente: "Devo trovare ristoranti stellati in Toscana"
Tu: "Per i ristoranti, il tool migliore e' **Google Maps Search**. Ti consiglio:
1. Cerca 'ristorante stellato' con location 'Toscana'
2. Dai risultati, seleziona quelli piu' interessanti e importali
3. Poi usa **Website Scraper** sui loro siti per trovare email e telefoni diretti
Vuoi che ti aiuti a definire meglio i criteri di ricerca?"
"""


class ConversationalChatService:
    """Chat service — Claude as strategic advisor, no tool execution."""

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
        """Stream chat response from Claude without tools."""
        try:
            session = await self.session_service.get_session(session_uuid)
            if not session:
                session = await self.session_service.create_session()

            # Add user message to DB
            message_metadata = {}
            if file_content:
                message_metadata["has_file_attachment"] = True

            await self.session_service.add_message(
                session_id=session.id,
                role="user",
                content=user_message,
                message_metadata=message_metadata if message_metadata else None,
            )

            # Build conversation context (last 20 messages)
            messages = await self.session_service.get_conversation_context(
                session_id=session.id,
                max_messages=20,
            )

            if file_content and messages:
                last_message = messages[-1]
                if last_message["role"] == "user":
                    last_message["content"] += f"\n\nDocumento allegato:\n{file_content}"

            # Build system prompt
            system_prompt = await self._build_system_prompt(session)

            # Stream from Claude directly (no tools)
            if not settings.anthropic_api_key:
                yield f"data: {json.dumps({'type': 'error', 'error': 'Anthropic API key not configured'})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return

            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            accumulated_text = ""

            async with client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                system=system_prompt,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    accumulated_text += text
                    yield f"data: {json.dumps({'type': 'text', 'content': text})}\n\n"

                # Get final message for token usage
                final_message = await stream.get_final_message()
                input_tokens = final_message.usage.input_tokens
                output_tokens = final_message.usage.output_tokens

                # Save assistant message
                await self.session_service.add_message(
                    session_id=session.id,
                    role="assistant",
                    content=accumulated_text or "[no response]",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

                # Emit usage event
                yield f"data: {json.dumps({'type': 'usage', 'input_tokens': input_tokens, 'output_tokens': output_tokens})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error(f"Chat streaming error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'message': f'Error: {str(e)}'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    async def _build_system_prompt(self, session: ChatSession) -> str:
        """Build system prompt with agent context if available."""
        prompt = ADVISOR_SYSTEM_PROMPT

        # Inject AI Agent context (ICP, signals, knowledge base) if bound
        if session.ai_agent_id:
            try:
                from app.models.ai_agent import AIAgent
                agent = await self.db.get(AIAgent, session.ai_agent_id)
                if agent and agent.is_active:
                    prompt += f"\n\n## AGENTE: {agent.name}"
                    prompt += f"\n- Cliente: {agent.client_tag}"

                    if agent.icp_config:
                        prompt += "\n\n### ICP DEL CLIENTE (pre-configurato)"
                        for key, value in agent.icp_config.items():
                            if value:
                                prompt += f"\n- **{key}**: {value}"

                    if agent.signals_config:
                        prompt += "\n\n### SEGNALI DA CERCARE"
                        for key, value in agent.signals_config.items():
                            if value:
                                if isinstance(value, list):
                                    prompt += f"\n- **{key}**: {', '.join(str(v) for v in value)}"
                                else:
                                    prompt += f"\n- **{key}**: {value}"

                    if agent.knowledge_base_text:
                        kb_text = agent.knowledge_base_text[:2000]
                        if len(agent.knowledge_base_text) > 2000:
                            kb_text += "\n... [troncato]"
                        prompt += f"\n\n### CONTESTO CLIENTE\n{kb_text}"

                    prompt += f"\n\n### BUDGET"
                    prompt += f"\n- Crediti Apollo: {agent.credits_remaining}/{agent.apollo_credits_allocated}"
            except Exception as e:
                logger.warning(f"Could not load AI agent context: {e}")

        return prompt

    async def create_session(
        self,
        client_tag: Optional[str] = None,
        title: Optional[str] = None,
        ai_agent_id: Optional[int] = None,
    ) -> ChatSession:
        """Create new chat session."""
        return await self.session_service.create_session(
            client_tag=client_tag,
            title=title,
            ai_agent_id=ai_agent_id,
        )

    async def get_session(self, session_uuid: str) -> Optional[ChatSession]:
        """Get session by UUID."""
        return await self.session_service.get_session(session_uuid)

    async def get_session_summary(self, session_uuid: str) -> dict:
        """Get session statistics and summary."""
        session = await self.session_service.get_session(session_uuid)
        if not session:
            return {}
        return await self.session_service.get_session_summary(session.id)

    async def list_sessions(
        self,
        client_tag: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ChatSession]:
        """List sessions with pagination."""
        return await self.session_service.list_sessions(
            client_tag=client_tag,
            status=status,
            limit=limit,
            offset=offset,
        )

    async def archive_session(self, session_uuid: str):
        """Mark session as archived."""
        await self.session_service.archive_session(session_uuid)
