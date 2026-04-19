from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
from app.models.lead import Lead
from app.models.telegram_message import TelegramMessage
from app.models.activity_log import ActivityLog
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Score structure (0-100 pts):
#   Financial health  (0-60) — primary:  income tiers + DICOM status
#   Key profile       (0-25) — secondary: name (5) + phone (10) + income provided (10)
#   Engagement bonus  (0-15) — tertiary:  messages (5) + fast responder (5) + sessions (5)
#       fast responder: avg bot→lead reply ≤ FAST_RESPONSE_THRESHOLD_SECONDS
#       across at least FAST_RESPONSE_MIN_REPLIES recorded replies (see
#       app.services.leads.constants and response_metrics).
#   Penalties                            blocklist (-30), inactive (-5), bad phone (-10)
# ---------------------------------------------------------------------------


class ScoringService:
    """Lead scoring algorithm — financial-first model."""

    @staticmethod
    async def calculate_lead_score(db: AsyncSession, lead_id: int, broker_id: Optional[int] = None) -> Dict:
        result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalars().first()
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")
        if not broker_id:
            broker_id = lead.broker_id

        msg_result = await db.execute(select(TelegramMessage).where(TelegramMessage.lead_id == lead_id))
        messages = msg_result.scalars().all()

        act_result = await db.execute(select(ActivityLog).where(ActivityLog.lead_id == lead_id))
        activities = act_result.scalars().all()

        return await ScoringService._compute_score_components(db, lead, messages, activities, broker_id)

    @staticmethod
    async def calculate_lead_score_from_lead(
        db: AsyncSession,
        lead: Lead,
        broker_id: Optional[int] = None,
        messages: Optional[List[Any]] = None,
        activities: Optional[List[Any]] = None,
    ) -> Dict:
        if not broker_id:
            broker_id = lead.broker_id
        messages = messages if messages is not None else list(lead.telegram_messages) if hasattr(lead, "telegram_messages") else []
        activities = activities if activities is not None else list(lead.activities) if hasattr(lead, "activities") else []
        return await ScoringService._compute_score_components(db, lead, messages, activities, broker_id)

    @staticmethod
    async def _compute_score_components(
        db: AsyncSession,
        lead: Lead,
        messages: list,
        activities: list,
        broker_id: Optional[int],
    ) -> Dict:
        financial_score = await ScoringService._calculate_financial_score(db, lead, broker_id)
        profile_score = ScoringService._calculate_key_profile(lead)
        engagement_score = ScoringService._calculate_engagement_bonus(messages, activities)
        penalties = ScoringService._calculate_penalties(lead, messages)

        total = max(0, min(100, financial_score + profile_score + engagement_score - penalties))

        return {
            "total": total,
            "base": profile_score,
            "behavior": engagement_score,
            "engagement": engagement_score,
            "stage": 0,
            "financial": financial_score,
            "penalties": penalties,
        }

    @staticmethod
    def _calculate_key_profile(lead: Lead) -> int:
        """Key profile fields (0-25 pts): name(5) + phone(10) + income reported(10)."""
        pts = 0
        if lead.name and lead.name not in ["User", "Test User"]:
            pts += 5
        phone = lead.phone or ""
        if phone and not phone.startswith(("web_chat_", "whatsapp_", "+569999")):
            pts += 10
        metadata = lead.lead_metadata or {}
        if metadata.get("monthly_income"):
            pts += 10
        return min(25, pts)

    @staticmethod
    def _calculate_engagement_bonus(messages: list, activities: list) -> int:
        """Engagement bonus (0-15 pts)."""
        from app.services.leads.response_metrics import compute_response_metrics

        pts = 0
        # 5+ messages
        if len(messages) >= 5:
            pts += 5
        # Fast responder: real bot→lead turnaround averaged across all replies
        # (replaces the old "delta between first two messages" heuristic).
        metrics = compute_response_metrics(messages)
        if metrics.get("is_fast_responder"):
            pts += 5
        # Active sessions (3+ activity log entries)
        if len(activities) >= 3:
            pts += 5
        return min(15, pts)

    @staticmethod
    async def _calculate_financial_score(db: AsyncSession, lead: Lead, broker_id: Optional[int]) -> int:
        """Financial health (0-60 pts) using scoring_config income tiers + DICOM."""
        from app.services.broker import BrokerConfigService
        return await BrokerConfigService.calculate_financial_score(
            db, {"metadata": lead.lead_metadata or {}}, broker_id
        )

    @staticmethod
    def _calculate_penalties(lead: Lead, messages: list) -> int:
        """Penalties: blocklist (-30), inactive >60d (-5), invalid phone (-10)."""
        for msg in messages:
            if msg.message_text:
                text_lower = msg.message_text.lower()
                if "no llamar" in text_lower or "bloqueado" in text_lower:
                    return 30
        penalties = 0
        if lead.last_contacted:
            days_since = (datetime.utcnow() - lead.last_contacted).days
            if days_since > 60:
                penalties += 5
        metadata = lead.lead_metadata or {}
        if "invalid" in str(metadata.get("status", "")).lower():
            penalties += 10
        return penalties



