from celery import shared_task
from app.tasks.base import DLQTask
import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.services.leads import ScoringService
from app.services.shared import ActivityService
from app.models.lead import Lead, LeadStatus

logger = logging.getLogger(__name__)

# Create async engine for tasks
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@shared_task(
    name="app.tasks.scoring_tasks.recalculate_all_lead_scores",
    base=DLQTask,
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def recalculate_all_lead_scores(self):
    """Recalculate scores for all leads - runs daily. Uses eager loading to avoid N+1."""
    
    import asyncio
    
    async def async_recalculate():
        async with AsyncSessionLocal() as db:
            try:
                logger.info("Starting daily score recalculation")
                
                # Load all active leads with messages and activities in one query (avoid N+1)
                result = await db.execute(
                    select(Lead)
                    .where(Lead.status != LeadStatus.CONVERTED)
                    .options(
                        selectinload(Lead.telegram_messages),
                        selectinload(Lead.activities),
                    )
                )
                leads = result.scalars().all()
                
                updated_count = 0
                activities_to_log = []
                
                for lead in leads:
                    try:
                        broker_id = lead.broker_id
                        score_data = await ScoringService.calculate_lead_score_from_lead(
                            db, lead, broker_id
                        )
                        old_score = lead.lead_score
                        new_score = score_data["total"]
                        
                        lead.lead_score = new_score
                        lead.lead_score_components = {
                            "base": score_data["base"],
                            "behavior": score_data["behavior"],
                            "engagement": score_data["engagement"]
                        }
                        
                        from app.services.broker import BrokerConfigService
                        
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
                            if new_score < 20:
                                lead.status = LeadStatus.COLD
                            elif new_score < 50:
                                lead.status = LeadStatus.WARM
                            else:
                                lead.status = LeadStatus.HOT
                        
                        if new_score != old_score:
                            updated_count += 1
                            activities_to_log.append({
                                "lead_id": lead.id,
                                "old_score": old_score,
                                "new_score": new_score,
                                "score_data": score_data,
                            })
                    
                    except Exception as e:
                        logger.error(f"Error recalculating score for lead {lead.id}: {str(e)}")
                        continue
                
                # Single batch commit for all lead updates
                try:
                    await db.commit()
                except Exception as e:
                    logger.error(f"Batch commit failed: {str(e)}", exc_info=True)
                    await db.rollback()
                    return
                
                # Log activities after commit (each log_activity may commit)
                for item in activities_to_log:
                    try:
                        await ActivityService.log_activity(
                            db,
                            lead_id=item["lead_id"],
                            action_type="score_update",
                            details={
                                "old_score": item["old_score"],
                                "new_score": item["new_score"],
                                "reason": "daily_recalculation",
                                "components": item["score_data"]
                            }
                        )
                    except Exception as e:
                        logger.error(f"Error logging activity for lead {item['lead_id']}: {str(e)}")
                
                logger.info(f"Recalculation complete: {updated_count} leads updated")
                
            except Exception as e:
                logger.error(f"Error in recalculate_all_lead_scores: {str(e)}", exc_info=True)
                try:
                    await db.rollback()
                except Exception:
                    pass
    
    asyncio.run(async_recalculate())

