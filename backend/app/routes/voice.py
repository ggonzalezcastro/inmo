"""
Voice call routes for managing phone calls
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel
from app.database import get_db
from app.middleware.auth import get_current_user
from app.services.voice_call_service import VoiceCallService
from app.schemas.voice_call import (
    VoiceCallResponse,
    VoiceCallListResponse,
    CallInitiateRequest
)
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/initiate", response_model=VoiceCallResponse, status_code=201)
async def initiate_call(
    request: CallInitiateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Initiate an outbound call to a lead"""
    
    try:
        broker_id = current_user.get("id")
        
        voice_call = await VoiceCallService.initiate_call(
            db=db,
            lead_id=request.lead_id,
            campaign_id=request.campaign_id,
            broker_id=broker_id,
            agent_type=request.agent_type
        )
        
        return VoiceCallResponse.model_validate(voice_call)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error initiating call: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhooks/voice")
async def voice_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Webhook endpoint for voice provider callbacks
    
    This endpoint receives call status updates from Twilio/Telnyx.
    IP whitelist should be configured at provider level.
    """
    
    try:
        # Get webhook payload (form data for Twilio, JSON for others)
        content_type = request.headers.get("Content-Type", "")
        
        if "application/x-www-form-urlencoded" in content_type:
            # Twilio sends form data
            form_data = await request.form()
            payload = dict(form_data)
        else:
            # JSON payload
            payload = await request.json()
        
        # Get provider and parse webhook
        from app.services.voice_provider import get_voice_provider
        
        provider = get_voice_provider()
        event_data = await provider.handle_webhook(payload)
        
        external_call_id = event_data.get("call_id")
        event_type = event_data.get("event_type")
        
        if not external_call_id:
            logger.warning("Webhook received without call_id")
            return {"ok": True}
        
        # Update voice call in database
        await VoiceCallService.handle_call_webhook(
            db=db,
            external_call_id=external_call_id,
            event=event_type or "unknown",
            metadata=event_data
        )
        
        # If call completed, enqueue transcript/summary generation
        if event_type == "completed":
            from app.tasks.voice_tasks import generate_call_transcript_and_summary
            # Get voice_call_id from database
            from app.models.voice_call import VoiceCall
            from sqlalchemy.future import select
            
            result = await db.execute(
                select(VoiceCall).where(VoiceCall.external_call_id == external_call_id)
            )
            voice_call = result.scalars().first()
            
            if voice_call:
                generate_call_transcript_and_summary.delay(voice_call.id)
        
        return {"ok": True}
        
    except Exception as e:
        logger.error(f"Error handling voice webhook: {str(e)}", exc_info=True)
        # Return 200 to avoid provider retries for our errors
        return {"ok": False, "error": str(e)}


@router.get("/leads/{lead_id}", response_model=VoiceCallListResponse)
async def get_call_history(
    lead_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get call history for a lead"""
    
    try:
        broker_id = current_user.get("id")
        
        calls = await VoiceCallService.get_call_history(
            db=db,
            lead_id=lead_id,
            broker_id=broker_id
        )
        
        return VoiceCallListResponse(
            data=[VoiceCallResponse.model_validate(call) for call in calls]
        )
        
    except Exception as e:
        logger.error(f"Error getting call history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{call_id}")
async def get_call_details(
    call_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get call details including transcript and summary"""
    
    try:
        broker_id = current_user.get("id")
        
        from app.models.voice_call import VoiceCall
        from sqlalchemy.future import select
        
        query = select(VoiceCall).where(VoiceCall.id == call_id)
        
        if broker_id:
            query = query.where(VoiceCall.broker_id == broker_id)
        
        result = await db.execute(query)
        voice_call = result.scalars().first()
        
        if not voice_call:
            raise HTTPException(status_code=404, detail="Call not found")
        
        # Get transcript lines
        from app.models.voice_call import CallTranscript
        transcript_result = await db.execute(
            select(CallTranscript)
            .where(CallTranscript.voice_call_id == call_id)
            .order_by(CallTranscript.timestamp)
        )
        transcript_lines = transcript_result.scalars().all()
        
        return {
            "call": VoiceCallResponse.model_validate(voice_call),
            "transcript_lines": [
                {
                    "speaker": line.speaker.value,
                    "text": line.text,
                    "timestamp": line.timestamp,
                    "confidence": line.confidence
                }
                for line in transcript_lines
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting call details: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



