from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from typing import Optional, List, Dict
from app.models.lead import Lead
from app.models.telegram_message import TelegramMessage


class LeadContextService:
    """Service for building lead context for LLM"""
    
    @staticmethod
    async def get_or_create_lead(
        db: AsyncSession,
        telegram_user_id: int,
        username: str
    ) -> Lead:
        """Get or create lead by Telegram ID"""
        
        # Try to find by telegram_user_id in metadata
        # Using JSONB cast for PostgreSQL
        from sqlalchemy import cast, String
        from sqlalchemy.dialects.postgresql import JSONB
        
        result = await db.execute(
            select(Lead).where(
                cast(Lead.lead_metadata, JSONB)['telegram_user_id'].astext == str(telegram_user_id)
            )
        )
        lead = result.scalars().first()
        
        if lead:
            return lead
        
        # Create new lead with telegram ID as phone
        from app.models.lead import LeadStatus
        new_lead = Lead(
            phone=f"telegram_{telegram_user_id}",
            name=username,
            lead_metadata={"telegram_user_id": telegram_user_id, "username": username},
            status=LeadStatus.COLD,
            lead_score=0.0
        )
        
        db.add(new_lead)
        await db.commit()
        await db.refresh(new_lead)
        
        return new_lead
    
    @staticmethod
    async def get_lead_context(db: AsyncSession, lead_id: int) -> Dict:
        """Get lead context for LLM prompt"""
        
        # Get lead
        result = await db.execute(
            select(Lead).where(Lead.id == lead_id)
        )
        lead = result.scalars().first()
        
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")
        
        # Get last 20 messages (more for better context)
        msg_result = await db.execute(
            select(TelegramMessage)
            .where(TelegramMessage.lead_id == lead_id)
            .order_by(TelegramMessage.created_at)
            .limit(20)
        )
        messages = msg_result.scalars().all()
        
        # Format message history as structured array (standard format)
        # Format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        message_history = []
        for msg in messages:
            role = "user" if msg.direction.value == "in" else "assistant"
            message_history.append({
                "role": role,
                "content": msg.message_text
            })
        
        # Also keep legacy format for backward compatibility during migration
        legacy_message_history = []
        for msg in reversed(messages[-10:]):  # Last 10 for legacy
            direction = "U" if msg.direction.value == "in" else "B"
            clean_text = msg.message_text.replace("|", "‖").replace("\n", " ")
            legacy_message_history.append(f"{direction}:{clean_text}")
        
        # Get phone, handling different formats
        phone_number = lead.phone if lead.phone and not lead.phone.startswith("web_chat_") and not lead.phone.startswith("whatsapp_") and not lead.phone.startswith("+569999") else None
        
        # Convert metadata to TOON format if it's a dict
        metadata = lead.lead_metadata or {}
        if isinstance(metadata, dict):
            # Format: key:value|key:value (compact)
            metadata_toon = "|".join([f"{k}:{v}" for k, v in metadata.items() if v])
        else:
            metadata_toon = str(metadata)
        
        return {
            "lead_id": lead.id,
            "name": lead.name or "User",
            "phone": phone_number,
            "email": lead.email if lead.email else None,
            "status": lead.status,
            "score": lead.lead_score,
            "metadata": metadata,  # Keep as dict for internal use
            "metadata_toon": metadata_toon,  # TOON format for display
            "message_history": message_history,  # NEW: Structured array format
            "message_history_legacy": "|".join(legacy_message_history),  # Legacy format for backward compatibility
        }
    