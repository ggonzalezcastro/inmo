"""
TransbankService — thin wrapper over the Transbank Webpay Plus SDK.

Instantiated per broker via `TransbankService.for_broker(db, broker_id)`, which
loads that broker's credentials (or the shared integration fallback). The blocking
SDK calls (HTTP under the hood) are run in a thread so they don't block the event loop.
"""
import asyncio
import logging
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from transbank.error.transbank_error import TransbankError
from transbank.webpay.webpay_plus.transaction import Transaction

from app.services.broker.payment_config_service import (
    BrokerPaymentConfigService,
    TransbankCredentials,
)

logger = logging.getLogger(__name__)


class PaymentProviderError(Exception):
    """Raised when the Transbank SDK fails to create or commit a transaction."""

    def __init__(self, message: str, code: str | int | None = None):
        super().__init__(message)
        self.message = message
        self.code = code


class TransbankService:
    """Webpay Plus operations bound to a single broker's credentials."""

    def __init__(self, credentials: TransbankCredentials):
        self._creds = credentials
        if credentials.environment == "production":
            self._tx = Transaction.build_for_production(
                credentials.commerce_code, credentials.api_key
            )
        else:
            self._tx = Transaction.build_for_integration(
                credentials.commerce_code, credentials.api_key
            )

    @property
    def environment(self) -> str:
        return self._creds.environment

    @classmethod
    async def for_broker(cls, db: AsyncSession, broker_id: int) -> "TransbankService":
        creds = await BrokerPaymentConfigService.get_credentials(db, broker_id)
        return cls(creds)

    async def create_transaction(
        self, buy_order: str, session_id: str, amount: int, return_url: str
    ) -> Dict[str, Any]:
        """
        Create a Webpay Plus transaction.
        Returns the SDK dict: {"token": ..., "url": ...}.
        """
        try:
            resp = await asyncio.to_thread(
                self._tx.create, buy_order, session_id, amount, return_url
            )
            return dict(resp)
        except TransbankError as exc:
            logger.warning("[Transbank] create failed: %s", getattr(exc, "message", exc))
            raise PaymentProviderError(
                getattr(exc, "message", str(exc)), getattr(exc, "code", None)
            ) from exc

    async def commit_transaction(self, token: str) -> Dict[str, Any]:
        """
        Commit (confirm) a Webpay Plus transaction by token_ws.
        Returns the SDK dict with response_code, status, amount, authorization_code,
        card_detail, transaction_date, payment_type_code, installments_number, etc.
        """
        try:
            resp = await asyncio.to_thread(self._tx.commit, token)
            return dict(resp)
        except TransbankError as exc:
            logger.warning("[Transbank] commit failed: %s", getattr(exc, "message", exc))
            raise PaymentProviderError(
                getattr(exc, "message", str(exc)), getattr(exc, "code", None)
            ) from exc
