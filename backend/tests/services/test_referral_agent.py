"""Deterministic tests for the won-only referral agent."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.agents import referral_agent_instance
from app.services.agents.referral import ReferralAgent
from app.services.agents.supervisor import AgentSupervisor
from app.services.agents.types import AgentContext, AgentType
from app.models.campaign import Campaign, CampaignChannel, CampaignTrigger
from app.models.lead import Lead
from app.services.campaigns.service import CampaignService
from app.tasks.referral_tasks import _default_referral_message


def _context(stage: str = "ganado", current_agent: AgentType | None = None) -> AgentContext:
    return AgentContext(
        lead_id=44,
        broker_id=7,
        pipeline_stage=stage,
        conversation_state="COMPLETED",
        lead_data={
            "name": "Paula",
            "broker_name": "Broker Test",
            "agent_name": "Sofía",
            "referral_status": "pending",
            "referral_lead_ids": [],
        },
        message_history=[],
        current_agent=current_agent,
    )


@pytest.mark.asyncio
async def test_referral_agent_handles_only_won_leads():
    agent = ReferralAgent()
    assert await agent.should_handle(_context("ganado")) is True
    assert await agent.should_handle(_context("agendado")) is False
    assert await agent.should_handle(_context("perdido")) is False


@pytest.mark.asyncio
async def test_won_stage_overrides_previous_sticky_agent():
    selected = await AgentSupervisor._select_agent(
        _context("ganado", current_agent=AgentType.FOLLOW_UP)
    )
    assert selected is referral_agent_instance


@pytest.mark.asyncio
async def test_register_tool_passes_name_and_phone_to_referral_service():
    agent = ReferralAgent()
    db = MagicMock()

    async def fake_generate(**kwargs):
        result = await kwargs["tool_executor"](
            "register_referral",
            {"name": "Diego Soto", "phone": "+56912345678"},
        )
        assert result["status"] == "ok"
        return "Muchas gracias, ya quedó registrado.", [
            {"name": "register_referral"}
        ]

    with (
        patch(
            "app.services.llm.facade.LLMServiceFacade.generate_response_with_function_calling",
            side_effect=fake_generate,
        ),
        patch(
            "app.services.leads.referral_service.ReferralService.register",
            AsyncMock(return_value={"lead_id": 55, "created": True, "name": "Diego Soto"}),
        ) as register,
    ):
        response = await agent.process("Diego Soto, +56912345678", _context(), db)

    register.assert_awaited_once_with(
        db,
        source_lead_id=44,
        broker_id=7,
        name="Diego Soto",
        phone="+56912345678",
    )
    assert response.agent_type == AgentType.REFERRAL
    assert response.context_updates["referral_status"] == "collected"


@pytest.mark.asyncio
async def test_decline_tool_stops_future_requests():
    agent = ReferralAgent()
    db = MagicMock()

    async def fake_generate(**kwargs):
        await kwargs["tool_executor"]("decline_referral", {})
        return "Sin problema, gracias por responder.", []

    with (
        patch(
            "app.services.llm.facade.LLMServiceFacade.generate_response_with_function_calling",
            side_effect=fake_generate,
        ),
        patch(
            "app.services.leads.referral_service.ReferralService.decline",
            AsyncMock(),
        ) as decline,
    ):
        response = await agent.process("Prefiero que no", _context(), db)

    decline.assert_awaited_once_with(db, source_lead_id=44, broker_id=7)
    assert response.context_updates["referral_status"] == "declined"


@pytest.mark.asyncio
async def test_llm_failure_does_not_ask_again_after_decline():
    agent = ReferralAgent()
    ctx = _context()
    ctx.lead_data["referral_status"] = "declined"
    with patch(
        "app.services.llm.facade.LLMServiceFacade.generate_response_with_function_calling",
        AsyncMock(side_effect=RuntimeError("timeout")),
    ):
        response = await agent.process("Gracias", ctx, MagicMock())
    assert "no volveré a insistir" in response.message.lower()
    assert "nombre y teléfono" not in response.message


def test_default_request_is_gentle_and_asks_only_for_required_contact_data():
    lead = MagicMock()
    lead.name = "Paula"
    lead.phone = "+56999999999"
    message = _default_referral_message(lead)
    assert "nombre y teléfono" in message
    assert "Sin compromiso" in message
    assert "DICOM" not in message
    assert "renta" not in message.lower()


@pytest.mark.asyncio
async def test_referral_campaign_is_forced_to_won_stage():
    db = AsyncMock()
    db.add = MagicMock()
    campaign = await CampaignService.create_campaign(
        db=db,
        name="Referidos postventa",
        channel=CampaignChannel.WHATSAPP,
        broker_id=7,
        triggered_by=CampaignTrigger.MANUAL,
        is_referral_campaign=True,
    )
    assert campaign.is_referral_campaign is True
    assert campaign.triggered_by == CampaignTrigger.STAGE_CHANGE
    assert campaign.trigger_condition == {"stage": "ganado"}


@pytest.mark.asyncio
async def test_campaign_cannot_be_applied_to_lead_from_another_broker():
    campaign = Campaign(
        id=8,
        name="Referidos",
        channel=CampaignChannel.WHATSAPP,
        broker_id=7,
        is_referral_campaign=True,
    )
    lead = Lead(id=9, broker_id=99, phone="+56912345678")

    campaign_result = MagicMock()
    campaign_result.scalars.return_value.first.return_value = campaign
    lead_result = MagicMock()
    lead_result.scalars.return_value.first.return_value = lead
    db = AsyncMock()
    db.execute.side_effect = [campaign_result, lead_result]

    with pytest.raises(ValueError, match="same broker"):
        await CampaignService.apply_campaign_to_lead(db, campaign.id, lead.id)
