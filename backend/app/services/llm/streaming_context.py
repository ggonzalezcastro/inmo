"""
Context-var bridge that lets the voice pipeline subscribe to LLM text deltas
without changing the public signatures of every agent/supervisor function.

Usage (from voice processor)::

    from app.services.llm.streaming_context import set_text_stream_callback

    async def push_delta(text: str) -> None:
        await self.push_frame(TextFrame(text=text), direction)

    token = set_text_stream_callback(push_delta)
    try:
        await ChatOrchestratorService.process_for_voice(...)
    finally:
        reset_text_stream_callback(token)

The OpenAI/OpenRouter provider checks the context-var when it calls
`chat.completions.create`. When set, it switches to streaming mode
(``stream=True``) and invokes the callback on each text delta the upstream
LLM emits, in the order the chunks arrive.

This keeps the multi-agent supervisor/handoff logic intact while still
giving Fish TTS' sentence aggregator something to start speaking on within
~150–300 ms of the LLM response starting (vs ~1500 ms blocking).
"""
from __future__ import annotations

import contextvars
from typing import Awaitable, Callable, Optional

TextStreamCallback = Callable[[str], Awaitable[None]]

_text_stream_callback: contextvars.ContextVar[Optional[TextStreamCallback]] = (
    contextvars.ContextVar("llm_text_stream_callback", default=None)
)


def set_text_stream_callback(callback: TextStreamCallback) -> contextvars.Token:
    """Install ``callback`` for the current async context. Returns a token
    that must be passed to :func:`reset_text_stream_callback` when done."""
    return _text_stream_callback.set(callback)


def reset_text_stream_callback(token: contextvars.Token) -> None:
    """Restore the previous text-stream callback (or ``None``)."""
    _text_stream_callback.reset(token)


def get_text_stream_callback() -> Optional[TextStreamCallback]:
    """Return the active text-stream callback, or ``None``. Providers should
    call this on every LLM completion to decide whether to stream tokens."""
    return _text_stream_callback.get()
