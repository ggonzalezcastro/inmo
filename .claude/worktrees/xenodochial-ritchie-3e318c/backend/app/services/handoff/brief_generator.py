"""
EscalationBriefGenerator — generates a structured handoff summary for human agents.

When a lead escalates to human_mode, an LLM generates a brief that helps
the human agent understand the context immediately:
  - Why the lead escalated
  - Lead profile and qualification status
  - Data collected vs pending
  - Conversation summary
  - Emotional context
  - Suggested action

The brief is stored in escalation_briefs and displayed in the dashboard.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def generate_escalation_brief(
    db: AsyncSession,
    lead_id: int,
    broker_id: int,
    reason: str,
    lead_data: Dict[str, Any],
    recent_messages: List[Dict[str, Any]],
    frustration_score: Optional[float] = None,
    conversation_id: Optional[int] = None,
) -> Optional[str]:
    """
    Generate a structured escalation brief using the LLM.

    Returns the brief text, or None if generation fails.
    The brief is also persisted to the escalation_briefs table.
    """
    try:
        brief_text = await _generate_with_llm(
            reason=reason,
            lead_data=lead_data,
            recent_messages=recent_messages,
            frustration_score=frustration_score,
        )
        await _save_brief(
            db=db,
            lead_id=lead_id,
            brief_text=brief_text,
            reason=reason,
            frustration_score=frustration_score,
            conversation_id=conversation_id,
        )
        return brief_text
    except Exception as exc:
        logger.warning("Failed to generate escalation brief for lead %d: %s", lead_id, exc)
        return None


async def _generate_with_llm(
    reason: str,
    lead_data: Dict[str, Any],
    recent_messages: List[Dict[str, Any]],
    frustration_score: Optional[float],
) -> str:
    """Call the LLM to produce the brief text."""
    from app.services.llm.facade import LLMServiceFacade

    # Build message context (last 10 messages)
    msg_context = "\n".join(
        f"[{m.get('role', 'unknown')}]: {m.get('content', '')[:200]}"
        for m in (recent_messages or [])[-10:]
    )

    collected = [
        f"{k}: {v}"
        for k, v in lead_data.items()
        if v and k in ("name", "phone", "email", "salary", "budget", "location", "dicom_status")
    ]
    pending = [
        k for k in ("name", "phone", "email", "salary", "location", "dicom_status")
        if not lead_data.get(k)
    ]

    reason_map = {
        "frustration": "frustración/malestar detectado por IA",
        "explicit_request": "el lead pidió hablar con una persona",
        "low_confidence": "la IA detectó baja confianza en sus respuestas",
        "manual": "escalación manual por agente",
        "vip": "lead VIP o de alto valor",
    }
    reason_str = reason_map.get(reason, reason)

    prompt = f"""Genera un brief de escalación conciso para un agente humano que va a tomar esta conversación. El agente tiene 30 segundos para leerlo antes de responder. Sé directo y práctico.

DATOS DISPONIBLES:
- Razón de escalación: {reason_str}
- Score de frustración: {frustration_score:.2f if frustration_score else 'N/A'} (0=calmo, 1=muy frustrado)
- Datos recopilados: {', '.join(collected) if collected else 'Ninguno'}
- Datos pendientes: {', '.join(pending) if pending else 'Todos completos'}
- Últimos mensajes:
{msg_context}

Formato requerido (usa exactamente estos emojis y secciones):
🔴 MOTIVO: [razón en 1 línea]
👤 LEAD: {lead_data.get('name', 'Desconocido')} | {lead_data.get('phone', 'Sin teléfono')}
📊 PERFIL: [renta/presupuesto, DICOM, zona, tipo de propiedad buscada]
📋 ESTADO: [qué se recopiló, qué falta]
💬 CONTEXTO: [qué pasó en la conversación, 2-3 oraciones máximo]
⚠️ EMOCIÓN: [cómo está el lead emocionalmente, qué lo afectó]
🎯 ACCIÓN: [qué debería hacer el agente humano ahora mismo]"""

    brief = await LLMServiceFacade.generate_response(prompt)
    return brief.strip()


async def _save_brief(
    db: AsyncSession,
    lead_id: int,
    brief_text: str,
    reason: str,
    frustration_score: Optional[float],
    conversation_id: Optional[int],
) -> None:
    """Persist the escalation brief to the database."""
    from app.models.escalation_brief import EscalationBrief

    brief = EscalationBrief(
        lead_id=lead_id,
        conversation_id=conversation_id,
        brief_text=brief_text,
        reason=reason,
        frustration_score=frustration_score,
    )
    db.add(brief)
    # Don't commit here — let the caller's transaction handle it


async def get_latest_brief(
    db: AsyncSession,
    lead_id: int,
) -> Optional[Dict[str, Any]]:
    """Retrieve the most recent escalation brief for a lead."""
    from sqlalchemy import select
    from app.models.escalation_brief import EscalationBrief

    result = await db.execute(
        select(EscalationBrief)
        .where(EscalationBrief.lead_id == lead_id)
        .order_by(EscalationBrief.created_at.desc())
        .limit(1)
    )
    brief = result.scalar_one_or_none()
    if brief is None:
        return None

    return {
        "id": brief.id,
        "lead_id": brief.lead_id,
        "brief_text": brief.brief_text,
        "reason": brief.reason,
        "frustration_score": brief.frustration_score,
        "created_at": brief.created_at.isoformat() if brief.created_at else None,
    }
