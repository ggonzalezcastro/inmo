"""
Agents API — per-agent Google Calendar configuration and workload.

Endpoints:
  GET  /api/v1/agents/              — list agents of the broker with calendar info (admin)
  PUT  /api/v1/agents/{id}/calendar — configure calendar_id + connected flag (admin)
  DELETE /api/v1/agents/{id}/calendar — disconnect agent calendar (admin)
  GET  /api/v1/agents/workload      — workload stats per agent (admin)
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User, UserRole
from app.services.appointments.round_robin import RoundRobinService

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class AgentCalendarUpdate(BaseModel):
    calendar_id: Optional[str] = None     # Gmail / Workspace email of the agent's calendar
    connected: bool = True                 # Include in round-robin


class AgentInfo(BaseModel):
    id: int
    name: str
    email: str
    is_active: bool
    calendar_id: Optional[str]
    calendar_connected: bool

    class Config:
        from_attributes = True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_admin(current_user: dict):
    role = current_user.get("role", "")
    if role not in (UserRole.ADMIN.value, UserRole.SUPERADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de administrador",
        )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/")
async def list_agents(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all agents of the broker with their calendar configuration."""
    _require_admin(current_user)
    broker_id = current_user.get("broker_id")
    if not broker_id:
        raise HTTPException(status_code=400, detail="Usuario sin broker asignado")

    result = await db.execute(
        select(User).where(
            User.broker_id == broker_id,
            User.role == UserRole.AGENT,
            User.is_active == True,
        ).order_by(User.name)
    )
    agents = result.scalars().all()

    return [
        {
            "id": a.id,
            "name": a.name,
            "email": a.email,
            "is_active": a.is_active,
            "calendar_id": a.google_calendar_id,
            "calendar_connected": a.google_calendar_connected,
        }
        for a in agents
    ]


@router.get("/workload")
async def get_agents_workload(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return workload stats for all agents of the broker."""
    _require_admin(current_user)
    broker_id = current_user.get("broker_id")
    if not broker_id:
        raise HTTPException(status_code=400, detail="Usuario sin broker asignado")

    workload = await RoundRobinService.get_agents_workload(db, broker_id=broker_id)
    return workload


@router.put("/{agent_id}/calendar")
async def configure_agent_calendar(
    agent_id: int,
    body: AgentCalendarUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Configure a Google Calendar for an agent.

    The `calendar_id` should be the Gmail/Workspace email address of the agent's
    calendar. The agent must have shared their Google Calendar with the service
    account email configured in GOOGLE_CREDENTIALS_PATH.

    Only admins of the same broker can configure agents.
    """
    _require_admin(current_user)
    broker_id = current_user.get("broker_id")

    result = await db.execute(
        select(User).where(User.id == agent_id, User.broker_id == broker_id)
    )
    agent = result.scalars().first()
    if not agent:
        raise HTTPException(status_code=404, detail="Asesor no encontrado")
    if agent.role != UserRole.AGENT:
        raise HTTPException(status_code=400, detail="El usuario no es un asesor")

    agent.google_calendar_id = body.calendar_id
    agent.google_calendar_connected = body.connected if body.calendar_id else False
    await db.commit()

    logger.info(
        "Agent %s calendar configured: calendar_id=%s connected=%s (by admin %s)",
        agent_id, body.calendar_id, agent.google_calendar_connected, current_user.get("user_id"),
    )

    return {
        "message": "Calendario del asesor actualizado",
        "agent_id": agent_id,
        "calendar_id": agent.google_calendar_id,
        "calendar_connected": agent.google_calendar_connected,
    }


@router.delete("/{agent_id}/calendar")
async def disconnect_agent_calendar(
    agent_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect the agent's Google Calendar (removes from round-robin)."""
    _require_admin(current_user)
    broker_id = current_user.get("broker_id")

    result = await db.execute(
        select(User).where(User.id == agent_id, User.broker_id == broker_id)
    )
    agent = result.scalars().first()
    if not agent:
        raise HTTPException(status_code=404, detail="Asesor no encontrado")

    agent.google_calendar_id = None
    agent.google_calendar_connected = False
    await db.commit()

    logger.info("Agent %s calendar disconnected by admin %s", agent_id, current_user.get("user_id"))

    return {"message": "Calendario desconectado", "agent_id": agent_id}
