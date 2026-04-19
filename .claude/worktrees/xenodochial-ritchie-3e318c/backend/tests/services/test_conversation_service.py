"""
Tests for ConversationService — lifecycle management without DB.

Run without DB:
    python -m pytest tests/services/test_conversation_service.py -v --noconftest
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


def _mock_db_returning(obj):
    """Build a mock db that returns `obj` from execute().scalar_one_or_none()."""
    db = AsyncMock()
    result = AsyncMock()
    result.scalar_one_or_none = MagicMock(return_value=obj)
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


class TestConversationServiceGetOrCreate:
    @pytest.mark.asyncio
    async def test_returns_existing_conversation(self):
        from app.services.conversations.conversation_service import ConversationService

        existing = MagicMock()
        existing.id = 42
        existing.lead_id = 1

        db = _mock_db_returning(existing)

        conv = await ConversationService.get_or_create(
            db=db, lead_id=1, broker_id=1, channel="telegram"
        )
        assert conv.id == 42

    @pytest.mark.asyncio
    async def test_creates_conversation_when_none_exists(self):
        from app.services.conversations.conversation_service import ConversationService

        db = _mock_db_returning(None)

        conv = await ConversationService.get_or_create(
            db=db, lead_id=5, broker_id=2, channel="whatsapp"
        )
        db.add.assert_called_once()
        created = db.add.call_args[0][0]
        assert created.lead_id == 5
        assert created.broker_id == 2
        assert created.channel == "whatsapp"


class TestConversationServiceHumanMode:
    @pytest.mark.asyncio
    async def test_set_human_mode_true(self):
        from app.services.conversations.conversation_service import ConversationService

        conv = MagicMock()
        conv.human_mode = False
        conv.human_taken_at = None

        db = _mock_db_returning(conv)

        await ConversationService.set_human_mode(
            db=db, conversation_id=1, human_mode=True, assigned_to=7
        )

        assert conv.human_mode is True
        assert conv.human_assigned_to == 7
        assert conv.human_taken_at is not None
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_human_mode_false_clears_fields(self):
        from app.services.conversations.conversation_service import ConversationService

        conv = MagicMock()
        conv.human_mode = True

        db = _mock_db_returning(conv)

        await ConversationService.set_human_mode(
            db=db, conversation_id=1, human_mode=False
        )

        assert conv.human_mode is False
        assert conv.human_assigned_to is None
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_human_mode_noop_on_missing_conv(self):
        from app.services.conversations.conversation_service import ConversationService

        db = _mock_db_returning(None)

        # Should not raise when conversation is not found
        await ConversationService.set_human_mode(db=db, conversation_id=999, human_mode=True)
        db.add.assert_not_called()


class TestConversationServiceLinkMessage:
    @pytest.mark.asyncio
    async def test_link_message_sets_conversation_id(self):
        from app.services.conversations.conversation_service import ConversationService

        msg = MagicMock()
        msg.conversation_id = None

        db = _mock_db_returning(msg)

        await ConversationService.link_message(
            db=db, message_id=10, conversation_id=99
        )

        assert msg.conversation_id == 99
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_link_message_skips_if_message_not_found(self):
        from app.services.conversations.conversation_service import ConversationService

        db = _mock_db_returning(None)

        await ConversationService.link_message(db=db, message_id=999, conversation_id=1)
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_link_message_skips_if_already_linked(self):
        from app.services.conversations.conversation_service import ConversationService

        msg = MagicMock()
        msg.conversation_id = 55  # already linked

        db = _mock_db_returning(msg)

        await ConversationService.link_message(db=db, message_id=1, conversation_id=99)
        db.add.assert_not_called()


class TestConversationServiceOnMessage:
    @pytest.mark.asyncio
    async def test_on_message_increments_count(self):
        from app.services.conversations.conversation_service import ConversationService

        conv = MagicMock()
        conv.message_count = 3

        db = _mock_db_returning(conv)

        await ConversationService.on_message(db=db, conversation_id=1)

        assert conv.message_count == 4
        assert conv.last_message_at is not None
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_message_noop_when_conv_missing(self):
        from app.services.conversations.conversation_service import ConversationService

        db = _mock_db_returning(None)
        await ConversationService.on_message(db=db, conversation_id=999)
        db.add.assert_not_called()

