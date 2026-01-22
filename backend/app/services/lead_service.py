from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_, func
from typing import Optional, List, Dict, Tuple
import re


from app.models.lead import Lead, LeadStatus
from app.schemas.lead import LeadCreate, LeadUpdate


class LeadService:
    
    @staticmethod
    def normalize_phone(phone: str) -> str:
        """
        Normalize phone to international format
        Examples:
          912345678 → +56912345678
          +56912345678 → +56912345678
          56912345678 → +56912345678
        """
        # Remove all non-digits
        digits = re.sub(r'\D', '', phone)
        
        # If starts with 56, add +
        if digits.startswith('56'):
            return f"+{digits}"
        
        # If Chilean number without country code
        if len(digits) == 9 and digits.startswith('9'):
            return f"+56{digits}"
        
        # Add + if not present
        if not digits.startswith('+'):
            return f"+{digits}"
        
        return digits
    
    @staticmethod
    def validate_phone(phone: str) -> Tuple[bool, str]:
        """
        Validate phone number
        
        Allows placeholders that start with 'web_chat_', 'whatsapp_' or '+569999' 
        (these are temporary placeholders that will be replaced with real phones)
        """
        # Allow placeholders (web_chat_*, whatsapp_* or +569999*)
        if phone.startswith("web_chat_") or phone.startswith("whatsapp_") or phone.startswith("+569999"):
            return True, phone
        
        normalized = LeadService.normalize_phone(phone)
        digits = re.sub(r'\D', '', normalized)
        
        if len(digits) < 10:
            return False, "Phone must have at least 10 digits"
        
        if len(digits) > 15:
            return False, "Phone is too long"
        
        return True, normalized
    
    @staticmethod
    async def create_lead(
        db: AsyncSession,
        lead_data: LeadCreate
    ) -> Lead:
        """Create a new lead"""
        
        # Validate and normalize phone
        is_valid, phone = LeadService.validate_phone(lead_data.phone)
        if not is_valid:
            raise ValueError(phone)
        
        # Removed duplicate check - allow multiple leads with same phone
        
        # Create lead
        lead = Lead(
            phone=phone,
            name=lead_data.name,
            email=lead_data.email,
            tags=lead_data.tags,
            lead_metadata=lead_data.metadata,
            status=LeadStatus.COLD,
            lead_score=0.0
        )
        
        db.add(lead)
        await db.commit()
        await db.refresh(lead)
        
        return lead
    
    @staticmethod
    async def get_leads(
        db: AsyncSession,
        status: Optional[str] = None,
        min_score: float = 0,
        max_score: float = 100,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[Lead], int]:
        """Get leads with filters"""
        
        filters = []
        
        # Status filter
        if status:
            statuses = status.split(',')
            filters.append(Lead.status.in_(statuses))
        
        # Score range filter
        filters.append(and_(Lead.lead_score >= min_score, Lead.lead_score <= max_score))
        
        # Search filter (name or phone)
        if search:
            search_term = f"%{search}%"
            filters.append(
                or_(
                    Lead.name.ilike(search_term),
                    Lead.phone.ilike(search_term)
                )
            )
        
        # Get total count
        count_query = select(func.count(Lead.id))
        if filters:
            count_query = count_query.where(and_(*filters))
        count_result = await db.execute(count_query)
        total_count = count_result.scalar() or 0
        
        # Get leads
        query = select(Lead)
        if filters:
            query = query.where(and_(*filters))
        query = query.order_by(Lead.lead_score.desc())
        query = query.offset(skip).limit(limit)
        
        result = await db.execute(query)
        leads = result.scalars().all()
        
        return leads, total_count
    
    @staticmethod
    async def get_lead(db: AsyncSession, lead_id: int) -> Optional[Lead]:
        """Get single lead"""
        result = await db.execute(
            select(Lead).where(Lead.id == lead_id)
        )
        return result.scalars().first()
    
    @staticmethod
    async def update_lead(
        db: AsyncSession,
        lead_id: int,
        lead_data: LeadUpdate
    ) -> Lead:
        """Update lead"""
        lead = await LeadService.get_lead(db, lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")
        
        # Update fields
        update_data = lead_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(lead, field, value)
        
        await db.commit()
        await db.refresh(lead)
        
        return lead
    
    @staticmethod
    async def delete_lead(db: AsyncSession, lead_id: int) -> bool:
        """Soft delete lead"""
        lead = await LeadService.get_lead(db, lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")
        
        # In real implementation, add deleted_at timestamp
        await db.delete(lead)
        await db.commit()
        
        return True

