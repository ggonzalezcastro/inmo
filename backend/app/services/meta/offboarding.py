"""Preserve corporate history while removing an inactive executive from routing."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.websocket_manager import ws_manager
from app.models.activity_log import ActivityLog
from app.models.audit_log import AuditLog
from app.models.conversation import Conversation
from app.models.lead import Lead
from app.models.lead_follow_up import LeadTask, TASK_ACTIVE_STATUSES
from app.models.meta import MetaAsset
from app.models.user import User, UserRole


class MetaExecutiveOffboardingService:
    @staticmethod
    async def offboard(
        db: AsyncSession,
        *,
        user: User,
        performed_by_user_id: int | None,
    ) -> dict[str, int]:
        if user.role != UserRole.AGENT or not user.broker_id:
            user.is_active = False
            await db.commit()
            return {"assets_unassigned": 0, "assets_paused": 0, "leads_unassigned": 0, "tasks_unassigned": 0}

        broker_id = int(user.broker_id)
        corporate_result = await db.execute(
            update(MetaAsset)
            .where(
                MetaAsset.broker_id == broker_id,
                MetaAsset.owner_type == "broker",
                MetaAsset.assigned_user_id == user.id,
            )
            .values(assigned_user_id=None)
        )
        executive_result = await db.execute(
            update(MetaAsset)
            .where(
                MetaAsset.broker_id == broker_id,
                MetaAsset.owner_type.in_(("user", "executive")),
                MetaAsset.owner_user_id == user.id,
            )
            .values(status="paused", is_default=False)
        )

        leads = list((await db.scalars(
            select(Lead).where(
                Lead.broker_id == broker_id,
                or_(Lead.assigned_to == user.id, Lead.human_assigned_to == user.id),
                or_(
                    Lead.pipeline_stage.is_(None),
                    Lead.pipeline_stage.notin_(["ganado", "perdido"]),
                ),
            )
        )).all())
        for lead in leads:
            previous = lead.assigned_to
            lead.assigned_to = None
            if lead.human_assigned_to == user.id:
                lead.human_assigned_to = None
                lead.human_mode = False
                lead.human_released_at = datetime.now(timezone.utc)
            db.add(ActivityLog(
                lead_id=lead.id,
                action_type="agent_unassigned",
                details={
                    "old_agent_id": previous,
                    "new_agent_id": None,
                    "assigned_by": performed_by_user_id,
                    "reason": "executive_offboarding",
                },
                timestamp=datetime.now(timezone.utc),
            ))

        await db.execute(
            update(Conversation)
            .where(
                Conversation.broker_id == broker_id,
                Conversation.human_assigned_to == user.id,
                Conversation.status.in_(["active", "human_mode"]),
            )
            .values(
                human_assigned_to=None,
                human_mode=False,
                status="active",
                human_released_at=datetime.now(timezone.utc),
            )
        )

        task_result = await db.execute(
            update(LeadTask)
            .where(
                LeadTask.broker_id == broker_id,
                LeadTask.assigned_to == user.id,
                LeadTask.status.in_(TASK_ACTIVE_STATUSES),
            )
            .values(
                assigned_to=None,
                reminder_sent_at=None,
                reminder_acknowledged_at=None,
            )
        )

        user.is_active = False
        counts = {
            "assets_unassigned": corporate_result.rowcount or 0,
            "assets_paused": executive_result.rowcount or 0,
            "leads_unassigned": len(leads),
            "tasks_unassigned": task_result.rowcount or 0,
        }
        db.add(AuditLog(
            user_id=performed_by_user_id,
            broker_id=broker_id,
            action="meta_executive_offboarded",
            resource_type="user",
            resource_id=user.id,
            changes=counts,
        ))
        await db.commit()
        await ws_manager.broadcast(broker_id, "meta_executive_offboarded", {
            "user_id": user.id,
            **counts,
        })
        return counts
