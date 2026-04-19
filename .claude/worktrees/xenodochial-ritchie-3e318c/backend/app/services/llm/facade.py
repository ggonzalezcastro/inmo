"""
LLM Service Facade

This module provides backward-compatible access to LLM functionality
using the new provider abstraction layer.

The original LLMService methods are preserved but now delegate to
the configured provider (Gemini, Claude, or OpenAI).
"""
import asyncio
import json
import logging
import re
import time
from typing import Dict, Any, List, Tuple, Callable, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm.factory import get_llm_provider, get_fast_llm_provider, resolve_provider_for_agent
from app.services.llm.base_provider import LLMMessage, LLMToolDefinition, MessageRole
from app.core.telemetry import trace_span

logger = logging.getLogger(__name__)


# ── Regex fallback for data extraction when LLM analysis fails ───────────────

_PHONE_RE = re.compile(
    r'(?:(?:\+?56)?[\s-]?9[\s-]?\d{4}[\s-]?\d{4})'   # Chilean mobile: +56 9 XXXX XXXX
    r'|(?:\b9\d{8}\b)',                                  # 9XXXXXXXX
    re.IGNORECASE,
)

_NAME_PATTERNS = [
    re.compile(r'(?:me llamo|soy|mi nombre es)\s+([A-ZÁÉÍÓÚÑa-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑa-záéíóúñ]+){0,3})', re.IGNORECASE),
    re.compile(r'(?:nombre[:\s]+)\s*([A-ZÁÉÍÓÚÑa-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑa-záéíóúñ]+){0,3})', re.IGNORECASE),
]

_EMAIL_RE = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')

_GREETING_WORDS = frozenset({
    "hola", "buenos", "buenas", "dias", "tardes", "noches", "gracias",
    "si", "no", "ok", "bien", "claro", "dale", "ya",
})


def _regex_extract_fields(message: str) -> Dict[str, Any]:
    """Best-effort regex extraction of name, phone, and email from a message.

    Returns a dict with only the fields that were successfully extracted.
    Used as a fallback when the LLM analysis model fails or returns empty.
    """
    extracted: Dict[str, Any] = {}

    # Phone — inline normalization to avoid heavy import chain
    phone_match = _PHONE_RE.search(message)
    if phone_match:
        digits = re.sub(r'\D', '', phone_match.group())
        if digits.startswith('56'):
            extracted["phone"] = f"+{digits}"
        elif len(digits) == 9 and digits.startswith('9'):
            extracted["phone"] = f"+56{digits}"
        else:
            extracted["phone"] = f"+{digits}"

    # Email
    email_match = _EMAIL_RE.search(message)
    if email_match:
        extracted["email"] = email_match.group().lower()

    # Name — try explicit patterns first
    for pattern in _NAME_PATTERNS:
        m = pattern.search(message)
        if m:
            candidate = m.group(1).strip()
            words = candidate.split()
            # Filter out trailing noise words that got captured
            clean_words = []
            for w in words:
                if w.lower() in ("y", "mi", "numero", "telefono", "es", "el", "la", "de"):
                    break
                clean_words.append(w)
            if clean_words and clean_words[0].lower() not in _GREETING_WORDS:
                extracted["name"] = " ".join(clean_words)
                break

    # Fallback: "Name Surname, rest of message" pattern (leading name before comma)
    if "name" not in extracted:
        comma_match = re.match(
            r'^([A-ZÁÉÍÓÚÑa-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑa-záéíóúñ]+){1,3})\s*[,.]',
            message.strip(),
        )
        if comma_match:
            candidate = comma_match.group(1).strip()
            if candidate.lower().split()[0] not in _GREETING_WORDS:
                extracted["name"] = candidate

    return extracted


def _provider_meta(provider) -> tuple[str, str, bool]:
    """
    Extract (provider_name, model, used_fallback) from any provider/router.

    Returns:
        provider_name: short string like "gemini" / "claude" / "openai"
        model:         model identifier string
        used_fallback: True when the router's fallback was active
    """
    from app.services.llm.router import LLMRouter

    if isinstance(provider, LLMRouter):
        used_fallback = provider._failover_active
        active = provider.fallback if used_fallback else provider.primary
    else:
        active = provider
        used_fallback = False

    class_name = type(active).__name__.lower()
    if "gemini" in class_name:
        pname = "gemini"
    elif "claude" in class_name or "anthropic" in class_name:
        pname = "claude"
    elif "openai" in class_name:
        pname = "openai"
    else:
        pname = class_name

    model = getattr(active, "model", "unknown")
    return pname, model, used_fallback


async def _fire_log(
    *,
    provider_name: str,
    model: str,
    call_type: str,
    used_fallback: bool,
    latency_ms: int,
    broker_id: Optional[int] = None,
    lead_id: Optional[int] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    error: Optional[str] = None,
    agent_type: Optional[str] = None,
    raw_response_snippet: Optional[str] = None,
    system_prompt: Optional[str] = None,
    user_messages: Optional[list] = None,
    rag_chunks_used: Optional[list] = None,
    temperature: Optional[float] = None,
    thinking_content: Optional[str] = None,
) -> None:
    """Fire LLM call log in background. Never raises — observability must never block the pipeline."""
    try:
        from app.services.llm.call_logger import log_llm_call

        async def _do_log() -> None:
            try:
                await asyncio.wait_for(
                    log_llm_call(
                        provider=provider_name,
                        model=model,
                        call_type=call_type,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        latency_ms=latency_ms,
                        broker_id=broker_id,
                        lead_id=lead_id,
                        used_fallback=used_fallback,
                        error=error,
                    ),
                    timeout=5.0,
                )
            except Exception as _log_exc:
                logger.debug("[LLM-facade] _fire_log inner error: %s", _log_exc)

        asyncio.ensure_future(_do_log())
    except Exception as _log_exc:  # noqa: BLE001
        logger.debug("[LLM-facade] _fire_log skipped: %s", _log_exc)  # observability must never crash the pipeline

    # Also write to agent_events for the conversation debugger
    if lead_id and broker_id and not error:
        try:
            from app.services.llm.call_logger import _estimate_cost
            from app.services.observability.event_logger import event_logger
            cost = _estimate_cost(model, input_tokens or 0, output_tokens or 0) or 0.0
            async def _fire_event_log() -> None:
                try:
                    await event_logger.log_llm_call(
                        lead_id=lead_id,
                        broker_id=broker_id,
                        provider=provider_name,
                        model=model,
                        input_tokens=input_tokens or 0,
                        output_tokens=output_tokens or 0,
                        latency_ms=latency_ms,
                        cost_usd=cost,
                        agent_type=agent_type,
                        system_prompt=system_prompt,
                        raw_response_snippet=raw_response_snippet,
                        user_messages=user_messages,
                        rag_chunks_used=rag_chunks_used,
                        temperature=temperature,
                        thinking_content=thinking_content,
                    )
                except Exception as _inner_exc:
                    logger.debug("[LLM-facade] event_logger task error: %s", _inner_exc)

            asyncio.ensure_future(_fire_event_log())
        except Exception as _ev_exc:
            logger.debug("[LLM-facade] event_logger fire skipped: %s", _ev_exc)


class LLMServiceFacade:
    """
    Facade that provides the same interface as the original LLMService
    but delegates to the configured provider.

    This enables gradual migration - existing code continues to work
    while new code can use providers directly.
    """

    FALLBACK_RESPONSE = "Gracias por tu mensaje. Un agente estará contigo pronto para ayudarte."

    @staticmethod
    async def generate_response(prompt: str) -> str:
        """
        Generate response using the configured provider.

        Backward compatible with original LLMService.generate_response()
        """
        provider = get_llm_provider()
        return await provider.generate_response(prompt)

    @staticmethod
    async def analyze_lead_qualification(
        message: str,
        lead_context: Dict = None,
        broker_id: Optional[int] = None,
        lead_id: Optional[int] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Analyze message to qualify lead and extract data.

        This method uses the provider's generate_json capability
        to maintain the same analysis logic across providers.

        Resolution order:
        1. Per-broker qualifier config (if broker_id and db provided)
        2. Fast/lightweight provider (GEMMA_MODEL) for lower latency
        """
        if db and broker_id:
            try:
                provider = await resolve_provider_for_agent("qualifier", broker_id, db)
            except Exception as _exc:
                logger.debug("[LLM-facade] resolve_provider_for_agent failed for qualifier: %s", _exc)
                provider = get_fast_llm_provider()
        else:
            provider = get_fast_llm_provider()

        if not provider.is_configured:
            logger.warning("[LLMService] Provider not configured, returning defaults")
            return {
                "qualified": "maybe",
                "interest_level": 5,
                "budget": None,
                "timeline": "unknown",
                "name": None,
                "phone": None,
                "email": None,
                "salary": None,
                "location": None,
                "dicom_status": None,
                "morosidad_amount": None,
                "key_points": [],
                "score_delta": 0
            }

        # Build context
        existing_data = ""
        if lead_context:
            if lead_context.get("name"):
                existing_data += f"Ya tenemos nombre: {lead_context.get('name')}\n"
            phone = lead_context.get("phone", "")
            if phone and not str(phone).startswith(("web_chat_", "whatsapp_")):
                existing_data += f"Ya tenemos teléfono: {phone}\n"
            if lead_context.get("email"):
                existing_data += f"Ya tenemos email: {lead_context.get('email')}\n"
            metadata = lead_context.get("metadata", {})
            if metadata.get("monthly_income") or metadata.get("salary"):
                income = metadata.get("monthly_income") or metadata.get("salary")
                existing_data += f"Ya tenemos renta/sueldo: {income}\n"
            if metadata.get("location"):
                existing_data += f"Ya tenemos ubicación: {metadata.get('location')}\n"

        context_note = f"\n\nDatos existentes del lead:\n{existing_data}" if existing_data else "\n\nNo hay datos previos del lead."

        # Get last bot message for context (supports both list and legacy string formats)
        last_bot_message = ""
        if lead_context and lead_context.get("message_history"):
            try:
                history = lead_context.get("message_history", "")
                if isinstance(history, list):
                    # Structured format: [{"role": "assistant"|"user", "content": "..."}]
                    for msg in reversed(history):
                        if msg.get("role") == "assistant":
                            last_bot_message = msg.get("content", "")
                            break
                elif isinstance(history, str):
                    # Legacy pipe-delimited format: "B:message|U:message|..."
                    for part in reversed(history.split("|")):
                        if part.startswith("B:"):
                            last_bot_message = part[2:]
                            break
            except Exception:
                pass

        context_context = f'\nPREGUNTA ANTERIOR: "{last_bot_message}"\n' if last_bot_message else ""

        analysis_prompt = f"""Analiza este mensaje y extrae datos. Mensaje: "{message}"
{context_note}
{context_context}

IMPORTANTE:
- Solo extrae datos mencionados en este mensaje
- Cualquier cantidad monetaria mencionada como ingreso, renta, sueldo → salary (NUNCA budget)
- "budget" siempre es null — no usamos presupuesto, solo sueldo/renta
- Si preguntó por DICOM y responde "no" → dicom_status="clean"

Retorna JSON con:
{{
    "qualified": "yes"|"no"|"maybe",
    "interest_level": 1-10,
    "budget": null,
    "timeline": "immediate"|"30days"|"90days"|"just_looking"|"unknown",
    "name": string o null,
    "phone": string o null,
    "email": string o null,
    "salary": número o null,
    "location": string o null,
    "dicom_status": "clean"|"has_debt"|null,
    "morosidad_amount": número o null,
    "key_points": ["punto1", "punto2"],
    "score_delta": -20 a +20,
    "intent": "property_search"|"schedule_visit"|"financing_question"|"general_chat"
}}

Para "intent" (usa el que mejor describe la NECESIDAD PRINCIPAL del mensaje):
- "financing_question": PRIORIDAD ALTA — pregunta sobre crédito, pie, DICOM, financiamiento, cuotas, renta, subsidio, hipoteca. Úsalo aunque el mensaje también mencione una propiedad específica.
- "property_search": el lead pregunta qué propiedades/terrenos/departamentos/casas están disponibles, pide ver opciones o catálogo
- "schedule_visit": quiere agendar, visitar, ver una propiedad específica en persona
- "general_chat": saludo, consulta genérica, o no hay intención clara
}}"""

        pname, model, used_fallback = _provider_meta(provider)
        try:
            # temperature=0.3 for data extraction — financial data must be precise
            logger.info("[LLM-facade] analyze_lead_qualification START provider=%s model=%s", pname, model)
            _t0 = time.monotonic()
            with trace_span("llm.qualify", {"provider": pname, "model": model, "lead_id": str(lead_id or "")}):
                result, _usage = await provider.generate_json(analysis_prompt)
            _latency = int((time.monotonic() - _t0) * 1000)
            logger.info("[LLM-facade] analyze_lead_qualification DONE latency=%dms score_delta=%s intent=%s interest=%s name=%s", _latency, result.get("score_delta"), result.get("intent"), result.get("interest_level"), result.get("name"))
            # Use real token counts from API; fall back to char-length estimate if unavailable
            _in_tok = (_usage.get("input_tokens") if _usage else None) or len(analysis_prompt) // 4
            _out_tok = (_usage.get("output_tokens") if _usage else None) or len(str(result)) // 4
            await _fire_log(
                provider_name=pname,
                model=model,
                call_type="qualification",
                used_fallback=used_fallback,
                latency_ms=_latency,
                broker_id=broker_id,
                lead_id=lead_id,
                input_tokens=_in_tok,
                output_tokens=_out_tok,
                agent_type="qualifier",
                raw_response_snippet=str(result)[:500],
            )

            # Ensure all expected fields exist
            defaults = {
                "qualified": "maybe",
                "interest_level": 5,
                "budget": None,
                "timeline": "unknown",
                "name": None,
                "phone": None,
                "email": None,
                "salary": None,
                "location": None,
                "dicom_status": None,
                "morosidad_amount": None,
                "key_points": [],
                "score_delta": 0,
                "intent": "general_chat",
            }

            for key, default in defaults.items():
                if key not in result:
                    result[key] = default

            # Regex fallback: fill missing fields per-field when LLM returned empty/null
            _llm_empty = not result.get("name") and not result.get("phone") and not result.get("email")
            if _llm_empty:
                logger.warning(
                    "[LLM-facade] analyze_lead_qualification returned no contact fields "
                    "(provider=%s model=%s lead_id=%s) — trying regex fallback",
                    pname, model, lead_id,
                )
            _fallback = _regex_extract_fields(message)
            for _fk, _fv in _fallback.items():
                if not result.get(_fk):
                    result[_fk] = _fv
                    logger.info("[LLM-facade] regex fallback filled %s=%r", _fk, _fv)

            return result

        except Exception as e:
            logger.error(f"[LLMService] Analysis error: {e}", exc_info=True)
            await _fire_log(
                provider_name=pname,
                model=model,
                call_type="qualification",
                used_fallback=used_fallback,
                latency_ms=0,
                broker_id=broker_id,
                lead_id=lead_id,
                error=str(e)[:500],
            )
            # Even on full failure, try regex extraction from the raw message
            _fallback = _regex_extract_fields(message)
            if _fallback:
                logger.info("[LLM-facade] analysis failed but regex extracted: %s", list(_fallback.keys()))
            return {
                "qualified": "maybe",
                "interest_level": 5,
                "budget": None,
                "timeline": "unknown",
                "name": _fallback.get("name"),
                "phone": _fallback.get("phone"),
                "email": _fallback.get("email"),
                "salary": None,
                "location": None,
                "dicom_status": None,
                "morosidad_amount": None,
                "key_points": [],
                "score_delta": 0
            }

    @staticmethod
    async def generate_response_with_function_calling(
        system_prompt: str,
        contents: List[Any],  # Can be native types or LLMMessage
        tools: List[Any],
        tool_executor: Optional[Callable] = None,
        broker_id: Optional[int] = None,
        lead_id: Optional[int] = None,
        static_system_prompt: Optional[str] = None,
        agent_type: Optional[str] = None,
        tool_mode_override: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Generate response with function calling.

        Handles both native types (for backward compatibility)
        and unified LLMMessage/LLMToolDefinition types.

        When agent_type and broker_id are provided along with a db session,
        the provider is resolved per-agent from broker configuration, falling
        back to the global provider if no override exists.
        """
        if db and agent_type and broker_id:
            try:
                provider = await resolve_provider_for_agent(agent_type, broker_id, db)
            except Exception as _exc:
                logger.debug(
                    "[LLM-facade] resolve_provider_for_agent failed agent=%s: %s",
                    agent_type, _exc,
                )
                provider = get_llm_provider()
        else:
            provider = get_llm_provider()

        if not provider.is_configured:
            return LLMServiceFacade.FALLBACK_RESPONSE, []

        # Convert contents to LLMMessage if needed
        messages = []
        for content in contents:
            if isinstance(content, LLMMessage):
                messages.append(content)
            elif hasattr(content, 'role') and hasattr(content, 'parts'):
                # Google types.Content format
                role_str = str(content.role)
                role = MessageRole.USER if 'user' in role_str.lower() else MessageRole.ASSISTANT
                text = content.parts[0].text if content.parts else ""
                messages.append(LLMMessage(role=role, content=text))
            elif isinstance(content, dict):
                role = MessageRole(content.get('role', 'user'))
                messages.append(LLMMessage(role=role, content=content.get('content', '')))

        # Convert tools to LLMToolDefinition if needed
        tool_defs = []
        for tool in tools:
            if isinstance(tool, LLMToolDefinition):
                tool_defs.append(tool)
            elif isinstance(tool, dict) and "name" in tool:
                # Plain dict format: {"name": ..., "description": ..., "parameters": ...}
                tool_defs.append(LLMToolDefinition(
                    name=tool["name"],
                    description=tool.get("description", ""),
                    parameters=tool.get("parameters", {}),
                ))
            elif hasattr(tool, 'function_declarations'):
                # Google types.Tool format
                for fd in tool.function_declarations:
                    tool_defs.append(LLMToolDefinition(
                        name=fd.name,
                        description=fd.description or "",
                        parameters=dict(fd.parameters) if fd.parameters else {}
                    ))

        # ── TASK-028: Gemini Context Caching ─────────────────────────────────
        # When a static_system_prompt is provided and caching is enabled,
        # look up (or create) a Gemini Context Cache for the static part.
        # system_prompt then contains only the dynamic lead-context portion.
        cached_content: Optional[str] = None
        if static_system_prompt and broker_id:
            from app.services.llm.prompt_cache import PromptCacheManager
            from app.config import settings as _settings
            if _settings.GEMINI_CONTEXT_CACHING_ENABLED:
                try:
                    # Extract the raw Gemini client from the provider
                    from app.services.llm.gemini_provider import GeminiProvider
                    from app.services.llm.router import LLMRouter
                    _active = provider.primary if isinstance(provider, LLMRouter) else provider
                    if isinstance(_active, GeminiProvider) and _active._client:
                        cached_content = await PromptCacheManager.get_cache_name(
                            broker_id=broker_id,
                            system_prompt=static_system_prompt,
                            gemini_client=_active._client,
                            model=_active.model,
                        )
                except Exception as _cache_exc:
                    logger.debug("[Facade] Prompt cache lookup failed: %s", _cache_exc)

        # Chat responses use conversational temperature (default 0.7)
        pname, model, used_fallback = _provider_meta(provider)
        _t0 = time.monotonic()
        _err: Optional[str] = None
        logger.info("[LLM-facade] generate_response_with_function_calling START provider=%s model=%s", pname, model)
        try:
            with trace_span("llm.chat", {"provider": pname, "model": model, "lead_id": str(lead_id or "")}):
                result = await provider.generate_with_tools(
                    messages=messages,
                    tools=tool_defs,
                    system_prompt=system_prompt,
                    tool_executor=tool_executor,
                    cached_content=cached_content,
                    tool_mode_override=tool_mode_override,
                )
            # result is (text, tool_calls) or (text, tool_calls, usage) or (text, tool_calls, usage, thinking)
            usage = result[2] if len(result) >= 3 else None
            thinking_content = result[3] if len(result) >= 4 else None
            input_tokens = None
            output_tokens = None
            if usage:
                input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens")
                output_tokens = usage.get("output_tokens") or usage.get("completion_tokens")
            _response_text = result[0] or ""
            await _fire_log(
                provider_name=pname,
                model=model,
                call_type="chat_response",
                used_fallback=used_fallback,
                latency_ms=int((time.monotonic() - _t0) * 1000),
                broker_id=broker_id,
                lead_id=lead_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                error=None,
                agent_type=agent_type,
                raw_response_snippet=_response_text[:500],
                system_prompt=system_prompt,
                user_messages=[{"role": m.role.value if hasattr(m.role, "value") else str(m.role), "content": m.content} for m in messages],
                thinking_content=thinking_content,
            )
            logger.info("[LLM-facade] generate_response_with_function_calling DONE latency=%dms", int((time.monotonic() - _t0) * 1000))
            return result[0], result[1]
        except Exception as _exc:
            _err = str(_exc)[:500]
            await _fire_log(
                provider_name=pname,
                model=model,
                call_type="chat_response",
                used_fallback=used_fallback,
                latency_ms=int((time.monotonic() - _t0) * 1000),
                broker_id=broker_id,
                lead_id=lead_id,
                error=_err,
            )
            raise

    @staticmethod
    async def build_llm_prompt(
        lead_context: Dict,
        new_message: str,
        db: Optional[AsyncSession] = None,
        broker_id: Optional[int] = None
    ) -> Tuple[str, List[LLMMessage], str]:
        """
        Build LLM prompt with lead context.

        Returns (full_system_prompt, messages, static_system_prompt).

        ``static_system_prompt`` is the broker-specific base prompt without
        dynamic lead context — it is the cacheable part (TASK-028).
        ``full_system_prompt`` = static_system_prompt + dynamic lead context.
        """
        # Import here to avoid circular dependency
        from app.services.broker import BrokerConfigService

        # Get system prompt from broker config or default
        if db and broker_id:
            try:
                static_system_prompt = await BrokerConfigService.build_system_prompt(db, broker_id, lead_context=None)
            except Exception:
                static_system_prompt = BrokerConfigService.DEFAULT_SYSTEM_PROMPT
        else:
            static_system_prompt = BrokerConfigService.DEFAULT_SYSTEM_PROMPT

        # Build context summary
        context_summary = LLMServiceFacade._build_context_summary(lead_context, new_message)

        # TASK-009: inject prior-session summary for returning leads
        prior_summary = lead_context.get("conversation_summary") or (
            lead_context.get("metadata", {}).get("conversation_summary")
            if isinstance(lead_context.get("metadata"), dict) else None
        )
        prior_block = (
            f"\n\n--- HISTORIAL PREVIO (RESUMEN) ---\n{prior_summary}"
            if prior_summary
            else ""
        )

        # ── TASK-024: RAG — inject top-3 relevant KB chunks ──────────────────
        kb_block = ""
        if db and broker_id:
            try:
                from app.services.knowledge.rag_service import RAGService

                # Use the last user message as the search query
                last_msg = lead_context.get("message_history", [])
                search_query = new_message
                if isinstance(last_msg, list) and last_msg:
                    search_query = new_message

                chunks = await RAGService.search(db, broker_id=broker_id, query=search_query)
                kb_block = RAGService.format_for_prompt(chunks)
            except Exception as _rag_exc:
                logger.debug("[RAG] KB search failed: %s", _rag_exc)

        # dynamic context (changes per lead/request)
        from datetime import datetime
        import pytz
        try:
            broker_tz = pytz.timezone("America/Santiago")
            now_str = datetime.now(broker_tz).strftime("%A %d de %B de %Y, %H:%M (America/Santiago)")
        except Exception:
            now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        lead_id_val = lead_context.get("lead_id") or lead_context.get("id") or "desconocido"

        dynamic_context = (
            f"--- CONTEXTO OPERACIONAL ---\n"
            f"Fecha y hora actual: {now_str}\n"
            f"ID interno del lead (NO mencionar al usuario): {lead_id_val}\n"
            f"Zona horaria: America/Santiago. NUNCA preguntes al usuario por el lead ID ni la zona horaria.\n\n"
            f"--- CONTEXTO DEL LEAD ---\n{context_summary}{prior_block}"
        )
        if kb_block:
            dynamic_context = f"{kb_block}\n\n{dynamic_context}"

        # full prompt sent when context caching is OFF
        full_system_prompt = f"{static_system_prompt}\n\n{dynamic_context}"

        # Convert message history to LLMMessage format
        messages = []
        message_history = lead_context.get("message_history", [])

        if isinstance(message_history, list):
            for msg in message_history:
                if isinstance(msg, dict):
                    role = MessageRole.USER if msg.get("role") == "user" else MessageRole.ASSISTANT
                    messages.append(LLMMessage(role=role, content=msg.get("content", "")))

        # Add current message
        messages.append(LLMMessage(role=MessageRole.USER, content=new_message))

        return full_system_prompt, messages, static_system_prompt

    @staticmethod
    def _build_context_summary(lead_context: Dict, new_message: str = "") -> str:
        """Build context summary from lead context"""
        lead_name = lead_context.get("name") or "User"
        lead_phone = lead_context.get("phone") or ""
        lead_email = lead_context.get("email") or ""
        metadata = lead_context.get("metadata", {})

        has_name = lead_name and lead_name not in ["User", "Test User"]
        has_phone = lead_phone and not str(lead_phone).startswith(("web_chat_", "whatsapp_", "+569999"))
        has_email = bool(lead_email and str(lead_email).strip())
        has_salary = bool(metadata.get("salary") or metadata.get("monthly_income"))
        has_location = bool(metadata.get("location"))
        has_dicom = metadata.get("dicom_status") is not None

        info_collected = []
        if has_name:
            info_collected.append(f"NOMBRE: {lead_name}")
        if has_phone:
            info_collected.append(f"TELÉFONO: {lead_phone}")
        if has_email:
            info_collected.append(f"EMAIL: {lead_email}")
        if has_salary:
            salary = metadata.get("salary") or metadata.get("monthly_income")
            info_collected.append(f"RENTA: ${salary:,}" if isinstance(salary, (int, float)) else f"RENTA: {salary}")
        if has_location:
            info_collected.append(f"UBICACIÓN: {metadata.get('location')}")
        if has_dicom:
            dicom = metadata.get("dicom_status")
            info_collected.append(f"DICOM: {dicom}")

        info_needed = []
        if not has_name:
            info_needed.append("NOMBRE")
        if not has_phone:
            info_needed.append("TELÉFONO")
        if not has_email:
            info_needed.append("EMAIL")
        if not has_salary:
            info_needed.append("RENTA/SUELDO")
        if not has_location:
            info_needed.append("UBICACIÓN")
        if not has_dicom:
            info_needed.append("DICOM")

        summary_parts = []
        if info_collected:
            summary_parts.append("DATOS RECOPILADOS:\n" + "\n".join(info_collected))
        if info_needed:
            summary_parts.append(f"DATOS PENDIENTES: {', '.join(info_needed)}")
        else:
            summary_parts.append("TODOS LOS DATOS RECOPILADOS")

        return "\n\n".join(summary_parts)


# Alias for backward compatibility
# Code using LLMService will continue to work
LLMService = LLMServiceFacade
