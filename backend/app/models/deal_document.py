"""
DealDocument — archivo adjunto a un Deal (reserva/promesa/escritura).

Cada documento ocupa un "slot" tipado dentro del workflow del deal.
Workflow: pendiente → recibido → aprobado | rechazado
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, IdMixin, TimestampMixin

DOCUMENT_STATUSES = ["pendiente", "recibido", "aprobado", "rechazado"]


class DealDocument(Base, IdMixin, TimestampMixin):
    """Document attached to a Deal, occupying a typed slot in the workflow."""

    __tablename__ = "deal_documents"

    # ── Core FK ───────────────────────────────────────────────────────────────
    deal_id = Column(
        Integer,
        ForeignKey("deals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Slot identity ─────────────────────────────────────────────────────────
    slot = Column(String(50), nullable=False)
    # e.g. "ci_anverso", "liquidacion_sueldo" — matches SLOT_DEFINITIONS keys
    slot_index = Column(Integer, nullable=False, default=0)
    # for multi-instance slots (e.g. 3 liquidaciones: index 0, 1, 2)
    co_titular_index = Column(Integer, nullable=False, default=0)
    # 0 = titular, 1+ = co-titulares

    # ── Status ────────────────────────────────────────────────────────────────
    status = Column(String(20), nullable=False, default="pendiente")

    # ── File metadata ─────────────────────────────────────────────────────────
    storage_key = Column(String(500), nullable=True)
    original_filename = Column(String(255), nullable=True)
    mime_type = Column(String(100), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    sha256 = Column(String(64), nullable=True)

    # ── Upload tracking ───────────────────────────────────────────────────────
    uploaded_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    uploaded_by_ai = Column(Boolean, nullable=False, default=False)
    uploaded_at = Column(DateTime(timezone=True), nullable=True)

    # ── Review tracking ───────────────────────────────────────────────────────
    reviewed_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_notes = Column(Text, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    deal = relationship("Deal", back_populates="documents")
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_user_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_user_id])

    # ── Indices ───────────────────────────────────────────────────────────────
    __table_args__ = (
        Index("idx_dealdoc_deal_slot", "deal_id", "slot", "slot_index", "co_titular_index"),
        Index("idx_dealdoc_status", "deal_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<DealDocument id={self.id} deal_id={self.deal_id} "
            f"slot={self.slot!r} status={self.status}>"
        )
