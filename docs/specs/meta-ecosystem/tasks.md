# Implementation Tasks: Ecosistema Meta multicanal

**Spec ID:** META-ECOSYSTEM-001
**Version:** 1.1
**Status:** 91/107 implementation tasks completed locally; 16 acceptance or external tasks pending
**Updated:** 2026-09-09
**Requirements:** [requirements.md](./requirements.md)
**Design:** [design.md](./design.md)
**Traceability:** [traceability.md](./traceability.md)

## Status convention

- `[x]` means the repository implementation and its directed local verification are complete.
- `[ ]` means the task remains open. Tasks may be open because code/UX is missing or because they require external Meta/Railway evidence.
- Local completion never substitutes sandbox, App Review, canary or production acceptance.

| Scope | Complete | Open | Exit condition |
|---|---:|---:|---|
| Local implementation, migrations and directed checks | 89 | 0 | Completed; maintain directed regression coverage |
| External setup and sandbox | 0 | 8 | Business/App setup, HTTPS legal pages, secrets and real channel evidence |
| Hardening and rollout | 2 | 8 | Load gate, Railway, App Review, canary and legacy retirement |
| **Total** | **91** | **16** | See [verification.md](./verification.md) |

## Execution rules

- Complete tasks in order unless marked `[P]` for safe parallel execution.
- Every task must include tests or an explicit verification artifact in the same commit.
- Database changes are additive until the legacy-retirement phase.
- All new tenant data must include and validate `broker_id`.
- No task may expose Meta tokens to the frontend or logs.
- A phase is complete only when its demo checklist passes.
- External Meta approval work runs in parallel but production activation waits for it.

## Phase 0 — Meta and delivery prerequisites

**Goal:** disponer de una aplicación Meta de desarrollo, activos de prueba y ambientes preparados.
**Requirements:** REQ-002, REQ-003, NFR-001, NFR-005.

- [ ] **0.1 Verify business ownership and access**
  - Confirmar portafolio empresarial, administradores, 2FA y dominio.
  - Registrar propietario y respaldo de la aplicación.
  - Validation: checklist firmado por producto/operaciones.
  - Evidence gate: [external setup runbook](./external-setup/README.md) and [status manifest](./external-setup/manifest.json).
  - Status: external business and ownership evidence required.

- [ ] **0.2 Publish legal and support pages** `[P]`
  - Publicar privacidad, términos, soporte, eliminación y desconexión.
  - Validation: URLs HTTPS públicas y accesibles sin autenticación.
  - Evidence gate: [external setup runbook](./external-setup/README.md) and [status manifest](./external-setup/manifest.json).
  - Status: repository pages exist; legal review and public HTTPS publication remain open.

- [ ] **0.3 Create Meta business app**
  - Añadir WhatsApp, Webhooks, Facebook Login for Business, Instagram, Messenger, Marketing API y Lead Ads.
  - Fijar v26.0 en configuración de desarrollo.
  - Validation: App Dashboard muestra todos los productos requeridos.
  - Evidence gate: [external setup runbook](./external-setup/README.md) and [status manifest](./external-setup/manifest.json).
  - Status: requires access to Meta App Dashboard.

- [ ] **0.4 Configure environments and callbacks**
  - Registrar OAuth redirects, app domains, webhook y data-deletion callbacks para desarrollo, staging y producción.
  - Validation: challenge de webhook y redirección OAuth funcionan en desarrollo.
  - Evidence gate: [external setup runbook](./external-setup/README.md) and [status manifest](./external-setup/manifest.json).
  - Status: callback handlers exist locally; provider and deployed-environment configuration remains open.

- [ ] **0.5 Prepare test assets** `[P]`
  - Crear WABA, dos números, página, Instagram corporativo, Instagram de ejecutivo, cuenta publicitaria, formulario y campaña pausada de prueba.
  - Validation: inventario de IDs y propietarios guardado fuera del repositorio.
  - Evidence gate: [external setup runbook](./external-setup/README.md) and [status manifest](./external-setup/manifest.json).
  - Status: external sandbox inventory required.

- [ ] **0.6 Configure secrets**
  - Añadir `META_APP_ID`, `META_APP_SECRET`, `META_GRAPH_API_VERSION`, `META_WEBHOOK_VERIFY_TOKEN`, OAuth redirect base y clave dedicada de cifrado en backend, Worker y Beat.
  - Validation: health check confirma presencia sin mostrar valores.
  - Evidence gate: [external setup runbook](./external-setup/README.md), [status manifest](./external-setup/manifest.json) and `python3 scripts/check_meta_external_setup.py`.
  - Status: variable contracts, secret-safe health signals and cross-service validation exist in the repository; real secrets must be provisioned per environment.

- [x] **0.7 Create feature flags** `[P]`
  - Definir flags globales y por broker para core Meta, WhatsApp asset-aware, Instagram, Messenger, Ads, Lead Ads y Conversions API.
  - Validation: flags desactivados no alteran la aplicación vigente.

### Phase 0 demo

- Meta valida el webhook de desarrollo.
- Un administrador inicia y cancela OAuth sin persistir secretos.
- Los activos de prueba están disponibles y los flags permanecen apagados.

## Phase 1 — Multi-tenant data foundation

**Goal:** persistir conexiones, activos, credenciales, identidades y eventos sin modificar el flujo vigente.
**Requirements:** REQ-001–003, REQ-007, REQ-017–018, NFR-004.

**Primary location:** `backend/app/features/meta`, `backend/app/services/meta`.

- [x] **1.1 Add connection and credential models**
  - Crear `meta_connections` y `meta_credentials` con índices, estados y relaciones.
  - Validation: migration upgrade/downgrade en base vacía y snapshot productivo.

- [x] **1.2 Add asset model**
  - Crear `meta_assets` con owner, assignee, capabilities, approval, default y sync state.
  - Añadir restricciones de unicidad e índices parciales.
  - Validation: pruebas de duplicidad, default único y tenant isolation.

- [x] **1.3 Add external identity model** `[P]`
  - Crear `channel_identities` con unicidad por broker, activo, canal y external ID.
  - Validation: identidades iguales en páginas distintas no colisionan.

- [x] **1.4 Add webhook event model** `[P]`
  - Crear `meta_webhook_events` con idempotency key, estado, intentos y expiración de payload.
  - Validation: inserción concurrente produce un solo evento efectivo.

- [x] **1.5 Add assignment conflict model** `[P]`
  - Crear `meta_assignment_conflicts` con estado abierto/resuelto y decisión auditada.
  - Validation: un solo conflicto abierto por lead y activo.

- [x] **1.6 Extend conversations and messages**
  - Añadir referencias nullable a activo e identidad, sender, generation mode, reply ID, window and remote errors.
  - Añadir índice único parcial de mensajes externos.
  - Validation: historial legacy continúa cargando.

- [x] **1.7 Register models and migration checks**
  - Registrar modelos en metadata SQLAlchemy sin eliminar imports load-bearing.
  - Añadir prueba que compara Alembic head y modelos.
  - Validation: aplicación inicia después de `alembic upgrade head`.

- [x] **1.8 Implement credential encryption repository**
  - Usar cifrado existente con key/version separada para Meta.
  - Implementar write-only secret inputs y masked outputs.
  - Validation: pruebas prueban round-trip y ausencia de plaintext en DB/API/logs.

- [x] **1.9 Implement tenant-scoped repositories**
  - Centralizar consultas de connections, assets, identities and webhook events.
  - Validation: matriz de acceso cruzado devuelve 404/403 sin leakage.

### Phase 1 demo

- Se crea una conexión y varios activos de dos brokers.
- Ningún broker accede al otro.
- El sistema vigente continúa usando WhatsApp legacy.

## Phase 2 — Graph client, OAuth and asset administration

**Goal:** conectar Meta sin tokens manuales y administrar activos descubiertos.
**Requirements:** REQ-002–003, REQ-017, NFR-001.

- [x] **2.1 Build typed MetaGraphClient**
  - Implementar auth, pagination, `appsecret_proof`, timeout, error mapping y telemetry.
  - Validation: contract tests para éxito, paginación, 4xx, 5xx y rate limit.

- [x] **2.2 Implement OAuth state service** `[P]`
  - Firmar broker, user, channel, nonce and expiry; consume nonce once from Redis.
  - Validation: reject altered, expired, replayed and cross-user callbacks.

- [x] **2.3 Implement connection strategies**
  - Business Login, Instagram Login and WhatsApp Embedded Signup.
  - Validation: sanitized callback fixtures persist correct auth mode and scopes.

- [x] **2.4 Implement token inspection and health**
  - Verify app, subject, scopes, expiry and revocation.
  - Validation: connection state transitions cover active, degraded and revoked.

- [x] **2.5 Implement asset discovery**
  - Fetch WABAs, phone numbers, Pages, Instagram accounts, ad accounts and forms according to granted scopes.
  - Validation: unsupported assets are stored disabled or omitted with reason.

- [x] **2.6 Add connection APIs**
  - Authorize, callback, list, revalidate and disconnect.
  - Validation: API tests for role, broker, owner and masked responses.

- [x] **2.7 Add asset APIs** `[P]`
  - List, approve, reject, pause, assign, default, AI mode and sync.
  - Validation: only admin changes operational properties.

- [x] **2.8 Add My Channels frontend** `[P]`
  - New agent-accessible page for assigned WhatsApp, Instagram and Pages.
  - Show corporate visibility consent and status.
  - Validation: Vitest for agent/admin states and OAuth result handling.

- [x] **2.9 Add management integration frontend**
  - Overview, channel tabs, asset assignment, approval, health and audit.
  - Replace manual token workflow under new flag.
  - Validation: browser flow with test API fixtures.

- [x] **2.10 Schedule connection health and asset sync**
  - Six-hour health check and daily asset refresh using DLQTask.
  - Validation: token expiry triggers audit, WS event and notification once.

### Phase 2 demo

- Broker and executive complete their respective OAuth flows.
- Assets appear without tokens.
- Management approves, assigns and pauses assets.

## Phase 3 — Asset-aware WhatsApp migration

**Goal:** operar múltiples números por broker sin perder compatibilidad.
**Requirements:** REQ-004, REQ-007–010, REQ-018.

- [x] **3.1 Create legacy backfill command**
  - Convert current broker WhatsApp JSON config to connection, encrypted credential and phone asset.
  - Make reruns idempotent and report discrepancies.
  - Validation: dry-run and apply tests on anonymized production-shaped data.

- [x] **3.2 Implement MetaAssetResolver for WhatsApp**
  - Resolve exact broker and number by `phone_number_id`.
  - Validation: unknown, duplicate, paused and revoked asset cases.

- [x] **3.3 Upgrade WhatsApp provider**
  - Remove hardcoded Graph version and require resolved asset credentials.
  - Support text, interactive responses, media metadata and status callbacks.
  - Validation: provider contract suite.

- [x] **3.4 Refactor WhatsApp webhook**
  - Route valid events through global durable ingestion while retaining verification compatibility.
  - Validation: duplicated WAMID creates one message and one AI execution.

- [x] **3.5 Refactor inbound task**
  - Resolve asset, identity, lead, conversation and assignment before orchestrator.
  - Validation: two numbers in one broker route to correct executives.

- [x] **3.6 Refactor all outbound WhatsApp paths**
  - Human inbox, AI, referral campaign and internal campaign use OutboundChannelResolver.
  - Remove runtime dependence on global credentials when flag enabled.
  - Validation: every outbound path sends through expected number.

- [x] **3.7 Implement templates and messaging-window guard**
  - Block free text outside permitted window and select only approved broker templates.
  - Validation: open, expired, missing template and provider rejection cases.

- [x] **3.8 Add number assignment UI** `[P]`
  - Assign one active broker agent, set corporate default and show quality/health.
  - Validation: duplicate assignment and inactive-agent guards.

- [x] **3.9 Add dual-read compatibility**
  - New resolver first, legacy fallback only under explicit flag.
  - Validation: rollback test returns to legacy without deleting new records.

### Phase 3 demo

- Two executives receive messages through different broker numbers.
- Replies, AI, takeover and referrals use the original number.
- Legacy conversation history remains visible.

## Phase 4 — Identity, assignment and unified inbox

**Goal:** convertir la bandeja existente en una bandeja por conversación y activo.
**Requirements:** REQ-008–010, REQ-016.

- [x] **4.1 Implement IdentityResolutionService**
  - Exact asset identity, safe normalized match, create and ambiguous review.
  - Validation: deterministic matrix including two Pages with same numeric user ID.

- [x] **4.2 Implement conversation service changes**
  - Create/reopen by lead, asset and identity; maintain message counts and window.
  - Validation: one lead can hold independent channel threads.

- [x] **4.3 Implement assignment policy**
  - New executive asset, general asset and inactive user rules.
  - Reuse centralized AssignmentService.
  - Validation: lead and open-task ownership remains consistent.

- [x] **4.4 Implement assignment conflicts**
  - Detect, notify and resolve without silent reassignment.
  - Validation: admin resolution transfers tasks and logs activity once.

- [x] **4.5 Refactor conversation list API**
  - Cursor pagination, SQL filters, unread status and no N+1.
  - Validation: query-count and role visibility tests.

- [x] **4.6 Add conversation detail and send APIs**
  - Fixed asset, attachments, read acknowledgement, errors and alternate-channel hint.
  - Validation: cross-broker and wrong-asset sends rejected.

- [x] **4.7 Redesign inbox frontend**
  - List/thread/context desktop and full-screen mobile navigation.
  - Show channel, asset, assignment, AI mode, window and conflicts.
  - Validation: loading, empty, offline, error and responsive states.

- [x] **4.8 Add WebSocket events and Sonner actions** `[P]`
  - New message, status, assignment, conflict and connection health.
  - Validation: event opens exact conversation and broker.

- [x] **4.9 Implement executive offboarding hook**
  - Unassign corporate numbers, pause executive assets, preserve history and queue leads/tasks.
  - Validation: inactive user cannot receive new assignment or send.

### Phase 4 demo

- Jefatura sees all threads; each executive sees only assigned threads.
- An existing lead contacting another executive creates a visible conflict.
- Reassignment preserves conversation asset and transfers open tasks.

## Phase 5 — Instagram professional messaging

**Goal:** conectar y operar Instagram corporativo y de ejecutivos.
**Requirements:** REQ-005, REQ-007–011.

- [x] **5.1 Implement Instagram account validation**
  - Confirm Professional Business/Creator and available messaging scopes.
  - Validation: personal and insufficient-scope fixtures are rejected.

- [x] **5.2 Implement InstagramProvider**
  - Parse/send text, replies and supported media; capture referral context.
  - Validation: provider contract tests.

- [x] **5.3 Subscribe and process Instagram webhooks**
  - Route events through durable event inbox and identity service.
  - Validation: retries and out-of-order statuses remain idempotent.

- [x] **5.4 Enforce approval and messaging-only capability**
  - Executive account stays pending; admin approval enables messages only.
  - Validation: asset is absent from every Ads endpoint and selector.

- [x] **5.5 Add Instagram-specific UX** `[P]`
  - Professional requirement, approval status, conversation folder/window hints and reconnect flow.
  - Validation: browser tests for connect, pending, active and revoked.

- [ ] **5.6 Add end-to-end sandbox test**
  - External user initiates DM, CRM creates/assigns lead, agent replies, statuses update.
  - Validation: captured test evidence for App Review.
  - Evidence gate: `AR-IG-DIRECT-001` in the [external setup runbook](./external-setup/README.md) and [App Review permission paths](./app-review-evidence/permission-paths.md).
  - Status: blocked on a real professional Instagram sandbox asset and reviewed permissions.

### Phase 5 demo

- An executive connects a professional account, gets approval and attends a real sandbox DM.
- The account cannot be selected for ads.

## Phase 6 — Messenger Pages

**Goal:** operar mensajes de páginas corporativas y páginas conectadas por ejecutivos.
**Requirements:** REQ-006–011.

- [x] **6.1 Implement Page discovery and token derivation**
  - List only administrable Pages and encrypt Page tokens.
  - Validation: profile IDs are never accepted as assets.

- [x] **6.2 Implement MessengerProvider**
  - Parse/send messages, attachments, postbacks, delivery and read events.
  - Validation: provider contract tests.

- [x] **6.3 Subscribe Page webhooks**
  - Manage subscription lifecycle and durable processing.
  - Validation: connect, revoke and permission-change fixtures.

- [x] **6.4 Enforce executive Page approval**
  - Pending until management approval; messaging capability only by default.
  - Validation: unauthorized Page cannot send or trigger AI.

- [x] **6.5 Add Messenger UX** `[P]`
  - Page identity, status, owner, permission errors and reconnect guidance.
  - Validation: agent/admin visibility tests.

- [ ] **6.6 Add end-to-end sandbox test**
  - Page message creates/links lead and replies from same Page.
  - Validation: recorded App Review evidence.
  - Evidence gate: `AR-FB-MSG-001` in the [external setup runbook](./external-setup/README.md) and [App Review permission paths](./app-review-evidence/permission-paths.md).
  - Status: blocked on a real Facebook Page sandbox asset and reviewed permissions.

### Phase 6 demo

- Corporate and approved executive Pages work in the unified inbox.
- No UI or API path accepts personal Messenger.

## Phase 7 — AI assistance and task suggestions

**Goal:** hacer que Sofía utilice la conversación y canal correctos con control humano.
**Requirements:** REQ-011, NFR-002.

- [x] **7.1 Extend AgentContext**
  - Add conversation, asset, channel, window and AI mode without mutating immutable snapshots.
  - Validation: existing multi-agent tests remain green.

- [x] **7.2 Make orchestrator conversation-aware**
  - Load only correct thread plus lead summary; avoid cross-channel reply leakage.
  - Validation: paired conversation tests prove context isolation.

- [x] **7.3 Add channel response policies** `[P]`
  - Prompt rules for concise WhatsApp, Instagram and Messenger styles.
  - Validation: deterministic eval rubric and safety cases.

- [x] **7.4 Implement AI summary endpoint** `[P]`
  - Cache summary by last message ID and invalidate on new message.
  - Validation: unchanged thread does not create another LLM call.

- [x] **7.5 Implement AI draft endpoint**
  - Return draft with generation metadata; never auto-send in suggestion mode.
  - Validation: permissions and human-mode behavior.

- [x] **7.6 Implement task suggestion flow**
  - Extract title, due date and evidence message; user approves before LeadTask creation.
  - Validation: ambiguous dates require user edit and do not create silently.

- [x] **7.7 Implement supervised auto mode**
  - Admin-only configuration, business rules, confidence gates and human handoff.
  - Validation: DICOM, complaint, human takeover and unavailable inventory tests.

- [x] **7.8 Extend evaluation dataset**
  - Location: `backend/tests/evals/dataset/conversations.json`, `backend/tests/evals/test_agent_quality.py`.
  - Add Spanish Chilean real-estate cases for all Meta channels.
  - Validation: no regression below agreed baseline.
  - Status: 54 labeled cases include one matched availability scenario for WhatsApp, Instagram and Messenger; baseline recorded on 2026-09-07.

### Phase 7 demo

- A multi-channel lead receives a correct summary and channel-specific draft.
- A detected commitment becomes a task only after executive approval.

## Phase 8 — Meta Ads foundation

**Goal:** conectar cuentas publicitarias y mantener un catálogo corporativo separado.
**Requirements:** REQ-012–013, REQ-017.

- [x] **8.1 Add Ads domain models and migration**
  - Campaign, ad set, creative, ad, form, attribution, insights and sync run tables.
  - Validation: constraints and tenant tests.

- [x] **8.2 Implement ad account discovery**
  - Fetch account status, currency, timezone, permissions and spend capabilities.
  - Validation: disabled/restricted accounts are read-only.

- [x] **8.3 Implement corporate ad asset catalog**
  - Include broker Pages, corporate Instagram, numbers and forms only.
  - Validation: executive Instagram is impossible to query as ad actor.

- [x] **8.4 Add Ads read APIs** `[P]`
  - Accounts, assets, forms, statuses and capabilities.
  - Validation: agent read scope vs admin management scope.

- [x] **8.5 Split campaign navigation** `[P]`
  - Preserve internal automations and add Meta Ads area.
  - Validation: referral campaign and current executor remain unchanged.

- [x] **8.6 Implement budget policy configuration**
  - Broker maximum, currency display, increase confirmation and audit.
  - Validation: overflow, negative, wrong currency and concurrent update tests.

### Phase 8 demo

- Management connects an ad account and sees only eligible corporate assets.
- Internal CRM campaigns continue running separately.

## Phase 9 — Campaign drafts, approval and publishing

**Goal:** construir campañas reales con doble control administrativo.
**Requirements:** REQ-013, NFR-001–002.

- [x] **9.1 Implement campaign draft service**
  - CRUD allowed fields, ownership, optimistic concurrency and immutable submission snapshot.
  - Validation: concurrent edits and role matrix.

- [x] **9.2 Implement campaign state machine**
  - Draft, pending, rejected, approved, publishing, published_paused, active, paused, completed and partial_error.
  - Validation: invalid transitions rejected.

- [x] **9.3 Implement Housing validation**
  - Category declaration and allowlist of supported targeting inputs.
  - Validation: prohibited targeting never reaches Graph API.

- [x] **9.4 Implement creative validation** `[P]`
  - Project association, URLs, media, copy, inventory and financing disclaimers.
  - Validation: broken links, unsupported media and unsafe claims.

- [x] **9.5 Implement approval APIs**
  - Submit, approve and reject with comment and audit.
  - Validation: creator cannot self-approve as agent.

- [x] **9.6 Implement idempotent publisher**
  - Create remote campaign, ad set, creative and ad paused; persist every remote ID.
  - Validation: retry after each simulated failure creates no duplicate active object.

- [x] **9.7 Implement activate and pause actions**
  - Admin-only second confirmation, remote verification and local reconciliation.
  - Validation: campaign cannot spend from draft/approved states.

- [x] **9.8 Build campaign wizard frontend** `[P]`
  - Objective, project, destination, creative, form/URL, audience, budget and review.
  - Validation: step validation and saved draft recovery.

- [x] **9.9 Build approval and activation frontend**
  - Location: `frontend/src/features/meta/components/MetaAdsPage.tsx`, `frontend/src/features/meta/components/MetaEcosystem.test.tsx`.
  - Diff since submission, rejection comment, spend confirmation and remote error display.
  - Validation: agent/admin E2E workflow.
  - Status: admin review compares the immutable submission snapshot, captures rejection comments and activates only after a structured account/budget/date/spend confirmation.

- [x] **9.10 Add campaign WebSocket events** `[P]`
  - Approval, rejection, publication, active, paused and error.
  - Validation: notification navigates to exact campaign.

### Phase 9 demo

- Executive creates and submits a campaign.
- Management approves, publishes paused and separately activates it.
- Failure simulation leaves every remote object paused and recoverable.

## Phase 10 — Lead Ads and attribution

**Goal:** convertir formularios y referencias publicitarias en leads trazables.
**Requirements:** REQ-014.

- [x] **10.1 Implement form synchronization**
  - Import forms, questions, Page, status and project mapping.
  - Validation: inactive forms remain historical but not selectable.

- [x] **10.2 Implement Lead Ads webhook processing**
  - Retrieve field data, verify broker/form and persist idempotently.
  - Validation: one leadgen ID creates one attribution effect.

- [x] **10.3 Implement field mapping UI** `[P]`
  - Location: `frontend/src/features/meta/components/MetaAdsPage.tsx`, `frontend/src/features/meta/services/meta.service.ts`.
  - Map form questions to lead fields and project; validate required fields.
  - Validation: preview shows normalized LeadCreate payload without saving.
  - Status: preview and ingestion share the production normalization path; saving remains disabled until an unsaved sample payload is reviewed.

- [x] **10.4 Implement lead deduplication and creation**
  - Reuse safe identity logic; never cross broker.
  - Validation: new, exact, ambiguous and repeated submissions.

- [x] **10.5 Implement first/last touch attribution**
  - Persist both without overwriting history.
  - Validation: repeated campaigns update last touch only.

- [x] **10.6 Capture messaging ad referrals**
  - Normalize WhatsApp and Instagram ad context into attribution.
  - Validation: conversation, identity and lead share the same reference.

- [x] **10.7 Add reconciliation task**
  - Poll every 15 minutes using cursor/checkpoint and overlap window.
  - Validation: missed webhook is recovered once.

- [x] **10.8 Expose origin in lead and pipeline UI** `[P]`
  - Show source, campaign, ad, form and project with drill-down.
  - Validation: agent sees assigned lead data; admin sees broker data.

### Phase 10 demo

- A real test form submission becomes an attributed CRM lead.
- Disabling the webhook temporarily is recovered by reconciliation without duplicate.

## Phase 11 — Insights, business outcomes and Conversions API

**Goal:** relacionar inversión publicitaria con el embudo y las ventas.
**Requirements:** REQ-015, REQ-017.

- [x] **11.1 Implement insights client and daily upsert**
  - Fetch campaign/ad set/ad metrics and upsert by date and remote IDs.
  - Validation: rerun produces identical totals.

- [x] **11.2 Schedule active and backfill sync**
  - Hourly current metrics and daily three-day reconciliation.
  - Validation: freshness alerts when jobs fail.

- [x] **11.3 Implement CRM outcome aggregation** `[P]`
  - Leads, advised, meetings, reservations, sales, UF and CLP by attribution.
  - Validation: totals reconcile with dashboard source tables.

- [x] **11.4 Implement calculated metrics**
  - Cost per conversation/lead/advised/meeting/reservation/sale and ROAS.
  - Define null rather than zero when denominator is absent.
  - Validation: deterministic service tests.

- [x] **11.5 Add Ads analytics APIs**
  - Filters by period, account, campaign, project and executive; drill-down lead IDs.
  - Validation: pagination, timezone and broker tests.

- [x] **11.6 Build Ads dashboard frontend** `[P]`
  - KPI cards, trends, funnel, campaign table and lead drill-down.
  - Validation: loading, empty, partial sync and error states.

- [x] **11.7 Implement Conversions API behind disabled flag**
  - Event mapping, normalization/hashing, consent gate, dedup event ID and retry.
  - Validation: no event leaves when flag or consent is absent.

- [x] **11.8 Add conversion diagnostics**
  - Show accepted/rejected events and last delivery without exposing PII.
  - Validation: permission and retention tests.

- [x] **11.9 Add dataset discovery and selection**
  - Location: `backend/app/services/meta/onboarding.py`, `backend/app/services/meta/conversions.py`, `backend/app/features/meta/routes.py`, `frontend/src/features/meta/components/MetaChannelsPage.tsx`.
  - Discover eligible broker datasets/pixels, persist them as corporate assets and let management select the conversion destination.
  - Dependencies: 2.5, 11.7.
  - Validation: Conversions API resolves an approved dataset without manual database insertion; executive-owned assets are rejected.
  - Status: business OAuth discovers ad-account pixels as corporate conversion assets; management selects one and delivery resolves only that approved default.

### Phase 11 demo

- Dashboard shows spend through sale for a test campaign.
- Every KPI opens its underlying leads.
- Conversions API remains off by default and sends only in an authorized sandbox.

## Phase 12 — Hardening, App Review and rollout

**Goal:** aprobar Meta, desplegar progresivamente y retirar el legado de forma segura.
**Requirements:** all requirements and NFRs.

- [x] **12.1 Complete security review**
  - Tenant audit, secret scan, log review, SSRF/media review, OAuth replay and webhook signatures.
  - Validation: security checklist has no critical/high findings.
  - Evidence: [security-review.md](./security-review.md).
  - Status: local review closed with no open critical/high findings in the Meta scope; production secrets and real-provider validation remain external gates.

- [ ] **12.2 Complete performance tests** `[P]`
  - Webhook ACK, message processing, inbox pagination and insights aggregation.
  - Validation: NFR P95 targets pass at expected peak load.
  - Evidence gate: task `12.2` in the [external setup manifest](./external-setup/manifest.json); intentionally marked `deferred`.
  - Status: deferred until a production-equivalent environment, representative data volume and expected peak-load profile are available; local functional timing is not accepted as NFR evidence.

- [x] **12.3 Run complete regression suite** `[P]`
  - Backend pytest, agent/eval tests, frontend type-check, Vitest and production build.
  - Validation: no regression in WhatsApp, Telegram, referral, tasks, pipeline or deals.
  - Status: closed locally with `DEBUG=false`: backend 756 passed and 8 skipped; frontend TypeScript passed, Vitest 32/32 passed and the Vite production build completed. The invalid local `.env` value `DEBUG=release` remains an environment correction outside the test command.

- [ ] **12.4 Validate Docker/Railway topology**
  - Backend, Worker, Beat, Redis, PostgreSQL and WebSocket with production-equivalent secrets.
  - Validation: health, queues, schedules and DLQ visible.
  - Evidence: [railway-topology-review.md](./railway-topology-review.md), [external setup runbook](./external-setup/README.md) and [status manifest](./external-setup/manifest.json).
  - Status: Compose and the local production-shaped topology pass, including healthchecks, migrations, Worker, Beat, Redis Pub/Sub and DLQ visibility. Closure requires the same checks against the linked Railway environment, its shared variables, persistent volume and replica settings.

- [ ] **12.5 Produce App Review evidence**
  - One video and written path per permission, reviewer account and clean demo data.
  - Validation: internal reviewer completes all flows unaided.
  - Evidence: [app-review-evidence/README.md](./app-review-evidence/README.md), [permission manifest](./app-review-evidence/manifest.json), [permission paths](./app-review-evidence/permission-paths.md) and [reviewer runbook](./app-review-evidence/reviewer-runbook.md).
  - Status: the local pack maps all 14 code-requested permissions to independent written paths and video slots, and its structural validator passes. Closure remains external: reconcile the current Meta portal, provision reviewer access and clean sandbox data, record the 14 videos, and pass an unaided internal review.

- [ ] **12.6 Submit and respond to App Review**
  - Track requested changes and update evidence without broadening scopes.
  - Validation: required permissions approved and app Live.
  - Evidence: [submission runbook](./app-review-evidence/submission-runbook.md) and [submission log](./app-review-evidence/submission-log.json).
  - Status: all 14 permission records and retry slots exist; submission, responses, approval and Live mode remain external.

- [ ] **12.7 Canary internal broker**
  - Enable new WhatsApp, then Instagram, Messenger, Ads and Lead Ads in order.
  - Observe at least seven days with rollback ready.
  - Validation: no message loss, duplicate effect or unexplained spend.
  - Evidence: [rollout runbook](./rollout/README.md) and [rollout manifest](./rollout/manifest.json).
  - Status: ordered stage, seven-day, zero-outcome and rollback gates are executable; canary traffic remains external.

- [ ] **12.8 Roll out broker cohorts**
  - Activate by cohort with preflight asset/permission checks.
  - Validation: each broker signs operational acceptance.
  - Evidence: [rollout runbook](./rollout/README.md) and [rollout manifest](./rollout/manifest.json).
  - Status: sequential cohort and acceptance gates are executable; no production cohort has been activated.

- [ ] **12.9 Retire runtime legacy fallback**
  - After two stable releases, disable fallback and monitor one release.
  - Validation: no legacy reads in telemetry.
  - Evidence: [rollout runbook](./rollout/README.md) and [rollout manifest](./rollout/manifest.json).
  - Status: the explicit fallback switch, blocked-send behavior and low-cardinality metric/log signal are implemented; two stable releases and the monitored disabled release remain external.

- [ ] **12.10 Remove legacy secrets in separate migration**
  - Backup, verify rollback and delete plaintext/JSON credential remnants.
  - Validation: secret scan and DB verification show only encrypted credentials.
  - Evidence: [rollout runbook](./rollout/README.md), [rollout manifest](./rollout/manifest.json) and read-only `backend/scripts/audit_meta_legacy_secrets.py`.
  - Status: inventory and strict migrated/retired audits are ready. Destructive migration/removal is intentionally blocked until 12.9 passes and a verified backup exists.

### Phase 12 demo

- A production broker completes the entire message-to-sale and draft-to-campaign flow.
- Operations can diagnose token, queue, webhook and Ads failures.
- Rollback has been exercised and documented.

## Next execution sequence

1. **Phase 0 and sandbox evidence:** configure the real Meta development app, legal URLs, credentials and representative test assets; close each record in `external-setup/manifest.json` with a non-secret evidence reference.
2. **12.4 Railway:** validate the linked production-equivalent topology with the strict external setup gate.
3. **12.5–12.6 App Review:** record/review the prepared evidence, submit it and track each permission through approval and Live mode.
4. **12.7–12.10 rollout:** execute the manifest-gated canary, cohorts and verified retirement of the legacy fallback/secrets.
5. **12.2 performance:** remains deferred until representative volume and peak-load profiles exist; it is not simulated locally.

## Final acceptance checklist

- [ ] Broker connects one WABA and assigns two numbers to two executives.
- [ ] Executive connects professional Instagram; admin approves it.
- [ ] Facebook Page and Instagram messages appear in the unified inbox.
- [ ] Personal Instagram, Messenger profile and independent WhatsApp are rejected.
- [ ] Management sees all broker conversations; agents see assigned conversations.
- [ ] Duplicate webhooks produce no duplicate message, lead, task, AI reply or ad operation.
- [ ] Replies always use the conversation asset.
- [ ] AI summary, draft and task suggestion respect human control and DICOM rules.
- [ ] Internal campaigns and referral outreach retain existing behavior.
- [ ] Executive Instagram never appears as an advertising actor.
- [ ] Campaign requires submission, approval, paused publication and explicit activation.
- [ ] Housing restrictions are enforced in frontend and backend.
- [ ] Lead form creates one attributed lead and reconciliation recovers missing events.
- [ ] Ads dashboard reconciles with lead, reservation and sale source data.
- [ ] Tokens are encrypted, masked and absent from logs/frontend.
- [ ] Existing WhatsApp history and rollback path are verified.
- [ ] Backend tests, frontend type-check, Vitest and build pass.
- [ ] Worker, Beat and WebSocket pass the production-equivalent Docker/Railway flow.
