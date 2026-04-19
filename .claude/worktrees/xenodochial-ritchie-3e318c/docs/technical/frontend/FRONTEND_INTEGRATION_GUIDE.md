# 🔗 Guía de Integración Frontend-Backend

**Fecha**: 2025-01-27  
**Estado**: ✅ Backend completo - Listo para integración

---

## 📋 Índice

1. [Estructuras de Datos Clave](#estructuras-de-datos-clave)
2. [Endpoints Disponibles](#endpoints-disponibles)
3. [Campos Nuevos en Lead](#campos-nuevos-en-lead)
4. [Consideraciones Importantes](#consideraciones-importantes)
5. [Schemas Exactos](#schemas-exactos)
6. [Ejemplos de Uso](#ejemplos-de-uso)

---

## 🎯 Estructuras de Datos Clave

### Lead Model - Campos Agregados

El modelo `Lead` ahora incluye campos del pipeline que el frontend debe manejar:

```typescript
interface Lead {
  // ... campos existentes ...
  
  // NUEVOS CAMPOS DEL PIPELINE
  pipeline_stage: string | null;
  // Valores posibles: "entrada", "perfilamiento", "calificacion_financiera", 
  //                   "agendado", "seguimiento", "referidos", "ganado", "perdido"
  
  stage_entered_at: string | null; // ISO datetime
  
  campaign_history: Array<{
    campaign_id: number;
    applied_at: string; // ISO datetime
    trigger: string;
    stage?: string;
    steps_enqueued?: number;
  }>;
  
  assigned_to: number | null; // User ID
  
  treatment_type: "automated_telegram" | "automated_call" | "manual_follow_up" | "hold" | null;
  
  next_action_at: string | null; // ISO datetime
  
  notes: string | null;
}
```

---

## 📡 Endpoints Disponibles

### 1. Campaigns (`/api/v1/campaigns`)

#### GET `/api/v1/campaigns`
**Query params**: `status?`, `channel?`, `skip?`, `limit?`

**Response**:
```typescript
{
  data: Campaign[];
  total: number;
  skip: number;
  limit: number;
}
```

**Campaign Schema**:
```typescript
interface Campaign {
  id: number;
  name: string;
  description: string | null;
  channel: "telegram" | "call" | "whatsapp" | "email";
  status: "draft" | "active" | "paused" | "completed";
  triggered_by: "manual" | "lead_score" | "stage_change" | "inactivity";
  trigger_condition: {
    score_min?: number;
    score_max?: number;
    stage?: string;
    inactivity_days?: number;
  };
  max_contacts: number | null;
  broker_id: number;
  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime
  steps?: CampaignStep[]; // Incluido en GET /{id}
}
```

#### GET `/api/v1/campaigns/{campaign_id}`
**Response**: `Campaign` con `steps` incluidos

#### POST `/api/v1/campaigns`
**Body**: `CampaignCreate` (igual que Campaign pero sin `id`, `status`, `broker_id`, `created_at`, `updated_at`)

**Response**: `Campaign`

#### PUT `/api/v1/campaigns/{campaign_id}`
**Body**: `CampaignUpdate` (todos los campos opcionales)

#### DELETE `/api/v1/campaigns/{campaign_id}`
**Response**: `204 No Content`

#### POST `/api/v1/campaigns/{campaign_id}/steps`
**Body**:
```typescript
{
  step_number: number; // >= 1
  action: "send_message" | "make_call" | "schedule_meeting" | "update_stage";
  delay_hours: number; // >= 0
  message_template_id?: number;
  conditions?: Record<string, any>;
  target_stage?: string;
}
```

**Response**: `CampaignStep`

#### DELETE `/api/v1/campaigns/{campaign_id}/steps/{step_id}`
**Response**: `204 No Content`

#### POST `/api/v1/campaigns/{campaign_id}/apply-to-lead/{lead_id}`
**Response**:
```typescript
{
  message: string;
  steps_enqueued: number;
  logs: CampaignLog[];
}
```

#### GET `/api/v1/campaigns/{campaign_id}/stats`
**Response**:
```typescript
{
  campaign_id: number;
  total_steps: number;
  unique_leads: number;
  pending: number;
  sent: number;
  failed: number;
  skipped: number;
  success_rate: number; // 0-100
  failure_rate: number; // 0-100
}
```

#### GET `/api/v1/campaigns/{campaign_id}/logs`
**Query params**: `lead_id?`, `skip?`, `limit?`

**Response**:
```typescript
{
  data: CampaignLog[];
  total: number;
  skip: number;
  limit: number;
}
```

**CampaignLog Schema**:
```typescript
interface CampaignLog {
  id: number;
  campaign_id: number;
  lead_id: number;
  step_number: number;
  status: "pending" | "sent" | "failed" | "skipped";
  response: Record<string, any> | null;
  created_at: string; // ISO datetime
  executed_at: string | null; // ISO datetime
}
```

**CampaignStep Schema**:
```typescript
interface CampaignStep {
  id: number;
  campaign_id: number;
  step_number: number;
  action: "send_message" | "make_call" | "schedule_meeting" | "update_stage";
  delay_hours: number;
  message_template_id: number | null;
  conditions: Record<string, any>;
  target_stage: string | null;
  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime
}
```

---

### 2. Pipeline (`/api/v1/pipeline`)

#### POST `/api/v1/pipeline/leads/{lead_id}/move-stage`
**Body**:
```typescript
{
  new_stage: string; // "entrada" | "perfilamiento" | ... | "ganado" | "perdido"
  reason?: string;
}
```

**Response**:
```typescript
{
  message: string;
  lead_id: number;
  old_stage: string | null;
  new_stage: string;
  stage_entered_at: string; // ISO datetime
}
```

#### POST `/api/v1/pipeline/leads/{lead_id}/auto-advance`
**Response**:
```typescript
{
  message: string;
  lead_id: number;
  new_stage?: string;
  stage_entered_at?: string; // ISO datetime
}
```

#### GET `/api/v1/pipeline/stages/{stage}/leads`
**Query params**: `treatment_type?`, `skip?`, `limit?`

**Response**:
```typescript
{
  stage: string;
  data: Lead[];
  total: number;
  skip: number;
  limit: number;
}
```

#### GET `/api/v1/pipeline/metrics`
**Response**:
```typescript
{
  total_leads: number;
  stage_counts: {
    entrada: number;
    perfilamiento: number;
    calificacion_financiera: number;
    agendado: number;
    seguimiento: number;
    referidos: number;
    ganado: number;
    perdido: number;
  };
  stage_avg_days: {
    entrada: number;
    perfilamiento: number;
    // ... etc
  };
  stages: {
    entrada: string;
    perfilamiento: string;
    // ... etc (descripciones)
  };
}
```

#### GET `/api/v1/pipeline/stages/{stage}/inactive`
**Query params**: `inactivity_days?` (default: 7)

**Response**:
```typescript
{
  stage: string;
  inactivity_days: number;
  count: number;
  leads: Lead[];
}
```

---

### 3. Templates (`/api/v1/templates`)

#### GET `/api/v1/templates`
**Query params**: `channel?`, `agent_type?`

**Response**:
```typescript
{
  data: Template[];
}
```

**Template Schema**:
```typescript
interface Template {
  id: number;
  name: string;
  channel: "telegram" | "call" | "email" | "whatsapp";
  content: string; // Puede contener {{variable}} placeholders
  agent_type: "perfilador" | "calificador_financiero" | "agendador" | "seguimiento" | null;
  variables: string[]; // Lista de variables extraídas del content
  broker_id: number;
  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime
}
```

#### GET `/api/v1/templates/{template_id}`
**Response**: `Template`

#### POST `/api/v1/templates`
**Body**: `TemplateCreate` (igual que Template pero sin `id`, `broker_id`, `created_at`, `updated_at`)

#### PUT `/api/v1/templates/{template_id}`
**Body**: `TemplateUpdate` (todos los campos opcionales)

#### DELETE `/api/v1/templates/{template_id}`
**Response**: `204 No Content`

#### GET `/api/v1/templates/agent-type/{agent_type}`
**Query params**: `channel?`

**Response**: `{ data: Template[] }`

---

### 4. Voice Calls (`/api/v1/calls`)

#### POST `/api/v1/calls/initiate`
**Body**:
```typescript
{
  lead_id: number;
  campaign_id?: number;
  agent_type?: string;
}
```

**Response**: `VoiceCall`

**VoiceCall Schema**:
```typescript
interface VoiceCall {
  id: number;
  lead_id: number;
  campaign_id: number | null;
  phone_number: string;
  external_call_id: string | null;
  status: "initiated" | "ringing" | "answered" | "completed" | "failed" | "no_answer" | "busy" | "cancelled";
  duration: number | null; // seconds
  recording_url: string | null;
  transcript: string | null;
  summary: string | null;
  stage_after_call: string | null;
  score_delta: number | null;
  started_at: string | null; // ISO datetime
  completed_at: string | null; // ISO datetime
  created_at: string; // ISO datetime
}
```

#### GET `/api/v1/calls/leads/{lead_id}`
**Response**:
```typescript
{
  data: VoiceCall[];
}
```

#### GET `/api/v1/calls/{call_id}`
**Response**:
```typescript
{
  call: VoiceCall;
  transcript_lines: Array<{
    speaker: "bot" | "customer";
    text: string;
    timestamp: number; // seconds into call
    confidence: number | null; // 0-1
  }>;
}
```

---

## ⚠️ Consideraciones Importantes

### 1. Pipeline Stages - Valores Válidos

El frontend debe validar que los valores de `pipeline_stage` sean exactamente:

```typescript
type PipelineStage = 
  | "entrada"
  | "perfilamiento"
  | "calificacion_financiera"
  | "agendado"
  | "seguimiento"
  | "referidos"
  | "ganado"
  | "perdido";
```

### 2. Campaign Responses - Steps No Incluidos por Defecto

**IMPORTANTE**: En `GET /api/v1/campaigns` (lista), los `steps` NO están incluidos. Solo se incluyen en `GET /api/v1/campaigns/{id}` (detalle).

El frontend debe:
- Hacer un request adicional para obtener steps cuando se visualiza una campaña individual
- O modificar el backend para incluir steps en la lista (si se necesita)

### 3. Auto-Advance Pipeline

El sistema hace auto-avance automáticamente cuando:
- Lead tiene toda la info básica → avanza a `calificacion_financiera`
- Hay una cita agendada → avanza a `agendado`
- La cita se completa → avanza a `seguimiento`

El frontend debe reflejar estos cambios con polling o WebSockets.

### 4. Campaign Triggers - Estructura de `trigger_condition`

```typescript
// Para triggered_by = "lead_score"
trigger_condition: {
  score_min: number;
  score_max: number;
}

// Para triggered_by = "stage_change"
trigger_condition: {
  stage: string;
}

// Para triggered_by = "inactivity"
trigger_condition: {
  inactivity_days: number;
}

// Para triggered_by = "manual"
trigger_condition: {}
```

### 5. Template Variables

Las variables se extraen automáticamente del `content`. Ejemplo:

```typescript
content: "Hola {{name}}, tu presupuesto es {{budget}}"
// variables: ["name", "budget"]
```

El frontend puede:
- Validar que todas las variables estén presentes en el lead
- Mostrar preview con datos reales del lead
- Auto-completar variables disponibles

### 6. Campaign History en Lead

El campo `campaign_history` es un array JSON que se actualiza automáticamente cuando se aplica una campaña. El frontend debe:

- Mostrar qué campañas se han aplicado al lead
- Mostrar cuándo se aplicaron
- Evitar aplicar la misma campaña dos veces (el backend ya lo previene)

---

## 🔄 Flujo de Datos Típico

### Pipeline Board (Kanban)

1. **Obtener leads por etapa**:
   ```
   GET /api/v1/pipeline/stages/{stage}/leads
   ```

2. **Mover lead a otra etapa** (drag-and-drop):
   ```
   POST /api/v1/pipeline/leads/{lead_id}/move-stage
   ```

3. **Verificar auto-avance**:
   ```
   POST /api/v1/pipeline/leads/{lead_id}/auto-advance
   ```

### Campaign Builder

1. **Crear campaña**:
   ```
   POST /api/v1/campaigns
   ```

2. **Agregar pasos**:
   ```
   POST /api/v1/campaigns/{id}/steps
   ```

3. **Activar campaña**:
   ```
   PUT /api/v1/campaigns/{id} { status: "active" }
   ```

### Template Manager

1. **Listar plantillas**:
   ```
   GET /api/v1/templates?channel=telegram
   ```

2. **Crear/editar plantilla**:
   ```
   POST /api/v1/templates
   PUT /api/v1/templates/{id}
   ```

3. **Preview con variables**:
   - El frontend puede renderizar las variables manualmente
   - O hacer un request a un endpoint de preview (no implementado, pero se puede agregar)

### Ticket Detail / Lead Detail

El lead ahora incluye:
- `pipeline_stage` - Para mostrar en qué etapa está
- `campaign_history` - Para mostrar campañas aplicadas
- `stage_entered_at` - Para mostrar tiempo en etapa

### Campaign Analytics

1. **Obtener estadísticas**:
   ```
   GET /api/v1/campaigns/{id}/stats
   ```

2. **Obtener logs**:
   ```
   GET /api/v1/campaigns/{id}/logs
   ```

### Call Widget

1. **Iniciar llamada**:
   ```
   POST /api/v1/calls/initiate
   ```

2. **Ver detalles**:
   ```
   GET /api/v1/calls/{call_id}
   ```

3. **Ver historial**:
   ```
   GET /api/v1/calls/leads/{lead_id}
   ```

---

## 🔧 Ajustes Recomendados para el Frontend

### 1. Actualizar Lead Interface

Asegúrate de que el tipo `Lead` incluya todos los nuevos campos del pipeline.

### 2. Pipeline Board - Etapas

El frontend debe mapear las 8 etapas a columnas del Kanban:

```typescript
const PIPELINE_STAGES = [
  "entrada",
  "perfilamiento",
  "calificacion_financiera",
  "agendado",
  "seguimiento",
  "referidos",
  "ganado",
  "perdido"
] as const;
```

### 3. Campaign Steps - Orden

Los steps tienen `step_number` y deben mostrarse en ese orden. El backend los retorna ordenados.

### 4. Real-time Updates

El backend no tiene WebSockets aún. El frontend debe usar:
- Polling (como ya tienes en `useRealtime`)
- O actualizar después de acciones del usuario

### 5. Template Variables - Auto-complete

El frontend puede:
- Mostrar lista de variables disponibles: `["name", "phone", "email", "budget", "location", "timeline", "score", "stage"]`
- Validar que todas las variables estén presentes antes de usar la plantilla

### 6. Campaign Status - Estados

El frontend debe manejar:
- `draft` - Borrador (no se ejecuta)
- `active` - Activa (se ejecuta automáticamente)
- `paused` - Pausada (no se ejecuta)
- `completed` - Completada (no se ejecuta)

---

## 📝 Ejemplos de Código

### Obtener Leads por Etapa (Pipeline Board)

```typescript
const fetchLeadsByStage = async (stage: string) => {
  const response = await api.get(`/api/v1/pipeline/stages/${stage}/leads`);
  return response.data.data; // Lead[]
};
```

### Mover Lead a Otra Etapa (Drag-and-Drop)

```typescript
const moveLeadToStage = async (leadId: number, newStage: string, reason?: string) => {
  const response = await api.post(`/api/v1/pipeline/leads/${leadId}/move-stage`, {
    new_stage: newStage,
    reason: reason
  });
  return response.data;
};
```

### Obtener Campaña con Steps

```typescript
const fetchCampaignWithSteps = async (campaignId: number) => {
  const campaign = await api.get(`/api/v1/campaigns/${campaignId}`);
  // campaign.data.steps está incluido
  return campaign.data;
};
```

### Crear Campaña con Steps

```typescript
const createCampaignWithSteps = async (campaignData: CampaignCreate, steps: CampaignStepCreate[]) => {
  // 1. Crear campaña
  const campaign = await api.post('/api/v1/campaigns', campaignData);
  
  // 2. Agregar steps uno por uno
  for (const step of steps) {
    await api.post(`/api/v1/campaigns/${campaign.data.id}/steps`, step);
  }
  
  return campaign.data;
};
```

### Obtener Métricas del Pipeline

```typescript
const fetchPipelineMetrics = async () => {
  const response = await api.get('/api/v1/pipeline/metrics');
  return response.data;
  // {
  //   total_leads: 100,
  //   stage_counts: { entrada: 20, perfilamiento: 15, ... },
  //   stage_avg_days: { entrada: 2.5, perfilamiento: 5.1, ... },
  //   stages: { entrada: "Lead inicial - recién recibido", ... }
  // }
};
```

---

## ✅ Checklist de Integración

- [ ] Actualizar tipo `Lead` con nuevos campos del pipeline
- [ ] Mapear 8 etapas del pipeline a columnas Kanban
- [ ] Integrar endpoints de campañas
- [ ] Integrar endpoints de pipeline
- [ ] Integrar endpoints de plantillas
- [ ] Integrar endpoints de llamadas
- [ ] Manejar `campaign_history` en lead detail
- [ ] Mostrar `pipeline_stage` en lead card
- [ ] Validar valores de `pipeline_stage`
- [ ] Manejar auto-avance de pipeline
- [ ] Mostrar estadísticas de campañas
- [ ] Mostrar logs de campañas
- [ ] Auto-completar variables en templates
- [ ] Renderizar preview de templates con datos reales

---

## 🚀 Próximos Pasos

1. **Probar endpoints** con Postman/Thunder Client
2. **Verificar schemas** - Comparar con tipos del frontend
3. **Ajustar tipos TypeScript** si hay diferencias
4. **Implementar polling** para actualizar pipeline en tiempo real
5. **Integrar con stores Zustand** existentes

---

**El backend está 100% listo. Solo necesitas conectar los endpoints!** 🎉



