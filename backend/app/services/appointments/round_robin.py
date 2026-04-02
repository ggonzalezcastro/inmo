"""
RoundRobinService — assigns leads to agents by least-loaded round-robin.

Selection logic:
  1. Agents of the broker that are active (is_active=True)
  2. Priority: agents with google_calendar_connected=True first
  3. Among them, order by appointment count (last 30 days) ASC
  4. Tie-break: Redis circular rotation to ensure fair distribution
  5. Fallback: if no agents have calendar connected, use all active agents
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import func, select, and_, outerjoin
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

REDIS_PREFIX = "round_robin:"
REDIS_TTL = 7 * 24 * 3600  # 7 days


class RoundRobinService:

    @staticmethod
    async def get_next_agent(
        db: AsyncSession,
        broker_id: int,
    ):
        """
        Return the next agent to assign using least-loaded round-robin.

        Priority order:
          1. Active agents with google_calendar_connected=True (have their own calendar)
          2. All active agents of the broker (fallback, event goes to broker calendar)

        Among the selected pool, pick the one with fewest appointments in the
        last 30 days. Ties are broken via a Redis-backed circular index so every
        agent gets turns in order even when load is equal.
        """
        from app.models.user import User, UserRole
        from app.models.appointment import Appointment, AppointmentStatus

        cutoff = datetime.utcnow() - timedelta(days=30)

        # Sub-query: count scheduled/confirmed appointments per agent in last 30d
        appt_count_sq = (
            select(
                Appointment.agent_id,
                func.count(Appointment.id).label("appt_count"),
            )
            .where(
                and_(
                    Appointment.start_time >= cutoff,
                    Appointment.status.in_([
                        AppointmentStatus.SCHEDULED,
                        AppointmentStatus.CONFIRMED,
                    ]),
                )
            )
            .group_by(Appointment.agent_id)
            .subquery()
        )

        # First try: agents with calendar connected
        for calendar_only in (True, False):
            conditions = [
                User.broker_id == broker_id,
                User.is_active == True,
                User.role == UserRole.AGENT,
            ]
            if calendar_only:
                conditions.append(User.google_calendar_connected == True)

            result = await db.execute(
                select(User, func.coalesce(appt_count_sq.c.appt_count, 0).label("load"))
                .outerjoin(appt_count_sq, User.id == appt_count_sq.c.agent_id)
                .where(and_(*conditions))
                .order_by(func.coalesce(appt_count_sq.c.appt_count, 0).asc(), User.id.asc())
            )
            rows = result.all()

            if rows:
                agent = await RoundRobinService._pick_with_rotation(broker_id, rows)
                logger.info(
                    "RoundRobin: broker=%s selected agent=%s (load=%s, calendar_only=%s)",
                    broker_id, agent.id, next((r[1] for r in rows if r[0].id == agent.id), 0), calendar_only,
                )
                return agent

        logger.warning("RoundRobin: no active agents found for broker=%s", broker_id)
        return None

    @staticmethod
    async def _pick_with_rotation(broker_id: int, rows: list):
        """
        Given a list of (User, load) ordered by load ASC, pick the next agent
        using Redis to break ties in a circular fashion.
        Falls back to the first row if Redis is unavailable.
        """
        try:
            from app.core.cache import cache_get, cache_set

            redis_key = f"{REDIS_PREFIX}{broker_id}"
            cached = await cache_get(redis_key)
            last_agent_id = int(cached) if cached else None

            # Build ordered list of agent IDs (already sorted by load)
            agent_ids = [r[0].id for r in rows]
            agent_map = {r[0].id: r[0] for r in rows}

            if last_agent_id and last_agent_id in agent_ids:
                # Find index of last assigned and pick next in circular order
                # But only rotate among agents with the SAME minimum load
                min_load = rows[0][1]
                min_load_ids = [r[0].id for r in rows if r[1] == min_load]

                if last_agent_id in min_load_ids:
                    idx = min_load_ids.index(last_agent_id)
                    next_id = min_load_ids[(idx + 1) % len(min_load_ids)]
                else:
                    next_id = min_load_ids[0]
            else:
                next_id = agent_ids[0]

            await cache_set(redis_key, str(next_id), REDIS_TTL)
            return agent_map[next_id]

        except Exception as exc:
            logger.warning("RoundRobin Redis unavailable (%s), using first agent", exc)
            return rows[0][0]

    @staticmethod
    async def get_agents_workload(
        db: AsyncSession,
        broker_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Return workload data for all agents of a broker.
        Used by the admin dashboard endpoint GET /agents/workload.
        """
        from app.models.user import User, UserRole
        from app.models.appointment import Appointment, AppointmentStatus
        from app.models.lead import Lead

        cutoff = datetime.utcnow() - timedelta(days=30)

        # Appointment counts
        appt_sq = (
            select(
                Appointment.agent_id,
                func.count(Appointment.id).label("appt_count"),
            )
            .where(
                and_(
                    Appointment.start_time >= cutoff,
                    Appointment.status.in_([
                        AppointmentStatus.SCHEDULED,
                        AppointmentStatus.CONFIRMED,
                    ]),
                )
            )
            .group_by(Appointment.agent_id)
            .subquery()
        )

        # Lead counts
        lead_sq = (
            select(
                Lead.assigned_to,
                func.count(Lead.id).label("lead_count"),
            )
            .where(Lead.assigned_to.isnot(None))
            .group_by(Lead.assigned_to)
            .subquery()
        )

        result = await db.execute(
            select(
                User,
                func.coalesce(appt_sq.c.appt_count, 0).label("appointments_30d"),
                func.coalesce(lead_sq.c.lead_count, 0).label("leads_assigned"),
            )
            .outerjoin(appt_sq, User.id == appt_sq.c.agent_id)
            .outerjoin(lead_sq, User.id == lead_sq.c.assigned_to)
            .where(
                and_(
                    User.broker_id == broker_id,
                    User.role == UserRole.AGENT,
                    User.is_active == True,
                )
            )
            .order_by(User.name.asc())
        )
        rows = result.all()

        return [
            {
                "id": row[0].id,
                "name": row[0].name,
                "email": row[0].email,
                "appointments_30d": int(row[1]),
                "leads_assigned": int(row[2]),
                "calendar_connected": row[0].google_calendar_connected,
                "calendar_id": row[0].google_calendar_id,
            }
            for row in rows
        ]
