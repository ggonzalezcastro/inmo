"""
Payment — a Transbank Webpay Plus payment for a Deal reservation.

Each payment represents one Webpay transaction attempt for a deal. An approved
payment (status="approved") stands in for the manual comprobante_transferencia
document and unblocks the draft → reserva transition.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, IdMixin, TimestampMixin

# created   — transaction created at Transbank, buyer has not paid yet
# pending   — buyer opened the pay link (redirected to Webpay)
# approved  — commit returned response_code 0 / AUTHORIZED
# failed    — commit returned a non-approved result
# aborted   — buyer cancelled at Webpay (TBK_TOKEN returned, no commit)
# cancelled — voided by the agent, or superseded when a new link was generated
# error     — SDK/transport error during create or commit
PAYMENT_STATUSES = ["created", "pending", "approved", "failed", "aborted", "cancelled", "error"]


class Payment(Base, IdMixin, TimestampMixin):
    """A Transbank Webpay Plus payment tied to a Deal."""

    __tablename__ = "payments"

    # ── Tenancy ───────────────────────────────────────────────────────────────
    broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Core FKs ──────────────────────────────────────────────────────────────
    deal_id = Column(
        Integer,
        ForeignKey("deals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Provider ──────────────────────────────────────────────────────────────
    provider = Column(String(30), nullable=False, default="transbank")
    environment = Column(String(20), nullable=False, default="integration")

    # ── Webpay transaction identity ───────────────────────────────────────────
    # buy_order max 26 chars at Transbank; must be unique per commerce.
    buy_order = Column(String(26), nullable=False, unique=True, index=True)
    session_id = Column(String(61), nullable=True)
    amount = Column(Integer, nullable=False)  # CLP, no decimals

    token = Column(String(128), nullable=True, index=True)  # token_ws
    webpay_url = Column(String(255), nullable=True)  # redirect target for the form

    status = Column(String(20), nullable=False, default="created")

    # ── Commit result ─────────────────────────────────────────────────────────
    response_code = Column(Integer, nullable=True)
    authorization_code = Column(String(20), nullable=True)
    payment_type_code = Column(String(10), nullable=True)
    installments_number = Column(Integer, nullable=True)
    card_last4 = Column(String(4), nullable=True)
    transaction_date = Column(String(40), nullable=True)  # ISO string from Transbank

    raw_response = Column(JSONB, nullable=True)  # full commit payload for audit

    committed_at = Column(DateTime(timezone=True), nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    broker = relationship("Broker", foreign_keys=[broker_id])
    deal = relationship("Deal", back_populates="payments")
    created_by = relationship("User", foreign_keys=[created_by_user_id])

    def __repr__(self) -> str:
        return (
            f"<Payment id={self.id} deal_id={self.deal_id} "
            f"buy_order={self.buy_order} amount={self.amount} status={self.status}>"
        )
