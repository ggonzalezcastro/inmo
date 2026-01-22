from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Dict, Any
from app.models.telegram_message import TelegramMessage, MessageDirection, MessageStatus
from app.models.activity_log import ActivityLog


class ActivityService:
    """Service for logging activities and messages"""
    
    @staticmethod
    async def log_telegram_message(
        db: AsyncSession,
        lead_id: int,
        telegram_user_id: int,
        message_text: str,
        direction: str,  # "in" or "out"
        ai_used: bool = True
    ) -> TelegramMessage:
        """Log telegram message"""
        
        msg = TelegramMessage(
            lead_id=lead_id,
            telegram_user_id=telegram_user_id,
            message_text=message_text,
            direction=MessageDirection.INBOUND if direction == "in" else MessageDirection.OUTBOUND,
            status=MessageStatus.SENT,
            ai_response_used=ai_used
        )
        
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        
        return msg
    
    @staticmethod
    async def log_activity(
        db: AsyncSession,
        lead_id: int,
        action_type: str,  # message, call, score_update, status_change
        details: Dict[str, Any]
    ) -> ActivityLog:
        """Log activity - details stored as JSON but can be converted to TOON format when needed"""
        
        # Store details as JSON (PostgreSQL JSONB)
        activity = ActivityLog(
            lead_id=lead_id,
            action_type=action_type,
            details=details,
            timestamp=datetime.utcnow()
        )
        
        db.add(activity)
        await db.commit()
        await db.refresh(activity)
        
        return activity
    
    @staticmethod
    def details_to_toon(details: Dict[str, Any]) -> str:
        """Convert activity details dict to TOON format"""
        if not details:
            return ""
        # Format: key:value|key:value
        parts = []
        for k, v in details.items():
            if v is not None:
                if isinstance(v, (dict, list)):
                    # Convert complex types to string
                    v_str = str(v).replace("|", "‖").replace("\n", " ")
                else:
                    v_str = str(v).replace("|", "‖")
                parts.append(f"{k}:{v_str}")
        return "|".join(parts)

