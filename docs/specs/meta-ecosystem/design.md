# Design Specification: Ecosistema Meta multicanal

**Spec ID:** META-ECOSYSTEM-001
**Version:** 1.1
**Status:** As-built local documentado — validación sandbox y producción pendiente
**Updated:** 2026-09-07
**Requirements:** [requirements.md](./requirements.md)

## 1. Design goals

- Reemplazar la suposición actual de una credencial por broker por un modelo multi-conexión y multi-activo.
- Reutilizar conversaciones, mensajes, leads, asignación, IA, Celery, WebSocket y auditoría existentes.
- Mantener las campañas publicitarias aisladas del dominio de automatizaciones CRM.
- Permitir migración progresiva por broker y rollback sin pérdida de datos.
- Encapsular los cambios frecuentes de Graph API detrás de clientes y adaptadores internos.

## 2. Baseline architecture impact

Antes de esta implementación, el proyecto ya contenía modelos provider-agnostic para `Conversation` y `ChatMessage`, un `ChatProviderFactory`, un orquestador de IA y un webhook de WhatsApp. La evaluación de partida detectó:

- `BrokerChatConfig.provider_configs` admite una sola configuración por proveedor.
- WhatsApp resuelve el broker buscando `phone_number_id` dentro de JSONB.
- Algunos envíos humanos instancian `WhatsAppService` con credenciales globales.
- `find_lead_by_channel` busca solo por broker, proveedor y usuario, sin activo.
- La bandeja lista principalmente leads, aunque el modelo de conversación ya existe.
- La versión de Graph API está codificada como v18.0.
- Instagram y Facebook están declarados en el enum, pero no implementados como proveedores.

El diseño nuevo incorpora un bounded context `meta` en:

- `backend/app/features/meta` para rutas y schemas públicos.
- `backend/app/services/meta` para Graph API, conexiones, activos, webhooks, mensajería, publicidad y sincronización.
- `frontend/src/features/meta` para conexiones, activos, campañas y métricas.

La bandeja existente de conversaciones se amplía; no se crea una segunda bandeja.

### 2.1 As-built status and residual gaps

La implementación local se encuentra en `backend/app/features/meta`, `backend/app/services/meta`, `backend/app/tasks/meta_tasks.py` y `frontend/src/features/meta`. Las migraciones aditivas terminan en `y0j1k2l3m4n5` y los flags permanecen apagados por defecto.

El cierre documental distingue las siguientes brechas reales, que no deben confundirse con trabajo ya completado:

- **Validación externa:** OAuth, webhooks, mensajería, Lead Ads, publicación pausada y Conversions API requieren activos sandbox reales y App Review.
- **Aceptación no funcional:** faltan mediciones P95 bajo carga y validación con el almacenamiento definitivo de archivos.
- **Flujos locales cerrados:** Business OAuth descubre datasets/píxeles corporativos, jefatura selecciona el destino de Conversions API, la aprobación compara `submission_snapshot` y el mapeo previsualiza la normalización antes de guardar.
- **Calidad transversal:** la suite Meta dirigida está verde, pero pytest, TypeScript y ESLint globales aún tienen deuda preexistente descrita en [verification.md](./verification.md).

## 3. System architecture

```mermaid
flowchart LR
    U[Ejecutivo / Jefatura] --> FE[React CRM]
    FE --> API[FastAPI]
    META[Meta Graph API] --> WH[/webhooks/meta]
    WH --> EV[(meta_webhook_events)]
    EV --> Q[Celery / Redis]
    Q --> RES[Meta Asset Resolver]
    RES --> MSG[Messaging Service]
    MSG --> LEAD[Lead + Assignment Services]
    MSG --> CONV[Conversation + ChatMessage]
    MSG --> AI[LLMServiceFacade / Sofía]
    API --> CONV
    API --> ADS[Meta Ads Service]
    ADS --> META
    Q --> SYNC[Lead forms + Insights Sync]
    SYNC --> ADSDB[(Meta Ads + Attribution)]
    MSG --> WS[WebSocket por broker]
    ADS --> WS
    WS --> FE
```

## 4. Component design

### 4.1 MetaGraphClient

Cliente asíncrono único sobre `httpx`.

Responsibilities:

- Construir URLs usando la versión configurada.
- Inyectar tokens sin registrarlos.
- Aplicar timeouts separados para conexión y respuesta.
- Interpretar errores Graph y producir un error interno tipado.
- Detectar rate limiting, token inválido y permisos insuficientes.
- Aplicar `appsecret_proof` donde corresponda.
- Registrar métricas de latencia y resultado.
- Soportar paginación por cursor.
- No reintentar automáticamente operaciones de creación sin clave idempotente local.

La integración no dependerá directamente del SDK síncrono de Meta; los servicios usarán el cliente asíncrono y contratos propios.

### 4.2 ConnectionService

Responsibilities:

- Generar OAuth state firmado y nonce de un solo uso.
- Intercambiar códigos por tokens.
- Verificar app, usuario, permisos y expiración.
- Cifrar, rotar y revocar credenciales.
- Ejecutar health checks.
- Descubrir activos tras una conexión exitosa.
- Administrar estados `pending`, `active`, `degraded`, `revoked`, `disconnected` y `error`.

Authorization modes:

- `business_login`: broker, páginas, activos publicitarios y Messenger.
- `instagram_login`: Instagram profesional de ejecutivo destinado a mensajes.
- `whatsapp_embedded_signup`: WABA y números del broker.

### 4.3 MetaAssetResolver

Inputs:

- Tipo de webhook.
- WABA ID, `phone_number_id`, Instagram ID, Page ID, Ad Account ID o Form ID.

Outputs:

- Broker.
- Conexión activa.
- Activo.
- Credencial utilizable.
- Ejecutivo propietario/asignado.
- Capacidades y configuración IA.

Invariants:

- El activo externo activo es único por tipo e identificador.
- La credencial pertenece a la misma conexión o a una credencial derivada del activo.
- Ningún envío se ejecuta si broker, activo, credencial y conversación no son consistentes.

### 4.4 Provider adapters

Implementar `WhatsAppProvider`, `InstagramProvider` y `MessengerProvider` detrás del contrato de chat existente.

Cada adaptador debe:

- Parsear eventos entrantes.
- Normalizar texto, botones, respuestas y adjuntos.
- Enviar texto y archivos admitidos.
- Informar capacidades y restricciones del canal.
- Convertir respuestas Graph a estados internos.
- Conservar metadata de referencia publicitaria.

La fábrica recibirá configuración resuelta por activo; nunca buscará credenciales globales.

### 4.5 Webhook ingestion

El endpoint global realiza únicamente:

1. Lectura del cuerpo original.
2. Verificación de challenge o firma.
3. Clasificación de objeto y evento.
4. Resolución mínima del activo cuando sea posible.
5. Inserción idempotente de `meta_webhook_events`.
6. Encolado de la tarea.
7. Respuesta a Meta.

El procesamiento Celery realiza normalización, identidad, lead, conversación, mensaje, IA y envío.

Idempotency keys:

- WhatsApp: WAMID y tipo de estado.
- Instagram/Messenger: Page/Instagram ID más message/event ID.
- Lead Ads: Form ID más Leadgen ID.
- Publicidad: operación local UUID más objeto y acción.
- Fallback: hash HMAC del subconjunto estable del evento.

### 4.6 IdentityResolutionService

Resolution order:

1. Identidad exacta por broker, activo, canal y external user ID.
2. Coincidencia única por teléfono normalizado dentro del broker.
3. Coincidencia única por correo normalizado dentro del broker.
4. Creación de lead.
5. Caso de revisión si existen múltiples candidatos.

El teléfono sintético usado actualmente para proveedores sin teléfono deja de ser identidad primaria. La identidad externa se almacena en tabla propia y el lead mantiene teléfono nullable o real cuando sea obtenido.

### 4.7 Conversation routing

La conversación fija `meta_asset_id` y `channel_identity_id`.

Assignment rules:

| Situation | Result |
|---|---|
| Lead nuevo en activo de ejecutivo | Asignar al propietario activo |
| Lead nuevo en activo corporativo general | Ejecutar AssignmentService |
| Lead existente con mismo responsable | Conservar |
| Lead existente con otro responsable | Conservar y crear conflicto |
| Ejecutivo inactivo | Enviar lead activo a cola sin asignar |

El activo de respuesta siempre será el activo de la conversación. La asignación determina quién puede atender, no cambia la identidad emisora del hilo.

### 4.8 OutboundChannelResolver

For an existing conversation:

- Usar siempre `conversation.meta_asset_id`.
- Validar estado, credencial, capacidad y ventana.

For a new WhatsApp outbound:

1. Número corporativo asignado al responsable.
2. Número corporativo predeterminado.
3. Error explicativo si no existe ninguno.

Instagram y Messenger no ofrecerán inicio de conversación fría. Una respuesta fuera de regla se bloquea antes de llamar a Graph API.

### 4.9 AI integration

El orquestador recibe además:

- `conversation_id`.
- Canal.
- Activo.
- Modo IA del activo.
- Ventana de mensajería.
- Estado de atención humana.

AI modes:

- `suggestion`: genera borrador, no envía.
- `supervised_auto`: puede enviar si todas las reglas pasan.
- `human`: no responde automáticamente.

La extracción de compromisos crea una sugerencia de tarea; no crea una tarea definitiva sin una regla explícitamente habilitada. El modo inicial será aprobación humana.

### 4.10 Meta Ads bounded context

Meta Ads no extiende el modelo `Campaign` existente.

Components:

- `AdAssetCatalogService`.
- `MetaCampaignDraftService`.
- `MetaCampaignApprovalService`.
- `MetaCampaignPublisher`.
- `LeadFormSyncService`.
- `AdsInsightsSyncService`.
- `AttributionService`.
- `ConversionsService`, desactivado inicialmente.

Publishing order:

1. Validación local.
2. Validación de permisos y activos remotos.
3. Campaign pausada.
4. Ad set pausado.
5. Creative.
6. Ad pausado.
7. Persistencia de IDs remotos y resultado.

Cada paso utiliza una operación local idempotente. Si un paso falla, todos los objetos creados permanecen pausados y el draft pasa a `partial_error`.

### 4.11 Housing compliance

Los anuncios inmobiliarios se crearán con categoría especial Housing cuando corresponda. El frontend solo mostrará parámetros de audiencia admitidos por Meta para esa categoría. El backend repetirá la validación y nunca confiará únicamente en el formulario.

La IA podrá sugerir copy, pero jefatura debe revisar:

- Exactitud de precios e inventario.
- Ausencia de discriminación.
- Ausencia de promesas crediticias.
- Identificación clara del anunciante.
- Coherencia entre anuncio, formulario y landing page.

## 5. Data model

### 5.1 New tables

| Table | Purpose | Key constraints |
|---|---|---|
| `meta_connections` | Autorización raíz | broker, owner, auth mode, external principal unique |
| `meta_credentials` | Tokens cifrados | connection/asset subject, never exposed |
| `meta_assets` | Activos y capacidades | external type+id unique; one default per broker/channel and one selected pixel per broker |
| `meta_message_templates` | Plantillas WhatsApp sincronizadas | broker+WABA+name+language unique |
| `channel_identities` | Usuario externo por activo | broker+asset+channel+external user unique |
| `meta_webhook_events` | Inbox idempotente | idempotency key unique; raw payload expires |
| `meta_assignment_conflicts` | Conflictos entre canal y responsable | one open conflict per lead+asset |
| `conversation_read_states` | Lectura por usuario y conversación | conversation+user unique |
| `meta_ads_policies` | Límites y moneda publicitaria | one policy per broker; optimistic version |
| `meta_ad_campaigns` | Draft y espejo de campaign remota | local operation UUID unique |
| `meta_ad_sets` | Segmentación y presupuesto | campaign+remote ID unique |
| `meta_ad_creatives` | Creatividades | campaign+remote ID unique |
| `meta_ads` | Anuncios | campaign+remote ID unique |
| `meta_lead_forms` | Formularios sincronizados | broker+remote form ID unique |
| `meta_lead_attributions` | Primera/última atribución | lead+touch type+external reference |
| `meta_ad_insights_daily` | Métricas agregadas | date+account+campaign+ad set+ad unique |
| `meta_sync_runs` | Reconciliaciones y errores | broker+sync type+started_at index |
| `meta_conversion_events` | Entrega deduplicada a Conversions API | broker+event ID unique; no plaintext PII |

### 5.2 Existing table changes

`conversations`:

- `meta_asset_id`, nullable durante migración.
- `channel_identity_id`.
- `assigned_to` o reutilización coherente del responsable humano actual.
- `unread_count` o timestamp de lectura por usuario según la decisión de implementación.
- `messaging_window_expires_at`.
- `assignment_conflict`.

`chat_messages`:

- `meta_asset_id`.
- `sent_by_user_id`.
- `reply_to_external_id`.
- `message_type`.
- `remote_error_code` y `remote_error_subcode`.
- `generation_mode`: manual, ai_draft, ai_auto.
- Unique partial index sobre proveedor y `channel_message_id` no nulo.

`leads`:

- No agregar datos volátiles de Meta a columnas dispersas.
- Mantener relación normalizada con identidades y atribuciones.
- Exponer origen resumido mediante response schema.

### 5.3 Secret migration

- Leer las configuraciones actuales de WhatsApp.
- Crear conexión legacy por broker.
- Cifrar access token y app secret en `meta_credentials`.
- Crear WABA/número cuando los IDs estén disponibles.
- Mantener JSONB como fallback de solo lectura durante dos releases.
- Borrar secretos legacy mediante migración posterior, nunca en la migración aditiva inicial.

## 6. API design

Base path: `/api/v1/meta`.

### 6.1 Connections and assets

| Method | Path | Permission | Purpose |
|---|---|---|---|
| POST | `/connections/{channel}/authorize` | Authenticated | Crear URL OAuth/state |
| POST | `/connections/{channel}/complete` | Authenticated | Completar OAuth desde el frontend |
| GET | `/connections/{channel}/callback` | OAuth callback | Finalizar conexión |
| GET | `/connections` | Agent own / Admin all | Listar estado sin tokens |
| POST | `/connections/{id}/revalidate` | Owner/Admin | Validar permisos y activos |
| DELETE | `/connections/{id}` | Owner/Admin policy | Desconectar y revocar |
| GET | `/assets` | Scoped | Listar activos y capacidades |
| PATCH | `/assets/{id}` | Admin | Aprobar, pausar, asignar, default e IA |
| POST | `/connections/{id}/sync` | Owner/Admin | Sincronizar activos desde Meta |
| PATCH | `/features` | Admin | Configurar flags Meta por broker |
| GET | `/assets/{id}/message-templates` | Scoped | Listar plantillas aprobadas del número |

The callback redirects to a frontend result route and never includes credentials in the URL.

### 6.2 Conversations

Endpoints bajo `/api/v1/meta/inbox`:

- `GET /conversations` con cursor y filtros por canal, activo, responsable, proyecto, estado y fecha.
- `GET /conversations/{id}` y `GET /conversations/{id}/messages` para detalle e historial.
- `POST /conversations/{id}/messages` para enviar por el activo fijado.
- `POST /conversations/{id}/read` para lectura por usuario.
- `GET|POST /conversations/{id}/ai/*` para resumen, borrador y sugerencia/aprobación de tarea.
- `GET /assignment-conflicts` y `POST /assignment-conflicts/{id}/resolve` para resolución administrativa.

### 6.3 Meta Ads

| Method | Path | Purpose |
|---|---|---|
| GET | `/ads/catalog/assets` | Cuentas, páginas, Instagram corporativo, números y capacidades |
| GET | `/ads/catalog/projects` | Proyectos elegibles del broker |
| GET/PATCH | `/ads/policy` | Consultar o actualizar límites de gasto |
| GET/POST | `/ads/campaigns` | Listar o crear drafts |
| GET/PUT | `/ads/campaigns/{id}` | Consultar o editar draft permitido |
| POST | `/ads/campaigns/{id}/submit` | Enviar a aprobación |
| POST | `/ads/campaigns/{id}/approve` | Aprobar como jefatura |
| POST | `/ads/campaigns/{id}/reject` | Rechazar con comentario |
| POST | `/ads/campaigns/{id}/publish` | Crear objetos remotos pausados |
| POST | `/ads/campaigns/{id}/activate` | Confirmación administrativa de gasto |
| POST | `/ads/campaigns/{id}/pause` | Pausar remotamente |
| GET/PATCH | `/ads/forms[/{id}]` | Listar formularios o actualizar su mapeo |
| POST | `/ads/forms/sync` | Reconciliación administrativa |
| POST | `/ads/insights/sync` | Sincronización administrativa de métricas |
| GET | `/ads/analytics` | Métricas y resultados CRM |
| GET | `/ads/analytics/leads` | Drill-down de leads por resultado |
| GET | `/ads/conversions/diagnostics` | Estado de conversiones sin PII |

Campaign and Ads policy mutations require an expected version to prevent lost updates. Asset approval/assignment and form mapping are administrative last-write operations and remain auditable.

### 6.4 WebSocket events

- `meta_message_received`.
- `meta_message_sent`.
- `meta_message_status_changed`.
- `lead_assigned`.
- `meta_assignment_conflict`.
- `meta_assignment_conflict_resolved`.
- `meta_connection_health_changed`.
- `meta_connection_expiring`.
- `meta_assets_synchronized`.
- `meta_ai_handoff_required`.
- `meta_executive_offboarded`.
- `meta_ad_campaign_submitted`, `meta_ad_campaign_approved` y `meta_ad_campaign_rejected`.
- `meta_ad_campaign_published`, `meta_ad_campaign_activated` y `meta_ad_campaign_paused`.
- `meta_ad_campaign_error`.

Each event includes broker-safe IDs only; the frontend fetches full details using authenticated APIs.

Los webhooks externos no usan el prefijo autenticado: `GET|POST /webhooks/meta`, `POST /webhooks/meta/deauthorize` y `POST /webhooks/meta/data-deletion`.

## 7. Frontend design

### 7.1 Navigation

- `Conversaciones`: accessible to executives and management.
- `Mis canales`: accessible to all authenticated broker users.
- `Configuración > Integraciones Meta`: management only.
- `Campañas > Automatizaciones CRM`: current behavior.
- `Campañas > Meta Ads`: drafts for executives, full controls for management.

### 7.2 My Channels

- Show assigned WhatsApp number as corporate and non-transferable by the executive.
- Connect/disconnect Instagram professional.
- Connect/disconnect a Facebook Page.
- Show approval, token health, capabilities and last sync.
- Explain corporate visibility before authorization.

### 7.3 Management integrations

Tabs:

- Overview.
- WhatsApp.
- Instagram.
- Messenger.
- Ads.
- Health and audit.

Management can discover assets, approve, assign, set defaults, configure AI and test health. Credential input fields from the current broker dialog are replaced by OAuth; the legacy form remains hidden behind a migration flag only.

### 7.4 Inbox

Desktop uses conversation list, thread and context panel. Mobile uses one full-width level at a time. Channel and asset are always visible to prevent sending from the wrong corporate identity.

### 7.5 Campaign builder

Wizard steps:

1. Base: name, account, project and mandatory Housing category.
2. Destination: objective, corporate asset or form, budget, audience and schedule.
3. Ad: creative, copy, URL/media and optional corporate Instagram actor.
4. Review: consolidated summary and local draft creation.

The approval page displays exact differences since submission. Activation uses a structured modal showing account, budget, dates and expected maximum spend, with an explicit spend acknowledgement.

## 8. Background jobs

| Job | Schedule / trigger | Behavior |
|---|---|---|
| Process webhook | Event-driven | Normalize and dispatch with DLQTask |
| Send message | Event-driven | Resolve asset, send, persist status |
| Connection health | Every 6 hours | Validate token/scopes, notify changes |
| Asset sync | Daily and manual | Refresh names, capabilities and status |
| Lead form reconciliation | Every 15 minutes | Retrieve missing leads idempotently |
| Active ads insights | Hourly | Current-day metrics |
| Insights backfill | Daily | Reconcile previous 3 days |
| Webhook payload cleanup | Daily | Delete encrypted raw payload older than 7 days |
| Conversion delivery | Event-driven, flag off | Send CRM outcomes with retry and dedup |

All jobs inherit `DLQTask`, record `broker_id`, use bounded retries and expose operational metrics.

## 9. Security design

- Dedicated encryption key and key version for Meta credentials.
- App Secret, encryption keys and OAuth secrets only in Railway backend, worker and beat.
- Constant-time signature verification over raw body.
- OAuth nonce in Redis with short TTL and one-time consumption.
- Tokens masked in admin responses and excluded from exception serialization.
- `appsecret_proof` for applicable Graph calls.
- Allowed-host checks for media URLs before download.
- File size, MIME type and extension validation.
- Per-asset and per-sender rate limits.
- Audit events for any outbound message, permission change or spend action.
- Raw webhooks encrypted, access-restricted and automatically expired.
- Meta data deletion and deauthorization callbacks.

## 10. Error handling

Graph errors map to internal categories:

- `TOKEN_EXPIRED`.
- `PERMISSION_REVOKED`.
- `RATE_LIMITED`.
- `POLICY_WINDOW_CLOSED`.
- `ASSET_DISABLED`.
- `AD_REVIEW_REJECTED`.
- `PARTIAL_REMOTE_CREATE`.
- `TRANSIENT_PROVIDER_ERROR`.
- `INVALID_REQUEST`.

Transient errors retry with exponential backoff and jitter. Permission, policy and validation errors do not retry automatically. Final retry failures enter the existing DLQ and create an operational alert.

## 11. Correctness properties

1. No outbound message can cross broker boundaries.
2. A conversation replies through its original asset unless an explicit audited migration changes it.
3. Duplicate Meta events produce at most one normalized business effect.
4. A campaign cannot spend before approval, paused publication and explicit activation.
5. Executive Instagram assets can never become eligible ad actors.
6. An existing lead assignment is never silently replaced because the lead contacted another executive asset.
7. Revoking a connection never deletes message history.
8. AI failure never prevents persistence of an inbound message.
9. Remote advertising objects created after partial failure remain paused.
10. Legacy WhatsApp remains recoverable until migration acceptance is complete.

## 12. Observability

Metrics:

- Webhook ACK and processing latency.
- Accepted, rejected and duplicate events.
- Celery queue depth and DLQ size.
- Send, delivery, read and failure rates.
- Token expiry and permission failures.
- Graph rate limits by asset and endpoint family.
- Lead form webhook/reconciliation differences.
- Campaign publication and partial failure counts.
- Insight sync freshness.
- AI suggestion and automatic response counts.

Tracing propagates a correlation ID through webhook, Celery task, message, AI call and Graph request. Logs use internal IDs and masked external identifiers.

## 13. Migration and rollout

### Phase A — Additive foundation

- Deploy new tables and nullable foreign keys.
- Leave current paths active.
- Backfill WhatsApp connections and assets.
- Validate counts and credential decryption.

### Phase B — Dual read

- Resolver reads new tables first and legacy config only under fallback.
- New messages write asset and identity references.
- Old history remains readable with nullable references.

### Phase C — Broker canary

- Enable new WhatsApp path for an internal broker.
- Validate inbound, outbound, AI, takeover, tasks and WebSocket.
- Roll out broker by broker.

### Phase D — New channels and Ads

- Release Instagram.
- Release Messenger.
- Release Meta Ads drafts and approval.
- Release Lead Ads and metrics.
- Enable Conversions API only after privacy review.

### Phase E — Legacy retirement

- Maintain two stable releases.
- Take encrypted backup and test rollback.
- Remove runtime fallback.
- Remove legacy secrets in a separate migration.

Rollback disables feature flags, pauses remote campaigns and restores legacy WhatsApp resolution without dropping new data.

## 14. External Meta setup

Before production:

- Verified Meta business portfolio and domain.
- Public privacy, terms, support and deletion pages.
- Business-type Meta app with WhatsApp, Instagram, Messenger, Webhooks, Facebook Login for Business, Marketing API and Lead Ads.
- Development, staging and production callback URLs.
- Test WABA, two test numbers, Page, corporate Instagram, executive Instagram, ad account and lead form.
- App Review evidence and reviewer credentials for every requested permission.
- Live mode and Data Use Checkup process assigned to an owner.

## 15. Test strategy

- Unit tests for state machines, permissions, resolvers, idempotency and Graph error mapping.
- Contract tests with sanitized official webhook fixtures for every channel and status.
- Database integration tests for tenant isolation, unique constraints and migration.
- Celery tests for retry, reconciliation and DLQ.
- API tests for OAuth state, asset approval, messaging and campaign workflow.
- Frontend Vitest for permissions, filters, composer, approval and error states.
- Browser E2E for the complete broker/executive flow.
- Sandbox tests against Meta assets before App Review.
- Load test webhook ACK and list queries.
- Regression tests for Telegram, WebChat, referral campaigns, pipeline, tasks and existing WhatsApp history.

## 16. Requirements traceability

| Requirement | Primary design components |
|---|---|
| REQ-001 | Tenant filters, resolver, permission layer |
| REQ-002–003 | ConnectionService, credentials, assets, OAuth UI |
| REQ-004–006 | Provider adapters and asset-aware routing |
| REQ-007 | Webhook ingestion, idempotency, Celery |
| REQ-008–010 | Identity resolution, conversations, inbox |
| REQ-011 | AI integration and modes |
| REQ-012–013 | Meta Ads bounded context and approval workflow |
| REQ-014–015 | Lead forms, attribution, insights, conversions |
| REQ-016 | Offboarding service and connection lifecycle |
| REQ-017 | Audit, telemetry and alerting |
| REQ-018 | Dual-read migration and feature flags |

## 17. Local acceptance and remaining work

| Area | Local state | Exit gate |
|---|---|---|
| Foundation, security and tenant isolation | Implemented; [local security review](./security-review.md) has no open critical/high Meta findings | Production secret configuration and real-provider validation |
| WhatsApp asset routing | Implemented with legacy fallback | Real two-number sandbox and broker canary |
| Instagram and Messenger | Providers, webhooks and UI implemented | Real DM/Page sandbox plus App Review |
| Unified inbox and AI assistance | Implemented locally, including matched channel eval cases | Load test and real-channel evidence |
| Meta Ads | Draft, snapshot review, structured activation, paused publishing and analytics implemented | Real paused campaign |
| Lead Ads and attribution | Sync, mapping preview and dedup implemented | Real form/reconciliation |
| Conversions API | Dataset discovery/selection, delivery and diagnostics implemented behind disabled flag | Privacy approval, consent configuration and sandbox delivery |
| Rollout | Feature flags and rollback path implemented | Railway validation, seven-day canary and two stable releases |
