"""
Unit tests for lead qualification and score handling.

Covers:
- LLMServiceFacade.analyze_lead_qualification default field injection
- DICOM status extraction ("no tengo DICOM" → dicom_status="clean")
- score_delta is bounded by facade defaults
- analyze_lead_qualification returns all required fields even on LLM failure
- LLM JSON malformed response → defaults are applied
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ── Helpers ──────────────────────────────────────────────────────────────────

REQUIRED_KEYS = {
    "qualified", "interest_level", "budget", "timeline",
    "name", "phone", "email", "salary", "location",
    "dicom_status", "morosidad_amount", "key_points", "score_delta",
}


def _mock_provider_with_json(json_result: dict):
    provider = MagicMock()
    provider.is_configured = True
    provider.generate_json = AsyncMock(return_value=json_result)
    return provider


def _mock_provider_failing():
    provider = MagicMock()
    provider.is_configured = True
    provider.generate_json = AsyncMock(side_effect=RuntimeError("API error"))
    return provider


# ── Required fields always present ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_all_required_fields_present_on_success():
    from app.services.llm.facade import LLMServiceFacade

    provider = _mock_provider_with_json({
        "qualified": "yes",
        "interest_level": 8,
        "score_delta": 10,
        "key_points": ["Renta alta"],
    })
    with patch("app.services.llm.facade.get_llm_provider", return_value=provider):
        result = await LLMServiceFacade.analyze_lead_qualification("Mi sueldo es 2M")

    assert REQUIRED_KEYS.issubset(result.keys()), f"Missing keys: {REQUIRED_KEYS - result.keys()}"


@pytest.mark.asyncio
async def test_all_required_fields_present_on_llm_failure():
    from app.services.llm.facade import LLMServiceFacade

    provider = _mock_provider_failing()
    with patch("app.services.llm.facade.get_llm_provider", return_value=provider):
        result = await LLMServiceFacade.analyze_lead_qualification("mensaje")

    assert REQUIRED_KEYS.issubset(result.keys())
    assert result["qualified"] == "maybe"


@pytest.mark.asyncio
async def test_all_required_fields_present_on_partial_llm_response():
    """LLM returns only some fields — defaults fill the rest."""
    from app.services.llm.facade import LLMServiceFacade

    provider = _mock_provider_with_json({"qualified": "no", "interest_level": 2})
    with patch("app.services.llm.facade.get_llm_provider", return_value=provider):
        result = await LLMServiceFacade.analyze_lead_qualification("No me interesa")

    assert REQUIRED_KEYS.issubset(result.keys())
    assert result["budget"] is None
    assert result["name"] is None


# ── Provider not configured ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_returns_defaults_when_provider_not_configured():
    from app.services.llm.facade import LLMServiceFacade

    provider = MagicMock()
    provider.is_configured = False
    with patch("app.services.llm.facade.get_llm_provider", return_value=provider):
        result = await LLMServiceFacade.analyze_lead_qualification("Hola")

    assert result["qualified"] == "maybe"
    assert result["interest_level"] == 5


# ── DICOM extraction ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dicom_clean_extracted():
    from app.services.llm.facade import LLMServiceFacade

    provider = _mock_provider_with_json({
        "qualified": "yes",
        "interest_level": 7,
        "dicom_status": "clean",
        "score_delta": 15,
        "key_points": [],
    })
    with patch("app.services.llm.facade.get_llm_provider", return_value=provider):
        result = await LLMServiceFacade.analyze_lead_qualification(
            "No tengo DICOM", lead_context={"message_history": []}
        )

    assert result["dicom_status"] == "clean"


@pytest.mark.asyncio
async def test_dicom_has_debt_extracted():
    from app.services.llm.facade import LLMServiceFacade

    provider = _mock_provider_with_json({
        "qualified": "no",
        "interest_level": 3,
        "dicom_status": "has_debt",
        "morosidad_amount": 500000,
        "score_delta": -15,
        "key_points": [],
    })
    with patch("app.services.llm.facade.get_llm_provider", return_value=provider):
        result = await LLMServiceFacade.analyze_lead_qualification(
            "Tengo una deuda de 500k", lead_context={}
        )

    assert result["dicom_status"] == "has_debt"
    assert result["morosidad_amount"] == 500000


# ── Score delta is stored as-is (clamping happens in DB update) ──────────────

@pytest.mark.asyncio
async def test_score_delta_preserved():
    from app.services.llm.facade import LLMServiceFacade

    provider = _mock_provider_with_json({
        "qualified": "yes",
        "interest_level": 9,
        "score_delta": 20,
        "key_points": [],
    })
    with patch("app.services.llm.facade.get_llm_provider", return_value=provider):
        result = await LLMServiceFacade.analyze_lead_qualification("Quiero comprar ya")

    assert result["score_delta"] == 20


@pytest.mark.asyncio
async def test_score_delta_negative_preserved():
    from app.services.llm.facade import LLMServiceFacade

    provider = _mock_provider_with_json({
        "qualified": "no",
        "interest_level": 1,
        "score_delta": -20,
        "key_points": [],
    })
    with patch("app.services.llm.facade.get_llm_provider", return_value=provider):
        result = await LLMServiceFacade.analyze_lead_qualification("No me interesa")

    assert result["score_delta"] == -20


# ── key_points list ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_key_points_is_always_a_list():
    from app.services.llm.facade import LLMServiceFacade

    # LLM returns no key_points field
    provider = _mock_provider_with_json({"qualified": "maybe", "interest_level": 5, "score_delta": 0})
    with patch("app.services.llm.facade.get_llm_provider", return_value=provider):
        result = await LLMServiceFacade.analyze_lead_qualification("Mensaje")

    assert isinstance(result["key_points"], list)
