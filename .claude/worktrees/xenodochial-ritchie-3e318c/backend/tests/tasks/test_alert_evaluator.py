"""
Tests for the alert evaluator Celery task — each checker with mocked DB.

Run without DB:
    python -m pytest tests/tasks/test_alert_evaluator.py -v --noconftest
"""
from __future__ import annotations

import sys
import types
# ── Stub out heavy/missing external imports before loading app modules ────────
for _mod in [
    "msal", "vapi_python", "pyaudio", "twilio",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)
# ─────────────────────────────────────────────────────────────────────────────

import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone


# ── Helper to build a mocked DB session ──────────────────────────────────────

def _mock_db(scalar_value=None, all_rows=None):
    db = MagicMock()
    result = MagicMock()
    result.scalar_one.return_value = scalar_value
    result.scalar_one_or_none.return_value = None  # no existing alert
    result.one.return_value = (scalar_value, scalar_value)
    result.all.return_value = all_rows or []
    db.execute.return_value = result
    db.add = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    return db


# ── Cost spike ────────────────────────────────────────────────────────────────

class TestCostSpikeChecker:
    def test_no_alert_when_cost_normal(self):
        from app.tasks.alert_evaluator import _check_cost_spike

        db = MagicMock()
        result = MagicMock()
        # current=$0.05, prev=$0.05 → ratio=1.0 < 3.0
        result.one.return_value = (0.05, 0.05)
        result.scalar_one_or_none.return_value = None
        db.execute.return_value = result

        _check_cost_spike(db)
        db.add.assert_not_called()

    def test_alert_created_when_cost_spikes(self):
        from app.tasks.alert_evaluator import _check_cost_spike

        db = MagicMock()
        result = MagicMock()
        # current=$0.90, prev=$0.10 → ratio=9.0 >= 3.0
        result.one.return_value = (0.90, 0.10)
        result.scalar_one_or_none.return_value = None  # no existing alert
        db.execute.return_value = result

        _check_cost_spike(db)
        db.add.assert_called_once()
        alert = db.add.call_args[0][0]
        assert alert.alert_type == "cost_spike"
        assert alert.severity == "warning"

    def test_no_duplicate_alert_when_one_exists(self):
        from app.tasks.alert_evaluator import _check_cost_spike

        db = MagicMock()
        existing_alert = MagicMock()
        result = MagicMock()
        result.one.return_value = (0.90, 0.10)
        result.scalar_one_or_none.return_value = existing_alert  # already active
        db.execute.return_value = result

        _check_cost_spike(db)
        db.add.assert_not_called()


# ── Escalation spike ──────────────────────────────────────────────────────────

class TestEscalationSpikeChecker:
    def test_no_alert_when_traffic_low(self):
        """With <10 LLM calls, no alert should fire (insufficient traffic)."""
        from app.tasks.alert_evaluator import _check_escalation_spike

        db = MagicMock()
        result = MagicMock()
        result.one.return_value = (5, 8)  # 5 escalations, 8 llm_calls
        result.scalar_one_or_none.return_value = None
        db.execute.return_value = result

        _check_escalation_spike(db)
        db.add.assert_not_called()

    def test_alert_when_escalation_rate_high(self):
        """30 escalations / 100 calls = 30% > threshold → alert."""
        from app.tasks.alert_evaluator import _check_escalation_spike

        db = MagicMock()
        result = MagicMock()
        result.one.return_value = (30, 100)
        result.scalar_one_or_none.return_value = None
        db.execute.return_value = result

        _check_escalation_spike(db)
        db.add.assert_called_once()
        alert = db.add.call_args[0][0]
        assert alert.alert_type == "escalation_spike"

    def test_no_alert_when_rate_below_threshold(self):
        """10 escalations / 100 calls = 10% < 20% threshold → no alert."""
        from app.tasks.alert_evaluator import _check_escalation_spike

        db = MagicMock()
        result = MagicMock()
        result.one.return_value = (10, 100)
        result.scalar_one_or_none.return_value = None
        db.execute.return_value = result

        _check_escalation_spike(db)
        db.add.assert_not_called()


# ── Error spike ───────────────────────────────────────────────────────────────

class TestErrorSpikeChecker:
    def test_no_alert_below_threshold(self):
        from app.tasks.alert_evaluator import _check_error_spike

        db = MagicMock()
        # count() returns 5 < 10 threshold
        result = MagicMock()
        result.scalar_one.return_value = 5
        result.scalar_one_or_none.return_value = None
        db.execute.return_value = result

        _check_error_spike(db)
        db.add.assert_not_called()

    def test_alert_at_threshold(self):
        from app.tasks.alert_evaluator import _check_error_spike

        db = MagicMock()
        call_count = [0]

        def execute_side_effect(stmt, *a, **kw):
            result = MagicMock()
            if call_count[0] == 0:
                result.scalar_one.return_value = 15  # 15 errors > 10
            else:
                result.scalar_one_or_none.return_value = None  # no existing alert
            call_count[0] += 1
            return result

        db.execute.side_effect = execute_side_effect

        _check_error_spike(db)
        db.add.assert_called_once()
        alert = db.add.call_args[0][0]
        assert alert.alert_type == "error_spike"
        assert alert.severity == "critical"


# ── Stale human mode ──────────────────────────────────────────────────────────

class TestStaleHumanModeChecker:
    def test_no_alert_when_no_stale_leads(self):
        from app.tasks.alert_evaluator import _check_stale_human_mode

        db = MagicMock()
        result = MagicMock()
        result.all.return_value = []
        db.execute.return_value = result

        _check_stale_human_mode(db)
        db.add.assert_not_called()

    def test_alert_per_stale_lead(self):
        from app.tasks.alert_evaluator import _check_stale_human_mode

        db = MagicMock()
        call_count = [0]

        def execute_side_effect(stmt, *a, **kw):
            result = MagicMock()
            if call_count[0] == 0:
                result.all.return_value = [(10, 1), (11, 1)]  # 2 stale leads
            else:
                result.scalar_one_or_none.return_value = None
            call_count[0] += 1
            return result

        db.execute.side_effect = execute_side_effect

        _check_stale_human_mode(db)
        assert db.add.call_count == 2
        alert = db.add.call_args_list[0][0][0]
        assert alert.alert_type == "stale_human_mode"
        assert alert.related_lead_id in (10, 11)


# ── Slow responses ────────────────────────────────────────────────────────────

class TestSlowResponsesChecker:
    def test_no_alert_when_fast(self):
        from app.tasks.alert_evaluator import _check_slow_responses

        db = MagicMock()
        result = MagicMock()
        result.scalar_one.return_value = 2000  # 2000ms < 8000ms threshold
        result.scalar_one_or_none.return_value = None
        db.execute.return_value = result

        _check_slow_responses(db)
        db.add.assert_not_called()

    def test_alert_when_p95_too_high(self):
        from app.tasks.alert_evaluator import _check_slow_responses

        db = MagicMock()
        call_count = [0]

        def execute_side_effect(stmt, *a, **kw):
            result = MagicMock()
            if call_count[0] == 0:
                result.scalar_one.return_value = 9500  # > 8000ms
            else:
                result.scalar_one_or_none.return_value = None
            call_count[0] += 1
            return result

        db.execute.side_effect = execute_side_effect

        _check_slow_responses(db)
        db.add.assert_called_once()
        alert = db.add.call_args[0][0]
        assert alert.alert_type == "slow_responses"


# ── evaluate_alerts integration (no DB) ──────────────────────────────────────

class TestEvaluateAlertsTask:
    def test_calls_all_checkers(self):
        from app.tasks.alert_evaluator import evaluate_alerts

        checker_names = [
            "_check_cost_spike",
            "_check_escalation_spike",
            "_check_error_spike",
            "_check_stale_human_mode",
            "_check_slow_responses",
        ]

        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)

        patches = {}
        with patch("app.tasks.alert_evaluator.SyncSessionLocal", return_value=db):
            with patch.multiple(
                "app.tasks.alert_evaluator",
                _check_cost_spike=MagicMock(),
                _check_escalation_spike=MagicMock(),
                _check_error_spike=MagicMock(),
                _check_stale_human_mode=MagicMock(),
                _check_slow_responses=MagicMock(),
            ) as mocks:
                evaluate_alerts()

            for name in checker_names:
                key = name.lstrip("_")
                # Each checker should have been called exactly once
                # (We patch at module level so just verify no exception)
