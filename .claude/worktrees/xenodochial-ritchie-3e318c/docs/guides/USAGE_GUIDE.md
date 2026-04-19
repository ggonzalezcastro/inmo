# Guía de Uso: Sistema de Campañas + Pipeline + Llamadas IA

**Fecha**: 2025-01-27

---

## 🚀 Inicio Rápido

### 1. Aplicar Migración

Primero, ejecuta la migración para crear todas las tablas nuevas:

```bash
cd backend
alembic upgrade head
```

Esto creará:
- Tablas de campañas (campaigns, campaign_steps, campaign_logs)
- Tablas de plantillas (message_templates)
- Tablas de llamadas (voice_calls, call_transcripts)
- Tabla de auditoría (audit_logs)
- Campos nuevos en tabla leads (pipeline_stage, etc.)

### 2. Configurar Variables de Entorno

Agrega a tu `.env`:

```env
# Voice Provider (opcional - solo si usas llamadas)
VOICE_PROVIDER=twilio
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890
WEBHOOK_BASE_URL=https://your-domain.com
```

### 3. Reiniciar Servicios

```bash
# Reiniciar backend (para cargar nuevos modelos)
# Reiniciar Celery worker
# Reiniciar Celery beat
```

---

## 📋 Uso de Campañas

### Crear una Campaña

```bash
POST /api/v1/campaigns
{
  "name": "Bienvenida Leads Nuevos",
  "description": "Campaña para leads que acaban de entrar",
  "channel": "telegram",
  "triggered_by": "stage_change",
  "trigger_condition": {
    "stage": "entrada"
  }
}
```

### Agregar Pasos a la Campaña

```bash
POST /api/v1/campaigns/{campaign_id}/steps
{
  "step_number": 1,
  "action": "send_message",
  "message_template_id": 1,
  "delay_hours": 0
}

POST /api/v1/campaigns/{campaign_id}/steps
{
  "step_number": 2,
  "action": "update_stage",
  "target_stage": "perfilamiento",
  "delay_hours": 24
}
```

### Activar Campaña

```bash
PUT /api/v1/campaigns/{campaign_id}
{
  "status": "active"
}
```

La campaña se ejecutará automáticamente cada hora para leads que cumplan las condiciones.

---

## 🎯 Uso del Pipeline

### Mover Lead a Etapa

```bash
POST /api/v1/pipeline/leads/{lead_id}/move-stage
{
  "new_stage": "perfilamiento",
  "reason": "Lead respondió inicial"
}
```

### Auto-Avanzar Etapa

```bash
POST /api/v1/pipeline/leads/{lead_id}/auto-advance
```

Esto verificará condiciones y avanzará automáticamente si se cumplen.

### Obtener Leads por Etapa

```bash
GET /api/v1/pipeline/stages/perfilamiento/leads?skip=0&limit=50
```

### Ver Métricas del Pipeline

```bash
GET /api/v1/pipeline/metrics
```

---

## 📝 Uso de Plantillas

### Crear Plantilla

```bash
POST /api/v1/templates
{
  "name": "Bienvenida Perfilador",
  "channel": "telegram",
  "content": "Hola {{name}}, gracias por tu interés. ¿Podrías contarme un poco sobre qué tipo de propiedad buscas?",
  "agent_type": "perfilador",
  "variables": ["name"]
}
```

Las variables se extraen automáticamente si no las especificas.

### Renderizar Plantilla (internamente)

El sistema renderiza automáticamente las plantillas cuando se usan en campañas, reemplazando variables con datos del lead.

---

## ☎️ Uso de Llamadas

### Iniciar Llamada

```bash
POST /api/v1/calls/initiate
{
  "lead_id": 1,
  "campaign_id": 1,
  "agent_type": "perfilador"
}
```

### Ver Historial de Llamadas

```bash
GET /api/v1/calls/leads/{lead_id}
```

### Ver Detalles de Llamada

```bash
GET /api/v1/calls/{call_id}
```

Incluye transcripción completa y resumen generado por IA.

---

## 🔄 Flujo Completo de Ejemplo

### 1. Lead Entra al Sistema

- Lead se crea con `pipeline_stage = "entrada"`

### 2. Campaña se Dispara Automáticamente

- Sistema detecta lead en etapa "entrada"
- Campaña "Bienvenida" se aplica automáticamente
- Paso 1: Envía mensaje de bienvenida
- Paso 2: Mueve lead a "perfilamiento"

### 3. Lead Responde

- Chat procesa mensaje
- Extrae información (presupuesto, ubicación)
- Auto-avanza a "calificacion_financiera" si tiene toda la info

### 4. Llamada Automática

- Campaña de "calificacion_financiera" inicia llamada
- IA conversa con el cliente
- Extrae información financiera
- Genera resumen automático
- Avanza a "agendado" si es aprobado

### 5. Cita Agendada

- Cliente confirma horario en chat
- Sistema crea cita con Google Meet
- Lead avanza a "agendado"

### 6. Seguimiento Post-Reunión

- Después de reunión, lead avanza a "seguimiento"
- Campaña de seguimiento envía mensajes de seguimiento
- Eventualmente avanza a "ganado" o "perdido"

---

## 📊 Monitoreo

### Ver Estadísticas de Campaña

```bash
GET /api/v1/campaigns/{campaign_id}/stats
```

Retorna:
- Total de pasos ejecutados
- Leads únicos contactados
- Tasa de éxito/fallo

### Ver Logs de Campaña

```bash
GET /api/v1/campaigns/{campaign_id}/logs?lead_id=1
```

### Ver Leads Inactivos

```bash
GET /api/v1/pipeline/stages/perfilamiento/inactive?inactivity_days=7
```

---

## 🔧 Configuración Avanzada

### Triggers de Campaña

**Por Score**:
```json
{
  "triggered_by": "lead_score",
  "trigger_condition": {
    "score_min": 20,
    "score_max": 50
  }
}
```

**Por Etapa**:
```json
{
  "triggered_by": "stage_change",
  "trigger_condition": {
    "stage": "perfilamiento"
  }
}
```

**Por Inactividad**:
```json
{
  "triggered_by": "inactivity",
  "trigger_condition": {
    "inactivity_days": 30
  }
}
```

---

## ✅ Checklist de Configuración

- [ ] Migración aplicada
- [ ] Variables de entorno configuradas
- [ ] Celery worker corriendo
- [ ] Celery beat corriendo
- [ ] Twilio configurado (si usas llamadas)
- [ ] Campañas de ejemplo creadas
- [ ] Plantillas creadas

---

**El sistema está completo y listo para usar!** 🚀



