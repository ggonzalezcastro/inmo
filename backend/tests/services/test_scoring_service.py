"""
Tests for ScoringService - lead scoring algorithm.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import UTC, datetime, timedelta, timezone

from app.services.leads import ScoringService
from app.models.lead import Lead, LeadStatus


def _lead_for_profile(**overrides):
    lead = MagicMock(spec=Lead)
    lead.name = None
    lead.phone = None
    lead.lead_metadata = {}
    lead.pipeline_stage = None
    lead.last_contacted = None
    for key, value in overrides.items():
        setattr(lead, key, value)
    return lead


class TestScoringKeyProfile:
    """Test the current financial-first model's profile component."""

    def test_empty_profile_returns_zero(self):
        assert ScoringService._calculate_key_profile(_lead_for_profile()) == 0

    def test_name_returns_5(self):
        lead = _lead_for_profile(name="Juan")
        assert ScoringService._calculate_key_profile(lead) == 5

    def test_valid_phone_returns_10(self):
        lead = _lead_for_profile(phone="+56912345678")
        assert ScoringService._calculate_key_profile(lead) == 10

    def test_income_returns_10(self):
        lead = _lead_for_profile(lead_metadata={"monthly_income": 1_500_000})
        assert ScoringService._calculate_key_profile(lead) == 10

    def test_complete_profile_is_capped_at_25(self):
        lead = _lead_for_profile(
            name="Juan",
            phone="+56912345678",
            lead_metadata={"monthly_income": 1_500_000},
        )
        assert ScoringService._calculate_key_profile(lead) == 25


class TestScoringEngagement:
    """Test the current engagement bonus (0-15)."""

    def test_empty_activities_returns_zero(self):
        assert ScoringService._calculate_engagement_bonus([], []) == 0

    def test_three_activities_returns_5(self):
        activities = [
            MagicMock(action_type="score_update"),
            MagicMock(action_type="score_update"),
            MagicMock(action_type="score_update"),
        ]
        assert ScoringService._calculate_engagement_bonus([], activities) == 5

    def test_five_messages_returns_5(self):
        messages = [MagicMock(direction="in", created_at=None) for _ in range(5)]
        assert ScoringService._calculate_engagement_bonus(messages, []) == 5


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
        lead.last_contacted = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=61)
        lead.lead_metadata = {}
        messages = [MagicMock(message_text="hi")]
        assert ScoringService._calculate_penalties(lead, messages) == 5

    def test_inactive_timezone_aware_date_adds_5(self):
        lead = MagicMock(spec=Lead)
        lead.last_contacted = datetime.now(timezone.utc) - timedelta(days=61)
        lead.lead_metadata = {}
        messages = [MagicMock(message_text="hi")]
        assert ScoringService._calculate_penalties(lead, messages) == 5


class TestScoringStageIndependence:
    """Pipeline stage no longer adds points to the financial-first score."""

    @pytest.mark.parametrize("stage", [None, "entrada", "ganado", "perdido"])
    @pytest.mark.asyncio
    async def test_stage_component_is_zero(self, stage):
        lead = _lead_for_profile(pipeline_stage=stage)
        db = AsyncMock()

        with patch.object(
            ScoringService,
            "_calculate_financial_score",
            new_callable=AsyncMock,
            return_value=0,
        ):
            result = await ScoringService._compute_score_components(
                db, lead, [], [], broker_id=None
            )
        assert result["stage"] == 0


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

        with patch(
            "app.services.broker.BrokerConfigService.calculate_financial_score",
            new_callable=AsyncMock,
            return_value=0,
        ):
            result = await ScoringService.calculate_lead_score_from_lead(
                db_session, lead, broker_id=None, messages=[msg], activities=[]
            )
        assert "total" in result
        assert 0 <= result["total"] <= 100
        assert result["base"] >= 0
        assert result["behavior"] >= 0
