# Requirements Specification: Ecosistema Meta multicanal

**Spec ID:** META-ECOSYSTEM-001
**Version:** 1.1
**Status:** Baseline funcional local — brechas de aceptación y validación externa pendientes
**Updated:** 2026-09-09
**Owners:** Producto, Backend, Frontend y DevOps
**Traceability:** [traceability.md](./traceability.md)

## 1. Purpose

Expandir el CRM inmobiliario multi-tenant para que cada broker gestione WhatsApp, Instagram, Messenger y Meta Ads desde una misma plataforma. La solución debe permitir canales corporativos y canales profesionales asociados a ejecutivos, conservar supervisión de jefatura, crear y atribuir leads, asistir las conversaciones con IA y relacionar inversión publicitaria con reservas y ventas.

## 2. Product decisions

- La plataforma utilizará una sola aplicación Meta multi-tenant.
- Los números de WhatsApp pertenecerán al broker y se asignarán a ejecutivos.
- No se conectarán cuentas personales ni números independientes de WhatsApp de ejecutivos.
- Los ejecutivos podrán conectar Instagram Business o Creator para mensajería, sujeto a aprobación de jefatura.
- Las cuentas de Instagram de ejecutivos no podrán utilizarse para anuncios.
- Messenger solo admitirá páginas de Facebook; nunca perfiles o bandejas personales.
- Toda conversación ingresada al CRM será corporativa y visible para jefatura.
- Las cuentas publicitarias, métodos de pago y activos de anuncios pertenecerán al broker.
- Un ejecutivo podrá preparar un borrador publicitario; jefatura aprobará, publicará y activará el gasto.
- Toda campaña nueva se publicará pausada y exigirá una segunda confirmación para activarse.
- Las campañas pagadas de Meta permanecerán separadas de las automatizaciones CRM existentes.

## 3. Glossary

- **Broker:** empresa inmobiliaria tenant del CRM.
- **Executive:** usuario AGENT que atiende y vende dentro de un broker.
- **Management:** usuario ADMIN del broker.
- **Connection:** autorización OAuth o empresarial entregada a la aplicación.
- **Asset:** número de WhatsApp, WABA, Instagram, página, cuenta publicitaria, formulario o dataset administrado mediante una conexión.
- **Corporate asset:** activo controlado por el broker.
- **Executive asset:** Instagram profesional o página conectada por un ejecutivo y aprobada para uso corporativo.
- **External identity:** persona que conversa con un activo específico en Meta.
- **Internal campaign:** automatización CRM existente para contactar leads.
- **Meta campaign:** campaña publicitaria creada mediante Marketing API.

## 4. Personas and goals

### Executive

- Atender conversaciones y leads asignados.
- Conectar Instagram profesional o una página administrada.
- Usar IA para resumir y redactar respuestas.
- Crear tareas desde conversaciones.
- Preparar borradores de campañas con activos corporativos.

### Management

- Conectar y administrar activos corporativos.
- Aprobar activos de ejecutivos.
- Asignar números de WhatsApp.
- Supervisar todas las conversaciones.
- Resolver conflictos de asignación.
- Aprobar campañas, presupuestos y activación.
- Comparar inversión, leads, reservas y ventas.

### Superadmin

- Diagnosticar conexiones y operación entre brokers.
- Consultar sin enviar mensajes ni activar publicidad.
- Operar dentro de un broker únicamente mediante impersonación auditable.

## 5. Scope

### Included

- WhatsApp Cloud API con múltiples números por broker.
- Instagram professional messaging para broker y ejecutivos.
- Messenger para páginas de Facebook.
- Bandeja unificada y tiempo real.
- Identificación, deduplicación, creación y asignación de leads.
- IA para resumen, redacción y sugerencia de tareas.
- Lead Ads, click-to-WhatsApp, click-to-Instagram y tráfico a proyectos.
- Aprobación y administración de campañas de Meta.
- Atribución y métricas hasta reserva y venta.
- Preparación de Conversions API detrás de feature flag.

### Excluded from version 1

- WhatsApp personal o números de propiedad independiente del ejecutivo.
- Instagram personal.
- Messenger de perfiles personales.
- Publicación orgánica de posts, stories o reels.
- Moderación de comentarios públicos.
- Facebook Marketplace.
- Campañas pagadas desde activos personales de ejecutivos.
- Optimización automática de presupuesto decidida por IA.
- Activación automática de campañas.

### Delivery and acceptance boundary

La aceptación se controla en tres niveles independientes:

1. **Local:** modelos, migraciones, servicios, API y UI existen y pasan sus verificaciones dirigidas.
2. **Sandbox Meta:** los mismos flujos se prueban con activos reales de desarrollo y permisos concedidos por Meta.
3. **Producción:** App Review, configuración de Railway, canary, métricas P95 y retiro progresivo del fallback quedan aprobados.

Un requisito marcado como implementado localmente no se considera aceptado en producción hasta completar los niveles externos que le correspondan. El estado detallado y la evidencia se mantienen en [tasks.md](./tasks.md), [traceability.md](./traceability.md) y [verification.md](./verification.md). La matriz de trazabilidad se regenera y valida con `python3 scripts/check_meta_traceability.py --write`.

## 6. Functional requirements

### REQ-001 — Tenant isolation

**User story:** Como broker, quiero que mis conexiones, activos, conversaciones y campañas estén completamente aislados de otros brokers.

**Acceptance criteria:**

1. WHEN una consulta autenticada accede a datos Meta, THE SYSTEM SHALL filtrar por `broker_id` antes de devolver o modificar información.
2. IF un identificador pertenece a otro broker, THEN THE SYSTEM SHALL responder como recurso inexistente o acceso denegado sin revelar su propietario.
3. WHEN un webhook identifica un activo, THE SYSTEM SHALL resolver exactamente un broker antes de procesar mensajes o leads.
4. IF un activo externo aparece asociado a dos brokers activos, THEN THE SYSTEM SHALL bloquearlo y generar una alerta crítica.
5. A SUPERADMIN SHALL tener acceso de diagnóstico de solo lectura; cualquier mutación SHALL requerir una sesión de broker impersonada y auditable.

### REQ-002 — Connection lifecycle

**User story:** Como usuario autorizado, quiero conectar y desconectar Meta sin compartir tokens manualmente.

**Acceptance criteria:**

1. WHEN un usuario inicia OAuth, THE SYSTEM SHALL emitir un estado firmado, limitado al broker, usuario, canal, nonce y expiración.
2. WHEN Meta devuelve el callback, THE SYSTEM SHALL validar estado, nonce, aplicación, permisos y propietario antes de persistir la conexión.
3. WHEN una credencial se almacena, THE SYSTEM SHALL cifrarla y SHALL NOT devolverla al frontend ni escribirla en logs.
4. WHEN un permiso o token expira, THE SYSTEM SHALL marcar la conexión como degradada y notificar al propietario y a jefatura.
5. WHEN una conexión se revoca, THE SYSTEM SHALL impedir nuevos envíos, preservar el historial y ejecutar la eliminación o desconexión exigida por Meta.

### REQ-003 — Asset discovery, ownership and approval

**User story:** Como jefatura, quiero conocer qué activos fueron compartidos y controlar cuáles operan dentro del CRM.

**Acceptance criteria:**

1. WHEN una conexión es autorizada, THE SYSTEM SHALL descubrir los activos y capacidades permitidos por Meta.
2. WHEN un ejecutivo conecta Instagram o una página, THE SYSTEM SHALL mantener el activo en `pending_approval` hasta decisión administrativa.
3. WHEN jefatura aprueba un activo, THE SYSTEM SHALL habilitar exclusivamente sus capacidades autorizadas.
4. WHEN jefatura rechaza o pausa un activo, THE SYSTEM SHALL bloquear envíos y automatizaciones sin eliminar historial.
5. THE SYSTEM SHALL permitir un único activo predeterminado por broker y canal.

### REQ-004 — WhatsApp broker-owned numbers

**User story:** Como jefatura, quiero asignar números corporativos de WhatsApp a ejecutivos.

**Acceptance criteria:**

1. WHEN se conecta una WABA, THE SYSTEM SHALL descubrir todos sus números disponibles.
2. WHEN jefatura asigna un número, THE SYSTEM SHALL comprobar que el ejecutivo está activo y pertenece al broker.
3. THE SYSTEM SHALL impedir que un mismo número tenga más de un ejecutivo asignado simultáneamente.
4. WHEN llega un mensaje, THE SYSTEM SHALL resolver el broker y número mediante `phone_number_id`.
5. WHEN se responde una conversación, THE SYSTEM SHALL utilizar el mismo número receptor.
6. WHEN se inicia un contacto nuevo permitido, THE SYSTEM SHALL usar primero el número asignado al ejecutivo y luego el número corporativo predeterminado.
7. WHEN la ventana de atención haya expirado, THE SYSTEM SHALL exigir una plantilla de WhatsApp aprobada.

### REQ-005 — Instagram professional messaging

**User story:** Como ejecutivo, quiero atender los mensajes de mi cuenta profesional de Instagram desde el CRM.

**Acceptance criteria:**

1. WHEN se conecta Instagram, THE SYSTEM SHALL validar que sea Business o Creator.
2. IF la cuenta es personal, THEN THE SYSTEM SHALL rechazar la activación con una explicación comprensible.
3. WHEN un ejecutivo conecta la cuenta, THE SYSTEM SHALL asignarle propiedad operativa y SHALL requerir aprobación administrativa.
4. THE SYSTEM SHALL limitar los activos de ejecutivos a mensajería.
5. THE SYSTEM SHALL impedir que Instagram de un ejecutivo aparezca en el constructor de campañas.
6. THE SYSTEM SHALL permitir responder solamente conversaciones iniciadas por el usuario externo y dentro de las reglas vigentes de Meta.

### REQ-006 — Messenger Pages

**User story:** Como broker, quiero atender mensajes de páginas de Facebook desde la misma bandeja.

**Acceptance criteria:**

1. WHEN se conecta Messenger, THE SYSTEM SHALL listar únicamente páginas administrables.
2. THE SYSTEM SHALL NOT ofrecer conexión de perfiles o bandejas personales.
3. WHEN un ejecutivo conecta una página, THE SYSTEM SHALL exigir aprobación administrativa.
4. WHEN llega o se envía un mensaje, THE SYSTEM SHALL utilizar el token y la identidad de la página correspondiente.
5. THE SYSTEM SHALL respetar las ventanas, etiquetas y restricciones vigentes de Messenger.

### REQ-007 — Webhook ingestion and idempotency

**User story:** Como plataforma, quiero procesar eventos de Meta de manera segura y sin duplicados.

**Acceptance criteria:**

1. WHEN Meta envía un webhook, THE SYSTEM SHALL verificar su firma sobre el cuerpo original.
2. IF la firma no es válida, THEN THE SYSTEM SHALL rechazar el evento sin contaminar deduplicación o rate limits.
3. WHEN el evento es válido, THE SYSTEM SHALL persistir una referencia idempotente y encolarlo antes del procesamiento pesado.
4. IF Meta reenvía el mismo evento, THEN THE SYSTEM SHALL NOT crear mensajes, leads ni respuestas duplicadas.
5. WHEN un evento desconocido es válido, THE SYSTEM SHALL registrarlo de forma segura y devolver éxito para evitar reintentos inútiles.
6. IF el evento no puede persistirse, THEN THE SYSTEM SHALL devolver un estado reintentable a Meta.

### REQ-008 — Identity resolution and lead creation

**User story:** Como ejecutivo, quiero que los mensajes creen o encuentren el lead correcto.

**Acceptance criteria:**

1. WHEN llega un mensaje, THE SYSTEM SHALL buscar primero una identidad por broker, activo, canal e identificador externo.
2. WHEN no existe identidad, THE SYSTEM SHALL intentar coincidencia segura por teléfono o correo normalizado dentro del broker.
3. WHEN existe una única coincidencia segura, THE SYSTEM SHALL asociar la nueva identidad al lead existente.
4. WHEN no existe coincidencia, THE SYSTEM SHALL crear un lead con canal, activo y origen.
5. WHEN existen coincidencias ambiguas, THE SYSTEM SHALL crear un caso de revisión y SHALL NOT fusionar automáticamente.
6. THE SYSTEM SHALL almacenar campaña, anuncio, formulario, proyecto y referencia publicitaria cuando estén disponibles.

### REQ-009 — Assignment and corporate visibility

**User story:** Como jefatura, quiero que los leads se distribuyan correctamente sin perder control corporativo.

**Acceptance criteria:**

1. WHEN un lead nuevo llega a un activo asociado a un ejecutivo, THE SYSTEM SHALL asignarlo a ese ejecutivo.
2. WHEN un lead nuevo llega a un activo general, THE SYSTEM SHALL usar el servicio central de asignación vigente.
3. WHEN un lead existente escribe a un activo de otro ejecutivo, THE SYSTEM SHALL conservar al responsable actual y crear un conflicto visible.
4. WHEN jefatura resuelve el conflicto, THE SYSTEM SHALL registrar la decisión y transferir las tareas abiertas mediante el servicio central de asignación.
5. THE SYSTEM SHALL permitir a jefatura consultar todas las conversaciones del broker.
6. THE SYSTEM SHALL limitar al ejecutivo a sus leads y conversaciones asignados.

### REQ-010 — Unified inbox and outbound messaging

**User story:** Como usuario, quiero atender todos los canales desde una bandeja consistente.

**Acceptance criteria:**

1. THE SYSTEM SHALL listar conversaciones con canal, activo, lead, responsable, último mensaje, no leídos y estado IA/humano.
2. THE SYSTEM SHALL filtrar por canal, activo, ejecutivo, proyecto, etapa, estado y período.
3. WHEN un usuario responde, THE SYSTEM SHALL enviar mediante el activo fijado en la conversación.
4. WHEN Meta confirma entrega, lectura o fallo, THE SYSTEM SHALL actualizar el mensaje y emitir un evento WebSocket.
5. WHEN un activo no puede enviar, THE SYSTEM SHALL bloquear la acción, explicar la causa y ofrecer un canal alternativo cuando exista.
6. THE SYSTEM SHALL admitir texto y los archivos permitidos por cada canal con validación de tamaño y tipo.

### REQ-011 — AI assistance

**User story:** Como ejecutivo, quiero que Sofía me ayude sin perder control sobre la conversación.

**Acceptance criteria:**

1. WHEN se solicita un borrador, THE SYSTEM SHALL usar la conversación, lead, proyecto, etapa y canal correctos.
2. THE SYSTEM SHALL ofrecer resumen, borrador de respuesta y sugerencias de tareas.
3. THE SYSTEM SHALL identificar claramente contenido generado por IA.
4. THE SYSTEM SHALL usar modo sugerencia como valor predeterminado para activos nuevos.
5. ONLY management SHALL habilitar respuesta automática por activo.
6. WHEN existe toma humana, reclamo, contenido sensible o baja confianza, THE SYSTEM SHALL detener respuestas automáticas.
7. THE SYSTEM SHALL conservar las reglas DICOM, de disponibilidad y de no inventar condiciones comerciales.

### REQ-012 — Internal and paid campaign separation

**User story:** Como administrador, quiero diferenciar automatizaciones CRM de campañas publicitarias.

**Acceptance criteria:**

1. THE SYSTEM SHALL mantener modelos, endpoints, navegación y estados separados para automatizaciones CRM y Meta Ads.
2. THE SYSTEM SHALL conservar sin cambios semánticos las campañas internas, incluida la campaña de referidos.
3. THE SYSTEM SHALL presentar ambos productos bajo una navegación comprensible sin reutilizar identificadores entre dominios.

### REQ-013 — Meta Ads creation and approval

**User story:** Como equipo comercial, quiero preparar campañas con control administrativo del gasto.

**Acceptance criteria:**

1. WHEN un ejecutivo crea una campaña, THE SYSTEM SHALL mantenerla como borrador local hasta enviarla a aprobación.
2. THE SYSTEM SHALL permitir formularios, click-to-WhatsApp, click-to-Instagram y tráfico a proyectos.
3. THE SYSTEM SHALL usar únicamente páginas, Instagram corporativo, números y cuentas publicitarias del broker.
4. WHEN una campaña inmobiliaria lo requiera, THE SYSTEM SHALL declararla como categoría especial Housing y limitar la segmentación a opciones aceptadas por Meta.
5. WHEN jefatura aprueba, THE SYSTEM SHALL validar remotamente y crear los objetos publicitarios de forma idempotente.
6. THE SYSTEM SHALL publicar campaña, conjunto y anuncios en estado pausado.
7. ONLY management SHALL activar gasto mediante una segunda confirmación.
8. WHEN una creación falla parcialmente, THE SYSTEM SHALL conservar los objetos remotos pausados, registrar sus IDs y permitir reintento o limpieza controlada.
9. THE SYSTEM SHALL auditar creación, aprobación, rechazo, presupuesto, publicación, activación y pausa.

### REQ-014 — Lead Ads and attribution

**User story:** Como jefatura, quiero saber qué campaña produjo cada lead y venta.

**Acceptance criteria:**

1. WHEN Meta notifica un lead form, THE SYSTEM SHALL recuperar sus datos, mapearlos y crear o actualizar el lead.
2. THE SYSTEM SHALL reconciliar formularios periódicamente para recuperar eventos perdidos.
3. THE SYSTEM SHALL deduplicar por broker, formulario e identificador externo.
4. THE SYSTEM SHALL guardar cuenta, campaña, conjunto, anuncio, creatividad, formulario, proyecto y UTM disponibles.
5. WHEN un anuncio de mensajería entrega referencia publicitaria, THE SYSTEM SHALL asociarla a la identidad, conversación y lead.
6. THE SYSTEM SHALL conservar primera y última atribución sin sobrescribir el origen histórico.

### REQ-015 — Advertising metrics and CRM outcomes

**User story:** Como jefatura, quiero relacionar inversión con resultados comerciales reales.

**Acceptance criteria:**

1. THE SYSTEM SHALL sincronizar inversión, impresiones, alcance, frecuencia, clics, conversaciones y leads.
2. THE SYSTEM SHALL relacionar esos datos con leads asesorados, reuniones, reservas, ventas, UF y pesos del CRM.
3. THE SYSTEM SHALL calcular costo por conversación, lead, asesoría, reunión, reserva y venta.
4. THE SYSTEM SHALL filtrar métricas por período, cuenta, campaña, proyecto y ejecutivo.
5. WHEN el usuario abre un indicador, THE SYSTEM SHALL permitir navegar al conjunto de leads que lo compone.
6. IF Conversions API está desactivada, THEN THE SYSTEM SHALL NOT enviar datos comerciales a Meta.
7. WHEN management habilita Conversions API, THE SYSTEM SHALL exigir un dataset/pixel corporativo descubierto, aprobado y perteneciente al mismo broker antes de enviar eventos.

### REQ-016 — Offboarding and disconnection

**User story:** Como jefatura, quiero retirar a un ejecutivo sin perder clientes ni historial.

**Acceptance criteria:**

1. WHEN un ejecutivo es desactivado, THE SYSTEM SHALL retirar la asignación de sus números corporativos.
2. THE SYSTEM SHALL pausar sus activos profesionales y bloquear automatizaciones salientes.
3. THE SYSTEM SHALL conservar mensajes, auditoría y atribución histórica.
4. THE SYSTEM SHALL mover sus leads activos a la cola sin asignar mediante el servicio central y dejar tareas abiertas sin responsable hasta reasignación.
5. WHEN el activo puede transferirse, THE SYSTEM SHALL permitir que jefatura complete la transferencia antes de revocar la autorización.
6. WHEN el usuario solicita desconexión, THE SYSTEM SHALL explicar el impacto antes de confirmar.

### REQ-017 — Audit and observability

**User story:** Como operador, quiero detectar fallos antes de perder mensajes o inversión.

**Acceptance criteria:**

1. THE SYSTEM SHALL medir webhooks, latencia, duplicados, envíos, entregas, errores, rate limits, tokens, colas y sincronizaciones.
2. WHEN un token se acerca a su expiración, THE SYSTEM SHALL notificar con anticipación.
3. WHEN una cola, DLQ o sincronización supera el umbral configurado, THE SYSTEM SHALL alertar a operación.
4. THE SYSTEM SHALL permitir correlacionar un webhook, tarea, mensaje y llamada a Graph API sin registrar PII innecesaria.
5. THE SYSTEM SHALL auditar toda acción que pueda enviar mensajes o gastar presupuesto.

### REQ-018 — Backward-compatible migration

**User story:** Como broker existente, quiero adoptar la nueva integración sin perder WhatsApp ni conversaciones.

**Acceptance criteria:**

1. WHEN se despliega la migración, THE SYSTEM SHALL mantener operativa la configuración existente.
2. THE SYSTEM SHALL convertir cada configuración WhatsApp actual en una conexión y activo corporativo.
3. THE SYSTEM SHALL conservar lectura del historial que no tenga `asset_id`.
4. WHEN un broker haya sido validado en el modelo nuevo, THE SYSTEM SHALL permitir activar el resolver nuevo mediante feature flag.
5. THE SYSTEM SHALL NOT eliminar credenciales legacy hasta dos versiones estables, respaldo y verificación de rollback.

## 7. Non-functional requirements

### NFR-001 — Security

- Tokens cifrados con claves separadas de JWT.
- Secretos solo en backend, Worker y Beat.
- Firma de webhook obligatoria en producción.
- Rate limiting por activo y remitente.
- Descarga de archivos protegida contra SSRF y contenido excesivo.
- Logs sin tokens, cuerpos completos ni teléfonos sin enmascarar.

### NFR-002 — Reliability

- Procesamiento asíncrono mediante Celery y DLQTask.
- Operaciones remotas idempotentes.
- Reconciliación para formularios, campañas y métricas.
- Webhook durable antes de ejecutar IA.
- Ningún error de IA debe eliminar un mensaje entrante.

### NFR-003 — Performance

- ACK del webhook P95 menor a 2 segundos.
- Mensaje normalizado visible por WebSocket P95 menor a 5 segundos, excluyendo indisponibilidad de Meta.
- Listados paginados y consultas sin N+1.
- Índices por broker, activo, estado y fecha.

### NFR-004 — Privacy and retention

- Payload bruto cifrado con retención máxima de siete días.
- Mensajes normalizados sujetos a la política vigente del broker.
- Eliminación y revocación compatibles con las obligaciones de Meta.
- Conversions API requiere feature flag, base legal y consentimiento configurado.

### NFR-005 — Compatibility

- Backend FastAPI, PostgreSQL, Redis y Celery existentes.
- Frontend React/Vite, Zustand, Sonner y WebSocket existentes.
- Graph API fijada por configuración; versión inicial v26.0, revalidada contra el [anuncio oficial de Meta](https://developers.facebook.com/blog/post/2026/07/29/introducing-graph-api-v26-and-marketing-api-v26/) el 2026-09-07.
- Automatizaciones, referral agent, Telegram, WebChat y voz no deben cambiar de significado.

## 8. Product success criteria

Estos criterios son puertas de salida de producto y, salvo indicación expresa, requieren evidencia sandbox o productiva; no se satisfacen únicamente con mocks o fixtures locales.

- Un broker conecta una WABA y asigna dos números a dos ejecutivos.
- Un ejecutivo conecta Instagram profesional, jefatura lo aprueba y un mensaje genera un lead asignado.
- Una página de Facebook recibe y responde desde la bandeja.
- Jefatura puede leer, filtrar y reasignar todas las conversaciones del broker.
- No existen mensajes duplicados frente a reintentos de webhook.
- Un ejecutivo prepara una campaña y jefatura la publica pausada y luego la activa.
- Un formulario crea un lead atribuido a campaña, anuncio y proyecto.
- El dashboard relaciona gasto con leads asesorados, reservas y ventas.
- Un broker existente migra WhatsApp sin pérdida de mensajes ni interrupción prolongada.

## 9. Acceptance matrix

| Requirement | Local state | Remaining acceptance gate |
|---|---|---|
| REQ-001, REQ-008–009, REQ-011–012, REQ-016 | Implemented and covered by directed local verification | Full regression and broker canary |
| REQ-002–007, REQ-010 | Implemented against fixtures and local flows | Real OAuth, webhook and messaging evidence for each channel |
| REQ-013 | Draft, immutable snapshot review, publisher and structured spend controls implemented | Real paused publication |
| REQ-014 | Sync, normalized mapping preview, deduplication and attribution implemented | Real form/reconciliation evidence |
| REQ-015 | Analytics, drill-down, dataset selection, conversion sender and diagnostics implemented | Privacy approval and sandbox conversion delivery |
| REQ-017 | Metrics, audit and local task topology implemented | Load thresholds, alerts and production-equivalent Railway validation |
| REQ-018 | Additive migration, backfill and fallback implemented | Seven-day canary, two stable releases and verified legacy retirement |
| NFR-001–002 | Core controls and local security review complete; no open critical/high findings in the Meta scope | Production secret validation and failure/retry evidence with real provider calls |
| NFR-003 | Query design and metrics hooks implemented | Measured P95 at expected peak load |
| NFR-004 | Retention, encryption and consent gates implemented | Legal review, public HTTPS pages and definitive media-storage validation |
| NFR-005 | Target stack preserved | Resolve the pre-existing global pytest, TypeScript and ESLint baseline |
