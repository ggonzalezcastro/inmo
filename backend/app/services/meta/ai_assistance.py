"""Human-controlled AI summary, reply drafts, and task suggestions."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import get_redis
from app.models.chat_message import ChatMessage, MessageDirection
from app.models.conversation import Conversation
from app.models.lead import Lead
from app.services.llm.facade import LLMServiceFacade
from app.services.meta.inbox import MetaInboxService


def _strip_fences(value: str) -> str:
    text = (value or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _as_aware(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


class MetaAIAssistanceService:
    @staticmethod
    async def _context(
        db: AsyncSession,
        *,
        conversation_id: int,
        current_user: dict,
    ) -> tuple[Conversation, Lead, list[ChatMessage]]:
        conversation, lead = await MetaInboxService.assert_access(
            db,
            conversation_id=conversation_id,
            current_user=current_user,
        )
        messages = list((await db.scalars(
            select(ChatMessage)
            .where(
                ChatMessage.broker_id == conversation.broker_id,
                ChatMessage.conversation_id == conversation.id,
            )
            .order_by(ChatMessage.id.desc())
            .limit(40)
        )).all())
        messages.reverse()
        return conversation, lead, messages

    @staticmethod
    def _transcript(messages: list[ChatMessage]) -> str:
        lines = []
        for message in messages:
            role = "Cliente" if message.direction == MessageDirection.INBOUND else "Equipo"
            text = (message.message_text or "").replace("\x00", " ").strip()[:1200]
            if text:
                lines.append(f"[{message.id}] {role}: {text}")
        return "\n".join(lines)[-24000:]

    @staticmethod
    async def summary(
        db: AsyncSession,
        *,
        conversation_id: int,
        current_user: dict,
    ) -> dict[str, Any]:
        conversation, lead, messages = await MetaAIAssistanceService._context(
            db,
            conversation_id=conversation_id,
            current_user=current_user,
        )
        last_id = messages[-1].id if messages else None
        cache_key = f"meta:summary:{conversation.broker_id}:{conversation.id}:{last_id or 0}"
        try:
            redis = await get_redis()
            cached = await redis.get(cache_key)
            if cached:
                return {
                    "summary": cached,
                    "cached": True,
                    "based_on_message_id": last_id,
                }
        except Exception:
            redis = None
        prompt = f"""
Eres asistente comercial inmobiliario en Chile. Resume esta conversación interna para el ejecutivo.
Entrega máximo 120 palabras, en español claro, con: interés, datos confirmados, objeciones,
compromisos y próxima acción. No inventes información ni incluyas teléfono o correo.
Etapa CRM: {lead.pipeline_stage or 'sin etapa'}.
Estado DICOM informado: {(lead.lead_metadata or {}).get('dicom_status') or 'desconocido'}.
Canal: {conversation.channel}.

Conversación:
{MetaAIAssistanceService._transcript(messages)}
""".strip()
        summary = _strip_fences(await LLMServiceFacade.generate_response(prompt))[:2000]
        if redis is not None and summary:
            try:
                await redis.setex(cache_key, 86400, summary)
            except Exception:
                pass
        return {"summary": summary, "cached": False, "based_on_message_id": last_id}

    @staticmethod
    async def draft(
        db: AsyncSession,
        *,
        conversation_id: int,
        current_user: dict,
        instruction: Optional[str],
    ) -> dict[str, Any]:
        conversation, lead, messages = await MetaAIAssistanceService._context(
            db,
            conversation_id=conversation_id,
            current_user=current_user,
        )
        last_id = messages[-1].id if messages else None
        channel_style = {
            "whatsapp": "breve, cercano y fácil de leer; máximo 5 líneas",
            "instagram": "natural, directo y conversacional; máximo 4 líneas",
            "facebook": "cordial, claro y profesional; máximo 5 líneas",
        }.get(conversation.channel, "claro y profesional")
        dicom_status = (lead.lead_metadata or {}).get("dicom_status") or "desconocido"
        prompt = f"""
Redacta SOLO un borrador de respuesta para un lead inmobiliario chileno.
Canal: {conversation.channel}. Estilo: {channel_style}.
Etapa: {lead.pipeline_stage or 'sin etapa'}. DICOM: {dicom_status}.
Reglas obligatorias: no inventar stock, precios, descuentos, financiamiento ni condiciones;
si DICOM no está limpio, jamás prometer aprobación o preaprobación; no afirmar que una gestión
se realizó si no aparece en la conversación. Responde a la última intervención del cliente.
Instrucción opcional del ejecutivo: {instruction or 'ninguna'}.

Conversación:
{MetaAIAssistanceService._transcript(messages)}
""".strip()
        draft = _strip_fences(await LLMServiceFacade.generate_response(prompt))[:4096]
        return {
            "draft": draft,
            "based_on_message_id": last_id,
        }

    @staticmethod
    async def task_suggestion(
        db: AsyncSession,
        *,
        conversation_id: int,
        current_user: dict,
    ) -> dict[str, Any]:
        _, _, messages = await MetaAIAssistanceService._context(
            db,
            conversation_id=conversation_id,
            current_user=current_user,
        )
        now = datetime.now(timezone.utc)
        prompt = f"""
Analiza la conversación y detecta únicamente un compromiso concreto que requiera seguimiento humano.
Devuelve JSON válido, sin markdown, con estas claves:
{{"suggested": boolean, "title": string|null, "due_at": string ISO-8601 con zona|null,
"evidence_message_id": integer|null, "evidence": string|null, "needs_review": boolean,
"reason": string|null}}.
Ahora UTC: {now.isoformat()}.
Si no hay fecha/hora suficientemente clara, due_at debe ser null y needs_review true.
No crees la tarea; solo sugiere. Título máximo 200 caracteres.

Conversación:
{MetaAIAssistanceService._transcript(messages)}
""".strip()
        raw = _strip_fences(await LLMServiceFacade.generate_response(prompt))
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {
                "suggested": False,
                "needs_review": True,
                "reason": "La IA no pudo estructurar una sugerencia confiable",
            }
        evidence_id = parsed.get("evidence_message_id")
        allowed_ids = {message.id for message in messages}
        if evidence_id not in allowed_ids:
            evidence_id = None
        due_at = _as_aware(parsed.get("due_at"))
        needs_review = bool(parsed.get("needs_review")) or due_at is None
        title = str(parsed.get("title") or "").strip()[:200] or None
        suggested = bool(parsed.get("suggested") and title)
        if due_at and due_at <= now:
            needs_review = True
        return {
            "suggested": suggested,
            "title": title,
            "due_at": due_at,
            "reminder_minutes_before": 60,
            "evidence_message_id": evidence_id,
            "evidence": str(parsed.get("evidence") or "")[:500] or None,
            "needs_review": needs_review,
            "reason": str(parsed.get("reason") or "")[:500] or None,
        }
