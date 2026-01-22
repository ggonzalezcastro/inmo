from celery import shared_task
import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.future import select


from app.config import settings
from app.services.scoring_service import ScoringService
from app.services.activity_service import ActivityService
from app.models.lead import Lead


logger = logging.getLogger(__name__)


# Create async engine for tasks
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@shared_task(name="app.tasks.scoring_tasks.recalculate_all_lead_scores")
def recalculate_all_lead_scores():
    """Recalculate scores for all leads - runs daily"""
    
    import asyncio
    
    async def async_recalculate():
        async with AsyncSessionLocal() as db:
            try:
                logger.info("Starting daily score recalculation")
                
                # Get all active leads
                from app.models.lead import LeadStatus
                result = await db.execute(
                    select(Lead).where(Lead.status != LeadStatus.CONVERTED)
                )
                leads = result.scalars().all()
                
                updated_count = 0
                
                for lead in leads:
                    try:
                        # Calculate score
                        broker_id = lead.broker_id
                        score_data = await ScoringService.calculate_lead_score(db, lead.id, broker_id)
                        old_score = lead.lead_score
                        new_score = score_data["total"]
                        
                        # Update lead
                        lead.lead_score = new_score
                        lead.lead_score_components = {
                            "base": score_data["base"],
                            "behavior": score_data["behavior"],
                            "engagement": score_data["engagement"]
                        }
                        
                        # Auto-update status using broker configuration
                        from app.models.lead import LeadStatus
                        from app.services.broker_config_service import BrokerConfigService
                        
                        # Determine status using broker's thresholds
                        broker_id = lead.broker_id
                        if broker_id:
                            status_str = await BrokerConfigService.determine_lead_status(
                                db, new_score, broker_id
                            )
                            if status_str == "cold":
                                lead.status = LeadStatus.COLD
                            elif status_str == "warm":
                                lead.status = LeadStatus.WARM
                            else:
                                lead.status = LeadStatus.HOT
                        else:
                            # Fallback if no broker_id (shouldn't happen, but safe)
                            if new_score < 20:
                                lead.status = LeadStatus.COLD
                            elif new_score < 50:
                                lead.status = LeadStatus.WARM
                            else:
                                lead.status = LeadStatus.HOT
                        
                        await db.commit()
                        
                        # Log if changed
                        if new_score != old_score:
                            await ActivityService.log_activity(
                                db,
                                lead_id=lead.id,
                                action_type="score_update",
                                details={
                                    "old_score": old_score,
                                    "new_score": new_score,
                                    "reason": "daily_recalculation",
                                    "components": score_data
                                }
                            )
                            updated_count += 1
                    
                    except Exception as e:
                        logger.error(f"Error recalculating score for lead {lead.id}: {str(e)}")
                        continue
                
                logger.info(f"Recalculation complete: {updated_count} leads updated")
                
            except Exception as e:
                logger.error(f"Error in recalculate_all_lead_scores: {str(e)}", exc_info=True)
    
    # Run async code
    asyncio.run(async_recalculate())

