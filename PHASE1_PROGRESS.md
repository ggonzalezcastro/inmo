# Phase 1 Progress: Database Models & Campaigns

**Fecha**: 2025-01-27  
**Estado**: ✅ Modelos Creados - Pendiente Migración

---

## ✅ Tareas Completadas

### B1.1: Campaign Models ✅

**Archivos creados**: `backend/app/models/campaign.py`

**Modelos implementados**:

1. **`Campaign`** - Modelo principal de campaña
   - ✅ Todos los campos requeridos (name, description, channel, status, etc.)
   - ✅ Triggers configurables (manual, lead_score, stage_change, inactivity)
   - ✅ Condiciones de trigger en JSON
   - ✅ Multi-tenancy con broker_id
   - ✅ Relaciones con steps y logs

2. **`CampaignStep`** - Pasos de campaña
   - ✅ Orden secuencial (step_number)
   - ✅ Acciones soportadas (send_message, make_call, schedule_meeting, update_stage)
   - ✅ Delays configurables (delay_hours)
   - ✅ Condiciones de ejecución en JSON
   - ✅ Relación con MessageTemplate

3. **`CampaignLog`** - Log de ejecución
   - ✅ Rastro completo de ejecución
   - ✅ Estados (pending, sent, failed, skipped)
   - ✅ Respuestas/results en JSON
   - ✅ Timestamps de creación y ejecución

**Enums creados**:
- `CampaignChannel`: telegram, call, whatsapp, email
- `CampaignStatus`: draft, active, paused, completed
- `CampaignTrigger`: manual, lead_score, stage_change, inactivity
- `CampaignStepAction`: send_message, make_call, schedule_meeting, update_stage
- `CampaignLogStatus`: pending, sent, failed, skipped

---

### B1.2: Message Template Models ✅

**Archivos creados**: `backend/app/models/template.py`

**Modelos implementados**:

1. **`MessageTemplate`** - Plantillas de mensajes
   - ✅ Contenido con variables ({{name}}, {{budget}}, etc.)
   - ✅ Soporte para múltiples canales
   - ✅ Asociación con tipo de agente (perfilador, calificador_financiero, agendador, seguimiento)
   - ✅ Lista de variables extraídas
   - ✅ Multi-tenancy con broker_id

**Enums creados**:
- `TemplateChannel`: telegram, call, email, whatsapp
- `AgentType`: perfilador, calificador_financiero, agendador, seguimiento

---

### B1.3: Voice Call Models ✅

**Archivos creados**: `backend/app/models/voice_call.py`

**Modelos implementados**:

1. **`VoiceCall`** - Registro de llamadas
   - ✅ Información de llamada (phone_number, external_call_id)
   - ✅ Estados completos (initiated, ringing, answered, completed, failed, etc.)
   - ✅ Duración de llamada
   - ✅ URLs de grabación
   - ✅ Transcripción y resumen generado por IA
   - ✅ Cambios de etapa y score después de la llamada
   - ✅ Timestamps (started_at, completed_at)
   - ✅ Multi-tenancy con broker_id

2. **`CallTranscript`** - Líneas de transcripción
   - ✅ Identificación de speaker (bot, customer)
   - ✅ Texto de transcripción
   - ✅ Timestamp en la llamada (segundos)
   - ✅ Nivel de confianza (STT confidence)

**Enums creados**:
- `CallStatus`: initiated, ringing, answered, completed, failed, no_answer, busy, cancelled
- `SpeakerType`: bot, customer

---

### B1.4: Lead Model Updates ✅

**Archivos modificados**: `backend/app/models/lead.py`

**Campos agregados al modelo Lead**:

1. ✅ **`pipeline_stage`** (String)
   - Estados: "entrada", "perfilamiento", "calificacion_financiera", "agendado", "seguimiento", "referidos", "ganado", "perdido"
   - Indexado para búsquedas rápidas

2. ✅ **`stage_entered_at`** (DateTime)
   - Timestamp de cuándo entró a la etapa actual
   - Permite calcular tiempo en etapa

3. ✅ **`campaign_history`** (JSON)
   - Array de campañas aplicadas: `[{"campaign_id": 1, "applied_at": "...", "steps_completed": 2}]`
   - Evita aplicar campañas duplicadas

4. ✅ **`assigned_to`** (FK to User)
   - Agente asignado para seguimiento manual
   - Nullable (puede no estar asignado)

5. ✅ **`treatment_type`** (Enum)
   - Tipos: automated_telegram, automated_call, manual_follow_up, hold
   - Define cómo tratar al lead

6. ✅ **`next_action_at`** (DateTime)
   - Próxima acción programada
   - Útil para scheduling de campañas

7. ✅ **`notes`** (Text)
   - Notas internas de agentes

**Enum creado**:
- `TreatmentType`: automated_telegram, automated_call, manual_follow_up, hold

**Relaciones agregadas**:
- ✅ `campaign_logs` → CampaignLog
- ✅ `voice_calls` → VoiceCall
- ✅ `assigned_agent` → User

**Índices agregados**:
- ✅ `idx_pipeline_stage` (pipeline_stage, stage_entered_at)
- ✅ `idx_assigned_treatment` (assigned_to, treatment_type)
- ✅ `idx_next_action` (next_action_at, treatment_type)

---

## 📋 Archivos Creados/Modificados

### Nuevos Archivos:
1. ✅ `backend/app/models/campaign.py` - Modelos de campaña
2. ✅ `backend/app/models/template.py` - Modelos de plantillas
3. ✅ `backend/app/models/voice_call.py` - Modelos de llamadas

### Archivos Modificados:
1. ✅ `backend/app/models/lead.py` - Campos de pipeline agregados
2. ✅ `backend/app/models/__init__.py` - Exports actualizados

---

## ⏭️ Próximos Pasos

### Pendiente:

1. **Migración de Base de Datos** 🚨
   - Crear migración Alembic para todas las tablas nuevas
   - Agregar enums a PostgreSQL
   - Crear índices
   - Agregar campos al modelo Lead

2. **Phase 2: Campaign Management Services**
   - Crear `campaign_service.py`
   - Crear `template_service.py`
   - Crear `pipeline_service.py`

---

## 🔍 Validaciones Realizadas

- ✅ Todos los modelos compilan sin errores
- ✅ Todos los imports funcionan correctamente
- ✅ Relaciones entre modelos configuradas
- ✅ Enums definidos correctamente
- ✅ Índices configurados para rendimiento
- ✅ Multi-tenancy implementado (broker_id en todos los modelos relevantes)

---

## 📝 Notas Técnicas

### Estructura de Datos:

1. **Campaign → CampaignStep**: Relación one-to-many con orden
2. **Campaign → CampaignLog**: Relación one-to-many para auditoría
3. **CampaignStep → MessageTemplate**: Relación opcional (solo si action = send_message)
4. **Lead → CampaignLog**: Rastrea qué campañas se aplicaron
5. **Lead → VoiceCall**: Historial de llamadas por lead
6. **VoiceCall → CallTranscript**: Transcripción detallada línea por línea

### JSON Fields:

- `Campaign.trigger_condition`: Condiciones de trigger flexibles
- `CampaignStep.conditions`: Condiciones de ejecución por paso
- `CampaignLog.response`: Respuestas/results de ejecución
- `Lead.campaign_history`: Historial de campañas aplicadas

### Multi-tenancy:

Todos los modelos que requieren aislamiento tienen `broker_id`:
- Campaign
- MessageTemplate
- VoiceCall
- Lead (ya existía implícitamente, pero ahora explícito en relaciones)

---

## ✅ Objetivos Logrados

- ✅ Estructura de datos que soporta campañas complejas con múltiples pasos
- ✅ Disparadores automáticos basados en condiciones (score range, stage change, inactivity)
- ✅ Rastreo de qué campañas se han aplicado a cada lead (audit trail)
- ✅ Base para medir eficacia de campañas (sent, success, failed rates)
- ✅ Sistema de plantillas flexible y reutilizable
- ✅ Historial completo de llamadas con transcripciones
- ✅ Pipeline de leads con 8 etapas definidas
- ✅ Sistema de asignación de leads a agentes

---

**Próxima fase**: Crear migración de base de datos y comenzar Phase 2 con los servicios de gestión.

