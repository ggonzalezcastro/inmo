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

