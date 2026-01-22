from datetime import datetime
from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base, IdMixin


class ActivityLog(Base, IdMixin):
    """Track all lead activities"""
    
    __tablename__ = "activity_log"
    
    # Foreign key
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Action type
    action_type = Column(
        String(50),  # message, call, score_update, status_change
        nullable=False,
        index=True
    )
    
    # Details as JSON
    details = Column(JSON, default={}, nullable=False)
    
    # Timestamp
    timestamp = Column(
        DateTime(timezone=True),
        server_default="now()",
        nullable=False,
        index=True
    )
    
    # Relationship
    lead = relationship("Lead", back_populates="activities")
    
    def __repr__(self):
        return f"<ActivityLog id={self.id} lead_id={self.lead_id} action={self.action_type}>"

