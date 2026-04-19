"""
Tests for ScoringService - lead scoring algorithm.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta

from app.services.leads import ScoringService
from app.models.lead import Lead, LeadStatus


class TestScoringBaseInteraction:
    """Test _calculate_base_interaction"""

    def test_zero_messages_returns_zero(self):
        assert ScoringService._calculate_base_interaction([]) == 0

    def test_one_message_returns_5(self):
        msg = MagicMock()
        assert ScoringService._calculate_base_interaction([msg]) == 5

    def test_two_messages_returns_10(self):
        msg1, msg2 = MagicMock(), MagicMock()
        assert ScoringService._calculate_base_interaction([msg1, msg2]) == 10

    def test_five_messages_returns_17(self):
        msgs = [MagicMock() for _ in range(5)]
        assert ScoringService._calculate_base_interaction(msgs) == 17

    def test_capped_at_30(self):
        msgs = [MagicMock() for _ in range(100)]
        assert ScoringService._calculate_base_interaction(msgs) <= 30


class TestScoringEngagement:
    """Test _calculate_engagement"""

    def test_empty_activities_returns_zero(self):
        assert ScoringService._calculate_engagement([]) == 0

    def test_three_score_updates_returns_8(self):
        activities = [
            MagicMock(action_type="score_update"),
            MagicMock(action_type="score_update"),
            MagicMock(action_type="score_update"),
        ]
        assert ScoringService._calculate_engagement(activities) == 8

    def test_five_message_activities_returns_6(self):
        activities = [MagicMock(action_type="message") for _ in range(5)]
        assert ScoringService._calculate_engagement(activities) == 6


class TestScoringPenalties:
    """Test _calculate_penalties"""

    def test_no_penalties_returns_zero(self):
        lead = MagicMock(spec=Lead)
        lead.last_contacted = None
        lead.lead_metadata = {}
        messages = [MagicMock(message_text="hello")]
        assert ScoringService._calculate_penalties(lead, messages) == 0

    def test_no_llamar_returns_30(self):
        lead = MagicMock(spec=Lead)
        lead.last_contacted = None
        lead.lead_metadata = {}
        messages = [MagicMock(message_text="no llamar por favor")]
        assert ScoringService._calculate_penalties(lead, messages) == 30

    def test_inactive_60_days_adds_5(self):
        lead = MagicMock(spec=Lead)
        lead.last_contacted = datetime.utcnow() - timedelta(days=61)
        lead.lead_metadata = {}
        messages = [MagicMock(message_text="hi")]
        assert ScoringService._calculate_penalties(lead, messages) == 5


class TestScoringStageScore:
    """Test _calculate_stage_score"""

    def test_no_stage_returns_zero(self):
        lead = MagicMock(spec=Lead)
        lead.pipeline_stage = None
        lead.lead_metadata = {}
        assert ScoringService._calculate_stage_score(lead) == 0

    def test_entrada_returns_2(self):
        lead = MagicMock(spec=Lead)
        lead.pipeline_stage = "entrada"
        lead.lead_metadata = {}
        assert ScoringService._calculate_stage_score(lead) == 2

    def test_ganado_returns_20(self):
        lead = MagicMock(spec=Lead)
        lead.pipeline_stage = "ganado"
        lead.lead_metadata = {}
        assert ScoringService._calculate_stage_score(lead) == 20

    def test_perdido_returns_negative(self):
        lead = MagicMock(spec=Lead)
        lead.pipeline_stage = "perdido"
        lead.lead_metadata = {}
        assert ScoringService._calculate_stage_score(lead) == -10


class TestScoringIntegration:
    """Integration-style tests for calculate_lead_score (with mocked DB)"""

    @pytest.mark.asyncio
    async def test_calculate_lead_score_lead_not_found(self, db_session):
        with pytest.raises(ValueError, match="not found"):
            await ScoringService.calculate_lead_score(db_session, 99999)

    @pytest.mark.asyncio
    async def test_calculate_lead_score_from_lead_uses_relations(self, db_session):
        from app.models.lead import Lead
        from app.models.telegram_message import TelegramMessage, MessageDirection

        lead = Lead(
            phone="+56912345678",
            name="Test",
            status=LeadStatus.COLD,
            lead_score=0,
            broker_id=None,
        )
        db_session.add(lead)
        await db_session.commit()
        await db_session.refresh(lead)

        msg = TelegramMessage(
            lead_id=lead.id,
            telegram_user_id=1,
            message_text="Hola",
            direction=MessageDirection.INBOUND,
        )
        db_session.add(msg)
        await db_session.commit()

        with patch("app.services.broker_config_service.BrokerConfigService.calculate_financial_score", new_callable=AsyncMock, return_value=0):
            result = await ScoringService.calculate_lead_score_from_lead(
                db_session, lead, broker_id=None, messages=[msg], activities=[]
            )
        assert "total" in result
        assert 0 <= result["total"] <= 100
        assert result["base"] >= 0
        assert result["behavior"] >= 0
