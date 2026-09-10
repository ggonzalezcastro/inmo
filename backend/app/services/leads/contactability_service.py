"""Contactability risk derived from messages, calls and appointments."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.chat_message import ChatMessage
from app.models.lead import Lead
from app.models.telegram_message import TelegramMessage
from app.models.voice_call import VoiceCall


LOOKBACK_DAYS = 90
MINIMUM_LEAD_AGE_HOURS = 48
ATTEMPT_GROUP_HOURS = 12
CLOSED_STAGES = {"ganado", "perdido"}
CALL_FAILURE_STATUSES = {"no_answer", "busy"}
CALL_SUCCESS_STATUSES = {"answered", "completed"}

LEVELS = (
    "contactable",
    "intermittent",
    "difficult",
    "critical",
    "insufficient_data",
    "not_applicable",
)


def _value(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw or "").lower()


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _group_attempts(times: Iterable[datetime]) -> list[datetime]:
    """Collapse a burst of contacts into one attempt every twelve hours."""
    ordered = sorted({_aware(value) for value in times if value is not None})
    groups: list[list[datetime]] = []
    threshold = timedelta(hours=ATTEMPT_GROUP_HOURS)
    for occurred_at in ordered:
        if not groups or occurred_at - groups[-1][0] >= threshold:
            groups.append([occurred_at])
        else:
            groups[-1].append(occurred_at)
    return [group[0] for group in groups]


def _level_for_score(score: int) -> str:
    if score >= 75:
        return "critical"
    if score >= 50:
        return "difficult"
    if score >= 25:
        return "intermittent"
    return "contactable"


def _not_scored(level: str, reason: str, action: str) -> Dict[str, Any]:
    return {
        "score": None,
        "level": level,
        "reasons": [reason],
        "suggested_action": action,
        "attempt_count": 0,
        "unanswered_attempts": 0,
        "no_answer_calls": 0,
        "failed_messages": 0,
        "no_shows": 0,
        "last_attempt_at": None,
        "last_response_at": None,
    }


def calculate_contactability(
    lead: Lead,
    messages: Iterable[Any],
    calls: Iterable[Any],
    appointments: Iterable[Any],
    *,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Pure scoring function used by list, detail and dashboard endpoints."""
    now = _aware(now) or datetime.now(timezone.utc)
    created_at = _aware(getattr(lead, "created_at", None)) or now

    if (
        _value(getattr(lead, "pipeline_stage", None)) in CLOSED_STAGES
        or _value(getattr(lead, "status", None)) in {"converted", "lost"}
    ):
        return _not_scored(
            "not_applicable",
            "El lead ya está cerrado.",
            "No requiere evaluación de contacto.",
        )

    outbound_times: list[datetime] = []
    inbound_times: list[datetime] = []
    failed_message_keys: set[tuple[str, datetime]] = set()

    for message in messages:
        occurred_at = _aware(getattr(message, "created_at", None))
        if occurred_at is None:
            continue
        direction = _value(getattr(message, "direction", None))
        status = _value(getattr(message, "status", None))
        if direction == "out":
            outbound_times.append(occurred_at)
            if status == "failed":
                failed_message_keys.add((direction, occurred_at.replace(microsecond=0)))
        elif direction == "in":
            inbound_times.append(occurred_at)

    no_answer_call_keys: set[tuple[str, datetime]] = set()
    answered_call_times: list[datetime] = []
    for call in calls:
        occurred_at = _aware(
            getattr(call, "started_at", None) or getattr(call, "created_at", None)
        )
        if occurred_at is None:
            continue
        direction = _value(getattr(call, "call_direction", None)) or "outbound"
        status = _value(getattr(call, "status", None))
        if direction != "inbound":
            outbound_times.append(occurred_at)
            if status in CALL_FAILURE_STATUSES:
                no_answer_call_keys.add((status, occurred_at.replace(microsecond=0)))
        if status in CALL_SUCCESS_STATUSES:
            answered_call_times.append(
                _aware(getattr(call, "completed_at", None)) or occurred_at
            )

    no_shows = 0
    completed_appointments: list[datetime] = []
    for appointment in appointments:
        status = _value(getattr(appointment, "status", None))
        occurred_at = _aware(getattr(appointment, "start_time", None))
        if occurred_at is None:
            continue
        if status == "no_show":
            no_shows += 1
        elif status == "completed":
            completed_appointments.append(occurred_at)

    attempt_times = _group_attempts(outbound_times)
    success_times = sorted(set(inbound_times + answered_call_times))

    if now - created_at < timedelta(hours=MINIMUM_LEAD_AGE_HOURS) or len(attempt_times) < 2:
        payload = _not_scored(
            "insufficient_data",
            "Aún no hay dos intentos separados para evaluar.",
            "Registrar al menos dos intentos separados antes de calificar.",
        )
        payload.update(
            {
                "attempt_count": len(attempt_times),
                "failed_messages": len(failed_message_keys),
                "no_answer_calls": len(no_answer_call_keys),
                "no_shows": no_shows,
                "last_attempt_at": attempt_times[-1] if attempt_times else None,
                "last_response_at": success_times[-1] if success_times else None,
            }
        )
        return payload

    unanswered_attempts = 0
    for index, attempt_at in enumerate(attempt_times):
        next_attempt_at = attempt_times[index + 1] if index + 1 < len(attempt_times) else now
        answered = any(attempt_at <= success_at < next_attempt_at for success_at in success_times)
        if not answered:
            unanswered_attempts += 1

    latest_attempt = attempt_times[-1]
    latest_response = success_times[-1] if success_times else None
    waiting_on_response = latest_response is None or latest_response < latest_attempt
    hours_waiting = (now - latest_attempt).total_seconds() / 3600 if waiting_on_response else 0

    score = min(unanswered_attempts, 3) * 15
    if hours_waiting >= 24 * 7:
        score += 30
    elif hours_waiting >= 48:
        score += 20

    no_answer_calls = len(no_answer_call_keys)
    failed_messages = len(failed_message_keys)
    score += min(no_answer_calls, 2) * 10
    if failed_messages >= 2:
        score += 15
    if no_shows:
        score += 10

    recent_inbound = any(now - value <= timedelta(days=7) for value in inbound_times)
    recent_answered_call = any(
        now - value <= timedelta(days=7) for value in answered_call_times
    )
    recent_completed_appointment = any(
        now - value <= timedelta(days=30) for value in completed_appointments
    )
    if recent_inbound:
        score -= 25
    if recent_answered_call:
        score -= 25
    if recent_completed_appointment:
        score -= 25

    score = max(0, min(100, score))
    level = _level_for_score(score)

    reasons: list[str] = []
    if unanswered_attempts:
        reasons.append(
            f"{unanswered_attempts} intento{'s' if unanswered_attempts != 1 else ''} sin respuesta"
        )
    if hours_waiting >= 24 * 7:
        reasons.append("Más de 7 días esperando respuesta")
    elif hours_waiting >= 48:
        reasons.append("Más de 48 horas esperando respuesta")
    if no_answer_calls:
        reasons.append(
            f"{no_answer_calls} llamada{'s' if no_answer_calls != 1 else ''} no contestada{'s' if no_answer_calls != 1 else ''}"
        )
    if failed_messages >= 2:
        reasons.append("Mensajes con fallas de entrega")
    if no_shows:
        reasons.append(
            f"{no_shows} reunión{'es' if no_shows != 1 else ''} no asistida{'s' if no_shows != 1 else ''}"
        )
    if not reasons and recent_inbound:
        reasons.append("Respondió durante los últimos 7 días")
    if not reasons:
        reasons.append("Seguimiento dentro de rangos normales")

    if failed_messages >= 2:
        suggested_action = "Verificar el teléfono y probar un canal alternativo."
    elif no_answer_calls >= 2:
        suggested_action = "Probar otro horario o enviar un mensaje antes de volver a llamar."
    elif no_shows:
        suggested_action = "Confirmar disponibilidad antes de reagendar."
    elif level in {"difficult", "critical"}:
        suggested_action = "Crear una tarea y probar un canal u horario diferente."
    elif level == "intermittent":
        suggested_action = "Programar un nuevo seguimiento en un horario distinto."
    else:
        suggested_action = "Mantener el seguimiento habitual."

    return {
        "score": score,
        "level": level,
        "reasons": reasons[:3],
        "suggested_action": suggested_action,
        "attempt_count": len(attempt_times),
        "unanswered_attempts": unanswered_attempts,
        "no_answer_calls": no_answer_calls,
        "failed_messages": failed_messages,
        "no_shows": no_shows,
        "last_attempt_at": latest_attempt,
        "last_response_at": latest_response,
    }


class ContactabilityService:
    @staticmethod
    async def calculate_for_leads(
        db: AsyncSession,
        leads: Sequence[Lead],
        *,
        now: Optional[datetime] = None,
    ) -> Dict[int, Dict[str, Any]]:
        if not leads:
            return {}

        now = _aware(now) or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=LOOKBACK_DAYS)
        lead_ids = [lead.id for lead in leads]

        chat_messages = (
            await db.scalars(
                select(ChatMessage).where(
                    ChatMessage.lead_id.in_(lead_ids),
                    ChatMessage.created_at >= cutoff,
                )
            )
        ).all()
        telegram_messages = (
            await db.scalars(
                select(TelegramMessage).where(
                    TelegramMessage.lead_id.in_(lead_ids),
                    TelegramMessage.created_at >= cutoff,
                )
            )
        ).all()
        calls = (
            await db.scalars(
                select(VoiceCall).where(
                    VoiceCall.lead_id.in_(lead_ids),
                    VoiceCall.created_at >= cutoff,
                )
            )
        ).all()
        appointments = (
            await db.scalars(
                select(Appointment).where(
                    Appointment.lead_id.in_(lead_ids),
                    Appointment.start_time >= cutoff,
                )
            )
        ).all()

        messages_by_lead: dict[int, list[Any]] = defaultdict(list)
        calls_by_lead: dict[int, list[Any]] = defaultdict(list)
        appointments_by_lead: dict[int, list[Any]] = defaultdict(list)
        for message in [*chat_messages, *telegram_messages]:
            messages_by_lead[message.lead_id].append(message)
        for call in calls:
            calls_by_lead[call.lead_id].append(call)
        for appointment in appointments:
            appointments_by_lead[appointment.lead_id].append(appointment)

        return {
            lead.id: calculate_contactability(
                lead,
                messages_by_lead[lead.id],
                calls_by_lead[lead.id],
                appointments_by_lead[lead.id],
                now=now,
            )
            for lead in leads
        }

    @classmethod
    async def summary(
        cls,
        db: AsyncSession,
        *,
        broker_id: Optional[int] = None,
        assigned_to: Optional[int] = None,
    ) -> Dict[str, Any]:
        query = select(Lead).where(
            ((Lead.pipeline_stage.is_(None)) | (Lead.pipeline_stage.notin_(CLOSED_STAGES))),
            Lead.status.notin_(["converted", "lost"]),
        )
        if broker_id is not None:
            query = query.where(Lead.broker_id == broker_id)
        if assigned_to is not None:
            query = query.where(Lead.assigned_to == assigned_to)
        leads = (await db.scalars(query)).all()
        metrics = await cls.calculate_for_leads(db, leads)
        counts = {level: 0 for level in LEVELS}
        for item in metrics.values():
            counts[item["level"]] += 1
        return {
            "counts": counts,
            "difficult_total": counts["difficult"] + counts["critical"],
            "evaluated_total": len(leads) - counts["insufficient_data"],
            "active_total": len(leads),
        }
