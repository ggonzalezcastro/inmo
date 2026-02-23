from celery import shared_task
import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker


from app.config import settings
from app.services.shared import TelegramService, ActivityService
from app.services.leads import LeadContextService, LeadService
from app.services.llm import LLMServiceFacade
from app.models.lead import Lead


logger = logging.getLogger(__name__)


# Create async engine for tasks
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@shared_task(name="app.tasks.telegram_tasks.process_telegram_message")
def process_telegram_message(
    chat_id: int,
    user_id: int,
    username: str,
    message_text: str
):
    """Process incoming Telegram message - Celery task"""
    
    import asyncio
    
    async def async_process():
        # Create session
        async with AsyncSessionLocal() as db:
            try:
                logger.info(f"Processing message from {username}: {message_text[:50]}")
                
                # Get or create lead
                lead = await LeadContextService.get_or_create_lead(db, user_id, username)
                logger.info(f"Lead ID: {lead.id}")
                
                # Log inbound message
                await ActivityService.log_telegram_message(
                    db,
                    lead_id=lead.id,
                    telegram_user_id=user_id,
                    message_text=message_text,
                    direction="in"
                )
                
                # Get lead context
                context = await LeadContextService.get_lead_context(db, lead.id)
                
                # Build LLM prompt (now returns system_prompt and contents)
                system_prompt, contents = await LLMServiceFacade.build_llm_prompt(context, message_text)
                
                # Generate response using structured format
                # For telegram, we use simple generate_response which still accepts string
                # Combine system_prompt and contents into a single prompt for backward compatibility
                # Extract last message (user's new message) for the prompt
                last_message = message_text  # Already included in contents
                combined_prompt = f"{system_prompt}\n\nMENSAJE ACTUAL: {last_message}"
                ai_response = await LLMServiceFacade.generate_response(combined_prompt)
                
                # Analyze lead qualification
                analysis = await LLMServiceFacade.analyze_lead_qualification(message_text, context)
                
                # Calculate new score
                old_score = lead.lead_score
                score_delta = analysis.get("score_delta", 0)
                new_score = max(0, min(100, old_score + score_delta))
                
                # Update lead
                lead.lead_score = new_score
                lead.lead_metadata = {
                    **lead.lead_metadata,
                    "last_analysis": analysis,
                    "telegram_user_id": user_id
                }
                
                # Auto-update status based on score
                from app.models.lead import LeadStatus
                if new_score < 20:
                    lead.status = LeadStatus.COLD
                elif new_score < 50:
                    lead.status = LeadStatus.WARM
                else:
                    lead.status = LeadStatus.HOT
                
                # Auto-advance pipeline stage if conditions met
                from app.services.pipeline import PipelineService
                try:
                    await PipelineService.auto_advance_stage(db, lead.id)
                except Exception as e:
                    logger.error(f"Error auto-advancing stage: {str(e)}")
                
                await db.commit()
                
                # Log score change
                if new_score != old_score:
                    await ActivityService.log_activity(
                        db,
                        lead_id=lead.id,
                        action_type="score_update",
                        details={
                            "old_score": old_score,
                            "new_score": new_score,
                            "delta": score_delta,
                            "reason": "telegram_message",
                            "analysis": analysis
                        }
                    )
                
                # Log outbound message
                await ActivityService.log_telegram_message(
                    db,
                    lead_id=lead.id,
                    telegram_user_id=user_id,
                    message_text=ai_response,
                    direction="out"
                )
                
                # Log activity
                await ActivityService.log_activity(
                    db,
                    lead_id=lead.id,
                    action_type="message",
                    details={
                        "direction": "in",
                        "message": message_text,
                        "response": ai_response,
                        "ai_used": True
                    }
                )
                
                # Send response via Telegram
                telegram = TelegramService()
                await telegram.send_message(chat_id, ai_response)
                
                logger.info(f"Message processed successfully for lead {lead.id}")
                
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}", exc_info=True)
                
                # Send error message
                telegram = TelegramService()
                try:
                    await telegram.send_message(
                        chat_id,
                        "Disculpa, hubo un error procesando tu mensaje. Por favor intenta de nuevo."
                    )
                except Exception as e2:
                    logger.error(f"Failed to send error message: {str(e2)}")
    
    # Run async code
    asyncio.run(async_process())

