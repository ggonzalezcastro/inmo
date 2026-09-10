"""
Broker payment configuration for Transbank Webpay Plus.

One row per broker holding that broker's own commerce credentials, so each
broker collects money into its own Transbank account (multi-tenant).

The API key is stored encrypted (Fernet, via app.core.encryption). Phase 1
forces `environment` to integration platform-wide; phase 2 enables production
per broker by setting environment="production" and TRANSBANK_FORCE_INTEGRATION=false.
"""
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, IdMixin, TimestampMixin


class BrokerPaymentConfig(Base, IdMixin, TimestampMixin):
    """Transbank payment configuration for a broker."""

    __tablename__ = "broker_payment_configs"

    broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    provider = Column(String(50), nullable=False, default="transbank")
    # integration | production  (phase 1: always treated as integration)
    environment = Column(String(20), nullable=False, default="integration")
    enabled = Column(Boolean, nullable=False, default=False)

    commerce_code = Column(String(64), nullable=True)
    # Fernet-encrypted ("enc:..." prefix) — never expose in API responses.
    api_key_encrypted = Column(Text, nullable=True)

    broker = relationship("Broker", back_populates="payment_config")

    def __repr__(self) -> str:
        return (
            f"<BrokerPaymentConfig broker_id={self.broker_id} "
            f"environment={self.environment} enabled={self.enabled}>"
        )
