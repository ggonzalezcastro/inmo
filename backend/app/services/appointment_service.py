from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_, func, extract
from datetime import datetime, timedelta, date, time as dt_time
from typing import List, Optional, Dict, Any
import secrets
import hashlib
import pytz
import logging
from app.models.appointment import (
    Appointment,
    AppointmentStatus,
    AppointmentType,
    AvailabilitySlot,
    AppointmentBlock
)
from app.models.lead import Lead
from app.services.google_calendar_service import get_google_calendar_service

logger = logging.getLogger(__name__)


class AppointmentService:
    """Service for managing appointments and availability"""
    
    # Timezone for Chile
    CHILE_TZ = pytz.timezone('America/Santiago')
    
    @staticmethod
    def generate_google_meet_url(lead_id: int, appointment_id: Optional[int] = None) -> str:
        """
        Generate a Google Meet URL for an appointment (fallback method)
        This is only used if Google Calendar API is not configured
        """
        # Create a unique identifier
        unique_str = f"{lead_id}_{appointment_id or 'new'}_{secrets.token_hex(4)}"
        # Generate a deterministic but unique code (12 characters, alphanumeric)
        hash_obj = hashlib.md5(unique_str.encode())
        hash_hex = hash_obj.hexdigest()[:12]
        
        # Format as Google Meet code (3-4-3 format)
        meet_code = f"{hash_hex[:3]}-{hash_hex[3:7]}-{hash_hex[7:10]}"
        
        return f"https://meet.google.com/{meet_code}"
    
    @staticmethod
    async def create_appointment(
        db: AsyncSession,
        lead_id: int,
        start_time: datetime,
        duration_minutes: int = 60,
        appointment_type: AppointmentType = AppointmentType.VIRTUAL_MEETING,
        agent_id: Optional[int] = None,
        location: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Appointment:
        """Create a new appointment - always generates Google Meet URL for online meetings"""
        
        # Ensure start_time is timezone-aware
        if start_time.tzinfo is None:
            start_time = AppointmentService.CHILE_TZ.localize(start_time)
        
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        # Check availability
        is_available = await AppointmentService.check_availability(
            db,
            start_time=start_time,
            end_time=end_time,
            agent_id=agent_id
        )
        
        if not is_available:
            raise ValueError("Time slot is not available")
        
        # Get lead information for event title
        lead_result = await db.execute(
            select(Lead).where(Lead.id == lead_id)
        )
        lead = lead_result.scalars().first()
        lead_name = lead.name if lead and lead.name else f"Lead #{lead_id}"
        
        # Try to create Google Calendar event with Meet link
        meet_url = None
        google_event_id = None
        
        calendar_service = get_google_calendar_service()
        if calendar_service.service:
            try:
                event_title = f"Reunión con {lead_name}"
                event_description = notes or f"Reunión virtual con {lead_name}"
                if lead and lead.phone:
                    event_description += f"\nTeléfono: {lead.phone}"
                
                calendar_event = calendar_service.create_event_with_meet(
                    title=event_title,
                    start_time=start_time,
                    end_time=end_time,
                    description=event_description,
                    location=location or "Reunión virtual"
                )
                
                if calendar_event and calendar_event.get('meet_url'):
                    meet_url = calendar_event['meet_url']
                    google_event_id = calendar_event.get('event_id')
                    logger.info(f"Google Calendar event created: {google_event_id}, Meet URL: {meet_url}")
                else:
                    logger.warning("Google Calendar event creation failed, using fallback URL")
                    meet_url = AppointmentService.generate_google_meet_url(lead_id)
            except Exception as e:
                logger.error(f"Error creating Google Calendar event: {str(e)}", exc_info=True)
                # Fallback to generated URL
                meet_url = AppointmentService.generate_google_meet_url(lead_id)
        else:
            # Fallback: generate a simulated URL
            logger.warning("Google Calendar service not configured, using fallback URL")
            meet_url = AppointmentService.generate_google_meet_url(lead_id)
        
        appointment = Appointment(
            lead_id=lead_id,
            agent_id=agent_id,
            appointment_type=appointment_type,
            status=AppointmentStatus.SCHEDULED,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
            location=location or "Reunión virtual",
            meet_url=meet_url,
            google_event_id=google_event_id,
            notes=notes
        )
        
        db.add(appointment)
        await db.commit()
        await db.refresh(appointment)
        
        return appointment
    
    @staticmethod
    async def check_availability(
        db: AsyncSession,
        start_time: datetime,
        end_time: datetime,
        agent_id: Optional[int] = None,
        exclude_appointment_id: Optional[int] = None
    ) -> bool:
        """Check if a time slot is available"""
        
        # Check for existing appointments in this time range
        query = select(Appointment).where(
            and_(
                Appointment.status.in_([
                    AppointmentStatus.SCHEDULED,
                    AppointmentStatus.CONFIRMED
                ]),
                or_(
                    and_(
                        Appointment.start_time < end_time,
                        Appointment.end_time > start_time
                    )
                )
            )
        )
        
        # Exclude current appointment if updating
        if exclude_appointment_id:
            query = query.where(Appointment.id != exclude_appointment_id)
        
        if agent_id:
            query = query.where(
                or_(
                    Appointment.agent_id == agent_id,
                    Appointment.agent_id.is_(None)
                )
            )
        
        result = await db.execute(query)
        conflicting_appointments = result.scalars().all()
        
        if conflicting_appointments:
            return False
        
        # Check for blocks
        block_query = select(AppointmentBlock).where(
            and_(
                AppointmentBlock.start_time < end_time,
                AppointmentBlock.end_time > start_time
            )
        )
        
        if agent_id:
            block_query = block_query.where(
                or_(
                    AppointmentBlock.agent_id == agent_id,
                    AppointmentBlock.agent_id.is_(None)
                )
            )
        
        block_result = await db.execute(block_query)
        blocks = block_result.scalars().all()
        
        if blocks:
            return False
        
        return True
    
    @staticmethod
    async def get_available_slots(
        db: AsyncSession,
        start_date: date,
        end_date: date,
        agent_id: Optional[int] = None,
        appointment_type: Optional[AppointmentType] = None,
        duration_minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """Get available time slots for a date range"""
        
        available_slots = []
        current_date = start_date
        
        while current_date <= end_date:
            day_of_week = current_date.weekday()  # 0=Monday, 6=Sunday
            
            # Get availability slots for this day
            slot_query = select(AvailabilitySlot).where(
                and_(
                    AvailabilitySlot.day_of_week == day_of_week,
                    AvailabilitySlot.is_active == True,
                    AvailabilitySlot.valid_from <= current_date,
                    or_(
                        AvailabilitySlot.valid_until.is_(None),
                        AvailabilitySlot.valid_until >= current_date
                    )
                )
            )
            
            if agent_id:
                slot_query = slot_query.where(
                    or_(
                        AvailabilitySlot.agent_id == agent_id,
                        AvailabilitySlot.agent_id.is_(None)
                    )
                )
            
            if appointment_type:
                slot_query = slot_query.where(
                    or_(
                        AvailabilitySlot.appointment_type == appointment_type,
                        AvailabilitySlot.appointment_type.is_(None)
                    )
                )
            
            slot_result = await db.execute(slot_query)
            slots = slot_result.scalars().all()
            
            # Generate time slots for each availability slot
            for slot in slots:
                slot_start = dt_time.combine(current_date, slot.start_time)
                slot_end = dt_time.combine(current_date, slot.end_time)
                
                # Make timezone-aware
                slot_start_dt = AppointmentService.CHILE_TZ.localize(
                    datetime.combine(current_date, slot.start_time)
                )
                slot_end_dt = AppointmentService.CHILE_TZ.localize(
                    datetime.combine(current_date, slot.end_time)
                )
                
                # Generate slots of specified duration
                current_slot_start = slot_start_dt
                while current_slot_start + timedelta(minutes=duration_minutes) <= slot_end_dt:
                    current_slot_end = current_slot_start + timedelta(minutes=duration_minutes)
                    
                    # Check if this specific slot is available
                    is_available = await AppointmentService.check_availability(
                        db,
                        start_time=current_slot_start,
                        end_time=current_slot_end,
                        agent_id=agent_id
                    )
                    
                    if is_available:
                        available_slots.append({
                            "start_time": current_slot_start.isoformat(),
                            "end_time": current_slot_end.isoformat(),
                            "duration_minutes": duration_minutes,
                            "date": current_date.isoformat(),
                            "time": current_slot_start.strftime("%H:%M")
                        })
                    
                    current_slot_start += timedelta(minutes=slot.slot_duration_minutes)
            
            current_date += timedelta(days=1)
        
        return available_slots
    
    @staticmethod
    async def get_appointments_for_lead(
        db: AsyncSession,
        lead_id: int,
        include_cancelled: bool = False
    ) -> List[Appointment]:
        """Get all appointments for a lead"""
        
        query = select(Appointment).where(Appointment.lead_id == lead_id)
        
        if not include_cancelled:
            query = query.where(Appointment.status != AppointmentStatus.CANCELLED)
        
        query = query.order_by(Appointment.start_time)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def update_appointment(
        db: AsyncSession,
        appointment_id: int,
        update_data: Any  # AppointmentUpdate schema
    ) -> Appointment:
        """Update an appointment and sync with Google Calendar"""
        
        result = await db.execute(
            select(Appointment).where(Appointment.id == appointment_id)
        )
        appointment = result.scalars().first()
        
        if not appointment:
            raise ValueError("Appointment not found")
        
        # Get update data as dict
        update_dict = update_data.dict(exclude_unset=True) if hasattr(update_data, 'dict') else update_data
        
        # Store old values for Google Calendar update
        old_start_time = appointment.start_time
        old_end_time = appointment.end_time
        old_location = appointment.location
        old_notes = appointment.notes
        
        # Track if time or duration changed (needs availability check)
        time_changed = False
        
        # Update fields
        for field, value in update_dict.items():
            if field == "status" and value:
                appointment.status = AppointmentStatus(value)
            elif field == "appointment_type" and value:
                # Convert enum if needed
                if isinstance(value, str):
                    appointment.appointment_type = AppointmentType(value)
                else:
                    appointment.appointment_type = value
            elif field == "start_time" and value:
                # Ensure timezone-aware
                if isinstance(value, datetime):
                    if value.tzinfo is None:
                        value = AppointmentService.CHILE_TZ.localize(value)
                appointment.start_time = value
                time_changed = True
                # Recalculate end_time if duration_minutes is set
                if "duration_minutes" in update_dict:
                    appointment.end_time = value + timedelta(minutes=update_dict["duration_minutes"])
                else:
                    appointment.end_time = value + timedelta(minutes=appointment.duration_minutes)
            elif field == "duration_minutes" and value:
                appointment.duration_minutes = value
                appointment.end_time = appointment.start_time + timedelta(minutes=value)
                time_changed = True
            else:
                if hasattr(appointment, field):
                    setattr(appointment, field, value)
        
        # Check availability if time changed (but exclude current appointment from conflict check)
        if time_changed:
            is_available = await AppointmentService.check_availability(
                db,
                start_time=appointment.start_time,
                end_time=appointment.end_time,
                agent_id=appointment.agent_id,
                exclude_appointment_id=appointment_id
            )
            
            if not is_available:
                raise ValueError("Time slot is not available")
        
        # Update Google Calendar event if exists
        if appointment.google_event_id:
            try:
                calendar_service = get_google_calendar_service()
                if calendar_service.service:
                    # Check if relevant fields changed
                    needs_calendar_update = (
                        appointment.start_time != old_start_time or
                        appointment.end_time != old_end_time or
                        appointment.location != old_location or
                        appointment.notes != old_notes
                    )
                    
                    if needs_calendar_update:
                        # Get lead info for title
                        lead_result = await db.execute(
                            select(Lead).where(Lead.id == appointment.lead_id)
                        )
                        lead = lead_result.scalars().first()
                        lead_name = lead.name if lead and lead.name else f"Lead #{appointment.lead_id}"
                        
                        event_title = f"Reunión con {lead_name}"
                        event_description = appointment.notes or f"Reunión virtual con {lead_name}"
                        if lead and lead.phone:
                            event_description += f"\nTeléfono: {lead.phone}"
                        
                        updated_event = calendar_service.update_event(
                            event_id=appointment.google_event_id,
                            title=event_title,
                            start_time=appointment.start_time,
                            end_time=appointment.end_time,
                            description=event_description
                        )
                        
                        if updated_event:
                            logger.info(f"Google Calendar event updated: {appointment.google_event_id}")
                        else:
                            logger.warning(f"Failed to update Google Calendar event: {appointment.google_event_id}")
            except Exception as e:
                logger.error(f"Error updating Google Calendar event: {str(e)}", exc_info=True)
                # Continue with update even if Google Calendar update fails
        
        await db.commit()
        await db.refresh(appointment)
        
        return appointment
    
    @staticmethod
    async def confirm_appointment(
        db: AsyncSession,
        appointment_id: int
    ) -> Appointment:
        """Confirm an appointment"""
        
        result = await db.execute(
            select(Appointment).where(Appointment.id == appointment_id)
        )
        appointment = result.scalars().first()
        
        if not appointment:
            raise ValueError("Appointment not found")
        
        appointment.status = AppointmentStatus.CONFIRMED
        await db.commit()
        await db.refresh(appointment)
        
        return appointment
    
    @staticmethod
    async def cancel_appointment(
        db: AsyncSession,
        appointment_id: int,
        reason: Optional[str] = None
    ) -> Appointment:
        """Cancel an appointment and delete Google Calendar event if exists"""
        
        result = await db.execute(
            select(Appointment).where(Appointment.id == appointment_id)
        )
        appointment = result.scalars().first()
        
        if not appointment:
            raise ValueError("Appointment not found")
        
        # Delete Google Calendar event if exists
        if appointment.google_event_id:
            try:
                calendar_service = get_google_calendar_service()
                if calendar_service.service:
                    deleted = calendar_service.delete_event(appointment.google_event_id)
                    if deleted:
                        logger.info(f"Google Calendar event deleted: {appointment.google_event_id}")
                    else:
                        logger.warning(f"Failed to delete Google Calendar event: {appointment.google_event_id}")
            except Exception as e:
                logger.error(f"Error deleting Google Calendar event: {str(e)}", exc_info=True)
                # Continue with cancellation even if Google Calendar deletion fails
        
        appointment.status = AppointmentStatus.CANCELLED
        appointment.cancelled_at = datetime.now(AppointmentService.CHILE_TZ)
        appointment.cancellation_reason = reason
        
        await db.commit()
        await db.refresh(appointment)
        
        return appointment
    
    @staticmethod
    def format_slots_for_llm(slots: List[Dict[str, Any]], max_slots: int = 10) -> str:
        """Format available slots for LLM prompt (TOON format)"""
        
        if not slots:
            return "No hay horarios disponibles"
        
        # Group by date
        slots_by_date = {}
        for slot in slots[:max_slots]:
            date_str = slot["date"]
            if date_str not in slots_by_date:
                slots_by_date[date_str] = []
            slots_by_date[date_str].append(slot["time"])
        
        # Format: fecha:hora1,hora2|fecha:hora1
        formatted = []
        for date_str, times in slots_by_date.items():
            formatted.append(f"{date_str}:{','.join(times)}")
        
        return "|".join(formatted)

