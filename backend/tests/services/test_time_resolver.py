from datetime import datetime

import pytest
import pytz

from app.services.appointments.time_resolver import (
    SchedulingTimeError,
    resolve_schedule_time,
    validate_future_start,
)


TZ = pytz.timezone("America/Santiago")
NOW = TZ.localize(datetime(2026, 7, 20, 16, 0))


def test_tomorrow_is_resolved_by_backend_clock():
    resolved = resolve_schedule_time(
        {"date_reference": "tomorrow", "local_time": "14:00"},
        conversation_text="Quiero una cita mañana martes a las 14:00",
        now=NOW,
    )
    assert resolved.start_time.isoformat().startswith("2026-07-21T14:00:00")


def test_relative_weekday_mismatch_is_rejected():
    with pytest.raises(SchedulingTimeError) as exc:
        resolve_schedule_time(
            {"date_reference": "tomorrow", "local_time": "14:00"},
            conversation_text="mañana miércoles a las 14:00",
            now=NOW,
        )
    assert exc.value.code == "ambiguous_relative_date"


def test_past_and_short_notice_are_rejected():
    with pytest.raises(SchedulingTimeError) as past:
        validate_future_start(TZ.localize(datetime(2025, 1, 21, 14)), now=NOW)
    assert past.value.code == "appointment_in_past"

    with pytest.raises(SchedulingTimeError) as short:
        validate_future_start(TZ.localize(datetime(2026, 7, 20, 16, 15)), now=NOW)
    assert short.value.code == "insufficient_lead_time"
