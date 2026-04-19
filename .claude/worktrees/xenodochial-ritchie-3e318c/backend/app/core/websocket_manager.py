"""
WebSocket connection manager (TASK-027).

Manages active WebSocket connections per broker and broadcasts events to
all connected clients of a given broker.

Event types
-----------
- new_message    : new inbound chat message from a lead
- stage_changed  : lead pipeline stage changed
- lead_assigned  : lead assigned to an agent
- lead_hot       : lead score crossed HOT threshold
- typing         : Sofía is generating a response (for chat UI)

Multi-worker broadcast (Phase 5)
---------------------------------
When ``init_redis()`` is called on startup, broadcasts are published via Redis
Pub/Sub (channel ``ws:broker:{broker_id}``) so every worker process receives
the event and delivers it to its own local WebSocket connections.

Without Redis (development / single-worker), broadcast falls back to
in-process delivery only.

Usage (from other services)
----------------------------
    from app.core.websocket_manager import ws_manager
    await ws_manager.broadcast(broker_id=1, event="new_message", data={...})
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Asyncio-safe manager for WebSocket connections with optional Redis Pub/Sub.

    Connections are keyed by broker_id. Within a broker, each connection
    is identified by (user_id, websocket).

    Call ``await init_redis(redis_url)`` once on application startup to enable
    cross-process broadcast via Redis Pub/Sub.
    """

    def __init__(self) -> None:
        # broker_id → list of (user_id, WebSocket)
        self._connections: Dict[int, List[tuple[str, WebSocket]]] = {}
        self._lock = asyncio.Lock()
        self._redis = None          # redis.asyncio.Redis instance (set by init_redis)
        self._subscriber_task: Optional[asyncio.Task] = None

    # ── Redis Pub/Sub lifecycle ───────────────────────────────────────────────

    async def init_redis(self, redis_url: str) -> None:
        """Initialize Redis Pub/Sub listener. Call once on app startup."""
        try:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(redis_url, decode_responses=True)
            # Test connectivity before starting the listener
            await self._redis.ping()
            self._subscriber_task = asyncio.create_task(
                self._redis_listener(), name="ws-redis-listener"
            )
            logger.info("[WS] Redis Pub/Sub listener started (url=%s)", redis_url)
        except Exception as exc:
            logger.warning(
                "[WS] Redis init failed — falling back to local-only broadcast: %s", exc
            )
            self._redis = None

    async def shutdown(self) -> None:
        """Cancel the Redis listener and close the connection. Call on app shutdown."""
        if self._subscriber_task and not self._subscriber_task.done():
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass
        if self._redis:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None

    async def _redis_listener(self) -> None:
        """Subscribe to all broker and user channels, deliver to local connections."""
        try:
            pubsub = self._redis.pubsub()
            await pubsub.psubscribe("ws:broker:*", "ws:user:*")
            async for message in pubsub.listen():
                if message.get("type") not in ("pmessage", "message"):
                    continue
                try:
                    payload = json.loads(message["data"])
                    channel: str = message.get("channel", "")

                    if channel.startswith("ws:user:"):
                        # ws:user:{broker_id}:{user_id}
                        parts = channel.split(":", 3)
                        if len(parts) == 4:
                            bid = int(parts[2])
                            uid = parts[3]
                            await self._local_send_to_user(bid, uid, payload)
                    else:
                        # ws:broker:{broker_id}
                        bid = payload.get("broker_id")
                        if bid is not None:
                            await self._local_broadcast_payload(int(bid), payload)
                except Exception as exc:
                    logger.debug("[WS-Redis] Listener parse error: %s", exc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("[WS-Redis] Listener crashed: %s", exc)

    # ── Connection lifecycle ──────────────────────────────────────────────────

    async def connect(self, broker_id: int, user_id: str, ws: WebSocket) -> None:
        """Register a WebSocket connection. The caller must call ws.accept() first."""
        async with self._lock:
            if broker_id not in self._connections:
                self._connections[broker_id] = []
            self._connections[broker_id].append((user_id, ws))
        logger.info("[WS] Connected broker=%s user=%s total=%d", broker_id, user_id, self.count(broker_id))

    async def disconnect(self, broker_id: int, user_id: str, ws: WebSocket) -> None:
        async with self._lock:
            conns = self._connections.get(broker_id, [])
            self._connections[broker_id] = [(uid, w) for uid, w in conns if w is not ws]
        logger.info("[WS] Disconnected broker=%s user=%s total=%d", broker_id, user_id, self.count(broker_id))

    # ── Broadcast ─────────────────────────────────────────────────────────────

    async def broadcast(self, broker_id: int, event: str, data: dict) -> int:
        """
        Send an event to all connections for ``broker_id``.

        When Redis is available, publishes to ``ws:broker:{broker_id}`` so all
        worker processes deliver the message to their own local connections.
        Falls back to local-only delivery when Redis is unavailable.

        Returns the number of successfully sent messages (local count only
        when using Redis, since remote delivery count is unknown).
        """
        if self._redis is not None:
            try:
                payload = json.dumps({
                    "broker_id": broker_id,
                    "event": event,
                    "data": data,
                    "ts": time.time(),
                })
                await self._redis.publish(f"ws:broker:{broker_id}", payload)
                return 1  # published; actual delivery count is unknown
            except Exception as exc:
                logger.warning("[WS] Redis publish failed, falling back to local: %s", exc)

        # Local-only fallback
        payload_dict = {"event": event, "data": data, "ts": time.time()}
        return await self._local_broadcast_payload(broker_id, payload_dict)

    async def send_to_user(self, broker_id: int, user_id: str, event: str, data: dict) -> bool:
        """
        Send an event to a specific user within a broker.

        Uses Redis Pub/Sub when available so the message reaches the correct
        worker process even if that user's connection lives elsewhere.

        Returns True if published (Redis mode) or delivered (local mode).
        """
        if self._redis is not None:
            try:
                payload = json.dumps({
                    "broker_id": broker_id,
                    "event": event,
                    "data": data,
                    "ts": time.time(),
                })
                await self._redis.publish(f"ws:user:{broker_id}:{user_id}", payload)
                return True
            except Exception as exc:
                logger.warning("[WS] Redis user-publish failed, falling back to local: %s", exc)

        return await self._local_send_to_user(broker_id, user_id, {"event": event, "data": data, "ts": time.time()})

    # ── Internal local-delivery helpers ──────────────────────────────────────

    async def _local_broadcast_payload(self, broker_id: int, payload: dict) -> int:
        """Deliver a pre-built payload dict to all local connections for broker_id."""
        raw = json.dumps(payload)
        conns = list(self._connections.get(broker_id, []))
        sent = 0
        dead: List[tuple[str, WebSocket]] = []

        for uid, ws in conns:
            try:
                await ws.send_text(raw)
                sent += 1
            except Exception as exc:
                logger.debug("[WS] Dead connection broker=%s user=%s: %s", broker_id, uid, exc)
                dead.append((uid, ws))

        if dead:
            async with self._lock:
                conns_now = self._connections.get(broker_id, [])
                self._connections[broker_id] = [(u, w) for u, w in conns_now if (u, w) not in dead]

        return sent

    async def _local_send_to_user(self, broker_id: int, user_id: str, payload: dict) -> bool:
        """Deliver a pre-built payload dict to a specific local user connection."""
        raw = json.dumps(payload)
        for uid, ws in list(self._connections.get(broker_id, [])):
            if uid == str(user_id):
                try:
                    await ws.send_text(raw)
                    return True
                except Exception:
                    pass
        return False

    # ── Stats ─────────────────────────────────────────────────────────────────

    def count(self, broker_id: Optional[int] = None) -> int:
        if broker_id is not None:
            return len(self._connections.get(broker_id, []))
        return sum(len(v) for v in self._connections.values())

    def stats(self) -> dict:
        return {
            "total_connections": self.count(),
            "by_broker": {str(bid): len(conns) for bid, conns in self._connections.items()},
            "redis_connected": self._redis is not None,
        }


# Singleton — import this in all places that need to broadcast
ws_manager = ConnectionManager()
