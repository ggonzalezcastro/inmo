"""
Unit tests for app.core.circuit_breakers

Covers:
- get_breaker_states returns all expected breakers
- All state strings are valid
- Breakers start in "closed" state
- State strings match pybreaker conventions
"""
import pytest
from app.core.circuit_breakers import (
    get_breaker_states,
    llm_breaker,
    calendar_breaker,
    telegram_breaker,
    _ALL_BREAKERS,
)


# ── State helpers ─────────────────────────────────────────────────────────────

def test_get_breaker_states_returns_all_breakers():
    states = get_breaker_states()
    assert "llm" in states
    assert "calendar" in states
    assert "telegram" in states


def test_get_breaker_states_all_closed_initially():
    states = get_breaker_states()
    for name, state in states.items():
        assert state == "closed", f"Expected closed, got {state!r} for {name}"


def test_all_breakers_list_matches_get_breaker_states():
    states = get_breaker_states()
    assert len(states) == len(_ALL_BREAKERS)


# ── Breaker configuration ────────────────────────────────────────────────────

def test_llm_breaker_has_correct_name():
    assert llm_breaker.name == "llm"


def test_calendar_breaker_has_correct_name():
    assert calendar_breaker.name == "calendar"


def test_telegram_breaker_has_correct_name():
    assert telegram_breaker.name == "telegram"


def test_llm_breaker_fail_max():
    assert llm_breaker.fail_max == 5


def test_calendar_breaker_fail_max():
    assert calendar_breaker.fail_max == 3


def test_telegram_breaker_fail_max():
    assert telegram_breaker.fail_max == 5


def test_llm_breaker_reset_timeout():
    assert llm_breaker.reset_timeout == 30


def test_calendar_breaker_reset_timeout():
    assert calendar_breaker.reset_timeout == 60


# ── Sync call passes through on success ──────────────────────────────────────

def test_breaker_call_passthrough():
    def fn(): return 42
    result = llm_breaker.call(fn)
    assert result == 42


def test_breaker_increments_fail_counter_on_error():
    import pybreaker
    # Use a dedicated fresh breaker so we don't affect the singleton
    breaker = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=60)
    initial = breaker.fail_counter

    def bad_fn(): raise ValueError("fail")

    with pytest.raises(ValueError):
        breaker.call(bad_fn)

    assert breaker.fail_counter > initial


def test_breaker_opens_after_fail_max():
    import pybreaker
    breaker = pybreaker.CircuitBreaker(fail_max=2, reset_timeout=60)

    def bad_fn(): raise ValueError("fail")

    for _ in range(2):
        with pytest.raises((ValueError, pybreaker.CircuitBreakerError)):
            breaker.call(bad_fn)

    assert breaker.current_state == "open"
