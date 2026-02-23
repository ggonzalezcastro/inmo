"""
WebSocket endpoint for real-time broker dashboard updates (TASK-027).

Endpoint
--------
    WS /ws/{broker_id}/{user_id}

Authentication
--------------
The client sends a JWT token as the first text message after connecting:
    {"token": "<jwt>"}
If the token is invalid or the user doesn't belong to the requested broker,
the connection is closed with code 4001.

Client → Server messages
-------------------------
    {"type": "ping"}  → server replies {"type": "pong"}

Server → Client events
-----------------------
All events have the shape:
    {"event": "<type>", "data": {...}, "ts": <epoch>}

Event types:
    connected     — handshake confirmation
    new_message   — new inbound lead message
    stage_changed — lead pipeline stage updated
    lead_assigned — lead assigned to agent
    lead_hot      — lead crossed HOT threshold
    typing        — AI is generating a response
    ping          — server heartbeat

Fallback
--------
If WebSocket is unavailable, the frontend should poll
GET /api/v1/leads every 30 seconds.
"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()

_HEARTBEAT_INTERVAL = 30  # seconds


async def _authenticate(ws: WebSocket, broker_id: int):
    """
    Wait up to 10 s for the client to send ``{"token": "<jwt>"}``.
    Returns the decoded payload dict, or None on failure.
    """
    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=10.0)
        msg = json.loads(raw)
        token = msg.get("token", "")
        if not token:
            return None

        from app.middleware.auth import decode_access_token
        payload = decode_access_token(token)
        if not payload:
            return None

        role = (payload.get("role") or "").upper()
        user_broker_id = payload.get("broker_id")

        if role == "SUPERADMIN":
            return payload
        if user_broker_id == broker_id:
            return payload
        return None

    except (asyncio.TimeoutError, json.JSONDecodeError, Exception) as exc:
        logger.debug("[WS] Auth error: %s", exc)
        return None


@router.websocket("/{broker_id}/{user_id}")
async def websocket_endpoint(ws: WebSocket, broker_id: int, user_id: str):
    """
    Real-time event stream for a broker dashboard.

    Protocol:
    1. Client connects.
    2. Client sends ``{"token": "<jwt>"}`` within 10 s.
    3. Server validates token → closes (4001) or registers connection.
    4. Server sends ``{"event": "connected", ...}``.
    5. Server sends ``{"event": "ping"}`` every 30 s as heartbeat.
    6. Client may send ``{"type": "ping"}`` → server replies ``{"type": "pong"}``.
    """
    await ws.accept()

    user = await _authenticate(ws, broker_id)
    if not user:
        await ws.close(code=4001, reason="Unauthorized")
        return

    await ws_manager.connect(broker_id, user_id, ws)

    try:
        # Confirm connection
        await ws.send_json({
            "event": "connected",
            "data": {"broker_id": broker_id, "user_id": user_id},
        })

        while True:
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=_HEARTBEAT_INTERVAL)
                msg = json.loads(raw) if raw else {}
                if msg.get("type") == "ping":
                    await ws.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                # Heartbeat
                try:
                    await ws.send_json({"event": "ping"})
                except Exception:
                    break
            except json.JSONDecodeError:
                pass  # ignore malformed messages

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("[WS] Error broker=%s user=%s: %s", broker_id, user_id, exc)
    finally:
        await ws_manager.disconnect(broker_id, user_id, ws)
