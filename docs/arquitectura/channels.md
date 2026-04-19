# Arquitectura de Canales de Chat

**Fecha:** 17 de abril de 2026
**Proyecto:** Inmo CRM
**Versión:** 1.0

---

## Índice

1. [Visión General](#visión-general)
2. [Diagrama de Arquitectura](#diagrama-de-arquitectura)
3. [Proveedores Disponibles](#proveedores-disponibles)
4. [Telegram](#telegram)
5. [WhatsApp](#whatsapp)
6. [Webchat](#webchat)
7. [Consideraciones Cross-Channel](#consideraciones-cross-channel)
8. [Comparativa de Canales](#comparativa-de-canales)
9. [Changelog](#changelog)

---

## Visión General

El sistema Inmo soporta múltiples canales de chat para la comunicación con leads. Cada canal tiene sus propias características, protocolos de autenticación y formatos de identificación de usuario. Todos los mensajes se procesan a través de un orquestador central que normaliza la comunicación antes de entregar al sistema de agentes multi-step.

### Principios de Diseño

- **Multi-tenancy:** Cada broker tiene configuración aislada por canal
- **Normalización:** Todos los canales convergen en un formato interno unificado
- **Escalabilidad:** Webhooks permiten procesamiento asíncrono sin polling
- **Seguridad:** Verificación de firma HMAC para cada canal (donde aplica)

---

## Diagrama de Arquitectura

```
                              ┌─────────────────────────────────────────────────────────────┐
                              │                    ORQUESTADOR DE CHAT                       │
                              │            app/services/chat/orchestrator.py                │
                              └─────────────────────────────────────────────────────────────┘
                                                 │
                    ┌────────────────────────────┼────────────────────────────┐
                    │                            │                            │
                    ▼                            ▼                            ▼
           ┌──────────────┐             ┌──────────────┐             ┌──────────────┐
           │   TELEGRAM   │             │   WHATSAPP   │             │   WEBCHAT    │
           │   Service    │             │   Service    │             │   Handler    │
           └──────────────┘             └──────────────┘             └──────────────┘
                    │                            │                            │
                    ▼                            ▼                            ▼
           ┌──────────────┐             ┌──────────────┐             ┌──────────────┐
           │ Telegram Bot │             │  Meta Graph  │             │  HTTP POST   │
           │    API       │             │     API      │             │  Response    │
           └──────────────┘             └──────────────┘             └──────────────┘

  INBOUND FLOW:
  ─────────────
  Telegram   ──► POST /webhooks/telegram ──► HMAC Verify ──► Parse ──► Orchestrator
  WhatsApp   ──► POST /webhooks/whatsapp ──► X-Hub Verify ──► Parse ──► Orchestrator
  Webchat    ──► POST /api/v1/chat/test ───► Direct Call ──► Create ──► Orchestrator

  OUTBOUND FLOW:
  ─────────────
  Orchestrator ──► ChatService.send_message() ──► Provider Service ──► External API
                                                    │
                                                    ▼
                                            ChatMessage Table (log)
```

---

## Proveedores Disponibles

El enum `ChatProvider` define los canales soportados:

```python
class ChatProvider(str, Enum):
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    WEBCHAT = "webchat"
```

**Estado de implementación:**

| Canal      | Inbound | Outbound | Estado  |
|------------|---------|----------|---------|
| Telegram   | ✅      | ✅        | Stable  |
| WhatsApp   | ✅      | ✅        | Stable  |
| Webchat    | ✅      | ✅        | Stable  |
| Instagram  | ❌      | ❌        | Planned |
| Facebook   | ❌      | ❌        | Planned |
| TikTok     | ❌      | ❌        | Planned |

---

## Telegram

### 1. Cómo llegan los mensajes (Inbound)

**Endpoint:** `POST /webhooks/telegram`

**Flujo:**
1. Telegram envía POST con `Update` object
2. Servidor verifica HMAC-SHA256 signature
3. Se extrae: `message.text`, `message.chat.id`, `message.from.id`

**Verificación de firma:**
```
HMAC-SHA256(TELEGRAM_BOT_TOKEN, request_body) == X-Telegram-Bot-Api-Signature-Token
```

**Parsing del mensaje:**
```python
# Estructura esperada
message.text      # Texto del mensaje
message.chat.id   # Chat ID (para respuesta)
message.from.id   # User ID (identificador único)
```

### 2. Cómo se envían respuestas (Outbound)

**Método:** `TelegramService.send_message()`

```python
# Implementación simplificada
async def send_message(chat_id: int, text: str):
    await bot.send_message(chat_id=chat_id, text=text)
```

**Parámetros:**
- `chat_id`: ID del chat de Telegram (proveniente de `message.chat.id`)
- `text`: Mensaje a enviar

### 3. Identificación del Lead

**channel_user_id = telegram_user_id**

- Se usa `message.from.id` como identificador único
- El lead se crea/busca usando este ID en el campo `channel_user_id`
- **Limitación:** El número de teléfono puede no estar disponible ya que los usuarios de Telegram pueden ocultar su número

**Flujo de resolución:**
```
telegram_user_id → Buscar Lead → Crear si no existe → Vincular conversation
```

### 4. Resolución del Broker

La resolución del broker para Telegram se realiza a través del `broker_id` incluido en la configuración del webhook. Cada bot de Telegram está vinculado a un broker específico.

### 5. Configuración Necesaria

```python
# Variables de entorno requeridas
TELEGRAM_BOT_TOKEN=<token_del_bot>
TELEGRAM_BOT_USERNAME=<username_del_bot>
```

**Pasos de configuración:**
1. Crear bot via @BotFather en Telegram
2. Obtener token de autenticación
3. Configurar webhook URL: `https://tu-dominio.com/webhooks/telegram`
4. Registrar `TELEGRAM_BOT_TOKEN` en variables de entorno

### 6. Limitaciones Específicas

| Aspecto              | Limitación                                        |
|----------------------|---------------------------------------------------|
| Identificación       | Phone puede no estar disponible                  |
| Formato ID           | Numeric (ej: 123456789)                          |
| Medios               | Soporta fotos, videos, documentos                |
| Sesiones             | No hay sesión persistente (stateless)            |
| Typing indicators    | No soportados natively                           |
| Webhook concurrency  | Procesamiento paralelo limitado                  |

---

## WhatsApp

### 1. Cómo llegan los mensajes (Inbound)

**Endpoint:** `POST /webhooks/whatsapp`

**Flujo:**
1. Meta envía POST con payload de WhatsApp Business
2. Servidor verifica `X-Hub-Signature-256` HMAC
3. Se extrae de `entry[0].changes[0].value.messages[0]`:
   - `message['from']` → Número de teléfono
   - `message['text']['body']` → Texto del mensaje
   - `message['id']` → Message ID

**Verificación de firma:**
```
HMAC-SHA256(WHATSAPP_WEBHOOK_SECRET, request_body) == X-Hub-Signature-256
```

**Payload parsing:**
```python
entry[0].changes[0].value.messages[0].from          # Phone number
entry[0].changes[0].value.messages[0].text.body     # Message text
entry[0].changes[0].value.messages[0].id            # Message ID
```

### 2. Cómo se envían respuestas (Outbound)

**Método:** Meta Graph API

```python
# Endpoint
POST https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages

# Headers
Authorization: Bearer {WHATSAPP_ACCESS_TOKEN}
Content-Type: application/json

# Body
{
    "messaging_product": "whatsapp",
    "to": "<phone_number>",
    "text": {"body": "<message_text>"}
}
```

**Implementación via `WhatsAppService.send_message()`:**

```python
async def send_message(phone_number: str, text: str):
    # Normalize phone to +56...
    # POST to Meta Graph API
    # Return message ID
```

### 3. Identificación del Lead

**channel_user_id = phone_number (normalizado)**

- Formato: `+56XXXXXXXXX` (Chile)
- El número se normaliza antes de buscar/crear el lead
- **Ventaja:** El teléfono es el identificador primario

**Normalización:**
```python
# Ejemplo: 56912345678 → +56912345678
def normalize_phone(phone: str) -> str:
    if not phone.startswith("+"):
        phone = f"+{phone}"
    return phone
```

### 4. Resolución del Broker

La resolución del broker para WhatsApp utiliza **WABA (WhatsApp Business Account)**:

```
Phone Number → WABA Mapping → Broker Configuration
```

Cada broker puede tener diferentes credenciales de WhatsApp Business:
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`

### 5. Configuración Necesaria

```python
# Variables de entorno requeridas
WHATSAPP_ACCESS_TOKEN=<token_de_acceso>
WHATSAPP_PHONE_NUMBER_ID=<ID_del_numero>
WHATSAPP_VERIFY_TOKEN=<token_para_verificacion>
WHATSAPP_WEBHOOK_SECRET=<secret_para_HMAC>
```

**Pasos de configuración:**
1. Crear WhatsApp Business App en Meta Developer Console
2. Obtener `WHATSAPP_ACCESS_TOKEN`
3. Configurar `WHATSAPP_PHONE_NUMBER_ID`
4. Configurar webhook con `WHATSAPP_VERIFY_TOKEN`
5. Suscribir al webhook los eventos de mensajes

### 6. Limitaciones Específicas

| Aspecto              | Limitación                                        |
|----------------------|---------------------------------------------------|
| Templates            | Mensajes fuera de ventana requieren templates     |
| Medios               | Solo imágenes, audio, documentos (no video)      |
| Sesiones             | 24h ventana de mensajes libres                   |
| Rate limits          | Límites por API de Meta                          |
| Webhook retry        | Meta reintenta delivery (manejar idempotencia)   |

---

## Webchat

### 1. Cómo llegan los mensajes (Inbound)

**Endpoints:**

| Método   | Path                        | Descripción           |
|----------|-----------------------------|------------------------|
| POST     | `/api/v1/chat/test`         | Chat simple (sync)     |
| POST     | `/api/v1/chat/stream`       | Chat con SSE streaming |

**Payload:**
```json
{
    "message": "Hola, me interesa comprar una propiedad",
    "lead_id": null,
    "provider": "webchat"
}
```

**Parámetros:**
- `message` (string, requerido): Texto del mensaje
- `lead_id` (integer, opcional): ID de lead existente. Si es `null`, se crea nuevo lead
- `provider` (string, requerido): Siempre `"webchat"`

### 2. Cómo se envían respuestas (Outbound)

**Chat simple (`/api/v1/chat/test`):**
```json
{
    "response": "Gracias por tu mensaje. Un agente te contactará pronto.",
    "lead_id": 123,
    "lead_score": 45.0,
    "lead_status": "warm"
}
```

**Chat con streaming (`/api/v1/chat/stream`):**
- Respuesta mediante Server-Sent Events (SSE)
- El frontend recibe tokens incrementalmente
- Mejor UX para respuestas largas

### 3. Identificación del Lead

**Canal sin identificación persistente:**

- Si `lead_id` es `null`: Se crea un nuevo lead
- Phone asignado: `"web_chat_pending"` (marcador temporal)
- Session: Stateless, sin cookies ni storage

**Flujo:**
```
lead_id=null → Crear Lead(phone="web_chat_pending") → Process → Return lead_id
lead_id=123  → Buscar Lead → Process → Return updated lead
```

### 4. Resolución del Broker

El broker se resuelve mediante:
1. JWT token en header de autenticación
2. O `broker_id` incluido en el contexto de la sesión

### 5. Configuración Necesaria

No requiere configuración de credenciales externas.

**Requisitos:**
- Endpoint accesible públicamente
- CORS configurado para frontend
- Rate limiting recomendado

### 6. Limitaciones Específicas

| Aspecto              | Limitación                                        |
|----------------------|---------------------------------------------------|
| Sesión               | Sin sesión persistente (stateless)                 |
| Identificación       | Lead creado con phone="web_chat_pending"         |
| Typing indicators    | No disponibles                                    |
| Read receipts        | No disponibles                                    |
| Historial            | No persistente en el cliente                      |
| Reingreso            | Nuevo lead si no se guarda lead_id en frontend   |

---

## Consideraciones Cross-Channel

### Diferencias en `channel_user_id`

El formato del identificador único varía por canal:

| Canal      | Formato channel_user_id              | Ejemplo           |
|------------|--------------------------------------|-------------------|
| Telegram   | Numeric user ID                      | `123456789`       |
| WhatsApp   | Phone con código de país             | `+56912345678`    |
| Webchat    | `"0"` o ID efímero                   | `"0"`             |

### Almacenamiento de Mensajes

**Todos los canales** registran en la tabla `ChatMessage`:

```python
ChatMessage(
    lead_id=lead.id,
    broker_id=broker.id,
    provider=provider_name,  # "telegram", "whatsapp", "webchat"
    channel_user_id=channel_user_id,
    direction="inbound" | "outbound",
    content=message_text,
    created_at=datetime.utcnow()
)
```

### Análisis de Sentimiento

El análisis de sentimiento se ejecuta en todos los canales:
- El parámetro `channel` se pasa a la función de análisis
- Permite métricas diferenciadas por canal

### Routing en ChatService

```python
async def send_message(
    db,
    broker_id,
    provider_name,      # "telegram" | "whatsapp" | "webchat"
    channel_user_id,
    message_text,
    lead_id
):
    if provider_name == "telegram":
        return await TelegramService.send_message(...)
    elif provider_name == "whatsapp":
        return await WhatsAppService.send_message(...)
    else:
        return await generic_handler(...)
```

---

## Comparativa de Canales

| Característica         | Telegram        | WhatsApp          | Webchat          |
|------------------------|-----------------|-------------------|------------------|
| **Identificador**      | User ID         | Phone             | Ephemeral (0)    |
| **Webhook**            | ✅              | ✅                | N/A (HTTP POST)  |
| **Streaming**          | ❌              | ❌                | ✅ (SSE)         |
| **Typing indicators**  | ❌              | ❌                | ❌               |
| **Phone disponible**   | ❌ (ocultable)  | ✅                | ❌               |
| **Templates**          | N/A             | ✅ (24h ventana)  | N/A              |
| **Auth externa**        | Bot Token       | Meta Token        | JWT              |
| **Complejidad setup**  | Baja            | Alta             | Mínima           |

---

## Changelog

| Versión | Fecha       | Cambios                                    |
|---------|-------------|-------------------------------------------|
| 1.0     | 17-04-2026  | Versión inicial                            |
|         |             | Documentación de Telegram, WhatsApp,      |
|         |             | Webchat y consideraciones cross-channel   |
|         |             |                                            |

---

*Documento generado automáticamente. Para actualizaciones, modificar la fuente en `app/services/chat/`.*
