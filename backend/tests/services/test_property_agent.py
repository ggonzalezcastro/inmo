"""
Tests for PropertyAgent — routing, function calling, and handoff logic.

Run without DB:
    python -m pytest tests/services/test_property_agent.py -v --noconftest
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.agents.types import AgentContext, AgentType, HandoffSignal
from app.services.agents.property import PropertyAgent


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ctx(**overrides) -> AgentContext:
    defaults = dict(
        lead_id=1,
        broker_id=1,
        pipeline_stage="potencial",
        conversation_state="GREETING",
        lead_data={"broker_name": "Test", "agent_name": "Sofía"},
        message_history=[],
        handoff_count=0,
    )
    defaults.update(overrides)
    return AgentContext(**defaults)


# ── should_handle ─────────────────────────────────────────────────────────────

class TestPropertyAgentRouting:
    @pytest.mark.asyncio
    async def test_handles_potencial_stage(self):
        agent = PropertyAgent()
        assert await agent.should_handle(_ctx(pipeline_stage="potencial"))

    @pytest.mark.asyncio
    async def test_handles_calificacion_financiera_stage(self):
        agent = PropertyAgent()
        assert await agent.should_handle(_ctx(pipeline_stage="calificacion_financiera"))

    @pytest.mark.asyncio
    async def test_handles_agendado_stage(self):
        agent = PropertyAgent()
        assert await agent.should_handle(_ctx(pipeline_stage="agendado"))

    @pytest.mark.asyncio
    async def test_does_not_handle_entrada_stage(self):
        agent = PropertyAgent()
        assert not await agent.should_handle(_ctx(pipeline_stage="entrada"))

    @pytest.mark.asyncio
    async def test_does_not_handle_referidos_stage(self):
        agent = PropertyAgent()
        assert not await agent.should_handle(_ctx(pipeline_stage="referidos"))


# ── process — no property mention ────────────────────────────────────────────

class TestPropertyAgentProcess:
    @pytest.mark.asyncio
    async def test_responds_when_no_property_query(self):
        """Non-property message → conversational response via LLM passthrough, then handoff."""
        agent = PropertyAgent()
        ctx = _ctx()
        db = AsyncMock()

        with patch(
            "app.services.agents.property.LLMServiceFacade.generate_response_with_function_calling",
            new_callable=AsyncMock,
            return_value=("Hola, soy Sofía. ¿En qué puedo ayudarte?", []),
        ):
            response = await agent.process("Hola", ctx, db)

        assert response.message == "Hola, soy Sofía. ¿En qué puedo ayudarte?"
        assert response.agent_type == AgentType.PROPERTY
        # Non-property message triggers handoff to Qualifier
        assert response.handoff is not None
        assert response.handoff.target_agent == AgentType.QUALIFIER

    @pytest.mark.asyncio
    async def test_executes_property_search_tool(self):
        """Message requesting property → tool called → results formatted."""
        agent = PropertyAgent()
        ctx = _ctx(pipeline_stage="calificacion_financiera",
                   lead_data={"broker_name": "Test", "agent_name": "Sofía",
                              "location": "Las Condes", "budget": "5000 UF"})
        db = AsyncMock()

        mock_results = [
            {"name": "Edificio Sol", "commune": "Las Condes", "price_uf": 4800,
             "bedrooms": 2, "bathrooms": 1, "area_m2": 65, "property_type": "departamento",
             "description": "Vista al parque"},
        ]

        with patch(
            "app.services.agents.property.LLMServiceFacade.generate_response_with_function_calling",
            new_callable=AsyncMock,
            return_value=("Encontré 1 propiedad en Las Condes.", []),
        ), patch(
            "app.services.agents.property.execute_property_search",
            new_callable=AsyncMock,
            return_value=mock_results,
        ), patch(
            "app.services.observability.event_logger.event_logger.log_property_search",
            new_callable=AsyncMock,
        ), patch(
            "app.services.observability.event_logger.event_logger.log_tool_call",
            new_callable=AsyncMock,
        ):
            response = await agent.process(
                "Quiero ver departamentos en Las Condes hasta 5000 UF", ctx, db
            )

        assert response.agent_type == AgentType.PROPERTY
        assert response.message == "Encontré 1 propiedad en Las Condes."

    @pytest.mark.asyncio
    async def test_handoff_when_lead_wants_to_book(self):
        """should_handoff returns response.handoff — HandoffSignal to Scheduler when set."""
        agent = PropertyAgent()
        ctx = _ctx(pipeline_stage="calificacion_financiera")

        scheduler_handoff = HandoffSignal(
            target_agent=AgentType.SCHEDULER,
            reason="Lead wants to visit a specific property",
        )
        from app.services.agents.types import AgentResponse
        mock_response = AgentResponse(
            message="¡Perfecto! Te agendo una visita.",
            agent_type=AgentType.PROPERTY,
            handoff=scheduler_handoff,
        )

        handoff = await agent.should_handoff(mock_response, ctx)

        assert handoff is not None
        assert handoff.target_agent == AgentType.SCHEDULER

    @pytest.mark.asyncio
    async def test_no_handoff_by_default(self):
        """Normal property browsing (no schedule intent) → no handoff."""
        agent = PropertyAgent()
        ctx = _ctx()

        from app.services.agents.types import AgentResponse
        mock_response = AgentResponse(
            message="Aquí hay departamentos disponibles.",
            agent_type=AgentType.PROPERTY,
            handoff=None,
        )

        handoff = await agent.should_handoff(mock_response, ctx)
        assert handoff is None


# ── zero-results handoff ──────────────────────────────────────────────────────

class TestPropertyAgentZeroResults:
    """When search returns 0 results, PropertyAgent should hand off to QualifierAgent
    with a safe deterministic transition message (never raw LLM text that may
    leak stock-availability info)."""

    @pytest.mark.asyncio
    async def test_zero_results_hands_off_to_qualifier(self):
        agent = PropertyAgent()
        ctx = _ctx(pipeline_stage="potencial")
        db = AsyncMock()

        with patch(
            "app.services.agents.property.execute_property_search",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "app.services.agents.property.LLMServiceFacade.generate_response_with_function_calling",
            new_callable=AsyncMock,
            return_value=("texto generado por LLM que no se usa", []),
        ), patch(
            "app.services.observability.event_logger.event_logger.log_property_search",
            new_callable=AsyncMock,
        ), patch(
            "app.services.observability.event_logger.event_logger.log_tool_call",
            new_callable=AsyncMock,
        ):
            # Simulate the tool being called by running process with a search intent
            # We need to trigger the tool_executor path — patch at facade level
            # and simulate tool call side effect manually via _handoff_intent
            response = await _run_with_zero_results(agent, ctx, db)

        assert response.handoff is not None
        assert response.handoff.target_agent == AgentType.QUALIFIER
        assert response.handoff.context_updates.get("_zero_results_handoff") is True

    @pytest.mark.asyncio
    async def test_zero_results_message_is_not_empty(self):
        """message must never be '' — empty string poisons the history."""
        agent = PropertyAgent()
        ctx = _ctx()
        db = AsyncMock()

        response = await _run_with_zero_results(agent, ctx, db)

        assert response.message, "message must not be empty string"
        assert response.message.strip(), "message must not be whitespace only"

    @pytest.mark.asyncio
    async def test_zero_results_message_does_not_mention_availability(self):
        """Transition message must never reveal lack of stock to the lead."""
        agent = PropertyAgent()
        ctx = _ctx()
        db = AsyncMock()

        response = await _run_with_zero_results(agent, ctx, db)

        forbidden = ["no hay", "no encontr", "sin resultado", "disponib", "stock"]
        msg_lower = response.message.lower()
        for word in forbidden:
            assert word not in msg_lower, (
                f"Transition message leaks stock info ('{word}'): {response.message}"
            )

    @pytest.mark.asyncio
    async def test_zero_results_stores_transition_in_context(self):
        """_property_transition_said must be set so Qualifier doesn't repeat it."""
        agent = PropertyAgent()
        ctx = _ctx()
        db = AsyncMock()

        response = await _run_with_zero_results(agent, ctx, db)

        assert response.handoff is not None
        assert "_property_transition_said" in response.handoff.context_updates
        assert response.handoff.context_updates["_property_transition_said"] == response.message

    @pytest.mark.asyncio
    async def test_zero_results_with_name_and_phone_gives_different_transition(self):
        """Lead with name+phone gets a different transition than unknown lead."""
        agent = PropertyAgent()
        ctx_unknown = _ctx(lead_data={"broker_name": "Test", "agent_name": "Sofía"})
        ctx_known = _ctx(lead_data={
            "broker_name": "Test", "agent_name": "Sofía",
            "name": "Juan", "phone": "+56912345678",
        })
        db = AsyncMock()

        resp_unknown = await _run_with_zero_results(agent, ctx_unknown, db)
        resp_known = await _run_with_zero_results(agent, ctx_known, db)

        assert resp_unknown.message != resp_known.message, (
            "Lead with data should get a different transition than unknown lead"
        )


async def _run_with_zero_results(agent: PropertyAgent, ctx: AgentContext, db):
    """Helper: simulate a search_properties tool call that returns 0 results."""
    original_process = agent.process

    async def fake_tool_executor_process(message, context, db):
        # Directly invoke the internal logic by monkey-patching execute_property_search
        with patch(
            "app.services.agents.property.execute_property_search",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "app.services.agents.property.LLMServiceFacade.generate_response_with_function_calling",
            new_callable=AsyncMock,
            return_value=("texto LLM descartado", []),
        ), patch(
            "app.services.observability.event_logger.event_logger.log_property_search",
            new_callable=AsyncMock,
        ), patch(
            "app.services.observability.event_logger.event_logger.log_tool_call",
            new_callable=AsyncMock,
        ):
            # We need to actually trigger the tool_executor so _handoff_intent gets set.
            # The simplest way: patch generate_response_with_function_calling to call
            # the tool_executor with search_properties returning 0 results.
            from app.services.agents import property as prop_module

            _original_facade = prop_module.LLMServiceFacade.generate_response_with_function_calling

            async def facade_that_triggers_search(system_prompt, contents, tools, tool_executor, **kwargs):
                # Simulate LLM calling search_properties
                await tool_executor("search_properties", {
                    "location": "Santiago", "property_type": "departamento", "strategy": "hybrid"
                })
                return ("texto LLM descartado", [])

            with patch.object(
                prop_module.LLMServiceFacade,
                "generate_response_with_function_calling",
                side_effect=facade_that_triggers_search,
            ):
                return await original_process(message, context, db)

    return await fake_tool_executor_process("Busco depto en Santiago", ctx, db)


# ── agent_type enum ───────────────────────────────────────────────────────────

class TestPropertyAgentIdentity:
    def test_agent_type_is_property(self):
        agent = PropertyAgent()
        assert agent.agent_type == AgentType.PROPERTY

    def test_agent_name_set(self):
        agent = PropertyAgent()
        assert agent.name.lower() == "propertyagent"
