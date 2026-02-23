"""
Circuit breakers for external service calls.

Each breaker tracks failures for one external service.  When `fail_max`
consecutive failures occur within `reset_timeout` seconds, the breaker
OPENS and immediately raises `CircuitBreakerError` on subsequent calls,
protecting the pipeline from cascading timeouts.

Breakers defined here (singletons, module-level):
  - llm_breaker        — LLM API calls (Gemini / Claude / OpenAI)
  - calendar_breaker   — Google Calendar API
  - telegram_breaker   — Telegram Bot API

Usage::

    from app.core.circuit_breakers import llm_breaker

    # Option A — decorator (sync & async)
    @llm_breaker
    async def call_llm(): ...

    # Option B — explicit call (async)
    result = await llm_breaker.call_async(coro_fn, *args, **kwargs)

    # Option C — sync
    result = llm_breaker.call(sync_fn, *args, **kwargs)

Health state::

    from app.core.circuit_breakers import get_breaker_states
    states = get_breaker_states()
    # Returns {"llm": "closed", "calendar": "open", "telegram": "closed"}
"""
import logging
from typing import Dict

import pybreaker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Listener — logs state transitions
# ---------------------------------------------------------------------------

class _LoggingListener(pybreaker.CircuitBreakerListener):
    """Emit a log line on every state transition."""

    def state_change(self, cb: pybreaker.CircuitBreaker, old_state, new_state) -> None:
        if new_state.name == "open":
            logger.error(
                "[CircuitBreaker] OPENED — %s is now unavailable",
                cb.name,
                extra={"breaker": cb.name, "failures": cb.fail_counter},
            )
        elif new_state.name == "half-open":
            logger.warning(
                "[CircuitBreaker] HALF-OPEN — testing %s", cb.name,
                extra={"breaker": cb.name},
            )
        elif new_state.name == "closed":
            logger.info(
                "[CircuitBreaker] CLOSED — %s recovered", cb.name,
                extra={"breaker": cb.name},
            )


_listener = _LoggingListener()


# ---------------------------------------------------------------------------
# Breaker definitions
# ---------------------------------------------------------------------------

#: LLM providers — open after 5 consecutive failures, re-test after 30 s
llm_breaker: pybreaker.CircuitBreaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=30,
    listeners=[_listener],
    name="llm",
)

#: Google Calendar — open after 3 failures, re-test after 60 s
calendar_breaker: pybreaker.CircuitBreaker = pybreaker.CircuitBreaker(
    fail_max=3,
    reset_timeout=60,
    listeners=[_listener],
    name="calendar",
)

#: Telegram Bot API — open after 5 failures, re-test after 60 s
telegram_breaker: pybreaker.CircuitBreaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    listeners=[_listener],
    name="telegram",
)

_ALL_BREAKERS: list[pybreaker.CircuitBreaker] = [
    llm_breaker,
    calendar_breaker,
    telegram_breaker,
]


# ---------------------------------------------------------------------------
# Health helper
# ---------------------------------------------------------------------------

def get_breaker_states() -> Dict[str, str]:
    """
    Return a dict of {name: state_string} for all circuit breakers.

    State strings: "closed" (healthy), "open" (unavailable), "half-open" (testing).
    """
    return {
        cb.name: cb.current_state
        for cb in _ALL_BREAKERS
    }
