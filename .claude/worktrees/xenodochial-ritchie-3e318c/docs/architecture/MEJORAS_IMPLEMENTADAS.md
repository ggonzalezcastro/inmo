# Mejoras implementadas – Plan de mejoras críticas

Documentación de los cambios realizados según la auditoría técnica y el plan de implementación.

---

## Resumen

Se implementaron las correcciones de **prioridad CRÍTICA y ALTA** en seguridad, rendimiento y mantenibilidad. Todas las tareas de las Fases 1 a 4 del plan están completadas.

---

## Fase 1: Seguridad y correcciones críticas

### 1.1 Validación de contraseña robusta

- **Archivos:** `backend/app/schemas/user.py`, `backend/app/routes/auth.py`, `backend/app/routes/broker_users.py`
- **Cambios:**
  - Función `validate_password_strength()` en esquemas de usuario: mínimo 8 caracteres, al menos una mayúscula, una minúscula y un dígito (opcional: carácter especial).
  - Aplicada a registro (`UserRegister` en `/auth/register`) y a creación de usuarios (`CreateUserRequest` en broker users).
- **Breaking change:** Las contraseñas que no cumplan estos requisitos serán rechazadas. Los usuarios existentes no se ven afectados hasta que cambien contraseña.

### 1.2 Race condition en appointments

- **Archivo:** `backend/app/services/appointment_service.py`
- **Cambios:** Bloqueo pesimista con `pg_advisory_xact_lock` (PostgreSQL) para el slot al crear/cancelar citas. En SQLite (tests) se omite el lock para compatibilidad.
- **Efecto:** Evita doble reserva del mismo slot por solicitudes concurrentes.

### 1.3 Race condition en actualización de score

- **Archivo:** `backend/app/routes/chat.py` (y orquestador de chat)
- **Cambios:** Actualización atómica del `lead_score` con `sqlalchemy.update()` y `func.least`/`func.greatest` para mantener el score en [0, 100] sin lost updates.
- **Efecto:** Evita pérdida de actualizaciones cuando varias peticiones modifican el mismo lead.

### 1.4 Sanitización XSS

- **Archivos:** `backend/app/schemas/lead.py`, `backend/app/routes/chat.py`, `backend/requirements.txt`
- **Cambios:**
  - Añadida dependencia `bleach`.
  - Función `sanitize_html()` para eliminar HTML en entradas de usuario.
  - Sanitización aplicada a `name` en `LeadBase` y al campo `message` en mensajes de chat.
- **Breaking change:** Ninguno; solo se restringe contenido HTML en esos campos.

---

## Fase 2: Optimización de rendimiento

### 2.1 N+1 en scoring tasks

- **Archivo:** `backend/app/tasks/scoring_tasks.py`
- **Cambios:**
  - Uso de `selectinload(Lead.telegram_messages)` y `selectinload(Lead.activities)` para cargar relaciones en una sola consulta por lead.
  - Nuevo método `ScoringService.calculate_lead_score_from_lead()` que trabaja con el lead ya cargado.
  - Batch: se hace commit al final del batch en lugar de por cada lead (manteniendo rollback por lead en error).
- **Mejora esperada:** ~60x en tareas de scoring con muchos leads (p. ej. 30s → ~0,5s para 1000 leads).

### 2.2 N+1 en campaign executor

- **Archivo:** `backend/app/tasks/campaign_executor.py`
- **Cambios:**
  - Filtrado de leads elegibles en SQL con una única query (`_build_eligible_leads_query()`), sin filtrar en Python dentro del bucle.
  - Inserción en batch de campaign logs donde aplica.
- **Mejora esperada:** ~22x (p. ej. 45s → ~2s en escenarios típicos).

### 2.3 Caché Redis

- **Archivos:** `backend/app/core/cache.py` (nuevo), `backend/app/services/broker_config_service.py`, `backend/app/services/lead_context_service.py`, `backend/app/routes/broker_config.py`
- **Cambios:**
  - Módulo de caché asíncrono: `cache_get`, `cache_set`, `cache_get_json`, `cache_set_json`.
  - Caché de `build_system_prompt` (broker config sin `lead_context`) con TTL 1 hora.
  - Caché de `get_lead_context` con TTL 5 minutos.
  - Invalidación de caché al actualizar configuración de prompts en broker config.
- **Requisito:** `REDIS_URL` configurado. Si Redis no está disponible, las funciones siguen funcionando sin caché (fail-open).
- **Mejora esperada:** Reducción drástica de queries en rutas calientes (p. ej. broker config de miles a decenas de queries/día).

---

## Fase 3: Refactoring y mantenibilidad

### 3.1 Refactorización de chat (God Class)

- **Archivos:** `backend/app/services/chat_orchestrator_service.py` (nuevo), `backend/app/routes/chat.py`
- **Cambios:**
  - Lógica principal del endpoint `test_chat` movida a `ChatOrchestratorService`: obtención/creación de lead, análisis de mensaje, actualización de score, avance de pipeline, generación de respuesta y function calling.
  - El endpoint `POST /api/v1/chat/test` queda como capa fina que delega en el orquestador.
- **Breaking change:** Ninguno; la API pública no cambia.

### 3.2 Tests críticos

- **Archivos nuevos:** `backend/tests/services/test_scoring_service.py`, `backend/tests/services/test_appointment_service.py`
- **Contenido:**
  - Tests unitarios de cálculo de score y de `ScoringService`.
  - Tests de integración para `check_availability` y `create_appointment` con mocks de Google Calendar y servicios externos.
- **Meta:** Aumentar cobertura en servicios críticos (scoring y citas).

### 3.3 Rate limiting en auth

- **Archivo:** `backend/app/middleware/rate_limiter.py`
- **Cambios:**
  - Límites por ruta: `/auth/login` 5 intentos/minuto, `/auth/register` 3 registros/hora.
  - En rutas de auth, si Redis o el rate limiter fallan, se aplica **fail-closed**: se rechaza la petición con 429 ("Rate limit unavailable"). El resto de rutas mantiene fail-open.
- **Nota:** El middleware de rate limit solo se activa cuando `ENVIRONMENT=production`.

---

## Fase 4: Limpieza y documentación

### 4.1 Migración LLM

- **Archivos:** `backend/app/services/llm_service.py`, `backend/app/services/llm_service_facade.py`, `backend/app/services/chat_orchestrator_service.py`, `backend/app/tasks/telegram_tasks.py`, `backend/app/services/call_agent_service.py`, `backend/tests/conftest.py`, `backend/tests/test_chat.py`
- **Cambios:**
  - Todos los usos de `LLMService` pasan a `LLMServiceFacade` (orquestador de chat, telegram tasks, call agent).
  - `llm_service.py` queda como shim: emite `DeprecationWarning` y log de aviso y reexporta `LLMService = LLMServiceFacade`.
  - Tests: `mock_gemini` en conftest ahora mockea `get_llm_provider` con un provider fake; test_chat mockea `LLMServiceFacade.analyze_lead_qualification` en el módulo del orquestador.
- **Breaking change:** Quien importe `from app.services.llm_service import LLMService` seguirá teniendo comportamiento (vía facade) pero verá el aviso de deprecación. Se recomienda migrar a `from app.services.llm_service_facade import LLMServiceFacade`.

### 4.2 Índices de base de datos

- **Archivo:** `backend/migrations/versions/f7a8b9c0d1e2_add_performance_indexes.py`
- **Índices creados:**
  - `idx_leads_broker_stage` en `leads(broker_id, pipeline_stage)` – pipeline/board por broker.
  - `idx_leads_assigned_status` en `leads(assigned_to, status)` – vistas por asignación y estado.
  - `idx_messages_lead_created` en `telegram_messages(lead_id, created_at)` – historial de mensajes por lead.
- **Compatibilidad:** La migración es compatible con PostgreSQL y SQLite (sin `postgresql_ops`).

### 4.3 Documentación de cambios

- **Archivo:** Este documento (`MEJORAS_IMPLEMENTADAS.md`).

---

## Instrucciones de migración

### Despliegue

1. **Dependencias:**  
   `pip install -r backend/requirements.txt` (incluye `bleach` y las ya existentes).

2. **Variables de entorno:**  
   - `REDIS_URL` para rate limiting y caché (recomendado en producción).  
   - Sin Redis, la app sigue funcionando; en producción no habrá rate limit ni caché.

3. **Base de datos:**  
   Ejecutar migraciones para crear los nuevos índices:
   ```bash
   cd backend && alembic upgrade head
   ```

4. **Contraseñas:**  
   Las nuevas contraseñas (registro y creación de usuarios) deben cumplir la política (8+ caracteres, mayúscula, minúscula, dígito). Las existentes no se validan hasta que se cambien.

### Rollback

- **Código:** Revertir los commits de las mejoras; la API y los modelos no tienen cambios incompatibles salvo la política de contraseñas en nuevos registros.
- **BD:** Para quitar los índices:
  ```bash
  alembic downgrade -1
  ```
  (retrocede una revisión; asegurarse de que `down_revision` de la migración de índices apunte a la revisión anterior).

---

## Métricas de éxito (plan)

- **Seguridad:** Contraseñas fuertes, sanitización XSS, rate limit en auth y fail-closed en auth cuando el limiter falla.
- **Rendimiento:** Menos N+1 en scoring y campañas; caché en broker config y lead context; índices para pipeline, asignación y mensajes.
- **Tests:** Tests añadidos para scoring y appointment service.
- **Mantenibilidad:** Chat orquestado en servicio dedicado; LLM unificado tras el facade y deprecación de `llm_service.py`.

Si quieres, el siguiente paso puede ser ejecutar la suite de tests o afinar algún punto concreto (por ejemplo, TTLs de caché o mensajes de error del rate limiter).
