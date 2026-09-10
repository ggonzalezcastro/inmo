"""Internal lead notes and executive follow-up tasks."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base, IdMixin, TimestampMixin


TASK_STATUS_OPEN = "open"
TASK_STATUS_IN_PROGRESS = "in_progress"
TASK_STATUS_COMPLETED = "completed"
TASK_ACTIVE_STATUSES = (TASK_STATUS_OPEN, TASK_STATUS_IN_PROGRESS)
TASK_STATUSES = (*TASK_ACTIVE_STATUSES, TASK_STATUS_COMPLETED)
REMINDER_OFFSETS_MINUTES = (0, 15, 60, 1440)
ADVISORY_CHANNELS = (
    "whatsapp",
    "phone",
    "video_call",
    "property_visit",
    "in_person",
    "other",
)


class LeadNote(Base, IdMixin):
    """Append-only internal note attached to a lead."""

    __tablename__ = "lead_notes"

    broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id = Column(
        Integer,
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    body = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    lead = relationship("Lead", back_populates="internal_notes")
    author = relationship("User", foreign_keys=[author_id])

    __table_args__ = (
        Index("ix_lead_notes_broker_lead_created", "broker_id", "lead_id", "created_at"),
    )


class LeadAdvisory(Base, IdMixin, TimestampMixin):
    """Immutable record of a verified commercial advisory interaction."""

    __tablename__ = "lead_advisories"

    broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id = Column(
        Integer,
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    advisor_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    recorded_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    channel = Column(String(30), nullable=False, index=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False, index=True)
    notes = Column(Text, nullable=True)

    lead = relationship("Lead", back_populates="advisories")
    advisor = relationship("User", foreign_keys=[advisor_id])
    recorder = relationship("User", foreign_keys=[recorded_by])

    __table_args__ = (
        CheckConstraint(
            "channel IN ('whatsapp', 'phone', 'video_call', "
            "'property_visit', 'in_person', 'other')",
            name="ck_lead_advisories_channel",
        ),
        Index(
            "ix_lead_advisories_broker_advisor_occurred",
            "broker_id",
            "advisor_id",
            "occurred_at",
        ),
        Index(
            "ix_lead_advisories_broker_lead_occurred",
            "broker_id",
            "lead_id",
            "occurred_at",
        ),
    )


class LeadTask(Base, IdMixin, TimestampMixin):
    """One-time follow-up task assigned to an executive."""

    __tablename__ = "lead_tasks"

    broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id = Column(
        Integer,
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(200), nullable=False)
    status = Column(
        String(20),
        nullable=False,
        default=TASK_STATUS_OPEN,
        server_default=TASK_STATUS_OPEN,
        index=True,
    )
    assigned_to = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    completed_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    due_at = Column(DateTime(timezone=True), nullable=False, index=True)
    reminder_minutes_before = Column(Integer, nullable=True, default=60)
    reminder_at = Column(DateTime(timezone=True), nullable=True, index=True)
    reminder_sent_at = Column(DateTime(timezone=True), nullable=True)
    reminder_acknowledged_at = Column(DateTime(timezone=True), nullable=True, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    lead = relationship("Lead", back_populates="follow_up_tasks")
    assignee = relationship("User", foreign_keys=[assigned_to])
    creator = relationship("User", foreign_keys=[created_by])
    completer = relationship("User", foreign_keys=[completed_by])

    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'in_progress', 'completed')",
            name="ck_lead_tasks_status",
        ),
        CheckConstraint(
            "reminder_minutes_before IS NULL OR "
            "reminder_minutes_before IN (0, 15, 60, 1440)",
            name="ck_lead_tasks_reminder_offset",
        ),
        Index(
            "ix_lead_tasks_assignee_status_due",
            "broker_id",
            "assigned_to",
            "status",
            "due_at",
        ),
        Index(
            "ix_lead_tasks_pending_reminders",
            "status",
            "reminder_acknowledged_at",
            "reminder_at",
        ),
    )
