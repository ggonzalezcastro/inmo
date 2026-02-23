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
import time
from typing import Dict, Any, List, Tuple, Callable, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm.factory import get_llm_provider
from app.services.llm.base_provider import LLMMessage, LLMToolDefinition, MessageRole
from app.core.telemetry import trace_span

logger = logging.getLogger(__name__)


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


def _fire_log(
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
) -> None:
    """Schedule a fire-and-forget LLM call log. Never raises."""
    try:
        from app.services.llm.call_logger import log_llm_call

        asyncio.ensure_future(
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
            )
        )
    except Exception:  # noqa: BLE001
        pass  # observability must never crash the pipeline


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
    ) -> Dict[str, Any]:
        """
        Analyze message to qualify lead and extract data.

        This method uses the provider's generate_json capability
        to maintain the same analysis logic across providers.
        """
        provider = get_llm_provider()

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

        # Get last bot message for context
        last_bot_message = ""
        if lead_context and lead_context.get("message_history"):
            try:
                history = lead_context.get("message_history", "")
                if isinstance(history, str):
                    parts = history.split("|")
                    for part in reversed(parts):
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
- Si preguntó por renta/sueldo y responde número → salary (NO budget)
- Si preguntó por DICOM y responde "no" → dicom_status="clean"

Retorna JSON con:
{{
    "qualified": "yes"|"no"|"maybe",
    "interest_level": 1-10,
    "budget": número o null,
    "timeline": "immediate"|"30days"|"90days"|"just_looking"|"unknown",
    "name": string o null,
    "phone": string o null,
    "email": string o null,
    "salary": número o null,
    "location": string o null,
    "dicom_status": "clean"|"has_debt"|null,
    "morosidad_amount": número o null,
    "key_points": ["punto1", "punto2"],
    "score_delta": -20 a +20
}}"""

        pname, model, used_fallback = _provider_meta(provider)
        try:
            # temperature=0.3 for data extraction — financial data must be precise
            _t0 = time.monotonic()
            with trace_span("llm.qualify", {"provider": pname, "model": model, "lead_id": str(lead_id or "")}):
                result = await provider.generate_json(analysis_prompt)
            _latency = int((time.monotonic() - _t0) * 1000)
            _fire_log(
                provider_name=pname,
                model=model,
                call_type="qualification",
                used_fallback=used_fallback,
                latency_ms=_latency,
                broker_id=broker_id,
                lead_id=lead_id,
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
                "score_delta": 0
            }

            for key, default in defaults.items():
                if key not in result:
                    result[key] = default

            return result

        except Exception as e:
            logger.error(f"[LLMService] Analysis error: {e}", exc_info=True)
            _fire_log(
                provider_name=pname,
                model=model,
                call_type="qualification",
                used_fallback=used_fallback,
                latency_ms=0,
                broker_id=broker_id,
                lead_id=lead_id,
                error=str(e)[:500],
            )
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

    @staticmethod
    async def generate_response_with_function_calling(
        system_prompt: str,
        contents: List[Any],  # Can be native types or LLMMessage
        tools: List[Any],
        tool_executor: Optional[Callable] = None,
        broker_id: Optional[int] = None,
        lead_id: Optional[int] = None,
        static_system_prompt: Optional[str] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Generate response with function calling.

        Handles both native types (for backward compatibility)
        and unified LLMMessage/LLMToolDefinition types.
        """
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
        try:
            with trace_span("llm.chat", {"provider": pname, "model": model, "lead_id": str(lead_id or "")}):
                result = await provider.generate_with_tools(
                    messages=messages,
                    tools=tool_defs,
                    system_prompt=system_prompt,
                    tool_executor=tool_executor,
                    cached_content=cached_content,
                )
        except Exception as _exc:
            _err = str(_exc)[:500]
            raise
        finally:
            _fire_log(
                provider_name=pname,
                model=model,
                call_type="chat_response",
                used_fallback=used_fallback,
                latency_ms=int((time.monotonic() - _t0) * 1000),
                broker_id=broker_id,
                lead_id=lead_id,
                error=_err,
            )
        return result

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
        dynamic_context = f"--- CONTEXTO DEL LEAD ---\n{context_summary}{prior_block}"
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
            summary_parts.append(f"✅ DATOS RECOPILADOS:\n" + "\n".join(info_collected))
        if info_needed:
            summary_parts.append(f"⚠️ DATOS PENDIENTES:\n{', '.join(info_needed)}")
        else:
            summary_parts.append("✅ TODOS LOS DATOS RECOPILADOS")

        return "\n\n".join(summary_parts)


# Alias for backward compatibility
# Code using LLMService will continue to work
LLMService = LLMServiceFacade
