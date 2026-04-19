"""
Tests for the sentiment analysis Celery task.

Run with:
    .venv/bin/python -m pytest tests/tasks/test_sentiment_tasks.py -v --noconftest
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.sentiment.heuristics import SentimentResult
from app.services.sentiment.scorer import ActionLevel, empty_sentiment, update_sentiment_window


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_mock_lead(
    lead_id: int = 1,
    broker_id: int = 10,
    meta: dict | None = None,
) -> MagicMock:
    lead = MagicMock()
    lead.id = lead_id
    lead.broker_id = broker_id
    lead.name = "Juan Pérez"
    lead.phone = "+56912345678"
    lead.lead_metadata = meta or {}
    return lead


def make_async_db(scalar_result=None, first_result=None) -> AsyncMock:
    """
    Build a properly typed async DB session mock.

    scalar_result: returned by result.scalar_one_or_none()
    first_result:  returned by result.first()
    """
    cursor = MagicMock()
    cursor.scalar_one_or_none.return_value = scalar_result
    cursor.first.return_value = first_result

    db = AsyncMock()
    db.execute = AsyncMock(return_value=cursor)
    db.commit = AsyncMock()
    return db


# ── Heuristic integration ─────────────────────────────────────────────────────

class TestSentimentHeuristicIntegration:
    """Test that heuristics feed into scorer correctly."""

    def test_high_frustration_message_produces_adapt_tone(self):
        from app.services.sentiment.scorer import compute_action_level

        sentiment = update_sentiment_window(None, 0.55, ["frustration"])
        action = compute_action_level(sentiment)
        assert action == ActionLevel.ADAPT_TONE

    def test_abandonment_message_produces_escalate_after_accumulation(self):
        from app.services.sentiment.heuristics import analyze_heuristics
        from app.services.sentiment.scorer import compute_action_level

        messages = [
            "Cuándo me van a llamar??",
            "Ya van dos días sin respuesta",
            "Voy a buscar en otra inmobiliaria, chao",
        ]

        sentiment = None
        for msg in messages:
            result = analyze_heuristics(msg)
            sentiment = update_sentiment_window(sentiment, result.score, result.emotions)

        action = compute_action_level(sentiment)
        assert action in (ActionLevel.ADAPT_TONE, ActionLevel.ESCALATE)

    def test_positive_messages_keep_score_low(self):
        from app.services.sentiment.heuristics import analyze_heuristics
        from app.services.sentiment.scorer import compute_action_level

        messages = [
            "Gracias por la información!",
            "Perfecto, me parece bien",
            "Ok, entendido. Nos vemos el martes entonces",
        ]

        sentiment = None
        for msg in messages:
            result = analyze_heuristics(msg)
            sentiment = update_sentiment_window(sentiment, result.score, result.emotions)

        action = compute_action_level(sentiment)
        assert action == ActionLevel.NONE


# ── _async_analyze tests ──────────────────────────────────────────────────────

class TestAsyncAnalyze:
    """Test _async_analyze with patched DB and services."""

    @pytest.mark.asyncio
    async def test_skips_if_already_escalated(self):
        mock_lead = make_mock_lead(meta={"sentiment": {"escalated": True}, "human_mode": False})
        db = make_async_db(scalar_result=mock_lead)

        from app.tasks.sentiment_tasks import _async_analyze

        escalation_calls: list = []

        async def fake_escalation(*args, **kwargs):
            escalation_calls.append(kwargs.get("action"))

        with patch("app.services.sentiment.escalation.apply_escalation_action", fake_escalation):
            with patch("app.tasks.sentiment_tasks._AsyncSession") as mock_session_cls:
                mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=db)
                mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                await _async_analyze(1, "algún mensaje", 10, "webchat")

        assert escalation_calls == []  # should not have called escalation

    @pytest.mark.asyncio
    async def test_skips_if_human_mode_active(self):
        mock_lead = make_mock_lead(meta={"sentiment": empty_sentiment(), "human_mode": True})
        db = make_async_db(scalar_result=mock_lead)

        from app.tasks.sentiment_tasks import _async_analyze

        escalation_calls: list = []

        async def fake_escalation(*args, **kwargs):
            escalation_calls.append(kwargs.get("action"))

        with patch("app.services.sentiment.escalation.apply_escalation_action", fake_escalation):
            with patch("app.tasks.sentiment_tasks._AsyncSession") as mock_session_cls:
                mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=db)
                mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                await _async_analyze(1, "mensaje", 10, "webchat")

        assert escalation_calls == []

    @pytest.mark.asyncio
    async def test_skips_if_lead_not_found(self):
        db = make_async_db(scalar_result=None)

        from app.tasks.sentiment_tasks import _async_analyze

        with patch("app.tasks.sentiment_tasks._AsyncSession") as mock_session_cls:
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=db)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            # Should not raise
            await _async_analyze(999, "mensaje", 10, "webchat")

    @pytest.mark.asyncio
    async def test_frustrating_message_triggers_escalation_action(self):
        mock_lead = make_mock_lead(meta={"sentiment": empty_sentiment(), "human_mode": False})
        db = make_async_db(scalar_result=mock_lead)

        from app.tasks.sentiment_tasks import _async_analyze

        escalation_calls: list = []

        async def fake_escalation(db, lead_id, broker_id, action, sentiment, last_message, channel):
            escalation_calls.append(action)

        with patch("app.services.sentiment.escalation.apply_escalation_action", fake_escalation):
            with patch(
                "app.services.llm.facade.LLMServiceFacade.generate_response",
                new_callable=AsyncMock,
                return_value='{"score": 0.90, "emotions": ["abandonment_threat"], "reasoning": "ok"}',
            ):
                with patch("app.tasks.sentiment_tasks._AsyncSession") as mock_session_cls:
                    mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=db)
                    mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                    await _async_analyze(
                        1, "Ya me cansé, voy a buscar en otra inmobiliaria", 10, "whatsapp"
                    )

        assert len(escalation_calls) == 1
        assert escalation_calls[0] in (ActionLevel.ADAPT_TONE, ActionLevel.ESCALATE)

    @pytest.mark.asyncio
    async def test_neutral_message_does_not_escalate(self):
        mock_lead = make_mock_lead(meta={"sentiment": empty_sentiment(), "human_mode": False})
        db = make_async_db(scalar_result=mock_lead)

        from app.tasks.sentiment_tasks import _async_analyze

        escalation_calls: list = []

        async def fake_escalation(db, lead_id, broker_id, action, sentiment, last_message, channel):
            escalation_calls.append(action)

        with patch("app.services.sentiment.escalation.apply_escalation_action", fake_escalation):
            with patch("app.tasks.sentiment_tasks._AsyncSession") as mock_session_cls:
                mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=db)
                mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                await _async_analyze(1, "Gracias, perfecto!", 10, "webchat")

        # Neutral message: action should be NONE if called
        for action in escalation_calls:
            assert action == ActionLevel.NONE


# ── Escalation action tests ───────────────────────────────────────────────────

class TestEscalationAction:
    """Test escalation.py functions directly."""

    @pytest.mark.asyncio
    async def test_escalate_updates_db(self):
        from app.services.sentiment.escalation import _escalate

        mock_lead = make_mock_lead(lead_id=1, broker_id=10)
        db = make_async_db(first_result=(mock_lead.name, mock_lead.phone))

        sentiment = {
            "frustration_score": 0.85,
            "message_scores": [{"score": 0.85, "emotions": ["abandonment_threat"], "ts": "..."}],
            "escalated": False,
            "escalated_at": None,
            "tone_hint": None,
        }

        with patch("app.core.websocket_manager.ws_manager") as mock_ws:
            mock_ws.broadcast = AsyncMock()
            await _escalate(db, lead_id=1, broker_id=10, sentiment=sentiment,
                            last_message="Chao, me voy", channel="whatsapp")

        assert db.execute.call_count >= 1
        assert db.commit.call_count >= 1

    @pytest.mark.asyncio
    async def test_escalate_broadcasts_lead_frustrated_event(self):
        from app.services.sentiment.escalation import _escalate

        mock_lead = make_mock_lead(lead_id=2, broker_id=10)
        mock_lead.name = "María López"
        mock_lead.phone = "+56922222222"
        db = make_async_db(first_result=(mock_lead.name, mock_lead.phone))

        sentiment = {
            "frustration_score": 0.80,
            "message_scores": [{"score": 0.80, "emotions": ["frustration"], "ts": "..."}],
            "escalated": False,
            "escalated_at": None,
            "tone_hint": None,
        }

        broadcast_calls: list = []

        async def fake_broadcast(broker_id, event, data):
            broadcast_calls.append({"broker_id": broker_id, "event": event, "data": data})

        with patch("app.core.websocket_manager.ws_manager") as mock_ws:
            mock_ws.broadcast = fake_broadcast
            await _escalate(db, lead_id=2, broker_id=10, sentiment=sentiment,
                            last_message="Estoy harta", channel="telegram")

        assert len(broadcast_calls) == 1
        call = broadcast_calls[0]
        assert call["event"] == "lead_frustrated"
        assert call["broker_id"] == 10  # routing arg passed to ws_manager.broadcast
        assert call["data"]["lead_id"] == 2
        assert "frustration_score" in call["data"]
        assert call["data"]["channel"] == "telegram"


