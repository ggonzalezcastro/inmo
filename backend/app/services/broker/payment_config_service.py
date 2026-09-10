"""
Broker payment (Transbank) configuration service.

Resolves the Transbank credentials to use for a broker, with a fallback to the
shared integration credentials from settings when the broker has not configured
its own. The broker's API key is stored encrypted; this service decrypts it on read
and encrypts on write.

Phase 1: environment is always forced to "integration" (settings.TRANSBANK_FORCE_INTEGRATION).
"""
import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.core.encryption import decrypt_value, encrypt_value
from app.models.broker_payment_config import BrokerPaymentConfig

logger = logging.getLogger(__name__)


@dataclass
class TransbankCredentials:
    commerce_code: str
    api_key: str
    environment: str  # "integration" | "production"
    source: str       # "broker" | "default"


class BrokerPaymentConfigService:
    """Transbank credentials + config per broker."""

    @staticmethod
    async def get_config(
        db: AsyncSession, broker_id: int
    ) -> Optional[BrokerPaymentConfig]:
        result = await db.execute(
            select(BrokerPaymentConfig).where(
                BrokerPaymentConfig.broker_id == broker_id
            )
        )
        return result.scalars().first()

    @staticmethod
    async def get_credentials(db: AsyncSession, broker_id: int) -> TransbankCredentials:
        """
        Resolve the Transbank credentials for a broker.

        Uses the broker's own commerce_code + decrypted api_key when configured
        and enabled; otherwise falls back to the shared integration credentials.
        Environment is forced to integration while TRANSBANK_FORCE_INTEGRATION is on.
        """
        row = await BrokerPaymentConfigService.get_config(db, broker_id)

        if row and row.enabled and row.commerce_code and row.api_key_encrypted:
            api_key = decrypt_value(row.api_key_encrypted)
            environment = row.environment or "integration"
            commerce_code = row.commerce_code
            source = "broker"
        else:
            commerce_code = settings.TRANSBANK_DEFAULT_COMMERCE_CODE
            api_key = settings.TRANSBANK_DEFAULT_API_KEY
            environment = "integration"
            source = "default"

        if getattr(settings, "TRANSBANK_FORCE_INTEGRATION", True):
            environment = "integration"

        return TransbankCredentials(
            commerce_code=commerce_code,
            api_key=api_key,
            environment=environment,
            source=source,
        )

    @staticmethod
    async def upsert_config(
        db: AsyncSession,
        broker_id: int,
        *,
        commerce_code: Optional[str] = None,
        api_key: Optional[str] = None,
        environment: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> BrokerPaymentConfig:
        """
        Create or update the broker's payment config. Encrypts api_key when provided.
        A None field is left unchanged (except on first create where defaults apply).
        Does NOT commit — caller commits.
        """
        row = await BrokerPaymentConfigService.get_config(db, broker_id)
        if row is None:
            row = BrokerPaymentConfig(broker_id=broker_id, provider="transbank")
            db.add(row)

        if commerce_code is not None:
            row.commerce_code = commerce_code.strip() or None
        if api_key is not None:
            # Empty string clears the stored key.
            row.api_key_encrypted = encrypt_value(api_key) if api_key.strip() else None
        if environment is not None:
            row.environment = environment
        if enabled is not None:
            row.enabled = enabled

        await db.flush()
        return row
