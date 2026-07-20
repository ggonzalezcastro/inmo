"""
NoteTaker — copilot mode processor.

Accumulates lead utterances and periodically calls Haiku 4.5 to extract
structured notes (interests, objections, data points). Notes are sent
via WebSocket to the broker dashboard only — the lead never hears them.
"""
from __future__ import annotations

import logging
from collections import deque
from typing import Any, Deque, Optional

logger = logging.getLogger(__name__)

try:
    from pipecat.frames.frames import Frame, TranscriptionFrame
    from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
    _PIPECAT_AVAILABLE = True
except ImportError:
    _PIPECAT_AVAILABLE = False
    FrameProcessor = object  # type: ignore[misc,assignment]
    FrameDirection = None    # type: ignore[assignment]

_NOTE_EVERY_N_TURNS = 4   # Generate a note after every N lead utterances
_MAX_WINDOW = 10           # Keep last N utterances for context


class NoteTaker(FrameProcessor):  # type: ignore[misc]
    """
    Accumulates lead speech and generates automated notes via LLM.

    Notes contain: extracted data, interests, objections, suggestions.
    Notes are broadcast as 'call_ai_note' WS events — not sent to lead.
    """

    def __init__(
        self,
        voice_call_id: int,
        broker_id: int,
        agent_user_id: Optional[int] = None,
    ) -> None:
        if not _PIPECAT_AVAILABLE:
            raise ImportError("pipecat-ai is not installed.")
        super().__init__()
        self._voice_call_id = voice_call_id
        self._broker_id = broker_id
        self._agent_user_id = agent_user_id
        self._buffer: Deque[str] = deque(maxlen=_MAX_WINDOW)
        self._turn_count = 0

    async def process_frame(self, frame: Any, direction: Any) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            text = (frame.text or "").strip()
            if text:
                self._buffer.append(text)
                self._turn_count += 1
                if self._turn_count % _NOTE_EVERY_N_TURNS == 0:
                    await self._generate_note()

        await self.push_frame(frame, direction)

    async def _generate_note(self) -> None:
        from app.core.websocket_manager import ws_manager
        from app.services.llm.facade import LLMServiceFacade

        transcript_window = "\n".join(f"- {t}" for t in self._buffer)
        prompt = (
            "Analiza estos mensajes de un lead inmobiliario y extrae información estructurada.\n"
            "Responde SOLO en JSON con estos campos:\n"
            '{"intereses": [...], "objeciones": [...], "datos_detectados": {...}, "sugerencia": "..."}\n\n'
            f"Mensajes del lead:\n{transcript_window}"
        )

        try:
            result_text, _ = await LLMServiceFacade.generate_response_with_function_calling(
                system_prompt="Eres un asistente que extrae datos de conversaciones inmobiliarias. Responde solo JSON.",
                contents=[{"role": "user", "content": prompt}],
                tools=[],
                tool_executor=None,
                tool_mode_override="NONE",
            )

            await ws_manager.broadcast(
                broker_id=self._broker_id,
                event="call_ai_note",
                data={
                    "voice_call_id": self._voice_call_id,
                    "note": result_text,
                    "turn_count": self._turn_count,
                },
            )
            logger.debug("[NoteTaker] note generated turn=%s", self._turn_count)

        except Exception as exc:
            logger.warning("[NoteTaker] LLM note generation failed: %s", exc)
