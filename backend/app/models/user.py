from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.models.base import Base, IdMixin, TimestampMixin
import enum


class UserRole(str, enum.Enum):
    """User roles in the system"""
    SUPERADMIN = "SUPERADMIN"  # Admin del sistema completo
    ADMIN = "ADMIN"            # Admin del broker
    AGENT = "AGENT"            # Agente inmobiliario


class User(Base, IdMixin, TimestampMixin):
    """User model for brokers"""
    
    __tablename__ = "users"
    
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)  # Renombrado de broker_name a name
    
    # Rol del usuario
    role = Column(SQLEnum(UserRole), default=UserRole.AGENT, nullable=False)
    
    # Broker al que pertenece (NULL para superadmin)
    broker_id = Column(Integer, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=True, index=True)
    
    is_active = Column(Boolean, default=True, nullable=False)

    # Google Calendar — per-agent calendar (shared with service account)
    google_calendar_id = Column(String(255), nullable=True)        # email del calendario (ej: juan@gmail.com)
    google_calendar_connected = Column(Boolean, default=False, nullable=False)  # incluir en round-robin

    # Google Calendar — per-agent OAuth (token personal del agente)
    google_refresh_token = Column(String, nullable=True)           # encriptado con encrypt_value()
    google_calendar_email = Column(String(255), nullable=True)     # email de la cuenta conectada

    # Outlook Calendar — per-agent OAuth
    outlook_refresh_token = Column(String, nullable=True)          # encriptado con encrypt_value()
    outlook_calendar_id = Column(String(500), nullable=True)       # Graph calendar ID
    outlook_calendar_email = Column(String(255), nullable=True)    # Cuenta Outlook conectada
    outlook_calendar_connected = Column(Boolean, default=False, nullable=False)

    # Relationships
    broker = relationship("Broker", back_populates="users", foreign_keys=[broker_id])
    
    appointments = relationship(
        "Appointment",
        back_populates="agent",
        cascade="all, delete-orphan"
    )
    availability_slots = relationship(
        "AvailabilitySlot",
        back_populates="agent",
        cascade="all, delete-orphan"
    )
    appointment_blocks = relationship(
        "AppointmentBlock",
        back_populates="agent",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<User id={self.id} email={self.email} role={self.role.value}>"

