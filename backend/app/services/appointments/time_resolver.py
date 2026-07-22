"""Deterministic date/time resolution for appointment tools.

LLMs may identify the user's intent, but they must not decide what a relative
date means.  This module resolves Spanish relative/absolute dates on the
server, in the broker timezone, and applies the scheduling safety window.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Mapping, Optional

import pytz


DEFAULT_TIMEZONE = "America/Santiago"
DEFAULT_DURATION_MINUTES = 30
MIN_LEAD_TIME_MINUTES = 30


class SchedulingTimeError(ValueError):
    """Validation error with a stable code suitable for tools and APIs."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ResolvedScheduleTime:
    start_time: datetime
    source: str
    timezone: str


_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
_WEEKDAYS = {
    "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2,
    "jueves": 3, "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6,
}


def _timezone(name: Optional[str]):
    try:
        return pytz.timezone(name or DEFAULT_TIMEZONE)
    except Exception as exc:
        raise SchedulingTimeError("invalid_timezone", "Zona horaria inválida") from exc


def _parse_local_time(value: Any, text: str = "") -> time:
    raw = str(value or "").strip()
    candidates = [raw] if raw else []
    candidates.extend(
        f"{m.group(1)}:{m.group(2) or '00'}"
        for m in re.finditer(r"(?<!\d)([01]?\d|2[0-3])(?:[:.h]([0-5]\d))?(?:\s*(?:hrs?|horas?))?", text.lower())
        if m.group(2) is not None or re.search(r"hrs?|horas?", m.group(0))
    )
    for candidate in reversed(candidates):
        match = re.fullmatch(r"\s*([01]?\d|2[0-3])(?:[:.]([0-5]\d))?\s*", candidate)
        if match:
            return time(int(match.group(1)), int(match.group(2) or 0))
    raise SchedulingTimeError("missing_local_time", "Falta una hora válida para agendar")


def _absolute_date_from_text(text: str) -> Optional[date]:
    match = re.search(
        r"(?<!\d)(\d{1,2})\s+de\s+(" + "|".join(_MONTHS) + r")(?:\s+(?:de|del)\s+(\d{4}))?",
        text.lower(),
    )
    if not match:
        return None
    year = int(match.group(3)) if match.group(3) else None
    if year is None:
        raise SchedulingTimeError("ambiguous_relative_date", "La fecha absoluta debe incluir el año")
    try:
        return date(year, _MONTHS[match.group(2)], int(match.group(1)))
    except ValueError as exc:
        raise SchedulingTimeError("invalid_local_date", "La fecha indicada no existe") from exc


def _last_relative_reference(text: str) -> Optional[str]:
    matches = [(m.start(), "today") for m in re.finditer(r"\bhoy\b", text.lower())]
    matches += [(m.start(), "tomorrow") for m in re.finditer(r"\bmañana\b|\bmanana\b", text.lower())]
    return max(matches)[1] if matches else None


def resolve_schedule_time(
    arguments: Mapping[str, Any],
    *,
    timezone_name: str = DEFAULT_TIMEZONE,
    conversation_text: str = "",
    now: Optional[datetime] = None,
) -> ResolvedScheduleTime:
    """Resolve structured tool arguments without trusting an LLM-generated year."""
    tz = _timezone(timezone_name)
    local_now = now.astimezone(tz) if now and now.tzinfo else (tz.localize(now) if now else datetime.now(tz))
    text = conversation_text or ""
    explicit_from_text = _absolute_date_from_text(text)
    relative_from_text = _last_relative_reference(text)
    reference = relative_from_text or str(arguments.get("date_reference") or "").lower()

    if explicit_from_text:
        target_date = explicit_from_text
        source = "absolute_text"
    elif reference == "today":
        target_date = local_now.date()
        source = "today"
    elif reference == "tomorrow":
        target_date = local_now.date() + timedelta(days=1)
        source = "tomorrow"
    elif reference == "absolute" or arguments.get("local_date"):
        try:
            target_date = date.fromisoformat(str(arguments.get("local_date")))
        except Exception as exc:
            raise SchedulingTimeError("invalid_local_date", "Fecha absoluta inválida; usa YYYY-MM-DD") from exc
        source = "absolute_argument"
    elif arguments.get("start_time"):
        try:
            parsed = datetime.fromisoformat(str(arguments["start_time"]).replace("Z", "+00:00"))
        except Exception as exc:
            raise SchedulingTimeError("invalid_start_time", "start_time debe usar ISO 8601") from exc
        if parsed.tzinfo is None:
            parsed = tz.localize(parsed)
        return ResolvedScheduleTime(parsed.astimezone(tz), "legacy_iso", timezone_name)
    else:
        raise SchedulingTimeError("ambiguous_relative_date", "No se pudo determinar el día de la cita")

    mentioned_weekdays = [(_WEEKDAYS[name], name) for name in _WEEKDAYS if re.search(rf"\b{name}\b", text.lower())]
    if mentioned_weekdays and mentioned_weekdays[-1][0] != target_date.weekday():
        raise SchedulingTimeError(
            "ambiguous_relative_date",
            f"El día mencionado ({mentioned_weekdays[-1][1]}) no coincide con la fecha calculada",
        )

    local_time = _parse_local_time(arguments.get("local_time"), text)
    return ResolvedScheduleTime(tz.localize(datetime.combine(target_date, local_time)), source, timezone_name)


def validate_future_start(
    start_time: datetime,
    *,
    timezone_name: str = DEFAULT_TIMEZONE,
    now: Optional[datetime] = None,
    min_lead_minutes: int = MIN_LEAD_TIME_MINUTES,
) -> datetime:
    tz = _timezone(timezone_name)
    if start_time.tzinfo is None:
        start_time = tz.localize(start_time)
    local_start = start_time.astimezone(tz)
    local_now = now.astimezone(tz) if now and now.tzinfo else (tz.localize(now) if now else datetime.now(tz))
    if local_start <= local_now:
        raise SchedulingTimeError("appointment_in_past", "No se puede agendar una cita en el pasado")
    if local_start < local_now + timedelta(minutes=min_lead_minutes):
        raise SchedulingTimeError(
            "insufficient_lead_time",
            f"La cita requiere al menos {min_lead_minutes} minutos de anticipación",
        )
    return local_start
