"""
Message template models for campaign messaging
"""
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship
from app.models.base import Base, IdMixin, TimestampMixin


class TemplateChannel(str, Enum):
    """Communication channel for template"""
    TELEGRAM = "telegram"
    CALL = "call"
    EMAIL = "email"
    WHATSAPP = "whatsapp"


class AgentType(str, Enum):
    """Type of AI agent using the template"""
    PERFILADOR = "perfilador"
    CALIFICADOR_FINANCIERO = "calificador_financiero"
    AGENDADOR = "agendador"
    SEGUIMIENTO = "seguimiento"


class MessageTemplate(Base, IdMixin, TimestampMixin):
    """
    Message template for reusable campaign messages
    
    Templates support variable substitution like {{name}}, {{budget}}, etc.
    Variables are auto-extracted from template content for validation.
    """
    
    __tablename__ = "message_templates"
    
    # Basic info
    name = Column(String(200), nullable=False)
    
    # Channel configuration
    channel = Column(
        SQLEnum(TemplateChannel),
        nullable=False,
        index=True
    )
    
    # Template content with variables
    # Example: "Hola {{name}}, queremos mostrarte propiedades en {{location}} dentro de tu presupuesto de {{budget}}"
    content = Column(Text, nullable=False)
    
    # Agent type that uses this template
    agent_type = Column(
        SQLEnum(AgentType),
        nullable=True,  # Can be null for generic templates
        index=True
    )
    
    # List of variables in template (auto-extracted or manual)
    # Example: ["name", "location", "budget"]
    variables = Column(JSON, default=[], nullable=False)
    
    # Multi-tenancy
    broker_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Relationships
    broker = relationship("User", foreign_keys=[broker_id])
    campaign_steps = relationship("CampaignStep", back_populates="message_template", foreign_keys="CampaignStep.message_template_id")
    
    # Indices
    __table_args__ = (
        Index('idx_template_broker_channel', 'broker_id', 'channel'),
        Index('idx_template_agent_type', 'agent_type', 'channel'),
    )
    
    def __repr__(self):
        return f"<MessageTemplate id={self.id} name={self.name} channel={self.channel} agent_type={self.agent_type}>"

