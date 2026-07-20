"""
HandoffMonitor — detects when to transfer an autonomous call to a human agent.

Signals that trigger handoff:
1. AgentSupervisor emits a HandoffSignal to a human (via lead_data["handoff_to_human"])
2. Lead score crosses HOT threshold (lead_data["lead_score"] >= 50)
3. Lead explicitly requests a person ("quiero hablar con alguien", etc.)

When triggered:
1. AI says a brief transition message
2. Twilio SIP transfer initiated (via TwilioHandler)
3. TTS muted in pipeline_manager
4. VoiceCall.handoff_occurred = True persisted in DB
5. WS event "call_handoff" broadcast
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from pipecat.frames.frames import Frame, TextFrame, TranscriptionFrame
    from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
    _PIPECAT_AVAILABLE = True
except ImportError:
    _PIPECAT_AVAILABLE = False
    FrameProcessor = object  # type: ignore[misc,assignment]
    FrameDirection = None    # type: ignore[assignment]

# Explicit human request patterns
_HUMAN_REQUEST_PATTERNS = re.compile(
    r"quiero (hablar|hablar con) (una persona|alguien|un humano|un asesor|el ejecutivo)"
    r"|pásame (con alguien|con un asesor|con una persona)"
    r"|hablar con (un humano|una persona|el ejecutivo|un agente real)",
    re.IGNORECASE,
)

_HOT_SCORE_THRESHOLD = 50


class HandoffMonitor(FrameProcessor):  # type: ignore[misc]
    """
    Monitors conversation for handoff triggers and executes the transfer.
    """

    def __init__(
        self,
        voice_call_id: int,
        broker_id: int,
        agent_phone: Optional[str],
        db_session_factory: Any,
        pipeline_manager: Any,
        twilio_handler: Optional[Any] = None,
        twilio_call_sid: Optional[str] = None,
    ) -> None:
        if not _PIPECAT_AVAILABLE:
            raise ImportError("pipecat-ai is not installed.")
        super().__init__()
        self._voice_call_id = voice_call_id
        self._broker_id = broker_id
        self._agent_phone = agent_phone
        self._db_factory = db_session_factory
        self._pipeline_manager = pipeline_manager
        self._twilio_handler = twilio_handler
        self._twilio_call_sid = twilio_call_sid
        self._handoff_done = False
        # Inject from CRMLLMProcessor via context_updates
        self._lead_score: float = 0.0
        self._handoff_to_human: bool = False

    def update_from_context(self, context_updates: dict) -> None:
        """Called by CRMLLMProcessor after each agent turn."""
        score = context_updates.get("lead_score")
        if score is not None:
            self._lead_score = float(score)
        if context_updates.get("handoff_to_human"):
            self._handoff_to_human = True

    async def process_frame(self, frame: Any, direction: Any) -> None:
        await super().process_frame(frame, direction)

        if self._handoff_done:
            await self.push_frame(frame, direction)
            return

        # Only check handoff triggers on transcription frames (not audio/control frames)
        if isinstance(frame, TranscriptionFrame):
            # Check lead's explicit request
            text = frame.text or ""
            if _HUMAN_REQUEST_PATTERNS.search(text):
                await self.trigger_handoff("Solicitud explícita del lead")
                await self.push_frame(frame, direction)
                return

            # Check hot score threshold
            if self._lead_score >= _HOT_SCORE_THRESHOLD:
                await self.trigger_handoff(f"Lead score {self._lead_score:.0f} alcanzó umbral")
                await self.push_frame(frame, direction)
                return

            # Check AgentSupervisor signal
            if self._handoff_to_human:
                await self.trigger_handoff("AgentSupervisor señaló handoff a humano")
                await self.push_frame(frame, direction)
                return

        await self.push_frame(frame, direction)

    async def trigger_handoff(self, reason: str) -> None:
        if self._handoff_done:
            return
        self._handoff_done = True
        logger.info("[HandoffMonitor] triggering handoff call=%s reason=%r", self._voice_call_id, reason)

        # Emit transition message through TTS
        transition_msg = "Te voy a comunicar con nuestro asesor, un momento por favor."
        await self.push_frame(TextFrame(text=transition_msg))

        # Mute TTS so AI stops responding
        if self._pipeline_manager:
            self._pipeline_manager.mute_tts(self._voice_call_id)

        # Execute phone transfer
        if self._twilio_handler and self._agent_phone and self._twilio_call_sid:
            try:
                await self._twilio_handler.transfer_call(self._twilio_call_sid, self._agent_phone)
            except Exception as exc:
                logger.error("[HandoffMonitor] Twilio transfer failed: %s", exc)

        # Persist handoff in DB
        await self._persist_handoff(reason)

        # Broadcast WS event
        from app.core.websocket_manager import ws_manager
        from datetime import datetime, timezone
        try:
            await ws_manager.broadcast(
                broker_id=self._broker_id,
                event="call_handoff",
                data={
                    "voice_call_id": self._voice_call_id,
                    "reason": reason,
                    "handoff_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as exc:
            logger.warning("[HandoffMonitor] WS broadcast failed: %s", exc)

    async def _persist_handoff(self, reason: str) -> None:
        from app.models.voice_call import VoiceCall
        from sqlalchemy import update
        from datetime import datetime, timezone

        try:
            async with self._db_factory() as db:
                await db.execute(
                    update(VoiceCall)
                    .where(VoiceCall.id == self._voice_call_id)
                    .values(
                        handoff_occurred=True,
                        handoff_at=datetime.now(timezone.utc),
                        handoff_reason=reason,
                    )
                )
                await db.commit()
        except Exception as exc:
            logger.error("[HandoffMonitor] DB persist failed: %s", exc)
