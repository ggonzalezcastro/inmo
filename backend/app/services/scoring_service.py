from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timedelta
from typing import Dict, Optional
from app.models.lead import Lead
from app.models.telegram_message import TelegramMessage
from app.models.activity_log import ActivityLog
import logging


logger = logging.getLogger(__name__)


class ScoringService:
    """Lead scoring algorithm"""
    
    @staticmethod
    async def calculate_lead_score(db: AsyncSession, lead_id: int, broker_id: Optional[int] = None) -> Dict:
        """Calculate complete lead score using broker configuration if available"""
        
        # Get lead
        result = await db.execute(
            select(Lead).where(Lead.id == lead_id)
        )
        lead = result.scalars().first()
        
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")
        
        # Use broker_id from lead if not provided
        if not broker_id:
            broker_id = lead.broker_id
        
        # Get interaction data
        msg_result = await db.execute(
            select(TelegramMessage).where(TelegramMessage.lead_id == lead_id)
        )
        messages = msg_result.scalars().all()
        
        # Get activities
        act_result = await db.execute(
            select(ActivityLog).where(ActivityLog.lead_id == lead_id)
        )
        activities = act_result.scalars().all()
        
        # Calculate components
        base_score = ScoringService._calculate_base_interaction(messages)
        behavior_score = ScoringService._calculate_behavior(messages, lead)
        engagement_score = ScoringService._calculate_engagement(activities)
        stage_score = ScoringService._calculate_stage_score(lead)
        financial_score = await ScoringService._calculate_financial_score(db, lead, broker_id)
        penalties = ScoringService._calculate_penalties(lead, messages)
        
        # Total score (adjust max to 100, financial replaces part of behavior)
        # Original max was 30+35+25+20 = 110, now with financial (45) we adjust
        # We cap base+behavior+engagement+stage at 60, financial at 45, total max 100
        base_components = base_score + behavior_score + engagement_score + stage_score
        base_components = min(60, base_components)  # Cap base components
        
        total = base_components + financial_score - penalties
        total = max(0, min(100, total))  # Clamp 0-100
        
        return {
            "total": total,
            "base": base_score,
            "behavior": behavior_score,
            "engagement": engagement_score,
            "stage": stage_score,
            "financial": financial_score,
            "penalties": penalties
        }
    
    @staticmethod
    def _calculate_base_interaction(messages: list) -> int:
        """BASE INTERACTION (0-30 points)"""
        points = 0
        
        if len(messages) == 0:
            return 0  # Never contacted
        
        if len(messages) == 1:
            points += 5  # Once contacted
        elif len(messages) >= 2:
            points += 10  # Responded
        
        if len(messages) >= 5:
            points += 7  # Multiple interactions
        
        return min(30, points)
    
    @staticmethod
    def _calculate_behavior(messages: list, lead: Lead) -> int:
        """BEHAVIOR (0-35 points)"""
        points = 0
        
        # Quick response time (<5 min)
        # Sort messages by created_at to get chronological order
        sorted_messages = sorted(messages, key=lambda m: m.created_at)
        if len(sorted_messages) >= 2:
            first_msg = sorted_messages[0]
            response_msg = sorted_messages[1]
            if first_msg.created_at and response_msg.created_at:
                time_diff = (response_msg.created_at - first_msg.created_at).total_seconds()
                
                if time_diff < 300:  # 5 minutes
                    points += 10
        
        # Budget mentioned
        if lead.lead_metadata.get("budget"):
            points += 8
        
        # Timeline mentioned
        if lead.lead_metadata.get("timeline"):
            points += 10
        
        # Personal info provided
        if lead.name or lead.email:
            points += 7
        
        return min(35, points)
    
    @staticmethod
    async def _calculate_financial_score(
        db: AsyncSession,
        lead: Lead,
        broker_id: Optional[int] = None
    ) -> int:
        """
        FINANCIAL SCORE (0-45 points)
        Based on monthly_income and dicom_status using broker configuration
        """
        points = 0
        metadata = lead.lead_metadata or {}
        
        # Use BrokerConfigService for financial scoring (no hardcoding)
        from app.services.broker_config_service import BrokerConfigService
        
        # Prepare lead data for financial score calculation
        lead_data = {
            "metadata": metadata
        }
        
        # Calculate financial score using broker configuration
        financial_score = await BrokerConfigService.calculate_financial_score(
            db, lead_data, broker_id
        )
        
        return financial_score
    
    @staticmethod
    def _calculate_engagement(activities: list) -> int:
        """ENGAGEMENT (0-25 points)"""
        points = 0
        
        # Multiple interactions
        score_updates = [a for a in activities if a.action_type == "score_update"]
        if len(score_updates) >= 3:
            points += 8
        
        # Sent documents/links
        message_activities = [a for a in activities if a.action_type == "message"]
        if len(message_activities) >= 5:
            points += 6
        
        # Scheduled meeting (future feature)
        # if any(a.action_type == "meeting_scheduled" for a in activities):
        #     points += 11
        
        return min(25, points)
    
    @staticmethod
    def _calculate_penalties(lead: Lead, messages: list) -> int:
        """PENALTIES"""
        penalties = 0
        
        # Check for "don't call" or blocked messages
        for msg in messages:
            text_lower = msg.message_text.lower()
            if "no llamar" in text_lower or "bloqueado" in text_lower:
                return 30  # Mark as LOST
        
        # Inactive >60 days
        if lead.last_contacted:
            days_since = (datetime.utcnow() - lead.last_contacted).days
            if days_since > 60:
                penalties += 5
        
        # Invalid phone (for future use)
        if "invalid" in lead.lead_metadata.get("status", "").lower():
            penalties += 25
        
        return penalties
    
    @staticmethod
    def _calculate_stage_score(lead: Lead) -> int:
        """
        STAGE SCORE (0-20 points)
        Score based on pipeline stage and stage-specific data
        """
        points = 0
        pipeline_stage = lead.pipeline_stage
        metadata = lead.lead_metadata or {}
        
        if not pipeline_stage:
            return 0  # No stage = no points
        
        # Stage-specific scoring multipliers
        if pipeline_stage == "entrada":
            points = 2  # Just entered
        elif pipeline_stage == "perfilamiento":
            # Weight budget/timeline mentions higher in this stage
            if metadata.get("budget"):
                points += 8
            if metadata.get("location"):
                points += 5
            if metadata.get("timeline"):
                points += 5
            points = min(15, points) if points > 0 else 5
        elif pipeline_stage == "calificacion_financiera":
            # Weight financial data higher
            if metadata.get("salary"):
                points += 10
            if metadata.get("budget"):
                points += 8
            points = min(18, points) if points > 0 else 10
        elif pipeline_stage == "agendado":
            # Boost if meeting confirmed
            from app.models.appointment import Appointment, AppointmentStatus
            # Note: This would require DB access, but for scoring we check appointments separately
            points = 15  # Base score for being scheduled
            # +5 if meeting confirmed (would need DB check in full implementation)
        elif pipeline_stage == "seguimiento":
            points = 18  # High score - post-meeting follow-up
        elif pipeline_stage == "referidos":
            points = 19  # Very high - waiting for referrals
        elif pipeline_stage == "ganado":
            points = 20  # Maximum - converted
        elif pipeline_stage == "perdido":
            points = -10  # Negative score for lost leads
        
        return min(20, max(-10, points))

