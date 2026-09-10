"""
Unit tests for Transbank Webpay Plus payment integration.

Run without DB:  .venv/bin/python -m pytest tests/services/test_payments.py -v --noconftest
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── payment_config_service.get_credentials ───────────────────────────────────

@pytest.mark.asyncio
async def test_get_credentials_falls_back_to_integration_defaults():
    from app.services.broker.payment_config_service import BrokerPaymentConfigService
    from app.config import settings

    db = MagicMock()
    with patch.object(BrokerPaymentConfigService, "get_config", AsyncMock(return_value=None)):
        creds = await BrokerPaymentConfigService.get_credentials(db, broker_id=1)

    assert creds.source == "default"
    assert creds.environment == "integration"
    assert creds.commerce_code == settings.TRANSBANK_DEFAULT_COMMERCE_CODE
    assert creds.api_key == settings.TRANSBANK_DEFAULT_API_KEY


@pytest.mark.asyncio
async def test_get_credentials_uses_broker_config_when_enabled():
    from app.services.broker.payment_config_service import BrokerPaymentConfigService
    from app.core.encryption import encrypt_value

    row = MagicMock()
    row.enabled = True
    row.commerce_code = "597000000001"
    row.api_key_encrypted = encrypt_value("SUPERSECRETKEY")
    row.environment = "integration"

    db = MagicMock()
    with patch.object(BrokerPaymentConfigService, "get_config", AsyncMock(return_value=row)):
        creds = await BrokerPaymentConfigService.get_credentials(db, broker_id=7)

    assert creds.source == "broker"
    assert creds.commerce_code == "597000000001"
    assert creds.api_key == "SUPERSECRETKEY"  # decrypted round-trip


@pytest.mark.asyncio
async def test_get_credentials_force_integration_overrides_production():
    from app.services.broker.payment_config_service import BrokerPaymentConfigService
    from app.core.encryption import encrypt_value

    row = MagicMock()
    row.enabled = True
    row.commerce_code = "597000000002"
    row.api_key_encrypted = encrypt_value("KEY2")
    row.environment = "production"

    db = MagicMock()
    with patch.object(BrokerPaymentConfigService, "get_config", AsyncMock(return_value=row)), \
         patch("app.services.broker.payment_config_service.settings.TRANSBANK_FORCE_INTEGRATION", True):
        creds = await BrokerPaymentConfigService.get_credentials(db, broker_id=9)

    # Phase 1 kill-switch downgrades production to integration.
    assert creds.environment == "integration"


@pytest.mark.asyncio
async def test_get_credentials_disabled_config_uses_default():
    from app.services.broker.payment_config_service import BrokerPaymentConfigService

    row = MagicMock()
    row.enabled = False
    row.commerce_code = "597000000003"
    row.api_key_encrypted = "enc:whatever"
    row.environment = "production"

    db = MagicMock()
    with patch.object(BrokerPaymentConfigService, "get_config", AsyncMock(return_value=row)):
        creds = await BrokerPaymentConfigService.get_credentials(db, broker_id=3)

    assert creds.source == "default"
    assert creds.environment == "integration"


# ── TransbankService environment selection ────────────────────────────────────

def test_transbank_service_uses_integration_builder():
    from app.services.payments.transbank.service import TransbankService
    from app.services.broker.payment_config_service import TransbankCredentials

    creds = TransbankCredentials(
        commerce_code="597055555532", api_key="k", environment="integration", source="default"
    )
    with patch("app.services.payments.transbank.service.Transaction") as tx_cls:
        svc = TransbankService(creds)
    tx_cls.build_for_integration.assert_called_once_with("597055555532", "k")
    tx_cls.build_for_production.assert_not_called()
    assert svc.environment == "integration"


def test_transbank_service_uses_production_builder():
    from app.services.payments.transbank.service import TransbankService
    from app.services.broker.payment_config_service import TransbankCredentials

    creds = TransbankCredentials(
        commerce_code="C", api_key="k", environment="production", source="broker"
    )
    with patch("app.services.payments.transbank.service.Transaction") as tx_cls:
        TransbankService(creds)
    tx_cls.build_for_production.assert_called_once_with("C", "k")


@pytest.mark.asyncio
async def test_create_transaction_wraps_sdk_error():
    from app.services.payments.transbank.service import TransbankService, PaymentProviderError
    from app.services.broker.payment_config_service import TransbankCredentials
    from transbank.error.transbank_error import TransbankError

    creds = TransbankCredentials(
        commerce_code="C", api_key="k", environment="integration", source="default"
    )
    with patch("app.services.payments.transbank.service.Transaction") as tx_cls:
        inst = MagicMock()
        inst.create.side_effect = TransbankError(message="boom", code=422)
        tx_cls.build_for_integration.return_value = inst
        svc = TransbankService(creds)

    with pytest.raises(PaymentProviderError):
        await svc.create_transaction("bo", "sess", 1000, "http://return")


# ── _guard_draft_to_reserva accepts an approved payment ───────────────────────

def _result_with_first(value):
    r = MagicMock()
    r.first.return_value = value
    return r


def _result_with_scalar(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


@pytest.mark.asyncio
async def test_guard_passes_when_approved_payment_exists():
    from app.services.deals.state_machine import _guard_draft_to_reserva

    deal = MagicMock()
    deal.id = 1
    db = MagicMock()
    # First execute → approved payment query returns a row.
    db.execute = AsyncMock(return_value=_result_with_first((1,)))

    # Should not raise.
    await _guard_draft_to_reserva(deal, db)
    assert db.execute.await_count == 1  # short-circuits before the doc query


@pytest.mark.asyncio
async def test_guard_falls_back_to_document_when_no_payment():
    from app.services.deals.state_machine import _guard_draft_to_reserva

    deal = MagicMock()
    deal.id = 1
    db = MagicMock()
    # 1st execute → no approved payment; 2nd → an approved/received doc exists.
    db.execute = AsyncMock(side_effect=[
        _result_with_first(None),
        _result_with_scalar(MagicMock()),
    ])

    await _guard_draft_to_reserva(deal, db)
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_guard_raises_when_no_payment_and_no_document():
    from app.services.deals.state_machine import _guard_draft_to_reserva
    from app.services.deals.exceptions import DealError

    deal = MagicMock()
    deal.id = 1
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[
        _result_with_first(None),
        _result_with_scalar(None),
    ])

    with pytest.raises(DealError):
        await _guard_draft_to_reserva(deal, db)
