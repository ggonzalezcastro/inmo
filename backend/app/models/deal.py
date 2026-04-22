"""
Deal — enlace entre un Lead y una unidad (Property) en proceso de compra.

Cycle: draft → reserva → docs_pendientes → en_aprobacion_bancaria
       → promesa_redaccion → promesa_firmada → escritura_firmada
       ↘ cancelado (desde cualquier etapa)
"""
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, IdMixin, TimestampMixin

DEAL_STAGES = [
    "draft",
    "reserva",
    "docs_pendientes",
    "en_aprobacion_bancaria",
    "promesa_redaccion",
    "promesa_firmada",
    "escritura_firmada",
    "cancelado",
]

DELIVERY_TYPES = [
    "inmediata",
    "futura",
    "desconocida",
]


class Deal(Base, IdMixin, TimestampMixin):
    """Deal linking a Lead to a Property unit in the purchase process."""

    __tablename__ = "deals"

    # ── Tenancy ───────────────────────────────────────────────────────────────
    broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Core FKs ──────────────────────────────────────────────────────────────
    lead_id = Column(
        Integer,
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    property_id = Column(
        Integer,
        ForeignKey("properties.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Stage & delivery ──────────────────────────────────────────────────────
    stage = Column(String(50), nullable=False, default="draft")
    delivery_type = Column(String(20), nullable=False, default="desconocida")

    # ── Bank review ───────────────────────────────────────────────────────────
    bank_review_status = Column(String(20), nullable=True)
    # pendiente | en_revision | aprobado | rechazado

    # ── Jefatura review (only relevant for futura delivery) ───────────────────
    jefatura_review_required = Column(Boolean, nullable=False, default=False)
    jefatura_review_status = Column(String(20), nullable=True)
    # pendiente | aprobado | rechazado
    jefatura_review_notes = Column(Text, nullable=True)

    # ── Stage timestamps ──────────────────────────────────────────────────────
    reserva_at = Column(DateTime(timezone=True), nullable=True)
    docs_completos_at = Column(DateTime(timezone=True), nullable=True)
    bank_decision_at = Column(DateTime(timezone=True), nullable=True)
    promesa_signed_at = Column(DateTime(timezone=True), nullable=True)
    escritura_signed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    # ── Cancellation ──────────────────────────────────────────────────────────
    cancellation_reason = Column(String(100), nullable=True)
    cancellation_notes = Column(Text, nullable=True)

    # ── Planning ──────────────────────────────────────────────────────────────
    escritura_planned_date = Column(Date, nullable=True)

    # ── Metadata ──────────────────────────────────────────────────────────────
    deal_metadata = Column("metadata", JSONB, nullable=False, default={})

    # ── Relationships ─────────────────────────────────────────────────────────
    broker = relationship("Broker", foreign_keys=[broker_id])
    lead = relationship("Lead", back_populates="deals")
    property = relationship("Property", back_populates="deals")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    documents = relationship(
        "DealDocument",
        back_populates="deal",
        cascade="all, delete-orphan",
    )

    # ── Indices ───────────────────────────────────────────────────────────────
    __table_args__ = (
        Index("idx_deal_broker_lead", "broker_id", "lead_id"),
        Index("idx_deal_broker_property", "broker_id", "property_id"),
        Index("idx_deal_stage", "broker_id", "stage"),
        # Enforce at most one active (non-cancelled) deal per property per broker
        Index(
            "uq_deal_active_property",
            "broker_id",
            "property_id",
            unique=True,
            postgresql_where="stage != 'cancelado'",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Deal id={self.id} broker_id={self.broker_id} "
            f"lead_id={self.lead_id} property_id={self.property_id} stage={self.stage}>"
        )
