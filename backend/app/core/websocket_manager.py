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
from typing import Dict, List, Optional, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Thread-safe (asyncio) manager for WebSocket connections.

    Connections are keyed by broker_id. Within a broker, each connection
    is identified by (user_id, websocket).
    """

    def __init__(self) -> None:
        # broker_id → set of (user_id, WebSocket)
        self._connections: Dict[int, List[tuple[str, WebSocket]]] = {}
        self._lock = asyncio.Lock()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

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

        Returns the number of successfully sent messages.
        """
        payload = json.dumps({"event": event, "data": data, "ts": time.time()})
        conns = list(self._connections.get(broker_id, []))
        sent = 0
        dead: List[tuple[str, WebSocket]] = []

        for uid, ws in conns:
            try:
                await ws.send_text(payload)
                sent += 1
            except Exception as exc:
                logger.debug("[WS] Dead connection broker=%s user=%s: %s", broker_id, uid, exc)
                dead.append((uid, ws))

        # Clean up dead connections
        if dead:
            async with self._lock:
                conns_now = self._connections.get(broker_id, [])
                self._connections[broker_id] = [(u, w) for u, w in conns_now if (u, w) not in dead]

        return sent

    async def send_to_user(self, broker_id: int, user_id: str, event: str, data: dict) -> bool:
        """Send an event to a specific user within a broker. Returns True if sent."""
        payload = json.dumps({"event": event, "data": data, "ts": time.time()})
        for uid, ws in list(self._connections.get(broker_id, [])):
            if uid == user_id:
                try:
                    await ws.send_text(payload)
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
        }


# Singleton — import this in all places that need to broadcast
ws_manager = ConnectionManager()
