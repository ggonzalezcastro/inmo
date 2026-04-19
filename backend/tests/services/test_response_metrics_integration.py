"""Integration test for ``update_lead_response_metrics``.

Exercises the full helper used by both the chat orchestrator (on_message)
and the daily Celery scoring task. Uses a dedicated SQLite in-memory
engine so it doesn't collide with the global conftest fixtures (which
have a pre-existing ``index already exists`` issue under StaticPool).

Run from the backend container::

    docker compose exec backend python -m pytest \
        tests/services/test_response_metrics_integration.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.future import select
from sqlalchemy.sql.functions import now

from app.models.base import Base
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.telegram_message import MessageDirection, TelegramMessage
from app.services.leads.constants import FAST_RESPONDER_TAG
from app.services.leads.response_metrics import update_lead_response_metrics


# ── SQLite compatibility shims (mirroring conftest.py) ───────────────────────

@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):  # pragma: no cover
    return "JSON"


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):  # pragma: no cover
    return "VARCHAR(36)"


@compiles(now, "sqlite")
def _compile_now_sqlite(element, compiler, **kw):  # pragma: no cover
    return "datetime('now')"


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dedicated engine + session for these tests (avoids global conftest collisions)."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    # Only create the subset of tables this test needs. Avoids a pre-existing
    # model issue where ``agent_model_configs`` declares the same index twice
    # (column index=True AND explicit Index in __table_args__).
    needed = [
        Broker.__table__,
        Lead.__table__,
        TelegramMessage.__table__,
    ]
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=needed))

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
        await session.rollback()

    await engine.dispose()


async def _seed_lead(db_session, *, tags=None):
    broker = Broker(name="Inmobiliaria Test")
    db_session.add(broker)
    await db_session.flush()

    lead = Lead(
        phone="+56911112222",
        name="Test Lead",
        broker_id=broker.id,
        tags=tags or [],
        lead_metadata={},
    )
    db_session.add(lead)
    await db_session.flush()
    return broker, lead


async def _add_messages(db_session, lead_id: int, sequence):
    """``sequence`` = list of (direction, offset_seconds_from_base) pairs."""
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    for direction, offset in sequence:
        msg = TelegramMessage(
            lead_id=lead_id,
            telegram_user_id=12345,
            message_text=f"msg {direction}@{offset}",
            direction=MessageDirection(direction),
            created_at=base + timedelta(seconds=offset),
        )
        db_session.add(msg)
    await db_session.flush()


async def test_fast_responder_applies_tag_and_persists_metrics(db_session):
    """3 quick replies (≤60s avg) should add the ``respuesta_rapida`` tag
    and persist ``response_metrics`` into ``lead_metadata``."""
    _, lead = await _seed_lead(db_session)
    # OUT/IN/OUT/IN/OUT/IN with deltas of 10s, 20s, 15s
    await _add_messages(db_session, lead.id, [
        ("out", 0), ("in", 10),
        ("out", 60), ("in", 80),
        ("out", 120), ("in", 135),
    ])

    result = await update_lead_response_metrics(db_session, lead.id)
    await db_session.commit()

    assert result["metrics"]["reply_count"] == 3
    assert result["metrics"]["is_fast_responder"] is True
    assert result["tag_changed"] is True
    assert result["applied"] is True

    fresh = (await db_session.execute(select(Lead).where(Lead.id == lead.id))).scalars().first()
    assert FAST_RESPONDER_TAG in (fresh.tags or [])
    assert "response_metrics" in (fresh.lead_metadata or {})
    assert fresh.lead_metadata["response_metrics"]["reply_count"] == 3
    assert fresh.lead_metadata["response_metrics"]["is_fast_responder"] is True


async def test_slow_responder_does_not_tag(db_session):
    _, lead = await _seed_lead(db_session)
    # Replies all >60s: 300s, 400s, 500s
    await _add_messages(db_session, lead.id, [
        ("out", 0), ("in", 300),
        ("out", 1000), ("in", 1400),
        ("out", 2000), ("in", 2500),
    ])

    result = await update_lead_response_metrics(db_session, lead.id)
    await db_session.commit()

    assert result["metrics"]["reply_count"] == 3
    assert result["metrics"]["is_fast_responder"] is False
    assert result["tag_changed"] is False
    assert result["applied"] is False

    fresh = (await db_session.execute(select(Lead).where(Lead.id == lead.id))).scalars().first()
    assert FAST_RESPONDER_TAG not in (fresh.tags or [])
    # Metrics still persisted even when tag does not apply.
    assert fresh.lead_metadata["response_metrics"]["reply_count"] == 3


async def test_min_replies_not_reached_does_not_tag(db_session):
    _, lead = await _seed_lead(db_session)
    # Only 2 replies, even if very fast.
    await _add_messages(db_session, lead.id, [
        ("out", 0), ("in", 5),
        ("out", 30), ("in", 35),
    ])

    result = await update_lead_response_metrics(db_session, lead.id)
    await db_session.commit()

    assert result["metrics"]["reply_count"] == 2
    assert result["tag_changed"] is False
    fresh = (await db_session.execute(select(Lead).where(Lead.id == lead.id))).scalars().first()
    assert FAST_RESPONDER_TAG not in (fresh.tags or [])


async def test_tag_removed_when_metrics_degrade(db_session):
    """Lead previously tagged but new (slow) messages should drop the tag."""
    _, lead = await _seed_lead(db_session, tags=[FAST_RESPONDER_TAG, "interesado"])
    await _add_messages(db_session, lead.id, [
        ("out", 0), ("in", 600),
        ("out", 1000), ("in", 1700),
        ("out", 2000), ("in", 2900),
    ])

    result = await update_lead_response_metrics(db_session, lead.id)
    await db_session.commit()

    assert result["tag_changed"] is True
    assert result["applied"] is False

    fresh = (await db_session.execute(select(Lead).where(Lead.id == lead.id))).scalars().first()
    assert FAST_RESPONDER_TAG not in (fresh.tags or [])
    assert "interesado" in (fresh.tags or [])  # other tags preserved


async def test_existing_metadata_keys_preserved(db_session):
    """Persisting response_metrics must not clobber other lead_metadata keys."""
    _, lead = await _seed_lead(db_session)
    lead.lead_metadata = {"sentiment": "positive", "budget": "200k"}
    await db_session.flush()

    await _add_messages(db_session, lead.id, [
        ("out", 0), ("in", 5),
        ("out", 30), ("in", 35),
        ("out", 60), ("in", 70),
    ])

    await update_lead_response_metrics(db_session, lead.id)
    await db_session.commit()

    fresh = (await db_session.execute(select(Lead).where(Lead.id == lead.id))).scalars().first()
    md = fresh.lead_metadata or {}
    assert md.get("sentiment") == "positive"
    assert md.get("budget") == "200k"
    assert "response_metrics" in md
    assert md["response_metrics"]["is_fast_responder"] is True


async def test_idempotent_no_changes_on_second_call(db_session):
    _, lead = await _seed_lead(db_session)
    await _add_messages(db_session, lead.id, [
        ("out", 0), ("in", 10),
        ("out", 60), ("in", 80),
        ("out", 120), ("in", 135),
    ])

    first = await update_lead_response_metrics(db_session, lead.id)
    await db_session.commit()
    assert first["tag_changed"] is True

    second = await update_lead_response_metrics(db_session, lead.id)
    await db_session.commit()
    assert second["tag_changed"] is False  # already applied, nothing to change
    assert second["applied"] is True


async def test_no_messages_returns_neutral(db_session):
    _, lead = await _seed_lead(db_session)
    result = await update_lead_response_metrics(db_session, lead.id)
    await db_session.commit()

    assert result["metrics"]["reply_count"] == 0
    assert result["metrics"]["is_fast_responder"] is False
    assert result["tag_changed"] is False


async def test_missing_lead_returns_safely(db_session):
    result = await update_lead_response_metrics(db_session, lead_id=99999)
    assert result["tag_changed"] is False
    assert result["applied"] is False
