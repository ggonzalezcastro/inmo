from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, and_, or_, func
from typing import Optional, List
from datetime import datetime, date, timedelta
from app.database import get_db
from app.middleware.auth import get_current_user
from app.services.appointment_service import AppointmentService
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentUpdate,
    AppointmentResponse,
    AppointmentDetailResponse,
    AppointmentListResponse,
    AvailableSlotResponse,
    AppointmentStatusEnum,
    AppointmentTypeEnum
)
from app.models.appointment import Appointment, AppointmentStatus, AppointmentType
from app.models.lead import Lead
from app.models.user import User
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=AppointmentResponse, status_code=201)
async def create_appointment(
    appointment_data: AppointmentCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new appointment"""
    
    try:
        # Verify lead exists
        lead_result = await db.execute(
            select(Lead).where(Lead.id == appointment_data.lead_id)
        )
        lead = lead_result.scalars().first()
        
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # Validate agent_id is provided (required for multi-agent support)
        if not appointment_data.agent_id:
            raise HTTPException(
                status_code=400, 
                detail="agent_id is required. Please specify which agent will handle this appointment."
            )
        
        # Verify agent exists
        agent_result = await db.execute(
            select(User).where(User.id == appointment_data.agent_id)
        )
        agent = agent_result.scalars().first()
        
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Use appointment type from request, default to VIRTUAL_MEETING if not specified
        apt_type = appointment_data.appointment_type
        if apt_type:
            # Convert AppointmentTypeEnum to AppointmentType
            appointment_type = AppointmentType(apt_type.value)
        else:
            appointment_type = AppointmentType.VIRTUAL_MEETING
        
        # Create appointment (generates Google Meet URL for virtual meetings)
        appointment = await AppointmentService.create_appointment(
            db=db,
            lead_id=appointment_data.lead_id,
            start_time=appointment_data.start_time,
            duration_minutes=appointment_data.duration_minutes,
            appointment_type=appointment_type,
            agent_id=appointment_data.agent_id,
            location=appointment_data.location or "Reunión virtual",
            notes=appointment_data.notes
        )
        
        logger.info(f"Appointment {appointment.id} created for lead {appointment_data.lead_id}")
        
        return appointment
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating appointment: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=AppointmentListResponse)
async def list_appointments(
    lead_id: Optional[int] = Query(None, description="Filter by lead ID"),
    agent_id: Optional[int] = Query(None, description="Filter by agent ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    start_date: Optional[date] = Query(None, description="Filter appointments from this date"),
    end_date: Optional[date] = Query(None, description="Filter appointments until this date"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List appointments with filters"""
    
    try:
        query = select(Appointment)
        
        # Apply filters
        if lead_id:
            query = query.where(Appointment.lead_id == lead_id)
        
        if agent_id:
            query = query.where(Appointment.agent_id == agent_id)
        
        if status:
            try:
                status_enum = AppointmentStatus(status)
                query = query.where(Appointment.status == status_enum)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        
        if start_date:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            query = query.where(Appointment.start_time >= start_datetime)
        
        if end_date:
            end_datetime = datetime.combine(end_date, datetime.max.time())
            query = query.where(Appointment.start_time <= end_datetime)
        
        # Get total count (before pagination) - apply same filters
        count_query = select(func.count(Appointment.id))
        
        if lead_id:
            count_query = count_query.where(Appointment.lead_id == lead_id)
        if agent_id:
            count_query = count_query.where(Appointment.agent_id == agent_id)
        if status:
            try:
                status_enum = AppointmentStatus(status)
                count_query = count_query.where(Appointment.status == status_enum)
            except ValueError:
                pass
        if start_date:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            count_query = count_query.where(Appointment.start_time >= start_datetime)
        if end_date:
            end_datetime = datetime.combine(end_date, datetime.max.time())
            count_query = count_query.where(Appointment.start_time <= end_datetime)
        
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Apply pagination and ordering
        query = query.order_by(desc(Appointment.start_time)).offset(skip).limit(limit)
        
        result = await db.execute(query)
        appointments = result.scalars().all()
        
        return AppointmentListResponse(
            data=[AppointmentResponse.model_validate(apt) for apt in appointments],
            total=total,
            skip=skip,
            limit=limit
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing appointments: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{appointment_id}", response_model=AppointmentDetailResponse)
async def get_appointment(
    appointment_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get appointment details"""
    
    result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    appointment = result.scalars().first()
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    # Get lead info
    lead_result = await db.execute(
        select(Lead).where(Lead.id == appointment.lead_id)
    )
    lead = lead_result.scalars().first()
    
    # Get agent info if assigned
    agent_name = None
    if appointment.agent_id:
        agent_result = await db.execute(
            select(User).where(User.id == appointment.agent_id)
        )
        agent = agent_result.scalars().first()
        if agent:
            agent_name = agent.broker_name
    
    appointment_dict = AppointmentResponse.model_validate(appointment).model_dump()
    return AppointmentDetailResponse(
        **appointment_dict,
        lead_name=lead.name if lead else None,
        lead_phone=lead.phone if lead else None,
        agent_name=agent_name
    )


@router.put("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: int,
    appointment_update: AppointmentUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update an appointment"""
    
    try:
        # Use service method to handle update and Google Calendar sync
        appointment = await AppointmentService.update_appointment(
            db=db,
            appointment_id=appointment_id,
            update_data=appointment_update
        )
        
        return appointment
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating appointment: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{appointment_id}/confirm", response_model=AppointmentResponse)
async def confirm_appointment(
    appointment_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Confirm an appointment"""
    
    try:
        appointment = await AppointmentService.confirm_appointment(db, appointment_id)
        return appointment
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{appointment_id}/cancel", response_model=AppointmentResponse)
async def cancel_appointment(
    appointment_id: int,
    reason: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Cancel an appointment"""
    
    try:
        appointment = await AppointmentService.cancel_appointment(db, appointment_id, reason)
        return appointment
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/available/slots", response_model=List[AvailableSlotResponse])
async def get_available_slots(
    start_date: date = Query(..., description="Start date for availability"),
    end_date: Optional[date] = Query(None, description="End date (defaults to start_date + 14 days)"),
    agent_id: Optional[int] = Query(None, description="Filter by agent ID"),
    appointment_type: Optional[str] = Query(None, description="Filter by appointment type"),
    duration_minutes: int = Query(60, ge=15, le=480, description="Duration in minutes"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get available time slots"""
    
    try:
        # Default end_date to 14 days from start_date
        if not end_date:
            end_date = start_date + timedelta(days=14)
        
        # Validate appointment_type
        apt_type = None
        if appointment_type:
            try:
                apt_type = AppointmentTypeEnum(appointment_type)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid appointment type: {appointment_type}")
        
        slots = await AppointmentService.get_available_slots(
            db=db,
            start_date=start_date,
            end_date=end_date,
            agent_id=agent_id,
            appointment_type=apt_type,
            duration_minutes=duration_minutes
        )
        
        return [AvailableSlotResponse(**slot) for slot in slots]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting available slots: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
