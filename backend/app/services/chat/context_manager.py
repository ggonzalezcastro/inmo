"""
ContextWindowManager — keeps the LLM conversation window bounded.

When a conversation grows beyond SUMMARIZE_THRESHOLD messages, the older
portion is replaced with a compact LLM-generated summary.  The summary is
stored in `lead_metadata["conversation_summary"]` so it survives across
sessions (TASK-009: returning-lead context recovery).

Flow
----
1. Load full message history (up to 20 from DB — see context_service.py).
2. If len(messages) >= SUMMARIZE_THRESHOLD:
   a. Split: "to summarise" = messages[:-KEEP_RECENT], "recent" = messages[-KEEP_RECENT:]
   b. Call LLM to summarise the older messages (appending any prior summary).
   c. Persist the new summary to lead_metadata["conversation_summary"].
   d. Return (new_summary, recent_messages).
3. Otherwise return (existing_summary_or_None, messages) unchanged.

Callers then inject the summary into the system prompt (build_llm_prompt) and
pass only the recent messages to the LLM.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple, Dict, Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ── Tunables ─────────────────────────────────────────────────────────────────

#: Trigger summarisation when message count reaches this value
SUMMARIZE_THRESHOLD: int = 10

#: Keep this many recent messages uncompressed for immediate context
KEEP_RECENT: int = 4

#: Tokens budget for the summary LLM call
_SUMMARY_MAX_TOKENS: int = 300


# ── Public helpers ────────────────────────────────────────────────────────────

def should_summarize(messages: List[Dict[str, Any]]) -> bool:
    """Return True when the conversation window needs compression."""
    return len(messages) >= SUMMARIZE_THRESHOLD


async def summarize_conversation(
    messages: List[Dict[str, Any]],
    prior_summary: Optional[str] = None,
) -> str:
    """
    Ask the LLM for a bullet-point summary of *messages*.

    If *prior_summary* is provided it is prepended so the new summary
    incorporates earlier context too.

    Returns the summary string, or an empty string on failure.
    """
    from app.services.llm.factory import get_llm_provider

    provider = get_llm_provider()
    if not provider.is_configured:
        return prior_summary or ""

    # Build text block from messages
    lines = []
    for m in messages:
        role = "Lead" if m.get("role") == "user" else "Agente"
        lines.append(f"{role}: {m.get('content', '')}")
    conversation_text = "\n".join(lines)

    prior_block = (
        f"\n\nRESUMEN PREVIO:\n{prior_summary}\n" if prior_summary else ""
    )

    prompt = (
        f"Eres un asistente de ventas inmobiliarias. Resume esta conversación "
        f"en viñetas cortas (máx 5) capturando: datos del lead recopilados, "
        f"interés expresado, objeciones y siguiente paso acordado. "
        f"Responde SOLO el resumen, sin introducción.{prior_block}\n\n"
        f"CONVERSACIÓN:\n{conversation_text}"
    )

    try:
        summary = await provider.generate_response(prompt)
        return summary.strip()
    except Exception as exc:
        logger.warning("[ContextManager] Summarization failed: %s", exc)
        return prior_summary or ""


async def compress_context(
    messages: List[Dict[str, Any]],
    existing_summary: Optional[str] = None,
    lead_id: Optional[int] = None,
    db: Optional[AsyncSession] = None,
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """
    Compress the conversation window if needed.

    Returns (summary, recent_messages).

    If compression is not needed, returns (existing_summary, messages)
    unchanged.  The new summary is also persisted to DB when *lead_id* and
    *db* are provided.
    """
    if not should_summarize(messages):
        return existing_summary, messages

    to_summarize = messages[:-KEEP_RECENT]
    recent = messages[-KEEP_RECENT:]

    logger.info(
        "[ContextManager] Compressing %d messages → %d recent + summary",
        len(messages),
        len(recent),
        extra={"lead_id": lead_id},
    )

    new_summary = await summarize_conversation(to_summarize, prior_summary=existing_summary)

    # Persist summary to lead metadata so returning sessions benefit too
    if lead_id and db and new_summary:
        try:
            from app.models.lead import Lead
            from sqlalchemy import func

            await db.execute(
                update(Lead)
                .where(Lead.id == lead_id)
                .values(
                    lead_metadata=func.jsonb_set(
                        Lead.lead_metadata,
                        "{conversation_summary}",
                        f'"{new_summary.replace(chr(34), chr(39))}"',
                        True,
                    )
                )
            )
            await db.flush()
            logger.debug("[ContextManager] Summary persisted for lead_id=%s", lead_id)
        except Exception as exc:
            logger.warning(
                "[ContextManager] Could not persist summary for lead_id=%s: %s",
                lead_id,
                exc,
            )

    return new_summary, recent
