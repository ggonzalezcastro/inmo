"""
CoachingAdvisor — coaching mode processor.

Listens to both lead and human-agent utterances and generates
proactive suggestions for the human agent. Suggestions are sent
via WebSocket only to the specific agent user — the lead never hears them.
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

_SUGGEST_EVERY_N_TURNS = 3
_MAX_WINDOW = 8


class CoachingAdvisor(FrameProcessor):  # type: ignore[misc]
    """
    Generates real-time coaching suggestions for the human agent.

    Suggestions include: what to ask next, which property to offer,
    how to handle an objection. Sent only to agent via send_to_user.
    """

    def __init__(
        self,
        voice_call_id: int,
        broker_id: int,
        agent_user_id: str,  # string for ws_manager.send_to_user
    ) -> None:
        if not _PIPECAT_AVAILABLE:
            raise ImportError("pipecat-ai is not installed.")
        super().__init__()
        self._voice_call_id = voice_call_id
        self._broker_id = broker_id
        self._agent_user_id = agent_user_id
        self._lead_buffer: Deque[str] = deque(maxlen=_MAX_WINDOW)
        self._agent_buffer: Deque[str] = deque(maxlen=_MAX_WINDOW)
        self._turn_count = 0
        # TranscriptSaver sets this flag externally to distinguish speaker
        self._current_speaker: str = "lead"

    def set_speaker(self, speaker: str) -> None:
        """Called by the pipeline before each frame to identify current speaker."""
        self._current_speaker = speaker

    async def process_frame(self, frame: Any, direction: Any) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            text = (frame.text or "").strip()
            if text:
                if self._current_speaker == "lead":
                    self._lead_buffer.append(f"Lead: {text}")
                else:
                    self._agent_buffer.append(f"Asesor: {text}")
                self._turn_count += 1
                if self._turn_count % _SUGGEST_EVERY_N_TURNS == 0:
                    await self._generate_suggestion()

        await self.push_frame(frame, direction)

    async def _generate_suggestion(self) -> None:
        from app.core.websocket_manager import ws_manager
        from app.services.llm.facade import LLMServiceFacade

        all_turns = list(self._agent_buffer) + list(self._lead_buffer)
        recent = "\n".join(all_turns[-_MAX_WINDOW:])
        prompt = (
            "Eres un coach de ventas inmobiliarias. Analiza esta conversacion y da UNA sugerencia concreta "
            "al asesor humano. Responde SOLO en JSON: "
            '{"sugerencia": "...", "tipo": "pregunta|oferta|objecion|cierre"}\n\n'
            f"Conversacion reciente:\n{recent}"
        )

        try:
            result_text, _ = await LLMServiceFacade.generate_response_with_function_calling(
                system_prompt="Eres un coach de ventas. Responde solo JSON con una sugerencia accionable.",
                contents=[{"role": "user", "content": prompt}],
                tools=[],
                tool_executor=None,
            )

            # Send only to the specific agent user, not broadcast
            await ws_manager.send_to_user(
                broker_id=self._broker_id,
                user_id=self._agent_user_id,
                event="call_coaching_suggestion",
                data={
                    "voice_call_id": self._voice_call_id,
                    "suggestion": result_text,
                    "turn_count": self._turn_count,
                },
            )
            logger.debug("[CoachingAdvisor] suggestion sent to user=%s", self._agent_user_id)

        except Exception as exc:
            logger.warning("[CoachingAdvisor] LLM suggestion failed: %s", exc)
