# ⚡ Quick Reference: Frontend-Backend Integration

**Versión**: 1.0  
**Fecha**: 2025-01-27

---

## 🎯 Cambios Principales en Lead

El modelo `Lead` ahora tiene estos campos nuevos que el frontend debe manejar:

```typescript
interface Lead {
  // ... campos existentes ...
  
  pipeline_stage: "entrada" | "perfilamiento" | "calificacion_financiera" | 
                  "agendado" | "seguimiento" | "referidos" | "ganado" | "perdido" | null;
  
  stage_entered_at: string | null; // ISO datetime
  
  campaign_history: Array<{
    campaign_id: number;
    applied_at: string;
    trigger: string;
    stage?: string;
  }>;
  
  assigned_to: number | null;
  treatment_type: "automated_telegram" | "automated_call" | "manual_follow_up" | "hold" | null;
  next_action_at: string | null;
  notes: string | null;
}
```

---

## 📍 Endpoints Nuevos

### Pipeline
- `GET /api/v1/pipeline/stages/{stage}/leads` - Leads por etapa
- `POST /api/v1/pipeline/leads/{id}/move-stage` - Mover lead
- `POST /api/v1/pipeline/leads/{id}/auto-advance` - Auto-avanzar
- `GET /api/v1/pipeline/metrics` - Métricas del pipeline
- `GET /api/v1/pipeline/stages/{stage}/inactive` - Leads inactivos

### Campaigns
- `GET /api/v1/campaigns` - Listar campañas
- `POST /api/v1/campaigns` - Crear campaña
- `GET /api/v1/campaigns/{id}` - Obtener campaña (incluye steps)
- `PUT /api/v1/campaigns/{id}` - Actualizar campaña
- `DELETE /api/v1/campaigns/{id}` - Eliminar campaña
- `POST /api/v1/campaigns/{id}/steps` - Agregar paso
- `DELETE /api/v1/campaigns/{id}/steps/{step_id}` - Eliminar paso
- `POST /api/v1/campaigns/{id}/apply-to-lead/{lead_id}` - Aplicar a lead
- `GET /api/v1/campaigns/{id}/stats` - Estadísticas
- `GET /api/v1/campaigns/{id}/logs` - Logs de ejecución

### Templates
- `GET /api/v1/templates` - Listar plantillas
- `POST /api/v1/templates` - Crear plantilla
- `GET /api/v1/templates/{id}` - Obtener plantilla
- `PUT /api/v1/templates/{id}` - Actualizar plantilla
- `DELETE /api/v1/templates/{id}` - Eliminar plantilla
- `GET /api/v1/templates/agent-type/{type}` - Por tipo de agente

### Voice Calls
- `POST /api/v1/calls/initiate` - Iniciar llamada
- `GET /api/v1/calls/leads/{lead_id}` - Historial de llamadas
- `GET /api/v1/calls/{call_id}` - Detalles de llamada (con transcript)

---

## ⚠️ Puntos Críticos

### 1. Campaign Steps NO están en la lista
Cuando haces `GET /api/v1/campaigns`, los `steps` NO están incluidos. Solo en `GET /api/v1/campaigns/{id}`.

**Solución**: Hacer request adicional para obtener steps cuando se necesite.

### 2. Pipeline Stages - Valores exactos
Los valores deben ser exactamente estos (case-sensitive):
```
"entrada", "perfilamiento", "calificacion_financiera", "agendado", 
"seguimiento", "referidos", "ganado", "perdido"
```

### 3. Campaign History es un Array JSON
El campo `campaign_history` en Lead es un array que se actualiza automáticamente cuando se aplica una campaña.

### 4. Auto-advance es automático
El backend avanza automáticamente las etapas cuando se cumplen condiciones. El frontend debe refrescar después de acciones.

---

## 🔄 Flujo de Pipeline Board

```typescript
// 1. Cargar leads por etapa
const leads = await api.get(`/api/v1/pipeline/stages/${stage}/leads`);

// 2. Mover lead (drag-and-drop)
await api.post(`/api/v1/pipeline/leads/${leadId}/move-stage`, {
  new_stage: newStage,
  reason: "Moved via drag-and-drop"
});

// 3. Verificar auto-advance (opcional)
await api.post(`/api/v1/pipeline/leads/${leadId}/auto-advance`);
```

---

## 📊 Estructuras de Respuesta Clave

### Campaign Response
```typescript
{
  id: number;
  name: string;
  channel: "telegram" | "call" | "whatsapp" | "email";
  status: "draft" | "active" | "paused" | "completed";
  triggered_by: "manual" | "lead_score" | "stage_change" | "inactivity";
  trigger_condition: Record<string, any>;
  steps?: CampaignStep[]; // Solo en GET /{id}
}
```

### Campaign Stats
```typescript
{
  total_steps: number;
  unique_leads: number;
  success_rate: number; // 0-100
  failure_rate: number; // 0-100
}
```

### Pipeline Metrics
```typescript
{
  total_leads: number;
  stage_counts: Record<string, number>;
  stage_avg_days: Record<string, number>;
}
```

---

## 🎨 Template Variables

Variables disponibles para usar en templates:
- `{{name}}` - Nombre del lead
- `{{phone}}` - Teléfono
- `{{email}}` - Email
- `{{budget}}` - Presupuesto
- `{{location}}` - Ubicación
- `{{timeline}}` - Timeline
- `{{score}}` - Lead score
- `{{stage}}` - Pipeline stage

---

## ✅ Checklist Rápido

- [ ] Actualizar tipo `Lead` con campos de pipeline
- [ ] Mapear 8 etapas a columnas Kanban
- [ ] Agregar endpoints de pipeline al API client
- [ ] Agregar endpoints de campaigns al API client
- [ ] Agregar endpoints de templates al API client
- [ ] Agregar endpoints de voice calls al API client
- [ ] Manejar `campaign_history` en lead detail
- [ ] Mostrar `pipeline_stage` en lead cards
- [ ] Implementar drag-and-drop con move-stage endpoint
- [ ] Mostrar estadísticas de campañas
- [ ] Auto-completar variables en template editor

---

**Ver guía completa**: `FRONTEND_INTEGRATION_GUIDE.md`



