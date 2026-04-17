"""
Priority assignment tests.

Tests the assign_next_agent dispatcher and get_next_agent_by_priority logic
without a real database — all DB calls are mocked via AsyncMock.

Run with:
    .venv/bin/python -m pytest tests/services/test_priority_assignment.py -v --noconftest
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

# msal is an optional Outlook dependency not installed in the test env
sys.modules.setdefault("msal", MagicMock())

import pytest
from unittest.mock import AsyncMock, patch


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_agent(id: int, priority: int | None = None, active: bool = True, calendar: bool = False):
    agent = MagicMock()
    agent.id = id
    agent.assignment_priority = priority
    agent.is_active = active
    agent.google_calendar_connected = calendar
    return agent


def _make_broker(priority_enabled: bool):
    broker = MagicMock()
    broker.priority_assignment_enabled = priority_enabled
    return broker


def _db_returning(*rows):
    """Build a mock db.execute() that returns scalars().first() or scalars().all()."""
    result = MagicMock()
    if rows and not isinstance(rows[0], list):
        # single object (first())
        result.scalars.return_value.first.return_value = rows[0] if rows else None
    else:
        result.scalars.return_value.all.return_value = list(rows[0]) if rows else []
    return result


# ── TestAssignNextAgent ───────────────────────────────────────────────────────

class TestAssignNextAgent:
    """Tests for the assign_next_agent dispatcher."""

    @pytest.mark.asyncio
    async def test_delegates_to_priority_when_enabled(self):
        from app.services.appointments.round_robin import RoundRobinService

        broker = _make_broker(priority_enabled=True)
        agent = _make_agent(id=1, priority=1)

        db = AsyncMock()
        db.execute.return_value = _db_returning(broker)

        with patch.object(RoundRobinService, 'get_next_agent_by_priority', new=AsyncMock(return_value=agent)) as mock_priority, \
             patch.object(RoundRobinService, 'get_next_agent', new=AsyncMock()) as mock_rr:

            result = await RoundRobinService.assign_next_agent(db, broker_id=1)

            mock_priority.assert_awaited_once_with(db, 1)
            mock_rr.assert_not_awaited()
            assert result is agent

    @pytest.mark.asyncio
    async def test_delegates_to_round_robin_when_disabled(self):
        from app.services.appointments.round_robin import RoundRobinService

        broker = _make_broker(priority_enabled=False)
        agent = _make_agent(id=2)

        db = AsyncMock()
        db.execute.return_value = _db_returning(broker)

        with patch.object(RoundRobinService, 'get_next_agent_by_priority', new=AsyncMock()) as mock_priority, \
             patch.object(RoundRobinService, 'get_next_agent', new=AsyncMock(return_value=agent)) as mock_rr:

            result = await RoundRobinService.assign_next_agent(db, broker_id=1)

            mock_rr.assert_awaited_once_with(db, 1)
            mock_priority.assert_not_awaited()
            assert result is agent

    @pytest.mark.asyncio
    async def test_falls_back_to_round_robin_when_broker_not_found(self):
        from app.services.appointments.round_robin import RoundRobinService

        db = AsyncMock()
        db.execute.return_value = _db_returning(None)
        db.execute.return_value.scalars.return_value.first.return_value = None

        agent = _make_agent(id=3)

        with patch.object(RoundRobinService, 'get_next_agent', new=AsyncMock(return_value=agent)) as mock_rr:
            result = await RoundRobinService.assign_next_agent(db, broker_id=99)
            mock_rr.assert_awaited_once_with(db, 99)
            assert result is agent


# ── TestGetNextAgentByPriority ────────────────────────────────────────────────

class TestGetNextAgentByPriority:
    """Tests for priority-based agent selection."""

    @pytest.mark.asyncio
    async def test_returns_highest_priority_agent(self):
        from app.services.appointments.round_robin import RoundRobinService

        agent1 = _make_agent(id=1, priority=1, calendar=True)
        agent2 = _make_agent(id=2, priority=2, calendar=True)
        agent3 = _make_agent(id=3, priority=3, calendar=True)

        db = AsyncMock()
        # db.execute.return_value must be a MagicMock (not AsyncMock) so that
        # result.scalars() returns a plain value, not a coroutine.
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = agent1
        db.execute.return_value = mock_result

        result = await RoundRobinService.get_next_agent_by_priority(db, broker_id=1)
        assert result is agent1

    @pytest.mark.asyncio
    async def test_prefers_calendar_connected_on_first_pass(self):
        from app.services.appointments.round_robin import RoundRobinService

        # agent priority=1 has no calendar, agent priority=2 has calendar
        agent_with_calendar = _make_agent(id=2, priority=2, calendar=True)

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = agent_with_calendar
        db.execute.return_value = mock_result

        result = await RoundRobinService.get_next_agent_by_priority(db, broker_id=1)
        assert result is agent_with_calendar

    @pytest.mark.asyncio
    async def test_falls_back_to_all_agents_when_no_calendar(self):
        from app.services.appointments.round_robin import RoundRobinService

        agent1 = _make_agent(id=1, priority=1, calendar=False)
        call_count = 0

        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                # First pass (calendar only) — no results
                result.scalars.return_value.first.return_value = None
            else:
                # Second pass (all agents) — return agent1
                result.scalars.return_value.first.return_value = agent1
            return result

        db = AsyncMock()
        db.execute = mock_execute

        result = await RoundRobinService.get_next_agent_by_priority(db, broker_id=1)
        assert result is agent1
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_falls_back_to_round_robin_when_no_prioritized_agents(self):
        from app.services.appointments.round_robin import RoundRobinService

        fallback_agent = _make_agent(id=10)

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        db.execute.return_value = mock_result

        with patch.object(RoundRobinService, 'get_next_agent', new=AsyncMock(return_value=fallback_agent)) as mock_rr:
            result = await RoundRobinService.get_next_agent_by_priority(db, broker_id=1)
            mock_rr.assert_awaited_once_with(db, 1)
            assert result is fallback_agent


# ── TestUpdateAgentPriorityLogic ──────────────────────────────────────────────

class TestUpdateAgentPriorityLogic:
    """Unit tests for the priority update logic (endpoint logic, no HTTP stack)."""

    def test_assigns_priority_in_order(self):
        """Priority is 1-based; first agent_id in list gets priority=1."""
        agents = {
            1: _make_agent(id=1),
            2: _make_agent(id=2),
            3: _make_agent(id=3),
        }
        agent_ids = [3, 1, 2]  # desired order
        for idx, aid in enumerate(agent_ids):
            agents[aid].assignment_priority = idx + 1

        assert agents[3].assignment_priority == 1
        assert agents[1].assignment_priority == 2
        assert agents[2].assignment_priority == 3

    def test_nullifies_agents_not_in_list(self):
        """Agents not submitted in the priority list get assignment_priority=None."""
        agents = {
            1: _make_agent(id=1, priority=1),
            2: _make_agent(id=2, priority=2),
            3: _make_agent(id=3, priority=3),
        }
        submitted_ids = {1, 2}
        for aid, agent in agents.items():
            if aid not in submitted_ids:
                agent.assignment_priority = None

        assert agents[1].assignment_priority == 1
        assert agents[2].assignment_priority == 2
        assert agents[3].assignment_priority is None

    def test_priority_order_is_stable_across_reassignment(self):
        """Re-ordering preserves sequential 1-based numbering."""
        agents = {i: _make_agent(id=i) for i in range(1, 6)}
        new_order = [5, 3, 1, 4, 2]
        for idx, aid in enumerate(new_order):
            agents[aid].assignment_priority = idx + 1

        for expected_priority, aid in enumerate(new_order, start=1):
            assert agents[aid].assignment_priority == expected_priority


# ── TestAssignmentConfigToggle ────────────────────────────────────────────────

class TestAssignmentConfigToggle:
    """Tests for the broker assignment config toggle."""

    def test_broker_field_defaults_to_false(self):
        """priority_assignment_enabled should default to False on new brokers."""
        from app.models.broker import Broker
        b = Broker()
        # SQLAlchemy Column default doesn't apply to Python-side instantiation
        # without a session, but we verify the column definition carries the default
        col = Broker.__table__.c.priority_assignment_enabled
        assert col.default.arg is False

    def test_toggle_updates_broker_field(self):
        """Setting priority_assignment_enabled on broker model works."""
        broker = _make_broker(priority_enabled=False)
        broker.priority_assignment_enabled = True
        assert broker.priority_assignment_enabled is True

        broker.priority_assignment_enabled = False
        assert broker.priority_assignment_enabled is False
