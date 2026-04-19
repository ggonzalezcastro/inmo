# Webhook Payload Reference

Inbound webhooks are called **directly by the messaging provider**. They are unauthenticated
(security is via HMAC signature verification where available).

---

## Telegram Webhook

**Endpoint:** `POST /webhooks/telegram`

Registered via `setWebhook` on the Telegram Bot API. Telegram sends an **Update** object
on every new message or event.

### Headers
| Header | Value |
|--------|-------|
| `Content-Type` | `application/json` |
| `X-Telegram-Bot-Api-Secret-Token` | `<secret>` (if `TELEGRAM_WEBHOOK_SECRET` is set) |

### Payload — Text message from user

```json
{
  "update_id": 123456789,
  "message": {
    "message_id": 42,
    "from": {
      "id": 987654321,
      "is_bot": false,
      "first_name": "Juan",
      "last_name": "Pérez",
      "username": "juanperez",
      "language_code": "es"
    },
    "chat": {
      "id": 987654321,
      "first_name": "Juan",
      "last_name": "Pérez",
      "username": "juanperez",
      "type": "private"
    },
    "date": 1740000000,
    "text": "Hola, me interesa un departamento"
  }
}
```

### Payload — Voice message

```json
{
  "update_id": 123456790,
  "message": {
    "message_id": 43,
    "from": {"id": 987654321, "first_name": "Juan"},
    "chat": {"id": 987654321, "type": "private"},
    "date": 1740000010,
    "voice": {
      "duration": 5,
      "mime_type": "audio/ogg",
      "file_id": "AwACAgIAAxk...",
      "file_size": 12345
    }
  }
}
```

### Response
```json
{"ok": true}
```

Always return **200 OK** — Telegram retries on any other status code.

---

## WhatsApp Webhook (Meta / 360dialog)

**Endpoint:** `POST /webhooks/chat/{broker_id}/whatsapp`

Supports both **Meta Cloud API** and **360dialog** payload formats.
The handler auto-detects the format from the payload structure.

### Headers
| Header | Value |
|--------|-------|
| `Content-Type` | `application/json` |
| `X-Hub-Signature-256` | `sha256=<hmac>` (Meta Cloud API) |

### Payload — Meta Cloud API (incoming message)

```json
{
  "object": "whatsapp_business_account",
  "entry": [
    {
      "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
      "changes": [
        {
          "value": {
            "messaging_product": "whatsapp",
            "metadata": {
              "display_phone_number": "56912345678",
              "phone_number_id": "PHONE_NUMBER_ID"
            },
            "contacts": [
              {
                "profile": {"name": "Juan Pérez"},
                "wa_id": "56987654321"
              }
            ],
            "messages": [
              {
                "from": "56987654321",
                "id": "wamid.HBgN...",
                "timestamp": "1740000000",
                "type": "text",
                "text": {"body": "Hola, busco departamento"}
              }
            ]
          },
          "field": "messages"
        }
      ]
    }
  ]
}
```

### Payload — 360dialog format

```json
{
  "contacts": [
    {
      "profile": {"name": "María González"},
      "wa_id": "56911223344"
    }
  ],
  "messages": [
    {
      "from": "56911223344",
      "id": "ABGGFlA5FpafAgo6tHcNmNjXmuSf",
      "timestamp": "1740000000",
      "type": "text",
      "text": {"body": "¿Tienen proyectos en Las Condes?"}
    }
  ]
}
```

### Webhook Verification (Meta GET challenge)

Meta sends a GET request to verify the webhook before activating it:

```
GET /webhooks/chat/{broker_id}/whatsapp
  ?hub.mode=subscribe
  &hub.challenge=1234567890
  &hub.verify_token=<WHATSAPP_VERIFY_TOKEN>
```

The endpoint responds with the `hub.challenge` value as plain text if `hub.verify_token`
matches the configured `WHATSAPP_VERIFY_TOKEN` environment variable.

### Response
```json
{"ok": true}
```

---

## Unified Chat Webhook

**Endpoint:** `POST /webhooks/chat/{broker_id}/{provider_name}`

Where `provider_name` ∈ `{telegram, whatsapp, webchat}`.

This single endpoint handles all providers and routes to the correct parser.

### Path parameters
| Parameter | Description |
|-----------|-------------|
| `broker_id` | The broker's numeric ID (used to scope the lead and select the right AI config) |
| `provider_name` | `telegram` / `whatsapp` / `webchat` |

---

## VAPI Voice Webhook

**Endpoint:** `POST /api/v1/calls/webhooks/voice/vapi`
**Endpoint (generic):** `POST /api/v1/calls/webhooks/voice`

Called by VAPI after call events (end-of-call report, mid-call transcript).

### Payload — end-of-call report

```json
{
  "message": {
    "type": "end-of-call-report",
    "call": {
      "id": "vapi-call-uuid",
      "status": "ended",
      "startedAt": "2026-02-22T10:00:00Z",
      "endedAt": "2026-02-22T10:03:45Z",
      "phoneNumber": {"number": "+56987654321"},
      "customer": {"number": "+56987654321"}
    },
    "transcript": "Sofía: ¡Hola! Soy Sofía...\nLead: Hola, me interesa un depto...",
    "summary": "Lead interested in 2-bedroom apartment in Las Condes.",
    "recordingUrl": "https://storage.vapi.ai/recordings/xxx.mp3",
    "stereoRecordingUrl": null
  }
}
```

### Response
```json
{"ok": true}
```

---

## Error Handling

All webhook endpoints return `{"ok": true}` for any payload they receive, **including**
payloads they cannot parse. This prevents provider retry loops.

Internal errors are logged with structured JSON for post-hoc debugging.
If signature verification fails (when `TELEGRAM_WEBHOOK_SECRET` or `WHATSAPP_APP_SECRET`
is set), the endpoint returns `403 Forbidden` with `{"detail": "Invalid signature"}`.
