"""
Voice call processing tasks for Celery
"""
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.future import select
from datetime import datetime
import logging
from app.config import settings
from app.models.voice_call import VoiceCall
from app.services.voice import CallAgentService, VoiceCallService
from app.services.pipeline import PipelineService

logger = logging.getLogger(__name__)

# Create async engine for tasks
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@shared_task(name="app.tasks.voice_tasks.generate_call_transcript_and_summary")
def generate_call_transcript_and_summary(voice_call_id: int):
    """
    Generate transcript and summary for a completed call
    
    This task processes the call recording and generates:
    - Full transcript
    - AI-generated summary
    - Extracted data (budget, timeline, etc.)
    - Recommended next steps
    """
    import asyncio
    
    async def _process():
        async with AsyncSessionLocal() as db:
            try:
                # Get voice call
                result = await db.execute(
                    select(VoiceCall).where(VoiceCall.id == voice_call_id)
                )
                voice_call = result.scalars().first()
                
                if not voice_call:
                    logger.error(f"Voice call {voice_call_id} not found")
                    return
                
                if not voice_call.recording_url:
                    logger.warning(f"Voice call {voice_call_id} has no recording URL")
                    return
                
                # TODO: Process recording with STT service
                # For now, we'll use placeholder transcript
                # In production, this would:
                # 1. Download recording from URL
                # 2. Send to STT service (Google Cloud Speech, AWS Transcribe)
                # 3. Get transcript back
                
                # Placeholder: transcript would come from STT
                transcript = f"[Transcript will be generated from recording: {voice_call.recording_url}]"
                
                # Update transcript in database
                await VoiceCallService.update_call_transcript(
                    db=db,
                    voice_call_id=voice_call_id,
                    transcript=transcript
                )
                
                # Get lead context for summary generation
                from app.models.lead import Lead
                
                lead_result = await db.execute(
                    select(Lead).where(Lead.id == voice_call.lead_id)
                )
                lead = lead_result.scalars().first()
                
                if not lead:
                    logger.error(f"Lead {voice_call.lead_id} not found")
                    return
                
                lead_context = {
                    "id": lead.id,
                    "name": lead.name,
                    "phone": lead.phone,
                    "email": lead.email,
                    "lead_score": lead.lead_score,
                    "pipeline_stage": lead.pipeline_stage,
                    "lead_metadata": lead.lead_metadata or {}
                }
                
                # Generate summary
                summary_data = await CallAgentService.generate_call_summary(
                    full_transcript=transcript,
                    lead_context=lead_context
                )
                
                # Update voice call with summary
                await VoiceCallService.update_call_summary(
                    db=db,
                    voice_call_id=voice_call_id,
                    summary=summary_data.get("summary", ""),
                    score_delta=summary_data.get("score_delta", 0),
                    stage_after_call=summary_data.get("stage_to_move")
                )
                
                # Update lead metadata with extracted data
                if summary_data.get("budget"):
                    if not isinstance(lead.lead_metadata, dict):
                        lead.lead_metadata = {}
                    lead.lead_metadata["budget"] = summary_data["budget"]
                
                if summary_data.get("timeline"):
                    if not isinstance(lead.lead_metadata, dict):
                        lead.lead_metadata = {}
                    lead.lead_metadata["timeline"] = summary_data["timeline"]
                
                # Update lead score
                if summary_data.get("score_delta"):
                    old_score = lead.lead_score
                    new_score = max(0, min(100, old_score + summary_data["score_delta"]))
                    lead.lead_score = new_score
                
                # Move to stage if recommended
                if summary_data.get("stage_to_move"):
                    try:
                        await PipelineService.move_lead_to_stage(
                            db=db,
                            lead_id=lead.id,
                            new_stage=summary_data["stage_to_move"],
                            reason=f"Call summary recommendation",
                            triggered_by_campaign=voice_call.campaign_id
                        )
                    except Exception as e:
                        logger.error(f"Error moving lead to stage: {str(e)}")
                
                await db.commit()
                
                logger.info(f"Call transcript and summary generated for call {voice_call_id}")
            
            except Exception as e:
                logger.error(f"Error generating transcript/summary: {str(e)}", exc_info=True)
                raise
    
    asyncio.run(_process())



