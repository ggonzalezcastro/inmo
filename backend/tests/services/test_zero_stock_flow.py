"""Coverage for the Sofía bug-fix bundle: zero-stock handling, dedupe,
extraction observability, and prompt-respect for "ya te lo dije".

Run isolated (no DB needed):
    .venv/bin/python -m pytest tests/services/test_zero_stock_flow.py -v --noconftest
"""
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _ctx(stage="entrada", state="DATA_COLLECTION", lead_data=None, history=None):
    from app.services.agents.types import AgentContext
    return AgentContext(
        lead_id=1,
        broker_id=1,
        pipeline_stage=stage,
        conversation_state=state,
        lead_data=lead_data or {},
        message_history=history or [],
    )


def _stub_provider(json_payload=None):
    p = MagicMock()
    p.is_configured = True
    p.name = "fast-stub"
    p.generate_json = AsyncMock(return_value=(json_payload or {}, {"input_tokens": 10, "output_tokens": 5}))
    return p


# Fix 1 — analyze_lead_qualification always uses fast provider
@pytest.mark.asyncio
async def test_analyze_uses_fast_provider_even_with_broker():
    from app.services.llm import facade

    provider = _stub_provider({"salary": 3000000})
    db_mock = MagicMock()

    with patch.object(facade, "get_fast_llm_provider", return_value=provider) as gf, \
         patch.object(facade, "resolve_provider_for_agent",
                      new=AsyncMock(side_effect=AssertionError("must NOT be called"))) as rp:
        out = await facade.LLMServiceFacade.analyze_lead_qualification(
            message="gano 3 millones",
            lead_context={"name": "test"},
            db=db_mock,
            broker_id=42,
            lead_id=1,
        )

    gf.assert_called()
    rp.assert_not_called()
    assert out.get("salary") == 3000000


# Fix 4 — observability warnings
@pytest.mark.asyncio
async def test_money_hint_without_extraction_emits_warning(caplog):
    from app.services.llm import facade

    provider = _stub_provider({})

    with patch.object(facade, "get_fast_llm_provider", return_value=provider), \
         caplog.at_level(logging.WARNING, logger="app.services.llm.facade"):
        await facade.LLMServiceFacade.analyze_lead_qualification(
            message="gano 3 millones liquidos",
            lead_context={},
            lead_id=99,
        )

    assert any("salary" in r.message.lower() for r in caplog.records), \
        f"expected salary miss warning, got: {[r.message for r in caplog.records]}"


@pytest.mark.asyncio
async def test_dicom_hint_without_extraction_emits_warning(caplog):
    from app.services.llm import facade

    provider = _stub_provider({})

    with patch.object(facade, "get_fast_llm_provider", return_value=provider), \
         caplog.at_level(logging.WARNING, logger="app.services.llm.facade"):
        await facade.LLMServiceFacade.analyze_lead_qualification(
            message="estoy limpio en dicom, sin deudas",
            lead_context={},
            lead_id=99,
        )

    assert any("dicom" in r.message.lower() for r in caplog.records)


# Fix 3 — _build_messages dedupe guard
def test_build_messages_dedupes_repeated_user():
    from app.services.agents.qualifier import _build_messages

    history = [
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "buenas"},
        {"role": "user", "content": "gano 3 millones"},
    ]
    msgs = _build_messages(history, "gano 3 millones")
    assert sum(1 for m in msgs if m.content == "gano 3 millones") == 1


def test_build_messages_appends_when_last_is_assistant():
    from app.services.agents.qualifier import _build_messages

    history = [
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "¿en qué te ayudo?"},
    ]
    msgs = _build_messages(history, "busco depto")
    assert msgs[-1].role == "user"
    assert msgs[-1].content == "busco depto"


def test_property_build_messages_also_dedupes():
    from app.services.agents.property import _build_messages

    history = [{"role": "user", "content": "quiero parcela"}]
    msgs = _build_messages(history, "quiero parcela")
    assert sum(1 for m in msgs if m.content == "quiero parcela") == 1


# Fix 5 — Property emits _no_stock_for in zero-results handoff
def test_no_stock_for_propagation_shape():
    import inspect
    from app.services.agents import property as prop_mod
    src = inspect.getsource(prop_mod)
    assert "_no_stock_for" in src
    assert "_zero_results_handoff" in src


# Fix 6 — qualifier prompt swaps recordatorio when no stock; bans zone literal
def test_qualifier_prompt_neutral_when_no_stock():
    from app.services.agents.qualifier import QualifierAgent

    agent = QualifierAgent()
    ctx = _ctx(lead_data={
        "name": "keka",
        "_handoff_from": "property",
        "_zero_results_handoff": True,
        "_no_stock_for": {"location": "Lomas Turbas", "city": "Santiago", "property_type": "parcela"},
    })
    prompt = agent.get_system_prompt(ctx)

    # Neutral recordatorio block must be present
    assert "te conectamos directamente con nuestro ejecutivo" in prompt
    # Zone literal must be banned explicitly
    assert "Lomas Turbas" in prompt
    assert "PROHIBIDO" in prompt or "NUNCA" in prompt


def test_qualifier_prompt_default_when_stock_available():
    from app.services.agents.qualifier import QualifierAgent

    agent = QualifierAgent()
    ctx = _ctx(lead_data={"name": "x"})
    prompt = agent.get_system_prompt(ctx)
    assert "videollamada" in prompt.lower()


# Fix 7 — qualifier respects "ya te lo dije"
def test_qualifier_prompt_includes_already_told_block():
    from app.services.agents.qualifier import QualifierAgent

    agent = QualifierAgent()
    ctx = _ctx(lead_data={})
    prompt = agent.get_system_prompt(ctx)

    assert "ya te lo dije" in prompt.lower() or "ya dio" in prompt.lower()
    assert "repetir" in prompt.lower() or "repítelo" in prompt.lower() or "repetirme" in prompt.lower()


# Fix 8 — scheduler blocks create_appointment when no stock + no property_interest
def test_scheduler_guard_present_in_source():
    from app.services.agents import scheduler as sched_mod
    src = open(sched_mod.__file__).read()
    assert "Blocking create_appointment" in src
    assert "results_count" in src
    assert "property_interest" in src


@pytest.mark.asyncio
async def test_scheduler_guard_blocks_when_no_stock(monkeypatch):
    """Scheduler must NOT call the LLM at all when stock is empty + no property_interest;
    instead it returns a clarification response."""
    from app.services.agents.scheduler import SchedulerAgent
    from app.services.llm import facade as facade_mod

    agent = SchedulerAgent()
    ctx = _ctx(
        stage="calificacion_financiera",
        state="FINANCIAL_QUAL",
        lead_data={
            "name": "x",
            "_handoff_from": "qualifier",  # bypass G1 financial pre-check
            "salary": 3000000,
            "dicom_status": "clean",
            "last_property_search": {"results_count": 0, "ts": __import__("time").time()},
        },
    )

    async def boom(*a, **k):
        raise AssertionError("LLM facade must NOT be called when guard trips")

    monkeypatch.setattr(
        facade_mod.LLMServiceFacade,
        "generate_response_with_function_calling",
        AsyncMock(side_effect=boom),
    )

    resp = await agent.process("agéndame visita", ctx, db=MagicMock())
    assert "propiedad concreta" in resp.message.lower() or "no hay propiedades" in resp.message.lower() or "qué propiedad" in resp.message.lower()


@pytest.mark.asyncio
async def test_scheduler_does_not_block_on_stale_search(monkeypatch):
    """Stale (>10 min) zero-results search must NOT block legitimate scheduling."""
    import time as _t
    from app.services.agents.scheduler import SchedulerAgent
    from app.services.llm import facade as facade_mod

    agent = SchedulerAgent()
    ctx = _ctx(
        stage="calificacion_financiera",
        state="FINANCIAL_QUAL",
        lead_data={
            "name": "x",
            "_handoff_from": "qualifier",
            "salary": 3000000,
            "dicom_status": "clean",
            # ts is 1 hour old → stale → guard must NOT trigger
            "last_property_search": {"results_count": 0, "ts": _t.time() - 3600},
        },
    )

    called = {"n": 0}

    async def fake_generate(**kw):
        called["n"] += 1
        return ("Te ayudo con el agendamiento.", [])

    monkeypatch.setattr(
        facade_mod.LLMServiceFacade,
        "generate_response_with_function_calling",
        AsyncMock(side_effect=fake_generate),
    )

    resp = await agent.process("agéndame visita", ctx, db=MagicMock())
    # Guard skipped → LLM called → no clarification message
    assert called["n"] >= 1
    assert "propiedad concreta" not in (resp.message or "").lower()


def test_qualifier_skips_no_stock_branch_without_property_handoff():
    """Stale `_no_stock_for` from a prior turn must NOT poison the prompt
    when the current turn was not triggered by a property handoff."""
    from app.services.agents.qualifier import QualifierAgent

    agent = QualifierAgent()
    ctx = _ctx(lead_data={
        "name": "x",
        # _no_stock_for set but _handoff_from is NOT "property"
        "_no_stock_for": {"location": "Lomas Turbas", "city": "Santiago"},
        "_handoff_from": "scheduler",
    })
    prompt = agent.get_system_prompt(ctx)
    # Default videocall offer must be present (neutral branch should be skipped)
    assert "videollamada" in prompt.lower()
    # No zone-ban block (would only render under property handoff)
    assert "PROHIBIDO mencionar" not in prompt
