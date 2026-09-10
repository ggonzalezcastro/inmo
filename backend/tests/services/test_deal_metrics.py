"""Focused tests for sales metric period and tenant scoping helpers."""

import os
from datetime import date, datetime, timezone

os.environ["DEBUG"] = "false"

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.dialects import postgresql  # noqa: E402

from app.models.deal import Deal  # noqa: E402
from app.services.deals.metrics_service import (  # noqa: E402
    _date_bounds,
    _delta_percent,
    _scope,
    _shift_months,
)


def test_date_bounds_include_the_entire_last_day_at_month_end():
    start, end = _date_bounds(date(2026, 1, 1), date(2026, 1, 31))

    assert start == datetime(2026, 1, 1, 3, tzinfo=timezone.utc)
    assert end == datetime(2026, 2, 1, 3, tzinfo=timezone.utc)


def test_month_shift_handles_year_boundaries():
    assert _shift_months(date(2026, 1, 1), -1) == date(2025, 12, 1)
    assert _shift_months(date(2026, 12, 1), 1) == date(2027, 1, 1)


def test_comparison_delta_does_not_invent_a_base_when_previous_is_zero():
    assert _delta_percent(3, 0) is None
    assert _delta_percent(3, 2) == 50.0
    assert _delta_percent(1, 2) == -50.0


def test_agent_scope_filters_broker_and_assigned_leads():
    query = _scope(select(func.count(Deal.id)), broker_id=4, agent_id=7)
    sql = str(
        query.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "deals.broker_id = 4" in sql
    assert "leads.assigned_to = 7" in sql
    assert "leads.broker_id = 4" in sql
