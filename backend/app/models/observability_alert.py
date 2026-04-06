"""
ObservabilityAlert — system-generated alerts for the super admin dashboard.

Alerts are evaluated by a Celery Beat task and broadcast via WebSocket
to the admin dashboard. Admins can acknowledge, resolve, or dismiss them.

Alert types:
  - high_cost_spike: LLM spend > 2x historical hourly average
  - high_escalation_rate: >20% escalation in last 2h
  - provider_failover: LLM fallback triggered
  - human_mode_stale: lead in human_mode >30 min without response
  - error_spike: >5 errors in last 30 min
  - slow_response: avg latency >5s in last 30 min
  - handoff_loop: A→B→A loop detected
  - sentiment_cluster: ≥3 escalations in last hour
"""
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql.functions import now

from app.models.base import Base, IdMixin


class ObservabilityAlert(Base, IdMixin):
    """System alert tracked for the super admin observability dashboard."""

    __tablename__ = "observability_alerts"

    # ── Classification ────────────────────────────────────────────────────────
    alert_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    # 'info', 'warning', 'critical'
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # ── Context ───────────────────────────────────────────────────────────────
    related_lead_id = Column(
        Integer,
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
    )
    related_broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    status = Column(String(20), nullable=False, default="active")
    # 'active', 'acknowledged', 'resolved', 'dismissed'
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # ── Payload ───────────────────────────────────────────────────────────────
    alert_data = Column(JSONB, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=now(),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    acknowledger = relationship("User", foreign_keys=[acknowledged_by])

    __table_args__ = (
        Index("idx_alerts_status", "status", "created_at"),
        Index("idx_alerts_severity", "severity", "status"),
        Index("idx_alerts_broker", "related_broker_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<ObservabilityAlert id={self.id} type={self.alert_type} "
            f"severity={self.severity} status={self.status}>"
        )
