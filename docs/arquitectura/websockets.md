# WebSocket Architecture

**Date:** 2026-04-17
**Status:** Confirmed

## Overview

The WebSocket system provides real-time, bidirectional communication between the backend and frontend clients. It enables live updates for lead management, AI response streaming, and pipeline stage changes across all connected users within a broker.

---

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Frontend (React)                               │
│                                                                             │
│  WebSocketContext (singleton per session)                                   │
│                                                                             │
│  ${BASE_WS_URL}/ws/${broker_id}/${user_id}                                 │
│       │                                                                     │
│       │  1. Connect (no token yet)                                         │
│       │  2. Send {token} on open                                           │
│       │  3. Receive normalized events                                       │
│       │                                                                     │
│       ▼                                                                     │
└─────────────────────────────────────────────────────────────────────────────┘
       │ WebSocket
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Backend (FastAPI)                                  │
│                                                                             │
│  GET /ws/{broker_id}/{user_id}                                              │
│       │                                                                     │
│       │  ┌─────────────────────────────────────────────────────────────┐   │
│       │  │              WebSocket Handler                               │   │
│       │  │                                                             │   │
│       │  │  1. Receive token from client                               │   │
│       │  │  2. Validate JWT                                            │   │
│       │  │  3. Extract broker_id, user_id                              │   │
│       │  │  4. Register: ws_manager.connect(ws, broker_id, user_id)    │   │
│       │  │  5. Send {event: "connected", data: {user_id}}               │   │
│       │  │  6. Listen for messages / broadcast events                   │   │
│       │  │  7. Cleanup on disconnect                                    │   │
│       │  └─────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     ConnectionManager (ws_manager)                    │   │
│  │                     (in-memory, single-process)                       │   │
│  │                                                                     │   │
│  │  active_connections: Dict[int, Dict[int, WebSocket]]               │   │
│  │  {broker_id: {user_id: WebSocket}}                                   │   │
│  │                                                                     │   │
│  │  ├── connect(broker_id, user_id, websocket)                         │   │
│  │  ├── disconnect(broker_id, user_id)                                 │   │
│  │  ├── send_to_user(broker_id, user_id, message)                     │   │
│  │  └── broadcast(broker_id, event, data)  ──► ALL users in broker     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Events originate from:                                                     │
│  ├── Chat Orchestrator (new_message, typing, ai_response)                 │
│  ├── Pipeline Service (stage_changed, lead_assigned, lead_hot)            │
│  ├── Agent System (human_mode_changed, human_mode_incoming)               │
│  └── Sentiment Analysis (lead_frustrated)                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ConnectionManager API

### Class Definition

```python
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Dict[int, WebSocket]] = {}
        # Structure: {broker_id: {user_id: WebSocket}}
```

### Methods

#### `connect(websocket: WebSocket, broker_id: int, user_id: int) -> None`

Registers a new WebSocket connection.

- **broker_id:** Tenant identifier (brokerage company)
- **user_id:** Authenticated user within the broker

Stores the WebSocket in `active_connections[broker_id][user_id]`.

#### `disconnect(broker_id: int, user_id: int) -> None`

Removes a WebSocket connection. Called on clean disconnect or connection drop.

#### `send_to_user(broker_id: int, user_id: int, message: dict) -> None`

Sends a message to a specific user within a broker.

```python
await ws_manager.send_to_user(
    broker_id=1,
    user_id=123,
    message={"event": "connected", "data": {"user_id": 123}}
)
```

**Error handling:** Silently ignores if user is not connected.

#### `broadcast(broker_id: int, event: str, data: dict) -> None`

Sends an event to **all** connected users in a broker.

```python
await ws_manager.broadcast(
    broker_id=1,
    event="new_message",
    data={"lead_id": 123, "message": "Hola", "direction": "in"}
)
```

---

## WebSocket Endpoint

```
WS /ws/{broker_id}/{user_id}
```

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `broker_id` | integer | Broker tenant ID |
| `user_id` | integer | Authenticated user ID |

**Connection Sequence:**

1. Client opens WebSocket connection (no token in URL)
2. On `onopen`, client sends JWT token:
   ```javascript
   ws.onopen = () => {
     ws.send(JSON.stringify({ token: "eyJhbGci..." }))
   }
   ```
3. Server validates token, extracts `broker_id` and `user_id`
4. Server registers connection in `ws_manager`
5. Server sends confirmation:
   ```json
   {"event": "connected", "data": {"user_id": 123}}
   ```

---

## Event Reference

### connected

Sent immediately after successful authentication and connection registration.

```json
{
  "event": "connected",
  "data": {
    "user_id": 123
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | integer | The authenticated user's ID |

---

### new_message

Broadcast when a new chat message is received or sent.

```json
{
  "event": "new_message",
  "data": {
    "lead_id": 123,
    "message": "texto del mensaje",
    "direction": "in",
    "human": true,
    "sent_by": 456
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `lead_id` | integer | Lead this message belongs to |
| `message` | string | Message content |
| `direction` | string | `"in"` = from lead, `"out"` = to lead |
| `human` | boolean | `true` if sent by human agent, `false` if AI |
| `sent_by` | integer | User ID who sent the message (null if from lead) |

---

### typing

Broadcast when a lead is typing a message.

```json
{
  "event": "typing",
  "data": {
    "lead_id": 123
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `lead_id` | integer | Lead that is typing |

---

### ai_response

Broadcast when an AI response has been fully generated and sent.

```json
{
  "event": "ai_response",
  "data": {
    "lead_id": 123,
    "response": "texto de IA",
    "lead_score": 45.0
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `lead_id` | integer | Lead the response was sent to |
| `response` | string | AI-generated message content |
| `lead_score` | float | Updated lead score after this interaction |

---

### stage_changed

Broadcast when a lead moves to a new pipeline stage.

```json
{
  "event": "stage_changed",
  "data": {
    "lead_id": 123,
    "old_stage": "entrada",
    "new_stage": "perfilamiento",
    "reason": "..."
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `lead_id` | integer | Lead that changed stages |
| `old_stage` | string | Previous pipeline stage |
| `new_stage` | string | New pipeline stage |
| `reason` | string | Reason for the transition |

**Pipeline Stages:**
- `entrada` — Lead entry point
- `perfilamiento` — Profiling and qualification
- `calificacion_financiera` — Financial qualification
- `agendado` — Appointment scheduled
- `seguimiento` — Follow-up in progress
- `referidos` — Referral stage
- `ganado` — Won (closed sale)
- `perdido` — Lost

---

### lead_assigned

Broadcast when a lead is assigned to an agent.

```json
{
  "event": "lead_assigned",
  "data": {
    "lead_id": 123,
    "assigned_to": 456
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `lead_id` | integer | Lead that was assigned |
| `assigned_to` | integer | User ID of the assigned agent |

---

### lead_hot

Broadcast when a lead's status changes to HOT (high priority).

```json
{
  "event": "lead_hot",
  "data": {
    "lead_id": 123
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `lead_id` | integer | Lead that is now hot |

---

### human_mode_changed

Broadcast when AI mode is disabled and a human agent takes over.

```json
{
  "event": "human_mode_changed",
  "data": {
    "lead_id": 123,
    "human_mode": true,
    "taken_by": 456
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `lead_id` | integer | Lead affected |
| `human_mode` | boolean | `true` = human takeover active, `false` = AI resumed |
| `taken_by` | integer \| null | User ID who took over, or `null` if AI resumed |

---

### human_mode_incoming

Broadcast when a new message arrives for a lead that is in human mode.

```json
{
  "event": "human_mode_incoming",
  "data": {
    "lead_id": 123,
    "lead_name": "John Doe",
    "phone": "+56912345678",
    "message_text": "Hola, tengo una consulta",
    "channel": "telegram",
    "assigned_to": 456
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `lead_id` | integer | Lead that sent the message |
| `lead_name` | string | Lead's display name |
| `phone` | string | Lead's phone number |
| `message_text` | string | Content of the incoming message |
| `channel` | string | Message channel (`telegram`, `whatsapp`, etc.) |
| `assigned_to` | integer | User ID the lead is assigned to |

---

### lead_frustrated

Broadcast when sentiment analysis detects frustration in a lead's message.

```json
{
  "event": "lead_frustrated",
  "data": {
    "lead_id": 123
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `lead_id` | integer | Lead exhibiting frustration |

---

### ping

Keepalive event sent periodically to maintain the connection.

```json
{
  "event": "ping",
  "data": {}
}
```

Clients should respond with `pong` to acknowledge.

---

## Frontend Consumption

### WebSocketContext

The frontend provides a singleton context for managing the WebSocket connection:

```typescript
import { WebSocketContext } from '@/contexts/WebSocketContext'

function MyComponent() {
  const wsContext = useContext(WebSocketContext)

  useEffect(() => {
    // Subscribe to events
    const unsubscribe = wsContext.subscribe((event) => {
      switch (event.type) {
        case 'new_message':
          console.log('New message:', event.data)
          break
        case 'stage_changed':
          console.log('Stage changed:', event.data)
          break
        case 'ai_response':
          console.log('AI response:', event.data)
          break
        // ... handle other events
      }
    })

    // Cleanup on unmount
    return unsubscribe
  }, [wsContext])

  // ...
}
```

### Connection URL

```typescript
const WS_URL = `${BASE_WS_URL}/ws/${broker_id}/${user_id}`
// e.g., wss://api.example.com/ws/1/123
```

### Event Normalization

The `WebSocketContext` normalizes raw server events by converting `event` to `type`:

```typescript
// Raw from server
{ "event": "connected", "data": { "user_id": 123 } }

// Normalized for subscribers
{ "type": "connected", "data": { "user_id": 123 } }
```

### Reconnection Strategy

The context implements exponential backoff with the following parameters:

| Parameter | Value |
|-----------|-------|
| Initial delay | 1,000 ms |
| Max delay | 30,000 ms |
| Multiplier | 2x |

### Cleanup

```typescript
const unsubscribe = wsContext.subscribe(handler)

// Later, when done:
unsubscribe()
```

---

## Single-Process Limitation

> **WARNING**

The `ConnectionManager` uses an **in-memory dictionary** to store active connections:

```python
self.active_connections: Dict[int, Dict[int, WebSocket]] = {}
```

This means:

- **Single-process only:** Events are only broadcast to users connected to the **same process**.
- **Does NOT work with multiple uvicorn workers:** If running with `uvicorn --workers N`, users connected to different workers will **not receive** broadcast events.
- **Works correctly with:** Single uvicorn process, or multiple gunicorn threads within one process.

**Current workaround:** Run with a single uvicorn worker in production, or use a pub/sub message broker (Redis) for cross-process broadcasting in a future iteration.

---

## Changelog

| Date | Change |
|------|--------|
| 2026-04-17 | Initial document — confirmed `ConnectionManager`, endpoint, all 11 event types, frontend context, and single-process limitation |
