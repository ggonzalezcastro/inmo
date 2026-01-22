"""
Campaign service for managing marketing campaigns
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_, func, desc
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging
from app.models.campaign import (
    Campaign,
    CampaignStep,
    CampaignLog,
    CampaignStatus,
    CampaignTrigger,
    CampaignChannel,
    CampaignLogStatus
)
from app.models.lead import Lead
from app.models.user import User

logger = logging.getLogger(__name__)


class CampaignService:
    """Service for managing campaigns and their execution"""
    
    @staticmethod
    async def create_campaign(
        db: AsyncSession,
        name: str,
        channel: CampaignChannel,
        broker_id: int,
        description: Optional[str] = None,
        triggered_by: CampaignTrigger = CampaignTrigger.MANUAL,
        trigger_condition: Optional[Dict[str, Any]] = None,
        max_contacts: Optional[int] = None
    ) -> Campaign:
        """Create a new campaign"""
        
        campaign = Campaign(
            name=name,
            description=description,
            channel=channel,
            status=CampaignStatus.DRAFT,
            triggered_by=triggered_by,
            trigger_condition=trigger_condition or {},
            max_contacts=max_contacts,
            broker_id=broker_id
        )
        
        db.add(campaign)
        await db.commit()
        await db.refresh(campaign)
        
        logger.info(f"Campaign created: {campaign.id} - {campaign.name}")
        return campaign
    
    @staticmethod
    async def add_step(
        db: AsyncSession,
        campaign_id: int,
        step_number: int,
        action: str,
        delay_hours: int = 0,
        message_template_id: Optional[int] = None,
        conditions: Optional[Dict[str, Any]] = None,
        target_stage: Optional[str] = None
    ) -> CampaignStep:
        """Add a step to a campaign"""
        
        # Verify campaign exists
        campaign_result = await db.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )
        campaign = campaign_result.scalars().first()
        
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")
        
        step = CampaignStep(
            campaign_id=campaign_id,
            step_number=step_number,
            action=action,
            delay_hours=delay_hours,
            message_template_id=message_template_id,
            conditions=conditions or {},
            target_stage=target_stage
        )
        
        db.add(step)
        await db.commit()
        await db.refresh(step)
        
        logger.info(f"Step {step_number} added to campaign {campaign_id}")
        return step
    
    @staticmethod
    async def get_campaign(
        db: AsyncSession,
        campaign_id: int,
        broker_id: Optional[int] = None
    ) -> Optional[Campaign]:
        """Get a campaign with all its steps"""
        
        query = select(Campaign).where(Campaign.id == campaign_id)
        
        if broker_id:
            query = query.where(Campaign.broker_id == broker_id)
        
        result = await db.execute(query)
        campaign = result.scalars().first()
        
        if campaign:
            # Eager load steps
            steps_result = await db.execute(
                select(CampaignStep)
                .where(CampaignStep.campaign_id == campaign_id)
                .order_by(CampaignStep.step_number)
            )
            campaign.steps = steps_result.scalars().all()
        
        return campaign
    
    @staticmethod
    async def list_campaigns(
        db: AsyncSession,
        broker_id: int,
        status: Optional[CampaignStatus] = None,
        channel: Optional[CampaignChannel] = None,
        skip: int = 0,
        limit: int = 50
    ) -> tuple[List[Campaign], int]:
        """List campaigns with filters and pagination"""
        
        query = select(Campaign).where(Campaign.broker_id == broker_id)
        
        if status:
            query = query.where(Campaign.status == status)
        
        if channel:
            query = query.where(Campaign.channel == channel)
        
        # Get total count
        count_query = select(func.count(Campaign.id)).where(Campaign.broker_id == broker_id)
        if status:
            count_query = count_query.where(Campaign.status == status)
        if channel:
            count_query = count_query.where(Campaign.channel == channel)
        
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Apply pagination
        query = query.order_by(desc(Campaign.created_at)).offset(skip).limit(limit)
        
        result = await db.execute(query)
        campaigns = result.scalars().all()
        
        return campaigns, total
    
    @staticmethod
    async def apply_campaign_to_lead(
        db: AsyncSession,
        campaign_id: int,
        lead_id: int
    ) -> List[CampaignLog]:
        """Apply a campaign to a lead (enqueue all steps)"""
        
        # Verify campaign exists
        campaign_result = await db.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )
        campaign = campaign_result.scalars().first()
        
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")
        
        # Verify lead exists
        lead_result = await db.execute(
            select(Lead).where(Lead.id == lead_id)
        )
        lead = lead_result.scalars().first()
        
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")
        
        # Check if campaign already applied (avoid duplicates)
        existing_logs_result = await db.execute(
            select(CampaignLog)
            .where(and_(
                CampaignLog.campaign_id == campaign_id,
                CampaignLog.lead_id == lead_id
            ))
        )
        existing_logs = existing_logs_result.scalars().all()
        
        if existing_logs:
            logger.warning(f"Campaign {campaign_id} already applied to lead {lead_id}")
            return existing_logs
        
        # Get all campaign steps
        steps_result = await db.execute(
            select(CampaignStep)
            .where(CampaignStep.campaign_id == campaign_id)
            .order_by(CampaignStep.step_number)
        )
        steps = steps_result.scalars().all()
        
        if not steps:
            raise ValueError(f"Campaign {campaign_id} has no steps")
        
        # Create log entries for all steps (all pending initially)
        logs = []
        for step in steps:
            log = CampaignLog(
                campaign_id=campaign_id,
                lead_id=lead_id,
                step_number=step.step_number,
                status=CampaignLogStatus.PENDING
            )
            db.add(log)
            logs.append(log)
        
        await db.commit()
        
        # Refresh logs
        for log in logs:
            await db.refresh(log)
        
        logger.info(f"Campaign {campaign_id} applied to lead {lead_id} - {len(logs)} steps enqueued")
        
        return logs
    
    @staticmethod
    async def get_campaign_stats(
        db: AsyncSession,
        campaign_id: int,
        broker_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get campaign statistics (sent, success, failed rates)"""
        
        query = select(CampaignLog).where(CampaignLog.campaign_id == campaign_id)
        
        if broker_id:
            # Verify campaign belongs to broker
            campaign_result = await db.execute(
                select(Campaign).where(and_(
                    Campaign.id == campaign_id,
                    Campaign.broker_id == broker_id
                ))
            )
            if not campaign_result.scalars().first():
                raise ValueError(f"Campaign {campaign_id} not found or access denied")
        
        result = await db.execute(query)
        logs = result.scalars().all()
        
        total = len(logs)
        pending = len([l for l in logs if l.status == CampaignLogStatus.PENDING])
        sent = len([l for l in logs if l.status == CampaignLogStatus.SENT])
        failed = len([l for l in logs if l.status == CampaignLogStatus.FAILED])
        skipped = len([l for l in logs if l.status == CampaignLogStatus.SKIPPED])
        
        # Get unique leads
        unique_leads_result = await db.execute(
            select(func.count(func.distinct(CampaignLog.lead_id)))
            .where(CampaignLog.campaign_id == campaign_id)
        )
        unique_leads = unique_leads_result.scalar() or 0
        
        return {
            "campaign_id": campaign_id,
            "total_steps": total,
            "unique_leads": unique_leads,
            "pending": pending,
            "sent": sent,
            "failed": failed,
            "skipped": skipped,
            "success_rate": (sent / total * 100) if total > 0 else 0,
            "failure_rate": (failed / total * 100) if total > 0 else 0
        }
    
    @staticmethod
    async def check_trigger_conditions(
        db: AsyncSession,
        campaign: Campaign,
        lead: Lead
    ) -> bool:
        """Check if a campaign's trigger conditions are met for a lead"""
        
        condition = campaign.trigger_condition or {}
        
        if campaign.triggered_by == CampaignTrigger.LEAD_SCORE:
            score_min = condition.get("score_min")
            score_max = condition.get("score_max")
            
            if score_min is not None and lead.lead_score < score_min:
                return False
            if score_max is not None and lead.lead_score > score_max:
                return False
            
            return True
        
        elif campaign.triggered_by == CampaignTrigger.STAGE_CHANGE:
            target_stage = condition.get("stage")
            if target_stage and lead.pipeline_stage == target_stage:
                return True
            return False
        
        elif campaign.triggered_by == CampaignTrigger.INACTIVITY:
            inactivity_days = condition.get("inactivity_days", 30)
            
            if not lead.last_contacted:
                # Never contacted, check days since created
                days_since_created = (datetime.now().replace(tzinfo=lead.created_at.tzinfo) - lead.created_at).days
                return days_since_created >= inactivity_days
            
            days_since_contact = (datetime.now().replace(tzinfo=lead.last_contacted.tzinfo) - lead.last_contacted).days
            return days_since_contact >= inactivity_days
        
        elif campaign.triggered_by == CampaignTrigger.MANUAL:
            # Manual campaigns don't auto-trigger
            return False
        
        return False
    
    @staticmethod
    async def update_campaign_status(
        db: AsyncSession,
        campaign_id: int,
        status: CampaignStatus,
        broker_id: Optional[int] = None
    ) -> Campaign:
        """Update campaign status"""
        
        query = select(Campaign).where(Campaign.id == campaign_id)
        
        if broker_id:
            query = query.where(Campaign.broker_id == broker_id)
        
        result = await db.execute(query)
        campaign = result.scalars().first()
        
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")
        
        campaign.status = status
        await db.commit()
        await db.refresh(campaign)
        
        logger.info(f"Campaign {campaign_id} status updated to {status}")
        return campaign
    
    @staticmethod
    async def delete_campaign(
        db: AsyncSession,
        campaign_id: int,
        broker_id: Optional[int] = None
    ) -> bool:
        """Delete a campaign (soft delete by setting to draft or hard delete)"""
        
        query = select(Campaign).where(Campaign.id == campaign_id)
        
        if broker_id:
            query = query.where(Campaign.broker_id == broker_id)
        
        result = await db.execute(query)
        campaign = result.scalars().first()
        
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")
        
        # For now, hard delete (can be changed to soft delete later)
        await db.delete(campaign)
        await db.commit()
        
        logger.info(f"Campaign {campaign_id} deleted")
        return True



