"""
Voice call service for managing phone calls
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_
from datetime import datetime
from typing import List, Optional, Dict, Any
import logging
from app.models.voice_call import VoiceCall, CallStatus
from app.models.lead import Lead
from app.services.voice_provider import get_voice_provider
from app.config import settings

logger = logging.getLogger(__name__)


class VoiceCallService:
    """Service for managing voice calls"""
    
    @staticmethod
    async def initiate_call(
        db: AsyncSession,
        lead_id: int,
        campaign_id: Optional[int] = None,
        broker_id: Optional[int] = None,
        agent_type: Optional[str] = None
    ) -> VoiceCall:
        """
        Initiate a voice call to a lead
        
        Args:
            db: Database session
            lead_id: Lead ID to call
            campaign_id: Optional campaign ID
            broker_id: Broker ID (required)
            agent_type: Type of agent for call script
        
        Returns:
            VoiceCall instance
        """
        
        # Get lead
        lead_result = await db.execute(
            select(Lead).where(Lead.id == lead_id)
        )
        lead = lead_result.scalars().first()
        
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")
        
        if not lead.phone:
            raise ValueError(f"Lead {lead_id} has no phone number")
        
        # Get broker_id from lead's assigned agent or use provided
        if not broker_id:
            broker_id = lead.assigned_to or 1  # Default to first user
        
        # Create voice call record
        voice_call = VoiceCall(
            lead_id=lead_id,
            campaign_id=campaign_id,
            phone_number=lead.phone,
            status=CallStatus.INITIATED,
            broker_id=broker_id
        )
        db.add(voice_call)
        await db.commit()
        await db.refresh(voice_call)
        
        try:
            # Get voice provider
            provider = get_voice_provider()
            
            # Build webhook URL
            webhook_base_url = getattr(settings, 'WEBHOOK_BASE_URL', 'http://localhost:8000')
            webhook_url = f"{webhook_base_url}/api/v1/webhooks/voice"
            
            # Get from number from settings
            from_number = getattr(settings, 'VOICE_FROM_NUMBER', None)
            if not from_number:
                # Try provider-specific settings
                from_number = getattr(settings, 'TWILIO_PHONE_NUMBER', None) or getattr(settings, 'TELNYX_PHONE_NUMBER', None)
            
            if not from_number:
                raise ValueError("No 'from' phone number configured. Set VOICE_FROM_NUMBER, TWILIO_PHONE_NUMBER, or TELNYX_PHONE_NUMBER")
            
            # Make call via provider
            external_call_id = await provider.make_call(
                phone=lead.phone,
                from_number=from_number,
                webhook_url=webhook_url,
                context={
                    "voice_call_id": voice_call.id,
                    "lead_id": lead_id,
                    "campaign_id": campaign_id,
                    "agent_type": agent_type
                }
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

