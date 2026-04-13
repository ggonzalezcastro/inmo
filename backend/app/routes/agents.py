"""
Agents API — per-agent Google Calendar configuration and workload.

Endpoints:
  GET  /api/v1/agents/              — list agents of the broker with calendar info (admin)
  PUT  /api/v1/agents/{id}/calendar — configure calendar_id + connected flag (admin)
  DELETE /api/v1/agents/{id}/calendar — disconnect agent calendar (admin)
  GET  /api/v1/agents/workload      — workload stats per agent (admin)
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
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


class AgentPriorityUpdate(BaseModel):
    agent_ids: List[int]  # ordered list — index 0 = priority 1 (highest)


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
        ).order_by(
            func.coalesce(User.assignment_priority, 999999).asc(),
            User.name.asc(),
        )
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
            "assignment_priority": a.assignment_priority,
        }
        for a in agents
    ]


@router.put("/priority")
async def update_agent_priority(
    body: AgentPriorityUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set the priority order for lead assignment. agent_ids is an ordered list: first = priority 1."""
    _require_admin(current_user)
    broker_id = current_user.get("broker_id")
    if not broker_id:
        raise HTTPException(status_code=400, detail="Usuario sin broker asignado")

    result = await db.execute(
        select(User).where(
            User.broker_id == broker_id,
            User.role == UserRole.AGENT,
            User.is_active == True,
        )
    )
    agents = {a.id: a for a in result.scalars().all()}

    # Validate all submitted IDs belong to this broker
    for aid in body.agent_ids:
        if aid not in agents:
            raise HTTPException(status_code=400, detail=f"Agente {aid} no encontrado en este broker")

    # Assign priority (1-based) to submitted agents
    for idx, aid in enumerate(body.agent_ids):
        agents[aid].assignment_priority = idx + 1

    # Null out agents not included in the priority list
    submitted_ids = set(body.agent_ids)
    for aid, agent in agents.items():
        if aid not in submitted_ids:
            agent.assignment_priority = None

    await db.commit()
    return {"message": "Prioridad actualizada", "count": len(body.agent_ids)}


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


# ── Per-Agent Calendar OAuth ──────────────────────────────────────────────────
# Each agent can connect their personal Google Calendar or Outlook calendar.
# These routes are self-service (the agent themselves calls them, not an admin).

import time
import jwt as pyjwt
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.core.encryption import encrypt_value, decrypt_value

GOOGLE_OAUTH_SCOPES = ["https://www.googleapis.com/auth/calendar"]
OUTLOOK_OAUTH_SCOPES = [
    "https://graph.microsoft.com/Calendars.ReadWrite",
    "offline_access",
]
_STATE_TTL = 600  # 10 minutes


def _make_agent_state_jwt(user_id: int, broker_id: int) -> str:
    """Create a signed JWT state token for the per-agent OAuth flow."""
    payload = {"user_id": user_id, "broker_id": broker_id, "exp": int(time.time()) + _STATE_TTL}
    return pyjwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def _verify_agent_state_jwt(state: str) -> tuple[int, int]:
    """Decode and verify the per-agent state JWT. Returns (user_id, broker_id)."""
    try:
        payload = pyjwt.decode(state, settings.SECRET_KEY, algorithms=["HS256"])
        return int(payload["user_id"]), int(payload["broker_id"])
    except Exception:
        raise HTTPException(status_code=400, detail="Estado OAuth inválido o expirado")


# ── Calendar connection status ─────────────────────────────────────────────────

@router.get("/me/calendar/status")
async def get_my_calendar_status(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the calendar connection status for the current agent."""
    user_id = int(current_user["user_id"])
    broker_id = current_user.get("broker_id")
    result = await db.execute(select(User).where(User.id == user_id, User.broker_id == broker_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return {
        "google": {
            "connected": bool(user.google_refresh_token),
            "email": user.google_calendar_email,
        },
        "outlook": {
            "connected": bool(user.outlook_refresh_token),
            "email": user.outlook_calendar_email,
        },
    }


# ── Google Calendar OAuth ──────────────────────────────────────────────────────

@router.get("/me/calendar/google/auth-url")
async def get_my_google_auth_url(
    current_user: dict = Depends(get_current_user),
):
    """Generate the Google OAuth URL for the current agent to connect their personal calendar."""
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth no está configurado en el servidor",
        )
    try:
        from google_auth_oauthlib.flow import Flow

        user_id = int(current_user["user_id"])
        broker_id = current_user.get("broker_id")
        state = _make_agent_state_jwt(user_id, broker_id)

        client_config = {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uris": [settings.GOOGLE_OAUTH_REDIRECT_URI.replace("/broker/", "/agents/me/")],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
        redirect_uri = settings.GOOGLE_OAUTH_REDIRECT_URI.replace("/broker/", "/agents/me/")
        flow = Flow.from_client_config(client_config, scopes=GOOGLE_OAUTH_SCOPES, state=state)
        flow.redirect_uri = redirect_uri

        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        return {"auth_url": auth_url, "state": state}
    except ImportError:
        raise HTTPException(status_code=503, detail="Librería google-auth-oauthlib no instalada")


@router.get("/me/calendar/google/callback")
async def my_google_calendar_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Google OAuth2 callback for per-agent calendar. Saves the refresh token to the agent's user record."""
    user_id, broker_id = _verify_agent_state_jwt(state)
    try:
        from google_auth_oauthlib.flow import Flow

        client_config = {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uris": [settings.GOOGLE_OAUTH_REDIRECT_URI.replace("/broker/", "/agents/me/")],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
        redirect_uri = settings.GOOGLE_OAUTH_REDIRECT_URI.replace("/broker/", "/agents/me/")
        flow = Flow.from_client_config(client_config, scopes=GOOGLE_OAUTH_SCOPES, state=state)
        flow.redirect_uri = redirect_uri
        flow.fetch_token(code=code)

        credentials = flow.credentials
        refresh_token = credentials.refresh_token

        if not refresh_token:
            logger.warning("Google OAuth callback for agent %s returned no refresh token", user_id)
            return RedirectResponse(url="/appointments?error=no_refresh_token")

        # Get the calendar email from the token info
        calendar_email = None
        try:
            import google.oauth2.credentials
            import googleapiclient.discovery
            creds = google.oauth2.credentials.Credentials(token=credentials.token)
            service = googleapiclient.discovery.build("oauth2", "v2", credentials=creds)
            user_info = service.userinfo().get().execute()
            calendar_email = user_info.get("email")
        except Exception:
            pass

        result = await db.execute(select(User).where(User.id == user_id, User.broker_id == broker_id))
        user = result.scalars().first()
        if not user:
            return RedirectResponse(url="/appointments?error=user_not_found")

        user.google_refresh_token = encrypt_value(refresh_token)
        user.google_calendar_email = calendar_email
        user.google_calendar_connected = True
        await db.commit()

        logger.info("Agent %s connected Google Calendar (%s)", user_id, calendar_email)
        return RedirectResponse(url="/appointments?connected=google")

    except Exception as exc:
        logger.error("Google OAuth callback error for agent %s: %s", user_id, exc)
        return RedirectResponse(url="/appointments?error=google_oauth_failed")


@router.delete("/me/calendar/google/disconnect")
async def disconnect_my_google_calendar(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove the agent's personal Google Calendar connection."""
    user_id = int(current_user["user_id"])
    broker_id = current_user.get("broker_id")
    result = await db.execute(select(User).where(User.id == user_id, User.broker_id == broker_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user.google_refresh_token = None
    user.google_calendar_email = None
    user.google_calendar_connected = False
    await db.commit()

    logger.info("Agent %s disconnected Google Calendar", user_id)
    return {"message": "Google Calendar desconectado"}


# ── Outlook Calendar OAuth ─────────────────────────────────────────────────────

def _build_agent_msal_app():
    """Build a ConfidentialClientApplication for Microsoft Graph OAuth (per-agent)."""
    import msal
    return msal.ConfidentialClientApplication(
        settings.MICROSOFT_CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}",
        client_credential=settings.MICROSOFT_CLIENT_SECRET,
    )


@router.get("/me/calendar/outlook/auth-url")
async def get_my_outlook_auth_url(
    current_user: dict = Depends(get_current_user),
):
    """Generate the Microsoft OAuth URL for the current agent to connect their Outlook calendar."""
    if not settings.MICROSOFT_CLIENT_ID or not settings.MICROSOFT_CLIENT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Outlook OAuth no está configurado en el servidor",
        )

    user_id = int(current_user["user_id"])
    broker_id = current_user.get("broker_id")
    state = _make_agent_state_jwt(user_id, broker_id)

    redirect_uri = settings.MICROSOFT_OAUTH_REDIRECT_URI.replace("/broker/", "/agents/me/")
    app = _build_agent_msal_app()
    auth_url = app.get_authorization_request_url(
        scopes=OUTLOOK_OAUTH_SCOPES,
        state=state,
        redirect_uri=redirect_uri,
    )
    return {"auth_url": auth_url, "state": state}


@router.get("/me/calendar/outlook/callback")
async def my_outlook_calendar_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Microsoft OAuth2 callback for per-agent calendar. Saves the refresh token."""
    user_id, broker_id = _verify_agent_state_jwt(state)
    try:
        redirect_uri = settings.MICROSOFT_OAUTH_REDIRECT_URI.replace("/broker/", "/agents/me/")
        app = _build_agent_msal_app()
        token_response = app.acquire_token_by_authorization_code(
            code=code,
            scopes=OUTLOOK_OAUTH_SCOPES,
            redirect_uri=redirect_uri,
        )

        if "error" in token_response:
            logger.error(
                "Outlook OAuth error for agent %s: %s — %s",
                user_id,
                token_response.get("error"),
                token_response.get("error_description"),
            )
            return RedirectResponse(url="/appointments?error=outlook_oauth_failed")

        refresh_token = token_response.get("refresh_token")
        if not refresh_token:
            return RedirectResponse(url="/appointments?error=no_refresh_token")

        # Retrieve calendar email from Graph API
        calendar_email = None
        import httpx
        try:
            headers = {"Authorization": f"Bearer {token_response['access_token']}"}
            resp = httpx.get("https://graph.microsoft.com/v1.0/me", headers=headers, timeout=10)
            if resp.status_code == 200:
                calendar_email = resp.json().get("mail") or resp.json().get("userPrincipalName")
        except Exception:
            pass

        result = await db.execute(select(User).where(User.id == user_id, User.broker_id == broker_id))
        user = result.scalars().first()
        if not user:
            return RedirectResponse(url="/appointments?error=user_not_found")

        user.outlook_refresh_token = encrypt_value(refresh_token)
        user.outlook_calendar_email = calendar_email
        user.outlook_calendar_connected = True
        await db.commit()

        logger.info("Agent %s connected Outlook Calendar (%s)", user_id, calendar_email)
        return RedirectResponse(url="/appointments?connected=outlook")

    except Exception as exc:
        logger.error("Outlook OAuth callback error for agent %s: %s", user_id, exc)
        return RedirectResponse(url="/appointments?error=outlook_oauth_failed")


@router.delete("/me/calendar/outlook/disconnect")
async def disconnect_my_outlook_calendar(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove the agent's personal Outlook calendar connection."""
    user_id = int(current_user["user_id"])
    broker_id = current_user.get("broker_id")
    result = await db.execute(select(User).where(User.id == user_id, User.broker_id == broker_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user.outlook_refresh_token = None
    user.outlook_calendar_email = None
    user.outlook_calendar_connected = False
    await db.commit()

    logger.info("Agent %s disconnected Outlook Calendar", user_id)
    return {"message": "Outlook Calendar desconectado"}
