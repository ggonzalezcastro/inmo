"""Appointment availability: check slots and get available slots."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_
from datetime import datetime, timedelta, date, time as dt_time
from typing import List, Optional, Dict, Any
import pytz
import logging

from app.models.appointment import (
    Appointment,
    AppointmentStatus,
    AppointmentType,
    AvailabilitySlot,
    AppointmentBlock,
)

logger = logging.getLogger(__name__)

CHILE_TZ = pytz.timezone("America/Santiago")


async def check_availability(
    db: AsyncSession,
    start_time: datetime,
    end_time: datetime,
    agent_id: Optional[int] = None,
    exclude_appointment_id: Optional[int] = None,
) -> bool:
    """Check if a time slot is available (no conflicts with appointments or blocks)."""
    query = select(Appointment).where(
        and_(
            Appointment.status.in_([
                AppointmentStatus.SCHEDULED,
                AppointmentStatus.CONFIRMED,
            ]),
            or_(
                and_(
                    Appointment.start_time < end_time,
                    Appointment.end_time > start_time,
                )
            ),
        )
    )
    if exclude_appointment_id:
        query = query.where(Appointment.id != exclude_appointment_id)
    if agent_id:
        query = query.where(
            or_(
                Appointment.agent_id == agent_id,
                Appointment.agent_id.is_(None),
            )
        )
    result = await db.execute(query)
    if result.scalars().first():
        return False

    block_query = select(AppointmentBlock).where(
        and_(
            AppointmentBlock.start_time < end_time,
            AppointmentBlock.end_time > start_time,
        )
    )
    if agent_id:
        block_query = block_query.where(
            or_(
                AppointmentBlock.agent_id == agent_id,
                AppointmentBlock.agent_id.is_(None),
            )
        )
    block_result = await db.execute(block_query)
    if block_result.scalars().first():
        return False
    return True


async def get_available_slots(
    db: AsyncSession,
    start_date: date,
    end_date: date,
    agent_id: Optional[int] = None,
    appointment_type: Optional[AppointmentType] = None,
    duration_minutes: int = 60,
) -> List[Dict[str, Any]]:
    """Get available time slots for a date range."""
    available_slots = []
    current_date = start_date

    while current_date <= end_date:
        day_of_week = current_date.weekday()
        slot_query = select(AvailabilitySlot).where(
            and_(
                AvailabilitySlot.day_of_week == day_of_week,
                AvailabilitySlot.is_active == True,
                AvailabilitySlot.valid_from <= current_date,
                or_(
                    AvailabilitySlot.valid_until.is_(None),
                    AvailabilitySlot.valid_until >= current_date,
                ),
            )
        )
        if agent_id:
            slot_query = slot_query.where(
                or_(
                    AvailabilitySlot.agent_id == agent_id,
                    AvailabilitySlot.agent_id.is_(None),
                )
            )
        if appointment_type:
            slot_query = slot_query.where(
                or_(
                    AvailabilitySlot.appointment_type == appointment_type,
                    AvailabilitySlot.appointment_type.is_(None),
                )
            )
        slot_result = await db.execute(slot_query)
        slots = slot_result.scalars().all()

        for slot in slots:
            slot_start_dt = CHILE_TZ.localize(
                datetime.combine(current_date, slot.start_time)
            )
            slot_end_dt = CHILE_TZ.localize(
                datetime.combine(current_date, slot.end_time)
            )
            current_slot_start = slot_start_dt
            while current_slot_start + timedelta(
                minutes=duration_minutes
            ) <= slot_end_dt:
                current_slot_end = current_slot_start + timedelta(
                    minutes=duration_minutes
                )
                is_available = await check_availability(
                    db,
                    start_time=current_slot_start,
                    end_time=current_slot_end,
                    agent_id=agent_id,
                )
                if is_available:
                    available_slots.append({
                        "start_time": current_slot_start.isoformat(),
                        "end_time": current_slot_end.isoformat(),
                        "duration_minutes": duration_minutes,
                        "date": current_date.isoformat(),
                        "time": current_slot_start.strftime("%H:%M"),
                    })
                current_slot_start += timedelta(
                    minutes=slot.slot_duration_minutes
                )
        current_date += timedelta(days=1)

    return available_slots
