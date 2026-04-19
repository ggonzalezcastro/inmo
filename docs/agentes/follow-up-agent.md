# Follow-Up Agent

**Versión:** 1.0
**Última actualización:** 2026-04-17
**Agente responsable de:** Seguimiento post-visita, re-enganche de leads inactivos, solicitudes de referidos

---

## Propósito y Responsabilidad

El **FollowUpAgent** gestiona todas las comunicaciones de seguimiento después de que un lead ha sido calificado y/o ha tenido una interacción inicial con la inmobiliaria. Su responsabilidad principal es:

- Mantener engagement con leads programados
- Re-activar leads que han caído en inactividad
- Solicitar referidos a leads cerrados exitosamente
- Guiar a leads con problemas DICOM hacia regularización
- Maximizar la tasa de conversión en etapas avanzadas del pipeline

### Etapas del Pipeline que Maneja

```
agendado → seguimiento → referidos → ganado/perdido
```

El agente mantiene presencia en múltiples etapas simultáneamente, aplicando la estrategia de seguimiento correspondiente a cada lead según su estado.

---

## should_handle() — Condiciones de Atribución

El `AgentSupervisor` delega al `FollowUpAgent` cuando se cumplen TODAS las condiciones:

```python
def should_handle(self, lead: Lead, context: AgentContext) -> bool:
    """
    Returns True si el lead debe ser manejado por FollowUpAgent.
    """
    # 1. El lead está en una etapa manejada por FollowUpAgent
    if lead.stage not in [
        StageEnum.AGENDADO,
        StageEnum.SEGUIMIENTO,
        StageEnum.REFERIDOS,
        StageEnum.GANADO,
        StageEnum.PERDIDO,
    ]:
        return False

    # 2. No hay un agente superior ya atendiendo (sticky agent)
    if lead.current_agent and lead.current_agent != "follow_up":
        # Solo Transferir si el agente actual cede el control
        pass

    # 3. El contexto no indica que otro agente tiene jurisdicción
    if context.intent in [AgentIntent.SCHEDULE_VISIT, AgentIntent.QUALIFY_LEAD]:
        return False

    return True
```

### Señales de Handoff desde Otros Agentes

```python
# Handoff desde QualifierAgent — DICOM dirty, necesita regularización
{
    "trigger": "dicom_dirty_high_debt",
    "next_agent": "follow_up",
    "reason": "Lead requiere seguimiento para normalizar situación DICOM"
}

# Handoff desde SchedulerAgent — Visita confirmada/completada
{
    "trigger": "appointment_confirmed",
    "next_agent": "follow_up",
    "reason": "Post-visita,需要对线跟进"
}

# Handoff desde PropertyAgent — Lead no interesado en propiedades
{
    "trigger": "not_interested_properties",
    "next_agent": "follow_up",
    "reason": "Lead necesita re-enganche"
}
```

---

## Tipos de Seguimiento

### 1. Post-Appointment Follow-Up

**Trigger:** Una cita ha sido marcada o completada.

**Objetivo:** Verificar asistencia, recoger feedback, avanzar al siguiente paso.

**Flujo:**
```
Appointment Scheduled → Mensaje de confirmación
                      → Recordatorio 24h antes
                      → Post-appointment check-in
                      → Evaluación de interés
```

**Mensaje típico:**
```
"¡Hola {nombre}! Tu visita a {dirección_propiedad} está confirmada para mañana a las {hora}.
¿Tienes alguna pregunta antes de ir? Estoy aquí para ayudarte."
```

### 2. Inactive Lead Re-Engagement

**Trigger:** `days_since_last_contact > threshold` (configurable por broker, default: 3 días en etapa agendado, 7 días en seguimiento)

**Estrategia:** Escalar gradualmente la urgencia del mensaje.

| Días inactivo | Tipo de mensaje |
|---------------|-----------------|
| 1-2 | recordatorio suave |
| 3-5 | mensaje de valor agregado |
| 6-10 | oferta de ayuda / alternativa |
| 11+ | última oportunidad / cierre |

**Mensaje típico (inactivo 3 días):**
```
"Hola {nombre}, hope you're doing well. I wanted to check in — did you have
a chance to visit {propiedad}? I'm here if you have any questions or want
to explore other options that might be a better fit."
```

### 3. Referral Request

**Trigger:** Lead alcanzó etapa `ganado` (cierre exitoso).

**Timing:** 2-3 días después del cierre confirmado, no inmediatamente.

**Objetivo:** Capturar red de contactos del lead satisfecho.

**Mensaje típico:**
```
"{nombre}, me alegra mucho que hayas encontrado tu nuevo hogar. ¿Conoces
a alguien que también esté buscando propiedad? Tu recomendación significa
mucho para nosotros — por cada referido que se convierte en cliente,
te entregamos un detalle de agradecimiento."
```

### 4. DICOM Follow-Up

**Trigger:** Lead tiene `dicom_status == "dirty"` pero la deuda es manejable.

**Objetivo:** Guiar al lead hacia regularización sin prometer aprobación crediticia.

**Restricción DICOM:**
> **NUNCA** prometer "pre-aprobación" o "crédito aprobado" a leads con DICOM sucio.

**Flujo:**
```
DICOM sucio identificado → Explicar situación sin alarmar
                        → Ofrecer recursos de regularización
                        → Seguir progresivamente
                        → Re-evaluar tras regularización
```

**Mensaje típico:**
```
"Entiendo que tu situación crediticia puede mejorar. Te recomiendo
regularizar tu DICOM lo antes posible — es más sencillo de lo que
parece. Aquí tienes algunos pasos: [recursos]. Cuando estés
listo(a), podemos continuar explorando opciones."
```

### 5. Win-Back Attempt (perdido)

**Trigger:** Lead alcanzó etapa `perdido`.

**Timing:** 30 días después de marcado como perdido.

**Objetivo:**Evaluar si las condiciones cambiaron.

**Mensaje típico:**
```
"Hola {nombre}, ¿cómo has estado? Hace un tiempo conversamos sobre
propiedades pero tuviste que pausar la búsqueda. ¿Ha cambiado algo?
Estoy aquí si quieres retomar. Esta vez tengo nuevas opciones que
pueden interesarte."
```

---

## Handoffs

### Handoffs Entrantes (incoming)

| Desde agente | Trigger | Razón |
|--------------|---------|-------|
| `QualifierAgent` | `dicom_dirty_high_debt` | Lead necesita seguimiento para normalizar DICOM |
| `QualifierAgent` | `re_engage_request` | Lead wants to restart qualification after inactivity |
| `SchedulerAgent` | `appointment_confirmed` | Post-confirmación de visita |
| `SchedulerAgent` | `appointment_completed` | Seguimiento post-visita |
| `PropertyAgent` | `not_interested` | Lead no está interesado en las propiedades vistas |
| `AgentSupervisor` | `stage_match` | Lead llegó a etapa manejada por follow_up |

### Handoffs Salientes (outgoing)

| Hacia agente | Trigger | Condición |
|--------------|---------|-----------|
| `QualifierAgent` | `restart_qualification` | Lead quiere重新资格认证 |
| `SchedulerAgent` | `schedule_visit` | Lead quiere agendar otra visita |
| `PropertyAgent` | `property_search` | Lead retomar búsqueda de propiedades |
| `AgentSupervisor` | `close_deal` | Lead indica intención de compra |
| `AgentSupervisor` | `lost_forever` | Lead explícitamente menolak todo |

### Mecanismo de Handoff

Los handoffs se realizan mediante **tool calling** (patrón Phase 3.1):

```python
# Herramientas de handoff definidas en FollowUpAgent
_HANDOFF_TOOLS = [
    LLMToolDefinition(
        name="handoff_to_qualifier",
        description="Transfer lead to QualifierAgent for re-qualification",
        parameters={"type": "object", "properties": {"reason": {"type": "string"}}}
    ),
    LLMToolDefinition(
        name="handoff_to_scheduler",
        description="Transfer lead to SchedulerAgent to schedule a visit",
        parameters={"type": "object", "properties": {"reason": {"type": "string"}}}
    ),
    LLMToolDefinition(
        name="close_lead",
        description="Mark lead as won or lost",
        parameters={"type": "object", "properties": {
            "outcome": {"type": "string", "enum": ["ganado", "perdido"]},
            "reason": {"type": "string"}
        }}
    ),
]
```

El agente invoking la herramienta apropiada → `tool_executor` captura el intent → `AgentSupervisor` procesa el `HandoffSignal`.

---

## Estados de Conversación

El FollowUpAgent maneja los siguientes estados de conversación:

| Estado | Descripción | Transiciones |
|--------|-------------|---------------|
| `post_appointment` | Lead tuvo visita programada | → `follow_up_active`, `lost` |
| `inactivity_reminder` | Envío de recordatorio de inactividad | → `follow_up_active`, `waiting_response`, `lost` |
| `referral_request` | Solicitud de referidos | → `referral_pending`, `lost` |
| `dicom_follow_up` | Seguimiento por situación DICOM | → `dicom_resolved`, `waiting_response`, `lost` |
| `win_back_attempt` |Intento de recuperar lead perdido | → `re_engaged`, `lost` |
| `waiting_response` | Esperando respuesta del lead | → `follow_up_active`, `inactivity_reminder`, `lost` |

### Flujo de Estados

```
                    ┌─────────────────┐
                    │   AGENDADO      │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
     post_appointment  inactivity    dicom_follow_up
              │              │              │
              └──────────────┴──────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   SEGUIMIENTO   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
         referral_request   win_back   waiting_response
              │              │              │
              └──────────────┴──────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
           REFERIDOS      GANADO        PERDIDO
```

---

## Integración con Celery Tasks

### task: check_trigger_campaigns

**Archivo:** `app/tasks/campaign_executor.py`
**Frecuencia:** Cada hora

```python
@celery_app.task(bind=True, base=DLQTask)
def check_trigger_campaigns(self):
    """
    Verifica cada hora si hay campañas activas con triggers activados.
    Trigger principales:
    - INACTIVITY: days_since_last_contact > threshold
    - STAGE_CHANGE: lead cambió de etapa
    - CAMPAIGN_STEP: paso configurado de campaña
    """
    campaigns = get_active_campaigns()
    for campaign in campaigns:
        triggered_leads = evaluate_campaign_triggers(campaign)
        for lead in triggered_leads:
            execute_campaign_step(lead, campaign)
```

### Campaign Step Actions

| Acción | Descripción | Servicio utilizado |
|--------|-------------|-------------------|
| `send_message` | Envío de mensaje Telegram/WhatsApp | `ChatService` via provider |
| `make_call` | Llamada de voz automática | `VoiceCallService` (VAPI) |
| `schedule_meeting` | Programar reunión en Google Calendar | `AppointmentService` |
| `update_stage` | Cambiar etapa del lead | `LeadService` |
| `assign_agent` | Reasignar lead a agente | `BrokerService` |

### Configuration por Campaña

```python
# En broker configuration, example campaign:
{
    "name": "Inactividad 3 días",
    "trigger": "inactivity",
    "threshold_days": 3,
    "conditions": {
        "stages": ["agendado", "seguimiento"],
        "exclude_tags": ["no_contactar"]
    },
    "steps": [
        {"action": "send_message", "template": "inactive_reminder_1"},
        {"action": "wait", "days": 2},
        {"action": "send_message", "template": "inactive_reminder_2"},
        {"action": "wait", "days": 3},
        {"action": "make_call", "voicemail_message": "recordatorio_inactivo"},
        {"action": "update_stage", "stage": "perdido", "condition": "no_response"}
    ]
}
```

---

## Message Templates

### Configuración por Broker

Los templates se configuran en `BrokerPromptConfig.follow_up_messages`:

```python
BrokerPromptConfig.follow_up_messages = {
    "no_response_24h": (
        "Hola {nombre}, espero que estés bien. Noté que no tuvimos "
        "respuesta. ¿Hay algo en lo que pueda ayudarte? Estoy a solo "
        "un mensaje de distancia."
    ),
    "post_appointment": (
        "¡Hola {nombre}! Espero que tu visita a {propiedad} haya ido "
        "excelente. Me encantaría saber tu opinión. ¿Qué te pareció "
        "la propiedad? ¿Tienes alguna duda que pueda resolver?"
    ),
    "post_appointment_no_show": (
        "Hola {nombre}, veo que no pudimos confirmar tu visita a "
        "{propiedad}. ¿Sucedió algo? Me gustaría reprogramar si "
        "aún estás interesado. ¡Estoy aquí para ayudarte!"
    ),
    "inactive_reminder_soft": (
        "Hola {nombre}, ¿cómo va tu búsqueda de propiedad? "
        "Quiero asegurarme de que estoy siendo útil. Si necesitas "
        "algo, aquí estoy."
    ),
    "inactive_reminder_urgent": (
        "Hola {nombre}, hemos notado que no hemos tenido noticias "
        "tuyas. Entiendo que la vida puede ponerse agitada. Solo "
        "quiero recordarte que tengo propiedades que podrían "
        "interesarte. ¿ seguimos en contacto?"
    ),
    "referral_request": (
        "¡Hola {nombre}! Me alegra mucho que hayas encontrado "
        "tu nuevo hogar. ¿Conoces a alguien que también esté "
        "buscando propiedad? Tu recomendación significa mucho "
        "para nosotros. Por cada referido que se convierte en "
        "cliente, te entregamos un detalle de agradecimiento."
    ),
    "dicom_follow_up": (
        "Entiendo que tu situación crediticia puede mejorar. "
        "Te recomiendo regularizar tu DICOM lo antes posible. "
        "Es más sencillo de lo que parece. Aquí tienes algunos "
        "recursos: [link]. Cuando estés listo(a), podemos "
        "continuar explorando opciones."
    ),
    "win_back_attempt": (
        "Hola {nombre}, ¿cómo has estado? Hace un tiempo "
        "conversamos sobre propiedades pero tuviste que pausar "
        "la búsqueda. ¿Ha cambiado algo? Estoy aquí si quieres "
        "retomar. Esta vez tengo nuevas opciones que pueden "
        "interesarte."
    ),
    "last_chance": (
        "{nombre}, esta será mi última conexión por un tiempo. "
        "Si aún estás interesado en buscar propiedad, por favor "
        "contáctame. De lo contrario, te deseo lo mejor en tu "
        "búsqueda."
    )
}
```

### Personalización de Variables

| Variable | Fuente | Ejemplo |
|----------|--------|---------|
| `{nombre}` | `lead.first_name` | "Juan" |
| `{propiedad}` | `appointment.property_address` | "Av. Providencia 1234, Depto 501" |
| `{hora}` | `appointment.scheduled_at` | "15:30" |
| `{agente_nombre}` | `agent.full_name` | "Sofía" |
| `{broker_nombre}` | `broker.name` | "Inmobiliaria ABC" |

---

## Flags de Configuración

| Flag | Tipo | Default | Descripción |
|------|------|---------|-------------|
| `FOLLOW_UP_ENABLED` | bool | `true` | Habilitar/deshabilitar seguimiento automático |
| `INACTIVITY_THRESHOLD_DAYS` | int | `3` | Días antes de activar seguimiento por inactividad |
| `POST_APPOINTMENT_DELAY_HOURS` | int | `24` | Horas a esperar antes de hacer post-appointment |
| `MAX_FOLLOW_UP_MESSAGES` | int | `5` | Máximo de mensajes de seguimiento antes de marcar perdido |
| `WIN_BACK_ENABLED` | bool | `true` | Habilitar intentos de win-back |
| `WIN_BACK_DELAY_DAYS` | int | `30` | Días antes de intentar win-back después de perdido |

---

## Métricas y KPIs

El FollowUpAgent reporta las siguientes métricas:

| Métrica | Descripción | Meta |
|---------|-------------|------|
| `follow_up_response_rate` | % de leads que responden a seguimiento | > 40% |
| `re_activation_rate` | % de leads inactivos re-enganchados | > 20% |
| `referral_capture_rate` | % de leadsganados que dan referidos | > 15% |
| `dicom_resolution_rate` | % de leads con DICOM sucio que regularizan | > 30% |
| `win_back_rate` | % de leads perdidos que se recuperan | > 10% |

---

## Dependencias

```
FollowUpAgent
├── LLMServiceFacade (para generación de respuestas)
├── LeadService (actualización de estado)
├── ChatService (envío de mensajes)
├── CampaignExecutor (celery task)
├── BrokerPromptConfig (templates)
└── AgentSupervisor (coordinación de handoffs)
```

---

## Changelog

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 1.0 | 2026-04-17 | Versión inicial del documento. Definición completa de propósito, tipos de seguimiento, handoffs, templates y integración con Celery. |