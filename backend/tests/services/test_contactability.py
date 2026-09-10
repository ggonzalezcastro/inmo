"""Deterministic contactability scoring tests."""

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

os.environ["DEBUG"] = "false"

from app.services.leads.contactability_service import (  # noqa: E402
    calculate_contactability,
)


NOW = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)


def _lead(*, age_days=20, stage="entrada", status="warm"):
    return SimpleNamespace(
        id=10,
        created_at=NOW - timedelta(days=age_days),
        pipeline_stage=stage,
        status=status,
    )


def _message(days_ago: float, direction="out", status="delivered"):
    return SimpleNamespace(
        created_at=NOW - timedelta(days=days_ago),
        direction=direction,
        status=status,
    )


def _call(days_ago: float, status="no_answer"):
    return SimpleNamespace(
        created_at=NOW - timedelta(days=days_ago),
        started_at=NOW - timedelta(days=days_ago),
        completed_at=None,
        call_direction="outbound",
        status=status,
    )


def _appointment(days_ago: float, status="no_show"):
    return SimpleNamespace(
        start_time=NOW - timedelta(days=days_ago),
        status=status,
    )


def test_new_lead_is_not_labelled_difficult():
    metric = calculate_contactability(
        _lead(age_days=1),
        [_message(0.8), _message(0.2)],
        [],
        [],
        now=NOW,
    )

    assert metric["level"] == "insufficient_data"
    assert metric["score"] is None


def test_message_burst_counts_as_one_attempt_and_separate_follow_up_as_another():
    metric = calculate_contactability(
        _lead(),
        [
            _message(5),
            _message(5 - 4 / 24),
            _message(5 - 11 / 24),
            _message(3),
        ],
        [],
        [],
        now=NOW,
    )

    assert metric["attempt_count"] == 2
    assert metric["unanswered_attempts"] == 2
    assert metric["level"] == "difficult"


def test_repeated_old_attempts_become_critical():
    metric = calculate_contactability(
        _lead(age_days=40),
        [_message(20), _message(15), _message(10)],
        [],
        [],
        now=NOW,
    )

    assert metric["score"] == 75
    assert metric["level"] == "critical"
    assert "Más de 7 días esperando respuesta" in metric["reasons"]


def test_recent_response_reduces_risk():
    metric = calculate_contactability(
        _lead(),
        [_message(10), _message(5), _message(4, direction="in", status="read")],
        [],
        [],
        now=NOW,
    )

    assert metric["level"] == "contactable"
    assert metric["score"] == 0
    assert metric["last_response_at"] == NOW - timedelta(days=4)


def test_unanswered_calls_and_no_show_are_explained():
    metric = calculate_contactability(
        _lead(),
        [],
        [_call(6), _call(3, status="busy")],
        [_appointment(2)],
        now=NOW,
    )

    assert metric["level"] == "critical"
    assert metric["no_answer_calls"] == 2
    assert metric["no_shows"] == 1
    assert "llamadas no contestadas" in " ".join(metric["reasons"])
    assert "otro horario" in metric["suggested_action"]


def test_repeated_delivery_failures_suggest_another_channel():
    metric = calculate_contactability(
        _lead(),
        [_message(6, status="failed"), _message(3, status="failed")],
        [],
        [],
        now=NOW,
    )

    assert metric["failed_messages"] == 2
    assert metric["level"] == "difficult"
    assert "canal alternativo" in metric["suggested_action"]


def test_closed_lead_is_not_evaluated():
    metric = calculate_contactability(
        _lead(stage="ganado", status="converted"),
        [_message(20), _message(10)],
        [],
        [],
        now=NOW,
    )

    assert metric["level"] == "not_applicable"
    assert metric["score"] is None
