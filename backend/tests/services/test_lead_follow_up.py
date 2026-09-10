"""Focused unit tests for lead notes, tasks, assignment and reminders.

Run without the integration conftest:
    pytest tests/services/test_lead_follow_up.py -v --noconftest
"""

from __future__ import annotations

import asyncio
import os
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

os.environ["DEBUG"] = "false"

from app.models.broker import Broker  # noqa: E402
from app.models.appointment import Appointment, AppointmentStatus, AppointmentType  # noqa: E402
from app.models.deal import Deal  # noqa: E402
from app.models.lead import Lead  # noqa: E402
from app.models.lead_follow_up import LeadAdvisory, LeadNote, LeadTask  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.models.property import Property  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.middleware.auth import create_access_token  # noqa: E402
from app.routes.ws import _authenticate  # noqa: E402
from app.schemas.lead_follow_up import (  # noqa: E402
    AdvisoryChannel,
    LeadAdvisoryCreate,
    LeadNoteCreate,
    LeadTaskCreate,
    LeadTaskUpdate,
    TaskStatus,
)
from app.services.leads.assignment_service import LeadAssignmentService  # noqa: E402
from app.services.leads.follow_up_service import LeadFollowUpService, _reminder_at  # noqa: E402
from app.services.pipeline.metrics_service import get_advised_lead_metrics  # noqa: E402
from app.services.pipeline.management_dashboard_service import ManagementDashboardService  # noqa: E402
from app.tasks.lead_task_reminders import _claim_due_reminders, _publish_reminder  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


def _lead(*, broker_id=1, assigned_to=7):
    return SimpleNamespace(id=10, broker_id=broker_id, assigned_to=assigned_to)


class TestSchemas:
    def test_advisory_requires_timezone_and_sanitizes_notes(self):
        with pytest.raises(ValidationError):
            LeadAdvisoryCreate(
                channel=AdvisoryChannel.PHONE,
                occurred_at=datetime(2026, 8, 25, 9, 0),
            )

        advisory = LeadAdvisoryCreate(
            channel=AdvisoryChannel.PHONE,
            occurred_at=datetime(2026, 8, 25, 9, 0, tzinfo=timezone.utc),
            notes=" <b>Revisamos alternativas</b> ",
        )
        assert advisory.notes == "Revisamos alternativas"

    def test_note_is_plain_text_and_trimmed(self):
        note = LeadNoteCreate(body="  <b>Contactar mañana</b>  ")
        assert note.body == "Contactar mañana"

    def test_task_requires_timezone(self):
        with pytest.raises(ValidationError):
            LeadTaskCreate(title="Llamar", due_at=datetime(2026, 8, 25, 9, 0))

    def test_task_rejects_unknown_reminder_offset(self):
        with pytest.raises(ValidationError):
            LeadTaskCreate(
                title="Llamar",
                due_at=datetime(2026, 8, 25, 9, 0, tzinfo=timezone.utc),
                reminder_minutes_before=30,
            )

    def test_reminder_time_is_calculated_in_utc(self):
        due = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
        assert _reminder_at(due, 60) == datetime(2026, 8, 25, 11, 0, tzinfo=timezone.utc)
        assert _reminder_at(due, None) is None


class TestLeadAccess:
    def test_agent_cannot_open_another_executives_lead(self):
        db = AsyncMock()
        db.scalar.return_value = _lead(assigned_to=99)

        with pytest.raises(HTTPException) as exc:
            _run(LeadFollowUpService.get_accessible_lead(
                db,
                10,
                {"role": "AGENT", "user_id": 7, "broker_id": 1},
            ))
        assert exc.value.status_code == 403

    def test_admin_cannot_cross_broker_boundary(self):
        db = AsyncMock()
        db.scalar.return_value = _lead(broker_id=2)

        with pytest.raises(HTTPException) as exc:
            _run(LeadFollowUpService.get_accessible_lead(
                db,
                10,
                {"role": "ADMIN", "user_id": 1, "broker_id": 1},
            ))
        assert exc.value.status_code == 403

    def test_superadmin_is_read_only_without_impersonation(self):
        db = AsyncMock()
        db.scalar.return_value = _lead(broker_id=2)

        with pytest.raises(HTTPException) as exc:
            _run(LeadFollowUpService.get_accessible_lead(
                db,
                10,
                {"role": "SUPERADMIN", "user_id": 1, "broker_id": None},
                write=True,
            ))
        assert exc.value.status_code == 403


class TestAssignment:
    def test_reassignment_transfers_only_open_tasks(self):
        db = AsyncMock()
        lead = _lead(assigned_to=7)
        agent = SimpleNamespace(
            id=8,
            broker_id=1,
            role=UserRole.AGENT,
            is_active=True,
            name="Nuevo ejecutivo",
        )
        db.scalar.side_effect = [lead, agent]
        tasks = [
            SimpleNamespace(
                id=task_id,
                assigned_to=7,
                reminder_sent_at=due,
                reminder_acknowledged_at=due,
            )
            for task_id, due in ((41, datetime.now(timezone.utc)), (42, None), (43, None))
        ]
        scalars_result = MagicMock()
        scalars_result.all.return_value = tasks
        db.scalars.return_value = scalars_result
        db.add = MagicMock()

        with patch(
            "app.services.leads.assignment_service.ws_manager.broadcast",
            new_callable=AsyncMock,
        ) as broadcast:
            response = _run(LeadAssignmentService.assign(
                db,
                lead_id=10,
                agent_id=8,
                current_user={"role": "ADMIN", "user_id": 2, "broker_id": 1},
            ))

        assert lead.assigned_to == 8
        assert response["transferred_open_tasks"] == 3
        assert all(task.assigned_to == 8 for task in tasks)
        assert all(task.reminder_sent_at is None for task in tasks)
        assert all(task.reminder_acknowledged_at is None for task in tasks)
        db.commit.assert_awaited_once()
        assert broadcast.await_count == 2


class TestAdvisoryAccess:
    def test_agent_cannot_register_advisory_for_another_executive(self):
        db = AsyncMock()
        db.scalar.return_value = _lead(assigned_to=7)
        payload = LeadAdvisoryCreate(
            advisor_id=8,
            channel=AdvisoryChannel.WHATSAPP,
            occurred_at=datetime.now(timezone.utc),
        )

        with pytest.raises(HTTPException) as exc:
            _run(LeadFollowUpService.create_advisory(
                db,
                10,
                payload,
                {"role": "AGENT", "user_id": 7, "broker_id": 1},
            ))
        assert exc.value.status_code == 403


class TestReminderClaim:
    def test_claim_marks_before_returning_payload(self):
        due = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
        task = SimpleNamespace(
            id=44,
            lead_id=10,
            broker_id=1,
            assigned_to=7,
            title="Confirmar documentos",
            due_at=due,
            reminder_sent_at=None,
            reminder_acknowledged_at=None,
            lead=SimpleNamespace(name="Ana", phone="+56911111111"),
            assignee=SimpleNamespace(name="Ejecutivo"),
        )
        result = MagicMock()
        result.unique.return_value.scalars.return_value.all.return_value = [task]
        session = MagicMock()
        session.execute.return_value = result
        session.__enter__.return_value = session
        session.__exit__.return_value = False

        with patch("app.tasks.lead_task_reminders.SyncSessionLocal", return_value=session):
            payloads = _claim_due_reminders()

        assert task.reminder_sent_at is not None
        assert payloads[0]["task_id"] == 44
        assert payloads[0]["assigned_to"] == 7
        assert payloads[0]["_claimed_at"] == task.reminder_sent_at
        session.commit.assert_called_once()

    def test_publish_does_not_expose_internal_claim_data(self):
        reminder = {
            "task_id": 44,
            "assigned_to": 7,
            "broker_id": 1,
            "title": "Confirmar documentos",
            "_claimed_at": datetime.now(timezone.utc),
        }
        client = MagicMock()
        client.publish.return_value = 1

        with patch("redis.from_url", return_value=client):
            assert _publish_reminder(reminder) is True

        published_payload = client.publish.call_args.args[1]
        assert '"broker_id": 1' in published_payload
        assert '"_claimed_at"' not in published_payload
        assert reminder["broker_id"] == 1

        client.publish.return_value = 0
        with patch("redis.from_url", return_value=client):
            assert _publish_reminder(reminder) is False


class TestWebSocketAuthentication:
    def test_user_can_only_subscribe_to_own_targeted_channel(self):
        token = create_access_token({"sub": "7", "role": "AGENT", "broker_id": 1})
        ws = SimpleNamespace(receive_text=AsyncMock(return_value=f'{{"token":"{token}"}}'))

        authenticated = _run(_authenticate(ws, broker_id=1, requested_user_id="7"))

        assert authenticated["sub"] == "7"

    def test_user_cannot_subscribe_to_another_executives_channel(self):
        token = create_access_token({"sub": "7", "role": "AGENT", "broker_id": 1})
        ws = SimpleNamespace(receive_text=AsyncMock(return_value=f'{{"token":"{token}"}}'))

        authenticated = _run(_authenticate(ws, broker_id=1, requested_user_id="8"))

        assert authenticated is None


class TestCrudIntegration:
    @pytest.mark.asyncio
    async def test_note_and_task_lifecycle(self, db_session):
        broker = Broker(name="Broker seguimiento", slug="broker-seguimiento-test")
        db_session.add(broker)
        await db_session.flush()

        admin = User(
            email="follow-up-admin@example.com",
            hashed_password="test",
            name="Admin Seguimiento",
            role=UserRole.ADMIN,
            broker_id=broker.id,
            is_active=True,
        )
        agent = User(
            email="follow-up-agent@example.com",
            hashed_password="test",
            name="Ejecutivo Seguimiento",
            role=UserRole.AGENT,
            broker_id=broker.id,
            is_active=True,
        )
        db_session.add_all([admin, agent])
        await db_session.flush()

        lead = Lead(
            broker_id=broker.id,
            assigned_to=agent.id,
            phone="+56900000001",
            name="Lead Seguimiento",
        )
        db_session.add(lead)
        await db_session.commit()

        admin_user = {
            "role": "ADMIN",
            "user_id": admin.id,
            "broker_id": broker.id,
        }
        agent_user = {
            "role": "AGENT",
            "user_id": agent.id,
            "broker_id": broker.id,
        }
        due = datetime(2026, 8, 26, 15, 0, tzinfo=timezone.utc)

        with patch(
            "app.services.leads.follow_up_service.ws_manager.broadcast",
            new_callable=AsyncMock,
        ):
            note = await LeadFollowUpService.create_note(
                db_session,
                lead.id,
                LeadNoteCreate(body="Confirmó interés en el proyecto"),
                agent_user,
            )
            assert note.author_id == agent.id
            assert note.author_name == agent.name

            advisory = await LeadFollowUpService.create_advisory(
                db_session,
                lead.id,
                LeadAdvisoryCreate(
                    channel=AdvisoryChannel.PHONE,
                    occurred_at=datetime.now(timezone.utc),
                    notes="Revisamos presupuesto y próximos pasos",
                ),
                agent_user,
            )
            assert advisory.advisor_id == agent.id
            assert advisory.advisor_name == agent.name

            second_advisory = await LeadFollowUpService.create_advisory(
                db_session,
                lead.id,
                LeadAdvisoryCreate(
                    advisor_id=agent.id,
                    channel=AdvisoryChannel.WHATSAPP,
                    occurred_at=datetime.now(timezone.utc),
                ),
                admin_user,
            )
            assert second_advisory.recorded_by == admin.id

            task = await LeadFollowUpService.create_task(
                db_session,
                lead.id,
                LeadTaskCreate(title="Enviar cotización", due_at=due),
                agent_user,
            )
            assert task.assigned_to == agent.id
            assert task.reminder_at == datetime(2026, 8, 26, 14, 0, tzinfo=timezone.utc)

            stored_task = await db_session.get(LeadTask, task.id)
            stored_task.reminder_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
            await db_session.commit()
            pending = await LeadFollowUpService.list_pending_reminders(
                db_session, agent_user
            )
            assert [item.id for item in pending] == [task.id]
            await LeadFollowUpService.acknowledge_reminder(
                db_session, task.id, agent_user
            )
            await db_session.refresh(stored_task)
            assert stored_task.reminder_acknowledged_at is not None

            edited = await LeadFollowUpService.update_task(
                db_session,
                task.id,
                LeadTaskUpdate(title="Enviar cotización actualizada", reminder_minutes_before=15),
                agent_user,
            )
            assert edited.title == "Enviar cotización actualizada"
            assert edited.reminder_minutes_before == 15
            assert edited.reminder_sent_at is None
            assert edited.reminder_acknowledged_at is None

            started = await LeadFollowUpService.set_in_progress(
                db_session,
                task.id,
                agent_user,
            )
            assert started.status is TaskStatus.IN_PROGRESS

            task_metrics = await LeadFollowUpService.get_task_metrics(
                db_session,
                admin_user,
            )
            assert task_metrics["in_progress"] == 1
            assert task_metrics["pending"] == 0

            completed = await LeadFollowUpService.set_completed(
                db_session,
                task.id,
                agent_user,
                completed=True,
            )
            assert completed.status is TaskStatus.COMPLETED
            assert completed.completed_by == agent.id

            reopened = await LeadFollowUpService.set_completed(
                db_session,
                task.id,
                admin_user,
                completed=False,
            )
            assert reopened.status is TaskStatus.OPEN
            assert reopened.reminder_sent_at is None

            notes, note_total = await LeadFollowUpService.list_notes(
                db_session, lead.id, agent_user, skip=0, limit=20
            )
            advisories, advisory_total = await LeadFollowUpService.list_advisories(
                db_session, lead.id, agent_user, skip=0, limit=20
            )
            tasks, task_total = await LeadFollowUpService.list_tasks(
                db_session,
                admin_user,
                lead_id=lead.id,
                skip=0,
                limit=20,
            )
            assert note_total == 1 and notes[0].id == note.id
            assert advisory_total == 2 and advisories[0].id == second_advisory.id
            assert task_total == 1 and tasks[0].id == task.id

            metrics = await get_advised_lead_metrics(
                db_session,
                broker_id=broker.id,
                total_leads=1,
            )
            assert metrics["advised_leads"] == 1
            assert metrics["advised_rate"] == 100.0

            await LeadFollowUpService.delete_task(db_session, task.id, agent_user)
            assert await db_session.get(LeadTask, task.id) is None
            assert await db_session.get(LeadNote, note.id) is not None
            assert await db_session.get(LeadAdvisory, advisory.id) is not None

    @pytest.mark.asyncio
    async def test_management_dashboard_uses_verified_records(self, db_session):
        broker = Broker(name="Broker KPI", slug="broker-kpi-test")
        db_session.add(broker)
        await db_session.flush()
        agent = User(
            email="kpi-agent@example.com",
            hashed_password="test",
            name="Ejecutivo KPI",
            role=UserRole.AGENT,
            broker_id=broker.id,
            is_active=True,
        )
        other_agent = User(
            email="other-kpi-agent@example.com",
            hashed_password="test",
            name="Otro Ejecutivo KPI",
            role=UserRole.AGENT,
            broker_id=broker.id,
            is_active=True,
        )
        db_session.add_all([agent, other_agent])
        await db_session.flush()
        now = datetime(2026, 8, 20, 12, tzinfo=timezone.utc)
        lead = Lead(
            broker_id=broker.id,
            assigned_to=agent.id,
            phone="+56900000009",
            name="Lead KPI",
            created_at=now - timedelta(days=5),
            last_contacted=now - timedelta(days=4),
            pipeline_stage="ganado",
            lead_metadata={"source": "Meta Ads"},
        )
        other_lead = Lead(
            broker_id=broker.id,
            assigned_to=other_agent.id,
            phone="+56900000010",
            name="Lead Otro Ejecutivo",
            created_at=now - timedelta(days=2),
            pipeline_stage="entrada",
            lead_metadata={"source": "Web"},
        )
        db_session.add_all([lead, other_lead])
        await db_session.flush()
        project = Project(broker_id=broker.id, name="Proyecto KPI", code="KPI")
        db_session.add(project)
        await db_session.flush()
        property_ = Property(
            broker_id=broker.id,
            project_id=project.id,
            name="Unidad KPI",
            price_uf=4000,
            price_clp=150_000_000,
        )
        db_session.add(property_)
        await db_session.flush()
        db_session.add_all([
            LeadAdvisory(
                broker_id=broker.id,
                lead_id=lead.id,
                advisor_id=agent.id,
                recorded_by=agent.id,
                channel="phone",
                occurred_at=now - timedelta(days=3),
            ),
            LeadTask(
                broker_id=broker.id,
                lead_id=lead.id,
                title="Gestionar firma",
                status="in_progress",
                assigned_to=agent.id,
                created_by=agent.id,
                due_at=now + timedelta(days=1),
            ),
            Appointment(
                lead_id=lead.id,
                agent_id=agent.id,
                appointment_type=AppointmentType.PROPERTY_VISIT,
                status=AppointmentStatus.COMPLETED,
                start_time=now - timedelta(days=2),
                end_time=now - timedelta(days=2) + timedelta(hours=1),
                duration_minutes=60,
            ),
            Deal(
                broker_id=broker.id,
                lead_id=lead.id,
                property_id=property_.id,
                created_by_user_id=agent.id,
                stage="escritura_firmada",
                reserva_at=now - timedelta(days=2),
                escritura_signed_at=now,
            ),
        ])
        await db_session.commit()

        result = await ManagementDashboardService.get_metrics(
            db_session,
            {"role": "ADMIN", "user_id": agent.id, "broker_id": broker.id},
            broker_id=None,
            date_from=date(2026, 8, 1),
            date_to=date(2026, 8, 31),
            agent_id=None,
            project_id=None,
            source=None,
        )

        assert result["commercial"]["received"] == 2
        assert result["commercial"]["advised"] == 1
        assert result["commercial"]["appointments"]["completed"] == 1
        assert result["commercial"]["sales"] == 1
        assert result["commercial"]["sales_uf"] == 4000
        assert result["commercial"]["sales_clp"] == 150_000_000
        assert result["tasks"]["in_progress"] == 1
        assert result["by_agent"][0]["sales"] == 1
        assert result["by_project"][0]["name"] == "Proyecto KPI"
        assert result["by_source"][0]["source"] == "Meta Ads"

        personal = await ManagementDashboardService.get_metrics(
            db_session,
            {"role": "AGENT", "user_id": agent.id, "broker_id": broker.id},
            broker_id=None,
            date_from=date(2026, 8, 1),
            date_to=date(2026, 8, 31),
            agent_id=other_agent.id,
            project_id=None,
            source=None,
        )
        assert personal["commercial"]["received"] == 1
        assert [row["id"] for row in personal["by_agent"]] == [agent.id]
        assert personal["filters"]["agents"] == [{"id": agent.id, "name": agent.name}]
