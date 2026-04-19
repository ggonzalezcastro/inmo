"""
Live-tail WebSocket for agent events.

Clients connect to:  WS /ws/admin/observability/live?broker_id=&event_type=&agent_type=

The server listens on the Redis channel "obs:live:{broker_id}" (or "obs:live:*" for all)
and forwards matching events to the connected client.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from starlette.websockets import WebSocketState

from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)
live_router = APIRouter(tags=["observability-live"])

REDIS_CHANNEL_PREFIX = "obs:live"


@live_router.websocket("/ws/admin/observability/live")
async def live_tail(
    websocket: WebSocket,
    broker_id: Optional[int] = Query(None),
    event_type: Optional[str] = Query(None),
    agent_type: Optional[str] = Query(None),
):
    """
    Stream real-time agent_events to the dashboard.

    Filters:
    - broker_id: only events for this broker (None = all, SUPERADMIN only)
    - event_type: comma-separated list of event types to include
    - agent_type: only events from this agent
    """
    await websocket.accept()
    event_types = set(event_type.split(",")) if event_type else set()

    channel = f"{REDIS_CHANNEL_PREFIX}:{broker_id}" if broker_id else f"{REDIS_CHANNEL_PREFIX}:*"

    try:
        redis = await get_redis()
        pubsub = redis.pubsub()

        if broker_id:
            await pubsub.subscribe(channel)
        else:
            await pubsub.psubscribe(channel)

        async def _reader():
            async for message in pubsub.listen():
                if message["type"] not in ("message", "pmessage"):
                    continue
                try:
                    data = json.loads(message["data"])
                except (json.JSONDecodeError, TypeError):
                    continue

                # Apply filters
                if event_types and data.get("event_type") not in event_types:
                    continue
                if agent_type and data.get("agent_type") != agent_type:
                    continue

                if websocket.client_state != WebSocketState.CONNECTED:
                    break
                await websocket.send_json(data)

        reader_task = asyncio.create_task(_reader())

        # Keep-alive: forward any client pings / handle disconnect
        while websocket.client_state == WebSocketState.CONNECTED:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if msg == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                # Send heartbeat so nginx doesn't close idle connection
                await websocket.send_json({"type": "heartbeat"})
            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("Live tail WS error: %s", exc)
    finally:
        try:
            if broker_id:
                await pubsub.unsubscribe(channel)
            else:
                await pubsub.punsubscribe(channel)
            await pubsub.close()
        except Exception:
            pass
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()
