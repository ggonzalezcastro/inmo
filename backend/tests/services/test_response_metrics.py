"""Unit tests for response-time metrics and the fast-responder tag helper.

Run with ``--noconftest`` to skip the integration conftest that requires a
running database/Redis::

    .venv/bin/python -m pytest tests/services/test_response_metrics.py -v --noconftest
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from app.services.leads.constants import (
    FAST_RESPONDER_TAG,
    FAST_RESPONSE_MIN_REPLIES,
    FAST_RESPONSE_THRESHOLD_SECONDS,
)
from app.services.leads.response_metrics import (
    apply_fast_responder_tag,
    compute_response_metrics,
)


@dataclass
class FakeMsg:
    direction: str
    created_at: datetime


def _now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _seq(deltas_seconds, *, start_outbound: bool = True):
    """Build alternating OUT/IN messages with the given inbound deltas.

    ``deltas_seconds[i]`` is the gap between bot message i and lead reply i.
    """
    base = _now()
    msgs = []
    cursor = base
    for d in deltas_seconds:
        if start_outbound:
            msgs.append(FakeMsg("out", cursor))
            cursor = cursor + timedelta(seconds=d)
            msgs.append(FakeMsg("in", cursor))
            cursor = cursor + timedelta(seconds=10)  # idle gap before next bot msg
    return msgs


def test_empty_messages_returns_neutral_payload():
    m = compute_response_metrics([])
    assert m["reply_count"] == 0
    assert m["avg_response_seconds"] is None
    assert m["is_fast_responder"] is False
    assert m["threshold_seconds"] == FAST_RESPONSE_THRESHOLD_SECONDS


def test_only_outbound_messages_no_replies():
    base = _now()
    msgs = [FakeMsg("out", base + timedelta(seconds=i * 30)) for i in range(3)]
    m = compute_response_metrics(msgs)
    assert m["reply_count"] == 0
    assert m["is_fast_responder"] is False


def test_inbound_before_any_outbound_is_ignored():
    base = _now()
    msgs = [
        FakeMsg("in", base),  # initial user-initiated message — no bot to time against
        FakeMsg("out", base + timedelta(seconds=5)),
        FakeMsg("in", base + timedelta(seconds=15)),  # 10s reply
    ]
    m = compute_response_metrics(msgs)
    assert m["reply_count"] == 1
    assert m["avg_response_seconds"] == 10.0


def test_consecutive_inbounds_count_once():
    base = _now()
    msgs = [
        FakeMsg("out", base),
        FakeMsg("in", base + timedelta(seconds=20)),  # counted: 20s
        FakeMsg("in", base + timedelta(seconds=25)),  # NOT counted (no new outbound)
        FakeMsg("out", base + timedelta(seconds=30)),
        FakeMsg("in", base + timedelta(seconds=40)),  # counted: 10s
    ]
    m = compute_response_metrics(msgs)
    assert m["reply_count"] == 2
    assert m["avg_response_seconds"] == 15.0


def test_fast_responder_threshold_and_min_replies():
    # Three replies all under threshold → should tag.
    msgs = _seq([10, 20, 30])
    m = compute_response_metrics(msgs)
    assert m["reply_count"] == 3
    assert m["avg_response_seconds"] == 20.0
    assert m["fast_reply_count"] == 3
    assert m["is_fast_responder"] is True


def test_min_replies_not_reached_does_not_tag():
    assert FAST_RESPONSE_MIN_REPLIES >= 2
    msgs = _seq([5, 5])  # only 2 replies
    m = compute_response_metrics(msgs)
    assert m["reply_count"] == 2
    assert m["is_fast_responder"] is False


def test_avg_above_threshold_does_not_tag():
    # 3 replies but avg above threshold.
    msgs = _seq([10, 30, 600])  # avg ≈ 213s > 60s
    m = compute_response_metrics(msgs)
    assert m["reply_count"] == 3
    assert m["avg_response_seconds"] > FAST_RESPONSE_THRESHOLD_SECONDS
    assert m["is_fast_responder"] is False


def test_apply_tag_adds_when_qualifying():
    msgs = _seq([10, 20, 30])
    m = compute_response_metrics(msgs)
    new_tags, changed = apply_fast_responder_tag(["existing"], m)
    assert changed is True
    assert FAST_RESPONDER_TAG in new_tags
    assert "existing" in new_tags


def test_apply_tag_idempotent_when_already_present():
    m = compute_response_metrics(_seq([10, 20, 30]))
    new_tags, changed = apply_fast_responder_tag([FAST_RESPONDER_TAG], m)
    assert changed is False
    assert new_tags.count(FAST_RESPONDER_TAG) == 1


def test_apply_tag_removes_when_no_longer_qualifying():
    # Lead previously tagged but recent metrics show slow responses.
    slow_metrics = compute_response_metrics(_seq([300, 400, 500]))
    assert slow_metrics["is_fast_responder"] is False
    new_tags, changed = apply_fast_responder_tag(
        [FAST_RESPONDER_TAG, "interesado"], slow_metrics
    )
    assert changed is True
    assert FAST_RESPONDER_TAG not in new_tags
    assert "interesado" in new_tags


def test_apply_tag_no_change_when_neither_qualifies_nor_present():
    m = compute_response_metrics([])
    new_tags, changed = apply_fast_responder_tag(["other"], m)
    assert changed is False
    assert new_tags == ["other"]


def test_negative_or_zero_deltas_are_ignored():
    base = _now()
    msgs = [
        FakeMsg("out", base),
        FakeMsg("in", base),  # 0s — clock skew, ignored
        FakeMsg("out", base + timedelta(seconds=10)),
        FakeMsg("in", base + timedelta(seconds=15)),  # 5s, counted
    ]
    m = compute_response_metrics(msgs)
    assert m["reply_count"] == 1
    assert m["avg_response_seconds"] == 5.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
