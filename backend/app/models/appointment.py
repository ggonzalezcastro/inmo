from datetime import datetime, time, date
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Time, Date, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship
from app.models.base import Base, IdMixin, TimestampMixin


class AppointmentStatus(str, Enum):
    """Status of an appointment"""
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class AppointmentType(str, Enum):
    """Type of appointment"""
    PROPERTY_VISIT = "property_visit"  # Visita a propiedad
    VIRTUAL_MEETING = "virtual_meeting"  # Reunión virtual
    PHONE_CALL = "phone_call"  # Llamada telefónica
    OFFICE_MEETING = "office_meeting"  # Reunión en oficina
    OTHER = "other"


class Appointment(Base, IdMixin, TimestampMixin):
    """Appointment model for scheduling property visits and meetings"""
    
    __tablename__ = "appointments"
    
    # Foreign keys
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Appointment details
    appointment_type = Column(
        SQLEnum(AppointmentType),
        default=AppointmentType.PROPERTY_VISIT,
        nullable=False
    )
    status = Column(
        SQLEnum(AppointmentStatus),
        default=AppointmentStatus.SCHEDULED,
        nullable=False,
        index=True
    )
    
    # Time
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=False)
    duration_minutes = Column(Integer, nullable=False, default=60)  # Default 1 hour
    
    # Location
    location = Column(String(500), nullable=True)  # Physical address or virtual link
    property_address = Column(String(500), nullable=True)  # If visiting a property
    meet_url = Column(String(500), nullable=True)  # Google Meet URL for online appointments
    google_event_id = Column(String(255), nullable=True, index=True)  # Google Calendar event ID
    
    # Notes
    notes = Column(Text, nullable=True)
    lead_notes = Column(Text, nullable=True)  # Notes from the lead
    
    # Reminders
    reminder_sent_24h = Column(Boolean, default=False, nullable=False)
    reminder_sent_1h = Column(Boolean, default=False, nullable=False)
    
    # Cancellation
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    
    # Relationships
    lead = relationship("Lead", back_populates="appointments")
    agent = relationship("User", back_populates="appointments")
    
    # Indices
    __table_args__ = (
        Index('idx_appointment_datetime', 'start_time', 'end_time'),
        Index('idx_appointment_lead_status', 'lead_id', 'status'),
        Index('idx_appointment_agent_status', 'agent_id', 'status'),
    )
    
    def __repr__(self):
        return f"<Appointment id={self.id} lead_id={self.lead_id} start={self.start_time}>"


class AvailabilitySlot(Base, IdMixin, TimestampMixin):
    """Recurring availability slots for agents"""
    
    __tablename__ = "availability_slots"
    
    # Foreign key
    agent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    # NULL = applies to all agents
    
    # Day and time
    day_of_week = Column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    
    # Validity period
    valid_from = Column(Date, nullable=False, default=date.today)
    valid_until = Column(Date, nullable=True)  # NULL = indefinitely
    
    # Appointment type this slot is for
    appointment_type = Column(
        SQLEnum(AppointmentType),
        nullable=True  # NULL = all types
    )
    
    # Slot configuration
    slot_duration_minutes = Column(Integer, nullable=False, default=60)
    max_appointments_per_slot = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Relationships
    agent = relationship("User", foreign_keys=[agent_id], back_populates="availability_slots")
    
    def __repr__(self):
        return f"<AvailabilitySlot id={self.id} agent_id={self.agent_id} day={self.day_of_week}>"


class AppointmentBlock(Base, IdMixin, TimestampMixin):
    """Blocked time periods (vacations, meetings, etc.)"""
    
    __tablename__ = "appointment_blocks"
    
    # Foreign key
    agent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    # NULL = applies to all agents
    
    # Block period
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=False)
    
    # Recurring block
    is_recurring = Column(Boolean, default=False, nullable=False)
    recurrence_pattern = Column(String(100), nullable=True)  # e.g., "daily", "weekly", "monthly"
    recurrence_end_date = Column(Date, nullable=True)
    
    # Reason
    reason = Column(String(200), nullable=False)  # "vacation", "internal_meeting", etc.
    notes = Column(Text, nullable=True)
    
    # Relationships
    agent = relationship("User", foreign_keys=[agent_id], back_populates="appointment_blocks")
    
    # Indices
    __table_args__ = (
        Index('idx_block_datetime', 'start_time', 'end_time'),
    )
    
    def __repr__(self):
        return f"<AppointmentBlock id={self.id} agent_id={self.agent_id} start={self.start_time}>"

