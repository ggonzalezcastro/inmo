"""Unit contracts for Housing drafts, spend control, and safe conversion data."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.meta_ads import MetaAdCampaignCreate, MetaAdCampaignResponse
from app.services.meta.ads import (
    HOUSING_TARGETING_KEYS,
    MetaCampaignDraftService,
    _cost,
    _identity,
    _require_public_https,
)
from app.services.meta.conversions import MetaConversionsService, _hash
from app.services.meta.lead_ads import _normalize_lead_form_values, _validate_field_mapping
from app.services.meta.url_safety import is_public_https_url


def _valid_payload(**overrides):
    payload = {
        "name": "Proyecto Norte",
        "ad_account_asset_id": 10,
        "project_id": 22,
        "objective": "OUTCOME_LEADS",
        "destination_type": "website",
        "special_ad_category": "HOUSING",
        "daily_budget": "15000",
        "currency": "CLP",
        "ad_set": {
            "name": "Chile",
            "optimization_goal": "LINK_CLICKS",
            "targeting": {"geo_locations": {"countries": ["CL"]}},
            "promoted_object": {},
        },
        "creative": {
            "page_asset_id": 3,
            "name": "Creatividad",
            "primary_text": "Departamentos disponibles según inventario vigente.",
            "headline": "Conoce el proyecto",
            "call_to_action": "LEARN_MORE",
            "destination_url": "https://example.com/proyecto",
        },
    }
    payload.update(overrides)
    return payload


def test_campaign_requires_exactly_one_budget():
    with pytest.raises(ValidationError):
        MetaAdCampaignCreate.model_validate(_valid_payload(lifetime_budget="300000"))
    without_budget = _valid_payload()
    without_budget.pop("daily_budget")
    with pytest.raises(ValidationError):
        MetaAdCampaignCreate.model_validate(without_budget)


def test_housing_contract_excludes_sensitive_targeting():
    assert "geo_locations" in HOUSING_TARGETING_KEYS
    assert "age_min" not in HOUSING_TARGETING_KEYS
    assert "age_max" not in HOUSING_TARGETING_KEYS
    assert "genders" not in HOUSING_TARGETING_KEYS
    assert "flexible_spec" not in HOUSING_TARGETING_KEYS


def test_cost_metric_is_null_without_outcome():
    assert _cost(Decimal("45000"), 0) is None
    assert _cost(Decimal("45000"), 3) == Decimal("15000.00")


def test_conversion_hash_normalizes_and_never_returns_plaintext():
    first = _hash(" Cliente@Example.COM ")
    second = _hash("cliente@example.com")
    assert first == second
    assert first != "cliente@example.com"
    assert len(first) == 64


def test_superadmin_without_impersonated_broker_is_rejected():
    with pytest.raises(HTTPException) as captured:
        _identity({"id": 1, "role": "SUPERADMIN", "broker_id": None})
    assert captured.value.status_code == 400


@pytest.mark.asyncio
async def test_published_campaign_cannot_return_to_review(monkeypatch):
    campaign = SimpleNamespace(id=5, version=4, status="active")
    monkeypatch.setattr(
        MetaCampaignDraftService,
        "get",
        AsyncMock(return_value=campaign),
    )
    payload = SimpleNamespace(expected_version=4, comment=None)
    with pytest.raises(HTTPException) as captured:
        await MetaCampaignDraftService.transition(
            AsyncMock(),
            campaign_id=5,
            action="submit",
            payload=payload,
            current_user={"id": 9, "broker_id": 2, "role": "AGENT"},
        )
    assert captured.value.status_code == 409


def test_real_estate_payload_cannot_change_special_category():
    with pytest.raises(ValidationError):
        MetaAdCampaignCreate.model_validate(_valid_payload(special_ad_category="NONE"))


def test_creative_urls_reject_private_networks():
    with pytest.raises(HTTPException):
        _require_public_https("http://example.com/image.jpg", "La imagen")
    with pytest.raises(HTTPException):
        _require_public_https("https://127.0.0.1/image.jpg", "La imagen")
    _require_public_https("https://cdn.example.com/image.jpg", "La imagen")


@pytest.mark.parametrize(
    "url",
    [
        "https://localhost/file.pdf",
        "https://localhost./file.pdf",
        "https://redis/file.pdf",
        "https://service.internal/file.pdf",
        "https://10.0.0.8/file.pdf",
        "https://[::1]/file.pdf",
        "https://user@cdn.example.com/file.pdf",
    ],
)
def test_media_urls_reject_local_or_credentialed_hosts(url):
    assert is_public_https_url(url) is False


def test_media_urls_accept_public_https_hosts():
    assert is_public_https_url("https://cdn.example.com/file.pdf") is True
    assert is_public_https_url("https://8.8.8.8/file.pdf") is True


@pytest.mark.asyncio
async def test_conversion_lookup_joins_lead_and_property_with_same_broker():
    result = Mock()
    result.first.return_value = None
    db = SimpleNamespace(execute=AsyncMock(return_value=result))

    assert await MetaConversionsService.send_purchase_for_deal(db, deal_id=18) == "not_found"
    statement = str(db.execute.await_args.args[0])
    assert "leads.broker_id = deals.broker_id" in statement
    assert "properties.broker_id = deals.broker_id" in statement


def test_campaign_response_exposes_immutable_submission_snapshot():
    assert "submission_snapshot" in MetaAdCampaignResponse.model_fields


def test_lead_form_preview_uses_production_normalization():
    payload, warnings = _normalize_lead_form_values(
        {
            "full_name": "  María Soto ",
            "phone_number": "9 1234 5678",
            "email_address": " MARIA@EXAMPLE.COM ",
            "budget_answer": "3.500 UF",
        },
        {
            "phone_number": "phone",
            "email_address": "email",
            "budget_answer": "budget",
        },
        project_id=22,
    )

    assert warnings == []
    assert payload["phone"] == "+56912345678"
    assert payload["name"] == "María Soto"
    assert payload["email"] == "maria@example.com"
    assert payload["metadata"] == {
        "source": "meta_lead_ads",
        "project_id": 22,
        "budget": "3.500 UF",
    }


def test_lead_form_mapping_requires_contact_identity():
    with pytest.raises(HTTPException) as captured:
        _validate_field_mapping({"budget_answer": "budget"})
    assert captured.value.status_code == 422
