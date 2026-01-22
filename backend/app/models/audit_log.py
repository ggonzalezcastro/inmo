"""
Audit log model for tracking changes
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from app.models.base import Base, IdMixin

# Note: Not using TimestampMixin to use our own timestamp field


class AuditLog(Base, IdMixin):
    """
    Audit log for tracking all changes made by users
    
    Records who did what, when, and what changed (before/after)
    """
    
    __tablename__ = "audit_logs"
    
    # User who made the change
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Action type
    action = Column(String(50), nullable=False, index=True)  # "create", "update", "delete", "apply_campaign", etc.
    
    # Resource information
    resource_type = Column(String(50), nullable=False, index=True)  # "campaign", "lead", "template", etc.
    resource_id = Column(Integer, nullable=False, index=True)
    
    # Changes (JSON with before/after)
    changes = Column(JSON, nullable=True, default={})
    
    # Additional context
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(String(255), nullable=True)
    
    # Timestamp
    timestamp = Column(DateTime(timezone=True), server_default="now()", nullable=False, index=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    
    # Indices
    __table_args__ = (
        Index('idx_audit_user_action', 'user_id', 'action'),
        Index('idx_audit_resource', 'resource_type', 'resource_id'),
        Index('idx_audit_timestamp', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<AuditLog id={self.id} action={self.action} resource={self.resource_type}:{self.resource_id}>"



