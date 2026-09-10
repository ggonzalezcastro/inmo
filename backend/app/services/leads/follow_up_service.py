"""Business rules for immutable lead notes and executive follow-up tasks."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.websocket_manager import ws_manager
from app.models.activity_log import ActivityLog
from app.models.lead import Lead
from app.models.lead_follow_up import (
    LeadAdvisory,
    LeadNote,
    LeadTask,
    TASK_ACTIVE_STATUSES,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_IN_PROGRESS,
    TASK_STATUS_OPEN,
)
from app.models.user import User, UserRole
from app.schemas.lead_follow_up import (
    LeadAdvisoryCreate,
    LeadAdvisoryResponse,
    LeadNoteCreate,
    LeadNoteResponse,
    LeadTaskCreate,
    LeadTaskResponse,
    LeadTaskUpdate,
    TaskStatus,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _role(current_user: dict) -> str:
    return str(current_user.get("role", "")).upper()


def _user_id(current_user: dict) -> int:
    raw = current_user.get("user_id") or current_user.get("id")
    if raw is None:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")
    return int(raw)


def _reminder_at(due_at: datetime, minutes_before: Optional[int]) -> Optional[datetime]:
    if minutes_before is None:
        return None
    return due_at.astimezone(timezone.utc) - timedelta(minutes=minutes_before)


class LeadFollowUpService:
    _task_load_options = (
        joinedload(LeadTask.lead),
        joinedload(LeadTask.assignee),
        joinedload(LeadTask.creator),
        joinedload(LeadTask.completer),
    )

    @staticmethod
    async def get_accessible_lead(
        db: AsyncSession,
        lead_id: int,
        current_user: dict,
        *,
        write: bool = False,
    ) -> Lead:
        lead = await db.scalar(select(Lead).where(Lead.id == lead_id))
        if lead is None:
            raise HTTPException(status_code=404, detail="Lead no encontrado")

        role = _role(current_user)
        if role == UserRole.SUPERADMIN.value:
            if write:
                raise HTTPException(
                    status_code=403,
                    detail="Usa impersonación de broker para modificar seguimientos",
                )
            return lead

        broker_id = current_user.get("broker_id")
        if not broker_id or lead.broker_id != int(broker_id):
            raise HTTPException(status_code=403, detail="No tienes acceso a este lead")

        if role == UserRole.AGENT.value and lead.assigned_to != _user_id(current_user):
            raise HTTPException(status_code=403, detail="El lead no está asignado a este ejecutivo")

        if role not in (UserRole.ADMIN.value, UserRole.AGENT.value):
            raise HTTPException(status_code=403, detail="Permiso insuficiente")
        return lead

    @staticmethod
    async def _active_agent(db: AsyncSession, user_id: int, broker_id: int) -> User:
        agent = await db.scalar(
            select(User).where(
                User.id == user_id,
                User.broker_id == broker_id,
                User.role == UserRole.AGENT,
                User.is_active.is_(True),
            )
        )
        if agent is None:
            raise HTTPException(
                status_code=422,
                detail="El responsable debe ser un ejecutivo activo del mismo broker",
            )
        return agent

    @staticmethod
    def note_response(note: LeadNote) -> LeadNoteResponse:
        return LeadNoteResponse(
            id=note.id,
            lead_id=note.lead_id,
            body=note.body,
            author_id=note.author_id,
            author_name=note.author.name if note.author else None,
            created_at=note.created_at,
        )

    @staticmethod
    def advisory_response(advisory: LeadAdvisory) -> LeadAdvisoryResponse:
        return LeadAdvisoryResponse(
            id=advisory.id,
            lead_id=advisory.lead_id,
            advisor_id=advisory.advisor_id,
            advisor_name=advisory.advisor.name if advisory.advisor else None,
            recorded_by=advisory.recorded_by,
            recorder_name=advisory.recorder.name if advisory.recorder else None,
            channel=advisory.channel,
            occurred_at=advisory.occurred_at,
            notes=advisory.notes,
            created_at=advisory.created_at,
        )

    @staticmethod
    def task_response(task: LeadTask) -> LeadTaskResponse:
        return LeadTaskResponse(
            id=task.id,
            lead_id=task.lead_id,
            lead_name=task.lead.name if task.lead else None,
            lead_phone=task.lead.phone if task.lead else None,
            title=task.title,
            status=TaskStatus(task.status),
            assigned_to=task.assigned_to,
            assignee_name=task.assignee.name if task.assignee else None,
            created_by=task.created_by,
            creator_name=task.creator.name if task.creator else None,
            completed_by=task.completed_by,
            due_at=task.due_at,
            reminder_minutes_before=task.reminder_minutes_before,
            reminder_at=task.reminder_at,
            reminder_sent_at=task.reminder_sent_at,
            reminder_acknowledged_at=task.reminder_acknowledged_at,
            completed_at=task.completed_at,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

    @staticmethod
    def _activity(lead_id: int, action_type: str, details: dict) -> ActivityLog:
        return ActivityLog(
            lead_id=lead_id,
            action_type=action_type,
            details=details,
            timestamp=_utcnow(),
        )

    @classmethod
    async def list_notes(
        cls,
        db: AsyncSession,
        lead_id: int,
        current_user: dict,
        *,
        skip: int,
        limit: int,
    ) -> tuple[list[LeadNoteResponse], int]:
        lead = await cls.get_accessible_lead(db, lead_id, current_user)
        filters = (LeadNote.lead_id == lead.id, LeadNote.broker_id == lead.broker_id)
        total = await db.scalar(select(func.count(LeadNote.id)).where(*filters)) or 0
        notes = list((await db.scalars(
            select(LeadNote)
            .options(joinedload(LeadNote.author))
            .where(*filters)
            .order_by(LeadNote.created_at.desc(), LeadNote.id.desc())
            .offset(skip)
            .limit(limit)
        )).all())
        return [cls.note_response(note) for note in notes], total

    @classmethod
    async def create_note(
        cls,
        db: AsyncSession,
        lead_id: int,
        payload: LeadNoteCreate,
        current_user: dict,
    ) -> LeadNoteResponse:
        lead = await cls.get_accessible_lead(db, lead_id, current_user, write=True)
        author_id = _user_id(current_user)
        note = LeadNote(
            broker_id=lead.broker_id,
            lead_id=lead.id,
            author_id=author_id,
            body=payload.body,
        )
        db.add(note)
        await db.flush()
        db.add(cls._activity(
            lead.id,
            "lead_note_created",
            {"note_id": note.id, "author_id": author_id},
        ))
        await db.commit()
        note = await db.scalar(
            select(LeadNote)
            .options(joinedload(LeadNote.author))
            .where(LeadNote.id == note.id)
        )
        return cls.note_response(note)

    @classmethod
    async def list_advisories(
        cls,
        db: AsyncSession,
        lead_id: int,
        current_user: dict,
        *,
        skip: int,
        limit: int,
    ) -> tuple[list[LeadAdvisoryResponse], int]:
        lead = await cls.get_accessible_lead(db, lead_id, current_user)
        filters = (
            LeadAdvisory.lead_id == lead.id,
            LeadAdvisory.broker_id == lead.broker_id,
        )
        total = await db.scalar(select(func.count(LeadAdvisory.id)).where(*filters)) or 0
        advisories = list((await db.scalars(
            select(LeadAdvisory)
            .options(
                joinedload(LeadAdvisory.advisor),
                joinedload(LeadAdvisory.recorder),
            )
            .where(*filters)
            .order_by(LeadAdvisory.occurred_at.desc(), LeadAdvisory.id.desc())
            .offset(skip)
            .limit(limit)
        )).all())
        return [cls.advisory_response(item) for item in advisories], total

    @classmethod
    async def create_advisory(
        cls,
        db: AsyncSession,
        lead_id: int,
        payload: LeadAdvisoryCreate,
        current_user: dict,
    ) -> LeadAdvisoryResponse:
        lead = await cls.get_accessible_lead(db, lead_id, current_user, write=True)
        role = _role(current_user)
        recorder_id = _user_id(current_user)

        if role == UserRole.AGENT.value:
            if payload.advisor_id not in (None, recorder_id):
                raise HTTPException(
                    status_code=403,
                    detail="Un ejecutivo solo puede registrar sus propias asesorías",
                )
            advisor_id = recorder_id
        else:
            advisor_id = payload.advisor_id or lead.assigned_to

        if advisor_id is None:
            raise HTTPException(
                status_code=422,
                detail="Selecciona el ejecutivo que realizó la asesoría",
            )
        await cls._active_agent(db, advisor_id, lead.broker_id)

        occurred_at = payload.occurred_at.astimezone(timezone.utc)
        if occurred_at > _utcnow() + timedelta(minutes=5):
            raise HTTPException(
                status_code=422,
                detail="La asesoría no puede registrarse en una fecha futura",
            )

        advisory = LeadAdvisory(
            broker_id=lead.broker_id,
            lead_id=lead.id,
            advisor_id=advisor_id,
            recorded_by=recorder_id,
            channel=payload.channel.value,
            occurred_at=occurred_at,
            notes=payload.notes,
        )
        db.add(advisory)
        await db.flush()
        db.add(cls._activity(
            lead.id,
            "lead_advisory_created",
            {
                "advisory_id": advisory.id,
                "advisor_id": advisor_id,
                "recorded_by": recorder_id,
                "channel": advisory.channel,
                "occurred_at": occurred_at.isoformat(),
            },
        ))
        await db.commit()
        advisory = await db.scalar(
            select(LeadAdvisory)
            .options(
                joinedload(LeadAdvisory.advisor),
                joinedload(LeadAdvisory.recorder),
            )
            .where(LeadAdvisory.id == advisory.id)
        )
        await ws_manager.broadcast(
            lead.broker_id,
            "lead_advisory_created",
            {
                "advisory_id": advisory.id,
                "lead_id": lead.id,
                "advisor_id": advisor_id,
            },
        )
        return cls.advisory_response(advisory)

    @classmethod
    async def _loaded_task(cls, db: AsyncSession, task_id: int) -> Optional[LeadTask]:
        return await db.scalar(
            select(LeadTask)
            .options(*cls._task_load_options)
            .where(LeadTask.id == task_id)
        )

    @classmethod
    async def get_task(
        cls,
        db: AsyncSession,
        task_id: int,
        current_user: dict,
    ) -> LeadTaskResponse:
        """Return one exact task while enforcing broker and assignee visibility."""
        task = await cls._loaded_task(db, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Tarea no encontrada")

        role = _role(current_user)
        if role == UserRole.SUPERADMIN.value:
            return cls.task_response(task)

        broker_id = current_user.get("broker_id")
        if not broker_id or task.broker_id != int(broker_id):
            raise HTTPException(status_code=403, detail="No tienes acceso a esta tarea")

        if role == UserRole.AGENT.value and task.assigned_to != _user_id(current_user):
            raise HTTPException(status_code=403, detail="La tarea no está asignada a este ejecutivo")
        if role not in (UserRole.ADMIN.value, UserRole.AGENT.value):
            raise HTTPException(status_code=403, detail="Permiso insuficiente")
        return cls.task_response(task)

    @classmethod
    async def list_pending_reminders(
        cls,
        db: AsyncSession,
        current_user: dict,
        *,
        limit: int = 20,
    ) -> list[LeadTaskResponse]:
        """Return due reminders that the authenticated assignee has not received yet."""
        role = _role(current_user)
        if role != UserRole.AGENT.value:
            return []

        broker_id = current_user.get("broker_id")
        if not broker_id:
            raise HTTPException(status_code=403, detail="Usuario sin broker asignado")

        tasks = list((await db.scalars(
            select(LeadTask)
            .options(*cls._task_load_options)
            .where(
                LeadTask.broker_id == int(broker_id),
                LeadTask.assigned_to == _user_id(current_user),
                LeadTask.status.in_(TASK_ACTIVE_STATUSES),
                LeadTask.reminder_at.is_not(None),
                LeadTask.reminder_at <= _utcnow(),
                LeadTask.reminder_acknowledged_at.is_(None),
            )
            .order_by(LeadTask.reminder_at.asc(), LeadTask.id.asc())
            .limit(limit)
        )).unique().all())
        return [cls.task_response(task) for task in tasks]

    @classmethod
    async def acknowledge_reminder(
        cls,
        db: AsyncSession,
        task_id: int,
        current_user: dict,
    ) -> None:
        """Persist that the assigned executive received the in-app reminder."""
        task = await cls._loaded_task(db, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Tarea no encontrada")

        broker_id = current_user.get("broker_id")
        user_id = _user_id(current_user)
        if (
            _role(current_user) != UserRole.AGENT.value
            or not broker_id
            or task.broker_id != int(broker_id)
            or task.assigned_to != user_id
        ):
            raise HTTPException(status_code=403, detail="No puedes confirmar este recordatorio")

        if task.reminder_acknowledged_at is None:
            task.reminder_acknowledged_at = _utcnow()
            await db.commit()

    @classmethod
    async def list_tasks(
        cls,
        db: AsyncSession,
        current_user: dict,
        *,
        lead_id: Optional[int] = None,
        task_status: Optional[TaskStatus] = None,
        assigned_to: Optional[int] = None,
        broker_id: Optional[int] = None,
        overdue: Optional[bool] = None,
        due_from: Optional[datetime] = None,
        due_to: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[LeadTaskResponse], int]:
        role = _role(current_user)
        filters = []

        if lead_id is not None:
            lead = await cls.get_accessible_lead(db, lead_id, current_user)
            filters.extend((LeadTask.lead_id == lead.id, LeadTask.broker_id == lead.broker_id))
        elif role == UserRole.AGENT.value:
            filters.extend((
                LeadTask.broker_id == int(current_user["broker_id"]),
                LeadTask.assigned_to == _user_id(current_user),
            ))
        elif role == UserRole.ADMIN.value:
            filters.append(LeadTask.broker_id == int(current_user["broker_id"]))
        elif role == UserRole.SUPERADMIN.value:
            if broker_id is not None:
                filters.append(LeadTask.broker_id == broker_id)
        else:
            raise HTTPException(status_code=403, detail="Permiso insuficiente")

        if assigned_to is not None and role != UserRole.AGENT.value:
            filters.append(LeadTask.assigned_to == assigned_to)
        if task_status is not None:
            filters.append(LeadTask.status == task_status.value)
        if due_from is not None:
            filters.append(LeadTask.due_at >= due_from)
        if due_to is not None:
            filters.append(LeadTask.due_at <= due_to)
        if overdue is True:
            filters.extend((LeadTask.status.in_(TASK_ACTIVE_STATUSES), LeadTask.due_at < _utcnow()))
        elif overdue is False:
            filters.append(LeadTask.due_at >= _utcnow())

        total = await db.scalar(select(func.count(LeadTask.id)).where(*filters)) or 0
        ordering = (
            case((LeadTask.status.in_(TASK_ACTIVE_STATUSES), 0), else_=1),
            LeadTask.due_at.asc(),
            LeadTask.id.asc(),
        )
        tasks = list((await db.scalars(
            select(LeadTask)
            .options(*cls._task_load_options)
            .where(*filters)
            .order_by(*ordering)
            .offset(skip)
            .limit(limit)
        )).unique().all())
        return [cls.task_response(task) for task in tasks], total

    @classmethod
    async def get_task_metrics(
        cls,
        db: AsyncSession,
        current_user: dict,
        *,
        assigned_to: Optional[int] = None,
    ) -> dict:
        role = _role(current_user)
        filters = []
        if role == UserRole.AGENT.value:
            filters.extend((
                LeadTask.broker_id == int(current_user["broker_id"]),
                LeadTask.assigned_to == _user_id(current_user),
            ))
        elif role == UserRole.ADMIN.value:
            filters.append(LeadTask.broker_id == int(current_user["broker_id"]))
            if assigned_to is not None:
                filters.append(LeadTask.assigned_to == assigned_to)
        else:
            raise HTTPException(status_code=403, detail="Usa impersonación de broker para consultar tareas")

        tasks = list((await db.scalars(select(LeadTask).where(*filters))).all())
        now = _utcnow()
        active = [task for task in tasks if task.status in TASK_ACTIVE_STATUSES]
        completed = [task for task in tasks if task.status == TASK_STATUS_COMPLETED]
        overdue = [task for task in active if _as_utc(task.due_at) < now]
        on_time = [task for task in completed if task.completed_at and _as_utc(task.completed_at) <= _as_utc(task.due_at)]
        resolution = [
            (_as_utc(task.completed_at) - _as_utc(task.created_at)).total_seconds() / 3600
            for task in completed if task.completed_at and task.created_at
        ]
        delay = [
            (now - _as_utc(task.due_at)).total_seconds() / 3600
            for task in overdue
        ]

        by_assignee = {}
        for task in tasks:
            key = task.assigned_to
            row = by_assignee.setdefault(key, {
                "assigned_to": key,
                "pending": 0,
                "in_progress": 0,
                "overdue": 0,
                "completed": 0,
            })
            if task.status == TASK_STATUS_COMPLETED:
                row["completed"] += 1
            elif task.status == TASK_STATUS_IN_PROGRESS:
                row["in_progress"] += 1
            else:
                row["pending"] += 1
            if task.status in TASK_ACTIVE_STATUSES and _as_utc(task.due_at) < now:
                row["overdue"] += 1

        return {
            "total": len(tasks),
            "pending": sum(1 for task in active if task.status == TASK_STATUS_OPEN),
            "in_progress": sum(1 for task in active if task.status == TASK_STATUS_IN_PROGRESS),
            "overdue": len(overdue),
            "completed": len(completed),
            "completion_rate": round(len(completed) / len(tasks) * 100, 1) if tasks else 0,
            "on_time_rate": round(len(on_time) / len(completed) * 100, 1) if completed else 0,
            "avg_resolution_hours": round(sum(resolution) / len(resolution), 1) if resolution else None,
            "avg_delay_hours": round(sum(delay) / len(delay), 1) if delay else None,
            "by_assignee": list(by_assignee.values()),
        }

    @classmethod
    async def create_task(
        cls,
        db: AsyncSession,
        lead_id: int,
        payload: LeadTaskCreate,
        current_user: dict,
    ) -> LeadTaskResponse:
        lead = await cls.get_accessible_lead(db, lead_id, current_user, write=True)
        role = _role(current_user)
        creator_id = _user_id(current_user)

        if role == UserRole.AGENT.value:
            assignee_id = creator_id
            if payload.assigned_to not in (None, creator_id):
                raise HTTPException(status_code=403, detail="Solo un administrador puede reasignar tareas")
        else:
            assignee_id = payload.assigned_to or lead.assigned_to

        if assignee_id is None:
            raise HTTPException(status_code=422, detail="Selecciona un ejecutivo responsable")
        await cls._active_agent(db, assignee_id, lead.broker_id)

        task = LeadTask(
            broker_id=lead.broker_id,
            lead_id=lead.id,
            title=payload.title,
            assigned_to=assignee_id,
            created_by=creator_id,
            due_at=payload.due_at.astimezone(timezone.utc),
            reminder_minutes_before=payload.reminder_minutes_before,
            reminder_at=_reminder_at(payload.due_at, payload.reminder_minutes_before),
        )
        db.add(task)
        await db.flush()
        db.add(cls._activity(
            lead.id,
            "lead_task_created",
            {
                "task_id": task.id,
                "title": task.title,
                "assigned_to": assignee_id,
                "created_by": creator_id,
                "due_at": task.due_at.isoformat(),
            },
        ))
        await db.commit()
        task = await cls._loaded_task(db, task.id)
        await cls._broadcast_change(task, "created")
        return cls.task_response(task)

    @classmethod
    async def _task_for_write(
        cls,
        db: AsyncSession,
        task_id: int,
        current_user: dict,
    ) -> LeadTask:
        task = await cls._loaded_task(db, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Tarea no encontrada")
        await cls.get_accessible_lead(db, task.lead_id, current_user, write=True)
        return task

    @classmethod
    async def update_task(
        cls,
        db: AsyncSession,
        task_id: int,
        payload: LeadTaskUpdate,
        current_user: dict,
    ) -> LeadTaskResponse:
        task = await cls._task_for_write(db, task_id, current_user)
        role = _role(current_user)
        user_id = _user_id(current_user)
        is_admin = role == UserRole.ADMIN.value
        if not is_admin and task.created_by != user_id:
            raise HTTPException(status_code=403, detail="Solo el creador o un administrador puede editar")

        changed = []
        fields = payload.model_fields_set
        old_assigned_to = task.assigned_to
        if "assigned_to" in fields:
            if not is_admin:
                raise HTTPException(status_code=403, detail="Solo un administrador puede reasignar tareas")
            if payload.assigned_to is not None:
                await cls._active_agent(db, payload.assigned_to, task.broker_id)
            task.assigned_to = payload.assigned_to
            changed.append("assigned_to")
        if "title" in fields and payload.title is not None:
            task.title = payload.title
            changed.append("title")
        if "due_at" in fields and payload.due_at is not None:
            task.due_at = payload.due_at.astimezone(timezone.utc)
            changed.append("due_at")
        if "reminder_minutes_before" in fields:
            task.reminder_minutes_before = payload.reminder_minutes_before
            changed.append("reminder_minutes_before")

        if any(field in changed for field in ("assigned_to", "due_at", "reminder_minutes_before")):
            task.reminder_at = _reminder_at(task.due_at, task.reminder_minutes_before)
            task.reminder_sent_at = None
            task.reminder_acknowledged_at = None

        if "assigned_to" in changed and old_assigned_to != task.assigned_to:
            db.add(cls._activity(
                task.lead_id,
                "lead_task_reassigned",
                {
                    "task_id": task.id,
                    "reassigned_by": user_id,
                    "old_assigned_to": old_assigned_to,
                    "new_assigned_to": task.assigned_to,
                },
            ))

        edited_fields = [field for field in changed if field != "assigned_to"]
        if edited_fields:
            db.add(cls._activity(
                task.lead_id,
                "lead_task_updated",
                {"task_id": task.id, "updated_by": user_id, "fields": edited_fields},
            ))
        await db.commit()
        task = await cls._loaded_task(db, task.id)
        await cls._broadcast_change(task, "updated")
        return cls.task_response(task)

    @classmethod
    async def set_completed(
        cls,
        db: AsyncSession,
        task_id: int,
        current_user: dict,
        *,
        completed: bool,
    ) -> LeadTaskResponse:
        task = await cls._task_for_write(db, task_id, current_user)
        role = _role(current_user)
        user_id = _user_id(current_user)
        if role != UserRole.ADMIN.value and task.assigned_to != user_id:
            raise HTTPException(status_code=403, detail="Solo el responsable o un administrador puede cambiar el estado")

        if completed:
            task.status = TASK_STATUS_COMPLETED
            task.completed_at = _utcnow()
            task.completed_by = user_id
            action = "lead_task_completed"
        else:
            task.status = TASK_STATUS_OPEN
            task.completed_at = None
            task.completed_by = None
            task.reminder_at = _reminder_at(task.due_at, task.reminder_minutes_before)
            task.reminder_sent_at = None
            task.reminder_acknowledged_at = None
            action = "lead_task_reopened"

        db.add(cls._activity(
            task.lead_id,
            action,
            {"task_id": task.id, "user_id": user_id},
        ))
        await db.commit()
        task = await cls._loaded_task(db, task.id)
        await cls._broadcast_change(task, "completed" if completed else "reopened")
        return cls.task_response(task)

    @classmethod
    async def set_in_progress(
        cls,
        db: AsyncSession,
        task_id: int,
        current_user: dict,
    ) -> LeadTaskResponse:
        task = await cls._task_for_write(db, task_id, current_user)
        role = _role(current_user)
        user_id = _user_id(current_user)
        if role != UserRole.ADMIN.value and task.assigned_to != user_id:
            raise HTTPException(
                status_code=403,
                detail="Solo el responsable o un administrador puede iniciar la tarea",
            )
        if task.status == TASK_STATUS_COMPLETED:
            raise HTTPException(status_code=409, detail="Reabre la tarea antes de iniciarla")
        if task.status != TASK_STATUS_IN_PROGRESS:
            task.status = TASK_STATUS_IN_PROGRESS
            db.add(cls._activity(
                task.lead_id,
                "lead_task_started",
                {"task_id": task.id, "user_id": user_id},
            ))
            await db.commit()
        task = await cls._loaded_task(db, task.id)
        await cls._broadcast_change(task, "started")
        return cls.task_response(task)

    @classmethod
    async def delete_task(
        cls,
        db: AsyncSession,
        task_id: int,
        current_user: dict,
    ) -> None:
        task = await cls._task_for_write(db, task_id, current_user)
        role = _role(current_user)
        user_id = _user_id(current_user)
        if role != UserRole.ADMIN.value and task.created_by != user_id:
            raise HTTPException(status_code=403, detail="Solo el creador o un administrador puede eliminar")

        lead_id = task.lead_id
        broker_id = task.broker_id
        assigned_to = task.assigned_to
        db.add(cls._activity(
            lead_id,
            "lead_task_deleted",
            {"task_id": task.id, "title": task.title, "deleted_by": user_id},
        ))
        await db.delete(task)
        await db.commit()
        await ws_manager.broadcast(
            broker_id,
            "lead_task_changed",
            {"task_id": task_id, "lead_id": lead_id, "assigned_to": assigned_to, "action": "deleted"},
        )

    @staticmethod
    async def _broadcast_change(task: LeadTask, action: str) -> None:
        await ws_manager.broadcast(
            task.broker_id,
            "lead_task_changed",
            {
                "task_id": task.id,
                "lead_id": task.lead_id,
                "assigned_to": task.assigned_to,
                "status": task.status,
                "action": action,
            },
        )
