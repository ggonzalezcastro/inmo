"""Single lead-assignment path shared by Leads and Pipeline APIs."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.websocket_manager import ws_manager
from app.models.activity_log import ActivityLog
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.lead_follow_up import LeadTask, TASK_ACTIVE_STATUSES
from app.models.user import User, UserRole


class LeadAssignmentService:
    @staticmethod
    async def assign_automatically(
        db: AsyncSession,
        *,
        lead: Lead,
        reason: str,
    ) -> Optional[int]:
        """Internal assignment path for newly captured leads.

        Priority-enabled brokers use the explicit priority queue. Other brokers
        use the active agent with the smallest current open-lead workload.
        """
        if not lead.broker_id or lead.assigned_to is not None:
            return lead.assigned_to
        broker = await db.scalar(select(Broker).where(Broker.id == lead.broker_id))
        if not broker:
            return None

        if broker.priority_assignment_enabled:
            agent = await db.scalar(
                select(User)
                .where(
                    User.broker_id == lead.broker_id,
                    User.role == UserRole.AGENT,
                    User.is_active.is_(True),
                    User.assignment_priority.isnot(None),
                )
                .order_by(User.assignment_priority.asc(), User.id.asc())
                .limit(1)
            )
        else:
            workload = (
                select(
                    Lead.assigned_to.label("agent_id"),
                    func.count(Lead.id).label("open_count"),
                )
                .where(
                    Lead.broker_id == lead.broker_id,
                    Lead.assigned_to.isnot(None),
                    or_(
                        Lead.pipeline_stage.is_(None),
                        Lead.pipeline_stage.notin_(["ganado", "perdido"]),
                    ),
                )
                .group_by(Lead.assigned_to)
                .subquery()
            )
            agent = await db.scalar(
                select(User)
                .outerjoin(workload, workload.c.agent_id == User.id)
                .where(
                    User.broker_id == lead.broker_id,
                    User.role == UserRole.AGENT,
                    User.is_active.is_(True),
                )
                .order_by(func.coalesce(workload.c.open_count, 0).asc(), User.id.asc())
                .limit(1)
            )
        if not agent:
            return None

        lead.assigned_to = agent.id
        db.add(ActivityLog(
            lead_id=lead.id,
            action_type="agent_assigned",
            details={
                "old_agent_id": None,
                "new_agent_id": agent.id,
                "agent_name": agent.name,
                "assigned_by": "system",
                "reason": reason,
            },
            timestamp=datetime.now(timezone.utc),
        ))
        await db.commit()
        await ws_manager.broadcast(
            lead.broker_id,
            "lead_assigned",
            {
                "lead_id": lead.id,
                "agent_id": agent.id,
                "agent_name": agent.name,
                "reason": reason,
            },
        )
        return agent.id

    @staticmethod
    async def assign(
        db: AsyncSession,
        *,
        lead_id: int,
        agent_id: Optional[int],
        current_user: dict,
    ) -> dict:
        role = str(current_user.get("role", "")).upper()
        if role == UserRole.SUPERADMIN.value:
            raise HTTPException(
                status_code=403,
                detail="Usa impersonación de broker para asignar ejecutivos",
            )
        if role != UserRole.ADMIN.value:
            raise HTTPException(status_code=403, detail="Se requiere rol de administrador")

        broker_id = current_user.get("broker_id")
        if not broker_id:
            raise HTTPException(status_code=400, detail="Usuario sin broker asignado")

        lead = await db.scalar(
            select(Lead).where(Lead.id == lead_id, Lead.broker_id == int(broker_id))
        )
        if lead is None:
            raise HTTPException(status_code=404, detail="Lead no encontrado")

        agent = None
        if agent_id is not None:
            agent = await db.scalar(
                select(User).where(
                    User.id == agent_id,
                    User.broker_id == lead.broker_id,
                    User.role == UserRole.AGENT,
                    User.is_active.is_(True),
                )
            )
            if agent is None:
                raise HTTPException(
                    status_code=422,
                    detail="El responsable debe ser un ejecutivo activo del mismo broker",
                )

        old_agent_id = lead.assigned_to
        lead.assigned_to = agent_id
        active_tasks = list((await db.scalars(
            select(LeadTask).where(
                LeadTask.lead_id == lead.id,
                LeadTask.broker_id == lead.broker_id,
                LeadTask.status.in_(TASK_ACTIVE_STATUSES),
            )
        )).all())
        for task in active_tasks:
            previous_task_assignee = task.assigned_to
            task.assigned_to = agent_id
            task.reminder_sent_at = None
            task.reminder_acknowledged_at = None
            if previous_task_assignee != agent_id:
                db.add(ActivityLog(
                    lead_id=lead.id,
                    action_type="lead_task_reassigned",
                    details={
                        "task_id": task.id,
                        "reassigned_by": current_user.get("user_id"),
                        "old_assigned_to": previous_task_assignee,
                        "new_assigned_to": agent_id,
                        "reason": "lead_reassigned",
                    },
                    timestamp=datetime.now(timezone.utc),
                ))
        transferred_tasks = len(active_tasks)

        db.add(ActivityLog(
            lead_id=lead.id,
            action_type="agent_assigned",
            details={
                "old_agent_id": old_agent_id,
                "new_agent_id": agent_id,
                "agent_name": agent.name if agent else None,
                "assigned_by": current_user.get("user_id"),
                "transferred_open_tasks": transferred_tasks,
            },
            timestamp=datetime.now(timezone.utc),
        ))
        await db.commit()

        await ws_manager.broadcast(
            lead.broker_id,
            "lead_assigned",
            {
                "lead_id": lead.id,
                "agent_id": agent_id,
                "agent_name": agent.name if agent else None,
                "transferred_open_tasks": transferred_tasks,
            },
        )
        if transferred_tasks:
            await ws_manager.broadcast(
                lead.broker_id,
                "lead_task_changed",
                {
                    "lead_id": lead.id,
                    "assigned_to": agent_id,
                    "action": "lead_reassigned",
                    "count": transferred_tasks,
                },
            )

        return {
            "message": "Ejecutivo asignado",
            "lead_id": lead.id,
            "agent_id": agent_id,
            "agent_name": agent.name if agent else None,
            "transferred_open_tasks": transferred_tasks,
        }
