"""
LLM call persistence helper.

Writes one `LLMCall` row per API round-trip.
Fire-and-forget: errors are swallowed and logged so they never block the
caller.

Usage::

    from app.services.llm.call_logger import log_llm_call

    await log_llm_call(
        provider="gemini",
        model="gemini-2.5-flash",
        call_type="chat_response",
        input_tokens=320,
        output_tokens=85,
        latency_ms=740,
        broker_id=3,
        lead_id=42,
        used_fallback=False,
    )
"""
import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ── Cost table (USD per 1 000 tokens, input / output) ─────────────────────────
# Sources: public pricing pages as of 2026-02-21
_COST_TABLE: dict[str, tuple[float, float]] = {
    "gemini-3.1-pro":                     (0.001250, 0.010000),
    "gemini-2.5-pro":                     (0.001250, 0.010000),
    "gemini-2.5-flash":                   (0.000075, 0.000300),
    "gemini-2.0-flash":                   (0.000075, 0.000300),
    "gemini-1.5-flash":                   (0.000075, 0.000300),
    "gemini-1.5-pro":                     (0.001250, 0.005000),
    "claude-opus-4-6":                    (0.015000, 0.075000),
    "claude-sonnet-4-6":                  (0.003000, 0.015000),
    "claude-sonnet-4-20250514":           (0.003000, 0.015000),
    "claude-haiku-4-5-20251001":          (0.000800, 0.004000),
    "gpt-4o":                             (0.005000, 0.015000),
    "gpt-4o-mini":                        (0.000150, 0.000600),
}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> Optional[float]:
    """Return estimated USD cost or None if model is not in the price table."""
    key = model.lower()
    for table_key, (in_price, out_price) in _COST_TABLE.items():
        if table_key in key:
            cost = (input_tokens / 1_000) * in_price + (output_tokens / 1_000) * out_price
            return round(cost, 8)
    return None


async def log_llm_call(
    *,
    provider: str,
    model: str,
    call_type: str,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    latency_ms: Optional[int] = None,
    broker_id: Optional[int] = None,
    lead_id: Optional[int] = None,
    used_fallback: bool = False,
    error: Optional[str] = None,
    actual_cost_usd: Optional[float] = None,
) -> None:
    """
    Persist one LLMCall row.  Errors are silently swallowed so that
    observability failures never propagate to the chat pipeline.
    """
    try:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        from app.config import settings
        from app.models.llm_call import LLMCall

        if actual_cost_usd is not None:
            estimated_cost = actual_cost_usd
        elif input_tokens is not None and output_tokens is not None:
            estimated_cost = _estimate_cost(model, input_tokens, output_tokens)
        else:
            estimated_cost = None

        row = LLMCall(
            broker_id=broker_id,
            lead_id=lead_id,
            provider=provider,
            model=model,
            call_type=call_type,
            used_fallback=1 if used_fallback else 0,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost,
            latency_ms=latency_ms,
            error=error,
        )

        # Create a local engine bound to the current event loop so this works
        # both in FastAPI (shared loop) and Celery tasks (asyncio.run per task).
        _engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_size=1, max_overflow=0)
        _session = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with _session() as db:
                db.add(row)
                await db.commit()
        finally:
            try:
                await _engine.dispose()
            except Exception:
                pass

    except Exception as exc:  # noqa: BLE001
        logger.warning("[LLMCallLogger] Failed to persist call row: %s", exc)
