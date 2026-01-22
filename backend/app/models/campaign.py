"""
Campaign models for multi-channel marketing automation
"""
from datetime import datetime
from enum import Enum
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, 
    ForeignKey, JSON, Index, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from app.models.base import Base, IdMixin, TimestampMixin


class CampaignChannel(str, Enum):
    """Communication channel for campaign"""
    TELEGRAM = "telegram"
    CALL = "call"
    WHATSAPP = "whatsapp"
    EMAIL = "email"


class CampaignStatus(str, Enum):
    """Status of a campaign"""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class CampaignTrigger(str, Enum):
    """What triggers a campaign"""
    MANUAL = "manual"
    LEAD_SCORE = "lead_score"
    STAGE_CHANGE = "stage_change"
    INACTIVITY = "inactivity"


class CampaignStepAction(str, Enum):
    """Action to perform in a campaign step"""
    SEND_MESSAGE = "send_message"
    MAKE_CALL = "make_call"
    SCHEDULE_MEETING = "schedule_meeting"
    UPDATE_STAGE = "update_stage"


class CampaignLogStatus(str, Enum):
    """Status of a campaign step execution"""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class Campaign(Base, IdMixin, TimestampMixin):
    """
    Campaign model for multi-channel marketing automation
    
    Campaigns can be triggered automatically based on lead conditions
    or manually applied to specific leads.
    """
    
    __tablename__ = "campaigns"
    
    # Basic info
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Channel configuration
    channel = Column(
        SQLEnum(CampaignChannel),
        nullable=False,
        index=True
    )
    
    # Status and control
    status = Column(
        SQLEnum(CampaignStatus),
        default=CampaignStatus.DRAFT,
        nullable=False,
        index=True
    )
    
    # Trigger configuration
    triggered_by = Column(
        SQLEnum(CampaignTrigger),
        default=CampaignTrigger.MANUAL,
        nullable=False,
        index=True
    )
    
    # Trigger conditions (JSON)
    # Examples:
    # - {"score_min": 20, "score_max": 50} for lead_score trigger
    # - {"stage": "perfilamiento"} for stage_change trigger
    # - {"inactivity_days": 30} for inactivity trigger
    trigger_condition = Column(JSON, nullable=True, default={})
    
    # Limits
    max_contacts = Column(Integer, nullable=True)  # NULL = unlimited
    
    # Multi-tenancy
    broker_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Relationships
    broker = relationship("User", foreign_keys=[broker_id])
    steps = relationship("CampaignStep", back_populates="campaign", cascade="all, delete-orphan", order_by="CampaignStep.step_number")
    logs = relationship("CampaignLog", back_populates="campaign", cascade="all, delete-orphan")
    
    # Indices
    __table_args__ = (
        Index('idx_campaign_broker_status', 'broker_id', 'status'),
        Index('idx_campaign_trigger', 'triggered_by', 'status'),
    )
    
    def __repr__(self):
        return f"<Campaign id={self.id} name={self.name} channel={self.channel} status={self.status}>"


class CampaignStep(Base, IdMixin, TimestampMixin):
    """
    Step within a campaign
    
    Campaigns can have multiple steps that execute sequentially
    with configurable delays between steps.
    """
    
    __tablename__ = "campaign_steps"
    
    # Campaign reference
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Step order
    step_number = Column(Integer, nullable=False)  # 1, 2, 3, etc.
    
    # Action to perform
    action = Column(
        SQLEnum(CampaignStepAction),
        nullable=False
    )
    
    # Template reference (if action is send_message)
    message_template_id = Column(Integer, ForeignKey("message_templates.id", ondelete="SET NULL"), nullable=True)
    
    # Delay before executing this step (hours)
    delay_hours = Column(Integer, default=0, nullable=False)
    
    # Conditions to execute this step (JSON)
    # Example: {"if_response": "yes", "if_no_response": true}
    conditions = Column(JSON, nullable=True, default={})
    
    # Target stage to move lead to (if action is update_stage)
    target_stage = Column(String(50), nullable=True)
    
    # Relationships
    campaign = relationship("Campaign", back_populates="steps")
    message_template = relationship("MessageTemplate", foreign_keys=[message_template_id])
    
    # Indices
    __table_args__ = (
        Index('idx_campaign_step_order', 'campaign_id', 'step_number'),
    )
    
    def __repr__(self):
        return f"<CampaignStep id={self.id} campaign_id={self.campaign_id} step={self.step_number} action={self.action}>"


class CampaignLog(Base, IdMixin):
    """
    Log of campaign execution for audit trail
    
    Tracks which campaigns were applied to which leads,
    when each step was executed, and the results.
    """
    
    __tablename__ = "campaign_logs"
    
    # References
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Step information
    step_number = Column(Integer, nullable=False)  # Which step was executed
    
    # Execution status
    status = Column(
        SQLEnum(CampaignLogStatus),
        default=CampaignLogStatus.PENDING,
        nullable=False,
        index=True
    )
    
    # Response/result data (JSON)
    # Contains webhook response, error messages, or execution results
    response = Column(JSON, nullable=True, default={})
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default="now()", nullable=False, index=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)  # When step actually executed
    
    # Relationships
    campaign = relationship("Campaign", back_populates="logs")
    lead = relationship("Lead")
    
    # Indices
    __table_args__ = (
        Index('idx_campaign_log_lead', 'lead_id', 'status'),
        Index('idx_campaign_log_campaign_lead', 'campaign_id', 'lead_id'),
        Index('idx_campaign_log_created', 'created_at'),
    )
    
    def __repr__(self):
        return f"<CampaignLog id={self.id} campaign_id={self.campaign_id} lead_id={self.lead_id} step={self.step_number} status={self.status}>"



