"""
Voice call service for managing phone calls
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.models.lead import Lead
from app.models.user import User
from app.models.voice_call import VoiceCall, CallStatus
from app.services.voice.provider import get_voice_provider
from app.services.voice.types import WebhookEvent, CallEventType

logger = logging.getLogger(__name__)


def _webhook_event_to_legacy(event: WebhookEvent) -> tuple:
    """Map WebhookEvent to (event_type_str, metadata dict) for legacy handlers."""
    _map = {
        CallEventType.CALL_ENDED: "completed",
        CallEventType.CALL_FAILED: "failed",
        CallEventType.CALL_RINGING: "ringing",
        CallEventType.CALL_ANSWERED: "answered",
        CallEventType.CALL_STARTED: "answered",
        CallEventType.TRANSCRIPT_UPDATE: "transcript",
        CallEventType.FUNCTION_CALL: "function-call",
    }
    event_type_str = _map.get(event.event_type, event.status or "unknown")
    if event.event_type == CallEventType.STATUS_UPDATE and event.status:
        event_type_str = {
            "ended": "completed",
            "in-progress": "answered",
            "ringing": "ringing",
            "queued": "initiated",
        }.get(event.status, event_type_str)
    metadata = {
        "duration": event.duration_seconds,
        "recording_url": event.recording_url,
        "transcript": event.transcript,
        "summary": event.summary,
        "message_data": (event.raw_data.get("message") or {}),
    }
    return event_type_str, metadata


async def _resolve_broker_user_id(
    db: AsyncSession,
    broker_user_id: Optional[int],
    lead: Lead,
    campaign_id: Optional[int],
) -> int:
    """
    Resolve broker user id for VoiceCall (user id of the agent).
    """
    user_id = broker_user_id or getattr(lead, "assigned_to", None)
    if not user_id and campaign_id:
        from app.models.campaign import Campaign
        result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = result.scalars().first()
        if campaign:
            user_id = campaign.broker_id
    if not user_id:
        raise ValueError(
            "No broker_id specified and lead has no assigned_to. "
            "Pass broker_id (user id) or assign lead to an agent."
        )
    return user_id


async def _company_broker_id_for_user(db: AsyncSession, user_id: int) -> Optional[int]:
    """Get Broker (company) id from User id."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    return getattr(user, "broker_id", None) if user else None


class VoiceCallService:
    """Service for managing voice calls"""

    @staticmethod
    async def initiate_call(
        db: AsyncSession,
        lead_id: int,
        campaign_id: Optional[int] = None,
        broker_id: Optional[int] = None,
        agent_type: Optional[str] = None,
    ) -> VoiceCall:
        """
        Initiate a voice call to a lead.
        broker_id is the user (agent) id; company broker is resolved for voice config.
        """
        lead_result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = lead_result.scalars().first()
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")
        if not lead.phone:
            raise ValueError(f"Lead {lead_id} has no phone number")

        broker_user_id = await _resolve_broker_user_id(db, broker_id, lead, campaign_id)
        # Resolve synchronously for the same session
        company_broker_id = await _company_broker_id_for_user(db, broker_user_id)

        voice_call = VoiceCall(
            lead_id=lead_id,
            campaign_id=campaign_id,
            phone_number=lead.phone,
            status=CallStatus.INITIATED,
            broker_id=broker_user_id,
        )
        db.add(voice_call)
        await db.commit()
        await db.refresh(voice_call)

        try:
            provider = get_voice_provider()
            webhook_base_url = getattr(settings, "WEBHOOK_BASE_URL", "http://localhost:8000")
            webhook_url = f"{webhook_base_url}/api/v1/calls/webhooks/voice"

            context = {
                "db": db,
                "voice_call_id": voice_call.id,
                "lead_id": lead_id,
                "campaign_id": campaign_id,
                "broker_id": company_broker_id,
                "agent_type": agent_type,
            }
            external_call_id = await provider.make_call(
                phone=lead.phone,
                webhook_url=webhook_url,
                context=context,
            )

            # Update voice call with external ID
            voice_call.external_call_id = external_call_id
            voice_call.started_at = datetime.now()
            await db.commit()
            await db.refresh(voice_call)

            logger.info(f"Voice call {voice_call.id} initiated: {external_call_id}")
            return voice_call

        except Exception as e:
            logger.error(f"Error initiating call: {str(e)}", exc_info=True)
            voice_call.status = CallStatus.FAILED
            await db.commit()
            raise

    @staticmethod
    async def handle_call_webhook(
        db: AsyncSession,
        external_call_id: str,
        event: str,
        metadata: Dict[str, Any]
    ) -> VoiceCall:
        """
        Handle call webhook from voice provider

        Args:
            db: Database session
            external_call_id: External call ID from provider
            event: Event type (initiated, ringing, answered, completed, failed)
            metadata: Additional event metadata

        Returns:
            Updated VoiceCall instance
        """

        # Find voice call by external ID
        result = await db.execute(
            select(VoiceCall).where(VoiceCall.external_call_id == external_call_id)
        )
        voice_call = result.scalars().first()

        if not voice_call:
            logger.warning(f"Voice call not found for external_call_id: {external_call_id}")
            raise ValueError(f"Voice call not found: {external_call_id}")

        # Update status based on event
        event_status_map = {
            "initiated": CallStatus.INITIATED,
            "ringing": CallStatus.RINGING,
            "answered": CallStatus.ANSWERED,
            "completed": CallStatus.COMPLETED,
            "failed": CallStatus.FAILED,
            "no-answer": CallStatus.NO_ANSWER,
            "busy": CallStatus.BUSY,
            "cancelled": CallStatus.CANCELLED
        }

        new_status = event_status_map.get(event.lower(), CallStatus.FAILED)
        voice_call.status = new_status

        # Update timestamps
        if event.lower() in ["answered", "ringing"] and not voice_call.started_at:
            voice_call.started_at = datetime.now()

        if event.lower() == "completed":
            voice_call.completed_at = datetime.now()
            # Update duration if provided
            if metadata.get("duration"):
                voice_call.duration = int(metadata.get("duration"))
            # Update recording URL if provided
            if metadata.get("recording_url"):
                voice_call.recording_url = metadata.get("recording_url")

        await db.commit()
        await db.refresh(voice_call)

        logger.info(f"Voice call {voice_call.id} status updated to {new_status}")
        return voice_call

    @staticmethod
    async def handle_normalized_event(
        db: AsyncSession,
        event: WebhookEvent,
    ) -> Optional[VoiceCall]:
        """
        Handle a normalized webhook event from any voice provider.
        Dispatches to transcript update, function-call, or status update.
        """
        event_type_str, metadata = _webhook_event_to_legacy(event)
        if event_type_str == "transcript":
            await VoiceCallService.handle_transcript_update(
                db,
                event.external_call_id,
                metadata.get("message_data", {}),
            )
            return None
        if event_type_str == "function-call":
            return None
        return await VoiceCallService.handle_call_webhook(
            db,
            event.external_call_id,
            event_type_str,
            metadata,
        )

    @staticmethod
    async def handle_transcript_update(
        db: AsyncSession,
        external_call_id: str,
        transcript_data: Dict[str, Any],
    ) -> None:
        """
        Handle real-time transcript update from Vapi.
        Logs the update; full transcript is stored when call completes.
        """
        result = await db.execute(
            select(VoiceCall).where(VoiceCall.external_call_id == external_call_id)
        )
        voice_call = result.scalars().first()
        if not voice_call:
            logger.debug("Voice call not found for transcript update: %s", external_call_id)
            return
        logger.debug("Transcript update for call %s: %s", external_call_id, transcript_data)

    @staticmethod
    async def get_call_history(
        db: AsyncSession,
        lead_id: int,
        broker_id: Optional[int] = None
    ) -> List[VoiceCall]:
        """Get call history for a lead"""

        query = select(VoiceCall).where(VoiceCall.lead_id == lead_id)

        if broker_id:
            query = query.where(VoiceCall.broker_id == broker_id)

        from sqlalchemy import desc
        query = query.order_by(desc(VoiceCall.started_at))

        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def update_call_transcript(
        db: AsyncSession,
        voice_call_id: int,
        transcript: str
    ) -> VoiceCall:
        """Update call transcript"""

        result = await db.execute(
            select(VoiceCall).where(VoiceCall.id == voice_call_id)
        )
        voice_call = result.scalars().first()

        if not voice_call:
            raise ValueError(f"Voice call {voice_call_id} not found")

        voice_call.transcript = transcript
        await db.commit()
        await db.refresh(voice_call)

        return voice_call

    @staticmethod
    async def update_call_summary(
        db: AsyncSession,
        voice_call_id: int,
        summary: str,
        score_delta: Optional[float] = None,
        stage_after_call: Optional[str] = None
    ) -> VoiceCall:
        """Update call summary and results"""

        result = await db.execute(
            select(VoiceCall).where(VoiceCall.id == voice_call_id)
        )
        voice_call = result.scalars().first()

        if not voice_call:
            raise ValueError(f"Voice call {voice_call_id} not found")

        voice_call.summary = summary

        if score_delta is not None:
            voice_call.score_delta = score_delta

        if stage_after_call:
            voice_call.stage_after_call = stage_after_call

        await db.commit()
        await db.refresh(voice_call)

        return voice_call
