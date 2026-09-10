"""Broker-management KPIs built only from persisted CRM records."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.appointment import Appointment
from app.models.deal import Deal
from app.models.lead import Lead
from app.models.lead_follow_up import LeadAdvisory, LeadTask, TASK_ACTIVE_STATUSES
from app.models.project import Project
from app.models.property import Property
from app.models.user import User, UserRole


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _source(lead: Lead) -> str:
    metadata = lead.lead_metadata if isinstance(lead.lead_metadata, dict) else {}
    value = (
        metadata.get("source")
        or metadata.get("utm_source")
        or metadata.get("origin")
        or metadata.get("origen")
    )
    return str(value).strip() if value else "Sin origen"


def _money(value: Any) -> float:
    return float(value or Decimal("0"))


def _price(property_: Optional[Property], currency: str) -> float:
    if property_ is None:
        return 0.0
    if currency == "uf":
        return _money(property_.offer_price_uf or property_.list_price_uf or property_.price_uf)
    return _money(property_.offer_price_clp or property_.list_price_clp or property_.price_clp)


def _pct(numerator: int | float, denominator: int | float) -> float:
    return round((numerator / denominator * 100), 1) if denominator else 0.0


def _lead_summary(lead: Lead) -> dict[str, Any]:
    return {
        "id": lead.id,
        "name": lead.name or lead.phone,
        "phone": lead.phone,
        "stage": lead.pipeline_stage or "entrada",
        "assigned_to": lead.assigned_to,
        "assignee_name": lead.assigned_agent.name if lead.assigned_agent else None,
        "source": _source(lead),
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "last_contacted": lead.last_contacted.isoformat() if lead.last_contacted else None,
        "close_reason": lead.close_reason,
    }


def _in_period(value: Optional[datetime], start: datetime, end: datetime) -> bool:
    if value is None:
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return start <= value.astimezone(timezone.utc) < end


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class ManagementDashboardService:
    @staticmethod
    def _broker_id(current_user: dict, broker_id: Optional[int]) -> int:
        role = str(current_user.get("role", "")).upper()
        if role == UserRole.SUPERADMIN.value:
            if broker_id is None:
                raise HTTPException(status_code=422, detail="Selecciona un broker")
            return broker_id
        current_broker = current_user.get("broker_id")
        if not current_broker:
            raise HTTPException(status_code=403, detail="Usuario sin broker asignado")
        return int(current_broker)

    @classmethod
    async def get_metrics(
        cls,
        db: AsyncSession,
        current_user: dict,
        *,
        broker_id: Optional[int],
        date_from: date,
        date_to: date,
        agent_id: Optional[int],
        project_id: Optional[int],
        source: Optional[str],
    ) -> dict[str, Any]:
        target_broker = cls._broker_id(current_user, broker_id)
        role = str(current_user.get("role", "")).upper()
        if role == UserRole.AGENT.value:
            agent_id = int(current_user.get("user_id") or current_user.get("id"))

        start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)

        agents = list((await db.scalars(
            select(User).where(
                User.broker_id == target_broker,
                User.role == UserRole.AGENT,
                User.is_active.is_(True),
            ).order_by(User.name)
        )).all())
        if role == UserRole.AGENT.value:
            agents = [agent for agent in agents if agent.id == agent_id]
        projects = list((await db.scalars(
            select(Project).where(Project.broker_id == target_broker).order_by(Project.name)
        )).all())

        lead_query = (
            select(Lead)
            .options(joinedload(Lead.assigned_agent))
            .where(Lead.broker_id == target_broker)
        )
        if agent_id is not None:
            lead_query = lead_query.where(Lead.assigned_to == agent_id)
        eligible_leads = list((await db.scalars(
            lead_query.order_by(Lead.created_at.desc())
        )).unique().all())
        available_sources = sorted({_source(lead) for lead in eligible_leads})
        if source:
            eligible_leads = [lead for lead in eligible_leads if _source(lead) == source]

        all_deals = list((await db.scalars(
            select(Deal)
            .options(joinedload(Deal.property).joinedload(Property.project))
            .where(Deal.broker_id == target_broker)
        )).unique().all())
        if project_id is not None:
            project_lead_ids = {
                deal.lead_id for deal in all_deals
                if deal.property and deal.property.project_id == project_id
            }
            interested_property_ids = set((await db.scalars(
                select(Property.id).where(
                    Property.broker_id == target_broker,
                    Property.project_id == project_id,
                )
            )).all())
            eligible_leads = [
                lead for lead in eligible_leads
                if lead.id in project_lead_ids
                or (
                    isinstance(lead.lead_metadata, dict)
                    and isinstance(lead.lead_metadata.get("property_interest"), dict)
                    and lead.lead_metadata["property_interest"].get("property_id") in interested_property_ids
                )
            ]

        lead_ids = {lead.id for lead in eligible_leads}
        lead_map = {lead.id: lead for lead in eligible_leads}
        leads = [lead for lead in eligible_leads if _in_period(lead.created_at, start, end)]
        deals = [deal for deal in all_deals if deal.lead_id in lead_ids]
        if project_id is not None:
            deals = [deal for deal in deals if deal.property and deal.property.project_id == project_id]

        advisories = []
        appointments = []
        task_query = select(LeadTask).where(
                LeadTask.broker_id == target_broker,
                LeadTask.lead_id.in_(lead_ids),
            )
        if agent_id is not None:
            task_query = task_query.where(LeadTask.assigned_to == agent_id)
        tasks = list((await db.scalars(task_query)).all()) if lead_ids else []
        if lead_ids:
            advisories = list((await db.scalars(
                select(LeadAdvisory).where(
                    LeadAdvisory.broker_id == target_broker,
                    LeadAdvisory.lead_id.in_(lead_ids),
                )
            )).all())
            appointments = list((await db.scalars(
                select(Appointment).where(Appointment.lead_id.in_(lead_ids))
            )).all())

        period_advisories = [item for item in advisories if _in_period(item.occurred_at, start, end)]
        advised_ids = {item.lead_id for item in period_advisories}
        advisory_ids_all = {item.lead_id for item in advisories}
        active_task_lead_ids = {item.lead_id for item in tasks if item.status in TASK_ACTIVE_STATUSES}

        assigned = [lead for lead in leads if lead.assigned_to is not None]
        contacted = [lead for lead in leads if lead.last_contacted is not None]
        advised = [lead for lead in eligible_leads if lead.id in advised_ids]
        active_stages = {"entrada", "perfilamiento", "calificacion_financiera", "potencial", "agendado", "seguimiento", "referidos"}
        without_follow_up = [
            lead for lead in leads
            if lead.assigned_to is not None
            and (lead.pipeline_stage or "entrada") in active_stages
            and lead.last_contacted is None
            and lead.id not in advisory_ids_all
            and lead.id not in active_task_lead_ids
        ]

        response_minutes = []
        for lead in contacted:
            if lead.created_at and lead.last_contacted:
                created = lead.created_at if lead.created_at.tzinfo else lead.created_at.replace(tzinfo=timezone.utc)
                contacted_at = lead.last_contacted if lead.last_contacted.tzinfo else lead.last_contacted.replace(tzinfo=timezone.utc)
                minutes = (contacted_at - created).total_seconds() / 60
                if minutes >= 0:
                    response_minutes.append(minutes)

        appointment_counts = Counter(
            _enum_value(item.status)
            for item in appointments
            if _in_period(item.start_time, start, end)
        )
        reservations = [
            deal for deal in deals
            if _in_period(deal.reserva_at, start, end)
            or (deal.reserva_at is None and deal.stage == "reserva" and _in_period(deal.created_at, start, end))
        ]
        sales = [deal for deal in deals if deal.stage == "escritura_firmada" and _in_period(deal.escritura_signed_at, start, end)]
        lost_leads = [
            lead for lead in eligible_leads
            if (lead.pipeline_stage or "") == "perdido"
            and (_in_period(lead.closed_at, start, end) or (lead.closed_at is None and lead in leads))
        ]
        cancelled_deals = [deal for deal in deals if deal.stage == "cancelado" and _in_period(deal.cancelled_at or deal.updated_at, start, end)]

        task_period = [item for item in tasks if _in_period(item.created_at, start, end)]
        completed_period = [item for item in tasks if item.status == "completed" and _in_period(item.completed_at, start, end)]
        completed_from_created = [item for item in task_period if item.status == "completed"]
        active_tasks = [item for item in tasks if item.status in TASK_ACTIVE_STATUSES]
        overdue_tasks = [item for item in active_tasks if item.due_at and _aware(item.due_at) < datetime.now(timezone.utc)]
        on_time = [item for item in completed_period if item.completed_at and _aware(item.completed_at) <= _aware(item.due_at)]
        resolution_hours = [
            (_aware(item.completed_at) - _aware(item.created_at)).total_seconds() / 3600
            for item in completed_period if item.completed_at and item.created_at
        ]
        delay_hours = [
            (datetime.now(timezone.utc) - _aware(item.due_at)).total_seconds() / 3600
            for item in overdue_tasks if item.due_at
        ]

        agent_rows = []
        for agent in agents:
            agent_leads = [lead for lead in leads if lead.assigned_to == agent.id]
            agent_sales = [deal for deal in sales if lead_map.get(deal.lead_id) and lead_map[deal.lead_id].assigned_to == agent.id]
            agent_cohort_ids = {lead.id for lead in agent_leads}
            agent_converted_ids = {deal.lead_id for deal in agent_sales if deal.lead_id in agent_cohort_ids}
            agent_tasks = [item for item in active_tasks if item.assigned_to == agent.id]
            agent_completed = [item for item in completed_period if item.assigned_to == agent.id]
            agent_on_time = [item for item in agent_completed if item.completed_at and _aware(item.completed_at) <= _aware(item.due_at)]
            agent_rows.append({
                "id": agent.id,
                "name": agent.name,
                "leads": len(agent_leads),
                "contacted": sum(1 for lead in agent_leads if lead.last_contacted),
                "advised": len({item.lead_id for item in period_advisories if item.advisor_id == agent.id}),
                "reservations": sum(1 for deal in reservations if lead_map.get(deal.lead_id) and lead_map[deal.lead_id].assigned_to == agent.id),
                "sales": len(agent_sales),
                "conversion_rate": _pct(len(agent_converted_ids), len(agent_leads)),
                "active_tasks": len(agent_tasks),
                "overdue_tasks": sum(1 for item in agent_tasks if item in overdue_tasks),
                "completed_tasks": len(agent_completed),
                "on_time_rate": _pct(len(agent_on_time), len(agent_completed)),
            })

        project_rows = []
        for project in projects:
            project_deals = [deal for deal in deals if deal.property and deal.property.project_id == project.id]
            if not project_deals and project_id is None:
                continue
            project_sales = [deal for deal in sales if deal.property and deal.property.project_id == project.id]
            project_rows.append({
                "id": project.id,
                "name": project.name,
                "deals": len(project_deals),
                "reservations": sum(1 for deal in reservations if deal.property and deal.property.project_id == project.id),
                "sales": len(project_sales),
                "uf": round(sum(_price(deal.property, "uf") for deal in project_sales), 2),
                "clp": round(sum(_price(deal.property, "clp") for deal in project_sales)),
            })

        source_rows = []
        for source_name, source_leads in sorted(defaultdict(list, {
            key: [lead for lead in leads if _source(lead) == key]
            for key in {_source(lead) for lead in eligible_leads}
        }).items()):
            source_sales = sum(
                1 for deal in sales
                if deal.lead_id in lead_map and _source(lead_map[deal.lead_id]) == source_name
            )
            source_converted_ids = {
                deal.lead_id for deal in sales
                if deal.lead_id in {lead.id for lead in source_leads}
            }
            source_rows.append({
                "source": source_name,
                "leads": len(source_leads),
                "contacted": sum(1 for lead in source_leads if lead.last_contacted),
                "advised": sum(
                    1 for lead in eligible_leads
                    if _source(lead) == source_name and lead.id in advised_ids
                ),
                "sales": source_sales,
                "conversion_rate": _pct(len(source_converted_ids), len(source_leads)),
            })

        lost_reasons = Counter(lead.close_reason or "Sin motivo registrado" for lead in lost_leads)
        lost_reasons.update(deal.cancellation_reason or "Sin motivo registrado" for deal in cancelled_deals)

        weeks = []
        cursor = start - timedelta(days=start.weekday())
        while cursor < end and len(weeks) < 54:
            week_end = cursor + timedelta(days=7)
            week_leads = [lead for lead in leads if _in_period(lead.created_at, cursor, week_end)]
            week_advised_ids = {item.lead_id for item in period_advisories if _in_period(item.occurred_at, cursor, week_end)}
            weeks.append({
                "week": cursor.date().isoformat(),
                "label": cursor.strftime("%d/%m"),
                "leads": len(week_leads),
                "advised": len(week_advised_ids),
                "sales": sum(1 for deal in sales if _in_period(deal.escritura_signed_at, cursor, week_end)),
                "tasks_completed": sum(1 for item in completed_period if _in_period(item.completed_at, cursor, week_end)),
            })
            cursor = week_end

        drilldown = {
            "received": leads,
            "assigned": assigned,
            "contacted": contacted,
            "advised": advised,
            "without_follow_up": without_follow_up,
            "lost": lost_leads,
            "reservations": [lead_map[deal.lead_id] for deal in reservations if deal.lead_id in lead_map],
            "sales": [lead_map[deal.lead_id] for deal in sales if deal.lead_id in lead_map],
            "appointments_scheduled": [
                lead_map[item.lead_id] for item in appointments
                if item.lead_id in lead_map
                and _in_period(item.start_time, start, end)
                and _enum_value(item.status) in ("scheduled", "confirmed")
            ],
            "appointments_completed": [
                lead_map[item.lead_id] for item in appointments
                if item.lead_id in lead_map
                and _in_period(item.start_time, start, end)
                and _enum_value(item.status) == "completed"
            ],
            "appointments_cancelled": [
                lead_map[item.lead_id] for item in appointments
                if item.lead_id in lead_map
                and _in_period(item.start_time, start, end)
                and _enum_value(item.status) == "cancelled"
            ],
            "appointments_no_show": [
                lead_map[item.lead_id] for item in appointments
                if item.lead_id in lead_map
                and _in_period(item.start_time, start, end)
                and _enum_value(item.status) == "no_show"
            ],
        }

        return {
            "period": {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
            "filters": {
                "agents": [{"id": agent.id, "name": agent.name} for agent in agents],
                "projects": [{"id": project.id, "name": project.name} for project in projects],
                "sources": available_sources,
            },
            "commercial": {
                "received": len(leads),
                "assigned": len(assigned),
                "contacted": len(contacted),
                "advised": len(advised),
                "without_follow_up": len(without_follow_up),
                "first_response_minutes": round(sum(response_minutes) / len(response_minutes), 1) if response_minutes else None,
                "appointments": {
                    "scheduled": appointment_counts["scheduled"] + appointment_counts["confirmed"],
                    "completed": appointment_counts["completed"],
                    "cancelled": appointment_counts["cancelled"],
                    "no_show": appointment_counts["no_show"],
                },
                "reservations": len(reservations),
                "sales": len(sales),
                "sales_uf": round(sum(_price(deal.property, "uf") for deal in sales), 2),
                "sales_clp": round(sum(_price(deal.property, "clp") for deal in sales)),
                "conversion_rate": _pct(
                    len({deal.lead_id for deal in sales if deal.lead_id in {lead.id for lead in leads}}),
                    len(leads),
                ),
                "lead_to_sale_days": round(sum(
                    ((_aware(deal.escritura_signed_at) - _aware(lead_map[deal.lead_id].created_at)).total_seconds() / 86400)
                    for deal in sales if deal.escritura_signed_at and deal.lead_id in lead_map and lead_map[deal.lead_id].created_at
                ) / len(sales), 1) if sales else None,
                "lost": len(lost_leads) + len(cancelled_deals),
            },
            "tasks": {
                "created": len(task_period),
                "pending": sum(1 for item in active_tasks if item.status == "open"),
                "in_progress": sum(1 for item in active_tasks if item.status == "in_progress"),
                "overdue": len(overdue_tasks),
                "completed": len(completed_period),
                "completion_rate": _pct(len(completed_from_created), len(task_period)),
                "on_time_rate": _pct(len(on_time), len(completed_period)),
                "avg_resolution_hours": round(sum(resolution_hours) / len(resolution_hours), 1) if resolution_hours else None,
                "avg_delay_hours": round(sum(delay_hours) / len(delay_hours), 1) if delay_hours else None,
            },
            "by_agent": agent_rows,
            "by_project": sorted(project_rows, key=lambda row: row["sales"], reverse=True),
            "by_source": sorted(source_rows, key=lambda row: row["leads"], reverse=True),
            "lost_reasons": [{"reason": reason, "count": count} for reason, count in lost_reasons.most_common()],
            "trend": weeks,
            "drilldowns": {
                key: {"total": len(items), "data": [_lead_summary(item) for item in items[:100]]}
                for key, items in drilldown.items()
            },
            "definitions": {
                "contacted": "Lead con fecha de último contacto registrada.",
                "first_response": "Promedio entre ingreso y primer contacto registrado; puede incluir automatización histórica.",
                "without_follow_up": "Lead activo asignado, sin contacto, asesoría verificada ni tarea activa.",
                "sales_clp": "Suma del precio CLP guardado en las unidades vendidas; no convierte UF sin un valor histórico.",
            },
        }
