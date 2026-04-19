# Pipeline de Estados del Lead — Arquitectura

**Fecha:** 17 de abril de 2026
**Versión:** 3.3
**Carpeta:** `docs/arquitectura/`

---

## 1. Resumen Ejecutivo

El sistema de pipeline de leads implementa **dos ejes independientes** que avanzan de forma separada:

| Eje | Descripción | Avanza cuando |
|-----|-------------|---------------|
| `pipeline_stage` | Posición comercial del lead | Criterios objetivos cumplidos (datos recopilados, cita confirmada, visita completada) |
| `conversation_state` | Estado conversacional del LLM | El LLM conversacional indica transición |

Esta separación permite que un lead esté en `agendado` (pipeline_stage) pero su conversación esté en `data_collection` (conversation_state), lo cual es válido y requiere intervención.

---

## 2. Diagrama ASCII del Pipeline Comercial

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           PIPELINE DE LEADS — INMO                                      │
└─────────────────────────────────────────────────────────────────────────────────────────┘

  ┌─────────┐    ┌────────────────┐    ┌────────────────────┐    ┌───────────┐
  │ entrada │───▶│ perfilamiento  │───▶│ calificacion_     │───▶│ agendado  │
  │         │    │                │    │ financiera         │    │           │
  └─────────┘    └────────────────┘    └────────────────────┘    └───────────┘
       │                │                        │                         │
       │                │                        │                         │
       ▼                ▼                        ▼                         ▼
  ┌─────────┐    ┌─────────────┐    ┌──────────┴─────────┐    ┌───────────┐
  │ perdido │    │   perdido    │    │ potencial           │    │ seguimiento│
  │ (dead)  │    │              │    │ (needs commercial   │    │           │
  └─────────┘    └─────────────┘    │   follow-up)         │    └───────────┘
                                    └──────────────────────┘           │
                                                                       │
                                                                       ▼
                                    ┌────────────────────────────────────┐
                                    │          referidos                 │
                                    │   (cliente referenciado)           │
                                    └────────────────────────────────────┘
                                                 │
                                                 ▼
                                    ┌────────────────────────────────────┐
                                    │           ganado                   │
                                    │    (cliente convertido)            │
                                    └────────────────────────────────────┘

                              ┌─────────────────────────────────────┐
                              │              perdido                 │
                              │        (lost from any stage)        │
                              └─────────────────────────────────────┘

NOTA: 「perdido」 es accesible desde CUALQUIER etapa excepto 「ganado」
```

---

## 3. Pipeline Stages — Definición Formal

### 3.1 Stage Definitions

```python
PIPELINE_STAGES = {
    "entrada": "Lead inicial - recién recibido",
    "perfilamiento": "Recopilando información del cliente",
    "calificacion_financiera": "Validando capacidad financiera",
    "potencial": "Lead con potencial - requiere seguimiento comercial",
    "agendado": "Cita agendada",
    "ganado": "Cliente convertido",
    "perdido": "Oportunidad perdida",
}
```

### 3.2 Stage Table

| Stage Key | Nombre Display | Descripción | Agente Asignado | Métrica Esperada |
|-----------|----------------|-------------|-----------------|------------------|
| `entrada` | Lead Inicial | Lead recién recibido, sin contacto aún | `QualifierAgent` | avg 0.5 días |
| `perfilamiento` | Perfilamiento | recopilando nombre, teléfono, ubicación, presupuesto | `QualifierAgent` | avg 1.2 días |
| `calificacion_financiera` | Calificación Financiera | validando capacidad económica del lead | `SchedulerAgent` | avg 2.1 días |
| `potencial` | Potencial | Lead con potencial pero requiere seguimiento comercial manual | `PropertyAgent` | avg 3.0 días |
| `agendado` | Cita Agendada | Cita programada (SCHEDULED o CONFIRMED) | `FollowUpAgent` | avg 5.0 días |
| `seguimiento` | Seguimiento | post-visita, esperando respuesta o decisión | `FollowUpAgent` | avg 4.0 días |
| `referidos` | Referidos | lead ha referido a otros prospectos | `FollowUpAgent` | avg 7.0 días |
| `ganado` | Ganado | cliente convertido exitosamente | `FollowUpAgent` | — terminal — |
| `perdido` | Perdido | oportunidad perdida (desde cualquier etapa) | `FollowUpAgent` | — terminal — |

### 3.3 Stage × Agent Mapping

```
┌─────────────────────────────┬───────────────────┐
│ Pipeline Stage              │ Agent Asignado    │
├─────────────────────────────┼───────────────────┤
│ entrada                     │ QualifierAgent    │
│ perfilamiento               │ QualifierAgent    │
│ potencial                   │ PropertyAgent     │
│ calificacion_financiera     │ SchedulerAgent    │
│ agendado                    │ FollowUpAgent     │
│ seguimiento                 │ FollowUpAgent     │
│ referidos                   │ FollowUpAgent     │
│ ganado                      │ FollowUpAgent     │
│ perdido                     │ FollowUpAgent     │
└─────────────────────────────┴───────────────────┘
```

---

## 4. Conversation States — Estados Conversacionales

Los estados conversacionales son controlados exclusivamente por el LLM conversacional. Son independientes del pipeline_stage.

### 4.1 Conversation States Table

| State Key | Nombre Display | Descripción | Se Permite en Stages |
|-----------|----------------|-------------|---------------------|
| `greeting` | Saludo | Primera interacción, presentación de SofIa | entrada, perfilamiento |
| `interest_check` | Verificación de Interés | Confirmar que el lead tiene intención real | entrada, perfilamiento |
| `data_collection` | Recopilación de Datos | Recolectar información de perfilamiento | perfilamiento, calificacion_financiera |
| `financial_qualification` | Calificación Financiera | Evaluar capacidad económica | calificacion_financiera |
| `scheduling` | Agendamiento | Gestionar la programación de visitas | agendado, seguimiento |
| `completed` | Completado | Conversación exitosa, lead convertido | ganado, referidos |
| `lost` | Perdido | Conversación terminada sin conversión | perdido |

### 4.2 Conversation State Machine Flow

```
  greeting ──▶ interest_check ──▶ data_collection ──▶ financial_qualification ──▶ scheduling ──▶ completed

       │              │                 │                      │                        │
       ▼              ▼                 ▼                      ▼                        ▼
     lost           lost              lost                   lost                     lost
```

---

## 5. LeadStatus Enum — Estados de Calidez

```python
class LeadStatus(str, Enum):
    COLD = "cold"        # Lead sin contacto exitoso
    WARM = "warm"        # Lead con contacto, interesa
    HOT = "hot"          # Lead altamente calificado (fast-track)
    CONVERTED = "converted"  # Lead ganado
    LOST = "lost"        # Lead perdido
```

| Status | Descripción | Fast-Track Eligible |
|--------|-------------|---------------------|
| `cold` | Sin contacto o sin respuesta | No |
| `warm` | Contacto establecido, interés moderado | No |
| `hot` | Altamente calificado, múltiples señales positivas | **SÍ** (bypass normal progression) |
| `converted` | Lead convertido a cliente | N/A |
| `lost` | Lead perdido | N/A |

---

## 6. TreatmentType Enum — Tipos de Tratamiento

```python
class TreatmentType(str, Enum):
    AUTOMATED_TELEGRAM = "automated_telegram"   # Mensajes automatizados por Telegram
    AUTOMATED_CALL = "automated_call"           # Llamadas automatizadas (VAPI)
    MANUAL_FOLLOW_UP = "manual_follow_up"        # Seguimiento manual por agente
    HOLD = "hold"                               # En espera, sin contacto activo
```

| Type | Descripción | Uso Típico |
|------|-------------|------------|
| `AUTOMATED_TELEGRAM` | Campañas automatizadas por chat | Leads en entrada/perfilamiento |
| `AUTOMATED_CALL` | Llamadas automatizadas por VAPI | Verificación de interés, recordatorios |
| `MANUAL_FOLLOW_UP` | Agente humano interviene | Casos complejos, HOT leads, potenciales |
| `HOLD` | Sin contacto activo | Leads en cooldown, esperando documentación |

---

## 7. Transiciones de Stage — Reglas Detalladas

### 7.1 Diagrama de Transiciones

```
                    ┌──────────────────────────────────────────────────────────────┐
                    │                     AUTO-ADVANCE LOGIC                        │
                    └──────────────────────────────────────────────────────────────┘

  entrada ──────────▶ perfilamiento
  ┌─────────────────────────┐
  │ Condición:              │
  │ has_basic_data =         │
  │   name AND              │
  │   (phone OR location    │
  │    OR budget)           │
  └─────────────────────────┘

  perfilamiento ──▶ calificacion_financiera
  ┌────────────────────────────────────────────┐
  │ Condición:                                 │
  │   score >= 40 AND budget AND location      │
  │   OR hot_fast_track (name + phone + income) │
  └────────────────────────────────────────────┘

  calificacion_financiera ──▶ agendado
  ┌────────────────────────────────────────────┐
  │ Condición:                                 │
  │   appointment.status IN (SCHEDULED,        │
  │                         CONFIRMED)         │
  │   OR hot_fast_track + CALIFICADO/POTENCIAL  │
  └────────────────────────────────────────────┘

  calificacion_financiera ──▶ potencial
  ┌────────────────────────────────────────────┐
  │ Condición:                                 │
  │   qualification = "POTENCIAL"              │
  │   (needs commercial follow-up)             │
  └────────────────────────────────────────────┘

  calificacion_financiera ──▶ perdido
  ┌────────────────────────────────────────────┐
  │ Condición:                                 │
  │   qualification = "NO_CALIFICADO"          │
  └────────────────────────────────────────────┘

  potencial ─────────▶ agendado
  ┌────────────────────────────────────────────┐
  │ Condición:                                 │
  │   appointment scheduled                    │
  └────────────────────────────────────────────┘

  agendado ─────────▶ seguimiento
  ┌────────────────────────────────────────────┐
  │ Condición:                                 │
  │   visit_completed = true                   │
  └────────────────────────────────────────────┘

  seguimiento ──────▶ referidos
  ┌────────────────────────────────────────────┐
  │ Condición:                                 │
  │   lead.referred_contacts > 0               │
  └────────────────────────────────────────────┘

  referidos ────────▶ ganado
  ┌────────────────────────────────────────────┐
  │ Condición:                                 │
  │   deal_closed = true                       │
  │   OR conversion_confirmed = true           │
  └────────────────────────────────────────────┘

  *** CUALQUIER stage (excepto ganado) ────▶ perdido
  ┌────────────────────────────────────────────┐
  │ Condición:                                 │
  │   lead.lost = true                         │
  │   OR manually marked as lost               │
  │   OR conversation_state = "lost"          │
  │   AND no reactivation in 30 days          │
  └────────────────────────────────────────────┘
```

### 7.2 Tabla de Transiciones Completas

| From Stage | To Stage | Condición | Método |
|------------|----------|-----------|--------|
| entrada | perfilamiento | `has_basic_data` | `actualizar_pipeline_stage()` |
| entrada | perdido | Lead marcadas como perdido | `move_lead_to_stage()` |
| perfilamiento | calificacion_financiera | `score >= 40 AND budget AND location` | `auto_advance_stage()` |
| perfilamiento | agendado | HOT fast-track (name + phone + income) | `auto_advance_stage()` |
| perfilamiento | perdido | Qualification = "NO_CALIFICADO" | `move_lead_to_stage()` |
| calificacion_financiera | agendado | Appointment scheduled | `check_appointment_status()` |
| calificacion_financiera | potencial | Qualification = "POTENCIAL" | `process_qualification_result()` |
| calificacion_financiera | perdido | Qualification = "NO_CALIFICADO" | `process_qualification_result()` |
| potencial | agendado | Appointment scheduled | `schedule_appointment()` |
| potencial | perdido | Lead marcada como perdido | `move_lead_to_stage()` |
| agendado | seguimiento | Visit completed | `mark_visit_completed()` |
| agendado | perdido | Lead perdida post-cita | `move_lead_to_stage()` |
| seguimiento | referidos | `referred_contacts > 0` | `process_referral()` |
| seguimiento | ganado | Deal closed | `close_deal()` |
| seguimiento | perdido | Lead perdida | `move_lead_to_stage()` |
| referidos | ganado | Conversion confirmed | `confirm_conversion()` |
| referidos | perdido | Lead perdida | `move_lead_to_stage()` |
| **ANY** | perdido | `lost = true` | `move_lead_to_stage()` |

---

## 8. G9 Guard — Prohibición de Retroceso

### 8.1 Regla Fundamental

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ⚠️  G9 GUARD — CRÍTICO  ⚠️                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   « Un lead NUNCA puede retroceder a una etapa anterior del pipeline »     │
│                                                                              │
│   Si `new_stage` < `current_stage` en orden PIPELINE_STAGES:               │
│       → `move_lead_to_stage()` RECHAZA la transición                       │
│       → Lanza `PipelineRegressionError`                                    │
│       → Loguea intento fraudulento de regresión                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Orden de Stages (para validación)

```
entrada < perfilamiento < calificacion_financiera < potencial < agendado < seguimiento < referidos < ganado

perdido = N/A (estado terminal, no tiene orden)
```

### 8.3 Ejemplo de Rechazo

```python
# ❌ INVÁLIDO — Intento de retroceso
current_stage = "agendado"
new_stage = "perfilamiento"
# move_lead_to_stage() → RECHAZA con PipelineRegressionError

# ✅ VÁLIDO — Avance normal
current_stage = "agendado"
new_stage = "seguimiento"
# move_lead_to_stage() → PERMITE
```

### 8.4 Justificación

- **Integridad del funnel**: Una vez que un lead avanza, los datos recopilados son válidos.
- **Prevención de fraude**: Evita que agentes marquen leads artificialmente hacia atrás para re-tratar.
- **Métricas limpias**: Las tasas de conversión por etapa son confiables.

---

## 9. Hot Fast-Track — bypass para Leads Calientes

### 9.1 Concepto

Leads con `lead_status = HOT` pueden **bypassear** la espera de criterios completos y avanzar más rápido por el pipeline.

### 9.2 Requisitos para Hot Fast-Track

```
┌─────────────────────────────────────────────────────────┐
│              HOT FAST-TRACK REQUIREMENTS                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   Mínimo requerido:                                    │
│   ✅ name                                               │
│   ✅ phone                                              │
│   ✅ monthly_income                                     │
│                                                         │
│   Con estos 3 datos, el lead HOT puede:               │
│   • entrada → agendado (bypass perfilamiento)         │
│   • perfilamiento → agendado (bypass calificacion)    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 9.3 Fast-Track Paths

```
Path 1: entrada → agendado (sin pasar por perfilamiento ni calificacion)
┌────────────────────────────────────────────────────────────┐
│ entrada ──▶ agendado (HOT)                                │
│                                                            │
│ Condición: has name + phone + monthly_income              │
│ Resultado: Appointment scheduled directamente              │
│ Uso: HOT leads con intención clara y recursos             │
└────────────────────────────────────────────────────────────┘

Path 2: perfilamiento → agendado (bypass calificacion_financiera)
┌────────────────────────────────────────────────────────────┐
│ perfilamiento ──▶ agendado (HOT)                           │
│                                                            │
│ Condición: score >= 40 OR (name + phone + income)         │
│ Resultado: Skip Waiting for full financial qualification   │
│ Uso: HOT leads where income already confirms capacity     │
└────────────────────────────────────────────────────────────┘

Path 3: calificacion_financiera → agendado (HOT + CALIFICADO/POTENCIAL)
┌────────────────────────────────────────────────────────────┐
│ calificacion_financiera ──▶ agendado (HOT)                │
│                                                            │
│ Condición: appointment.status IN (SCHEDULED, CONFIRMED)   │
│           OR (HOT AND qualification IN (CALIFICADO,        │
│                                      POTENCIAL))           │
│ Resultado: Appointment confirmed                          │
│ Uso: HOT leads que ya están cualificados                  │
└────────────────────────────────────────────────────────────┘
```

### 9.4 Comparación: Normal vs Hot Path

| Aspecto | Normal Path | Hot Fast-Track |
|---------|-------------|----------------|
| Tiempo avg entrada → agendado | 3.3 días | 0.5 días |
| Stages atravesados | entrada → perfilamiento → calificacion → agendado | entrada → agendado |
| Datos requeridos | name + phone + location + budget + income + score >= 40 | name + phone + income |
| Agente inicial | QualifierAgent (full flow) | Direct assignment to SchedulerAgent |

---

## 10. Métricas del Pipeline

### 10.1 Stage Average Days (Días Promedio por Etapa)

```
┌─────────────────────────────┬──────────────────┐
│ Pipeline Stage              │ avg_days         │
├─────────────────────────────┼──────────────────┤
│ entrada                     │ 0.5              │
│ perfilamiento               │ 1.2              │
│ calificacion_financiera     │ 2.1              │
│ potencial                   │ 3.0              │
│ agendado                    │ 5.0              │
│ seguimiento                 │ 4.0              │
│ referidos                   │ 7.0              │
│ ganado                      │ — terminal —     │
│ perdido                     │ — terminal —     │
└─────────────────────────────┴──────────────────┘

avg_total = sum(avg_days) = 23.8 días (ideal funnel)
```

### 10.2 Conversion Rates (Tasas de Conversión)

```
┌────────────────────────────────┬───────────────────┐
│ From → To                      │ conversion_rate   │
├────────────────────────────────┼───────────────────┤
│ entrada → perfilamiento        │ 85%               │
│ perfilamiento → calificacion   │ 65%               │
│ calificacion → agendado         │ 45%               │
│ calificacion → potencial       │ 20%               │
│ potencial → agendado           │ 50%               │
│ agendado → seguimiento         │ 75%               │
│ seguimiento → referidos        │ 30%               │
│ seguimiento → ganado           │ 25%               │
│ referidos → ganado             │ 60%               │
│ Any → perdido                  │ 15% (avg leak)    │
└────────────────────────────────┴───────────────────┘

end_to_end_conversion = 85% × 65% × 45% × 75% × 25% ≈ 5.5%
```

### 10.3 Lost By Stage (Pérdidas por Etapa)

```
┌────────────────────────────────┬───────────────────┐
│ From Stage                     │ avg_lost_count    │
├────────────────────────────────┼───────────────────┤
│ entrada                        │ 12%               │
│ perfilamiento                  │ 18%               │
│ calificacion_financiera        │ 25%               │
│ potencial                      │ 15%               │
│ agendado                       │ 8%                │
│ seguimiento                    │ 10%               │
│ referidos                      │ 5%                │
└────────────────────────────────┴───────────────────┘
```

---

## 11. Diagrama de Independencia de Ejes

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         TWO INDEPENDENT AXES                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   PIPELINE STAGE (eje comercial)      CONVERSATION STATE (eje conversacional)   │
│   ────────────────────────────         ────────────────────────────────           │
│                                                                                  │
│   entrada                              greeting                                 │
│       │                                interest_check                            │
│       ▼                                data_collection                          │
│   perfilamiento                        financial_qualification                   │
│       │                                scheduling                               │
│       ▼                                completed                                │
│   calificacion_financiera              lost                                     │
│       │                                                                        │
│       ▼                                                                        │
│   agendado                                                                          │
│       │                                                                           │
│       ▼                                                                           │
│   ...                                                                             │
│                                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ Status: UNRELATED — Un lead puede estar en cualquier combinación:      │   │
│   │   • agendado + data_collection (valid: necesita más datos)             │   │
│   │   • entrada + financial_qualification (invalid: no aplica)             │   │
│   │   • perdida + scheduling (invalid: estado terminal)                    │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 12. Estados Válidos de Combinación

### 12.1 Combinaciones Válidas

| Pipeline Stage | Conversation State | Significado |
|----------------|-------------------|-------------|
| entrada | greeting | Primer contacto, aún sin datos |
| entrada | interest_check | Verificando interés inicial |
| entrada | lost | Lead perdido antes de recopilary datos |
| perfilamiento | data_collection | Recopilando información activamente |
| perfilamiento | lost | Lead perdido durante perfilamiento |
| calificacion_financiera | financial_qualification | Evaluando capacidad financiera |
| calificacion_financiera | scheduling | Programando visita post-calificación |
| calificacion_financiera | lost | Lead perdido, no cualificado |
| potencial | data_collection | Re-perfilamiento para seguimiento comercial |
| potencial | scheduling | Agendando para follow-up comercial |
| agendado | scheduling | Gestionando confirmación de cita |
| agendado | completed | Cita confirmada, esperando ejecución |
| seguimiento | scheduling | Post-visita, reorganizando |
| seguimiento | completed | Seguimiento completado exitosamente |
| referidos | completed | Proceso de referidos exitoso |
| ganado | completed | Cliente convertido |
| perdido | lost | Oportunidad perdida (terminal) |

### 12.2 Combinaciones Inválidas (Validación)

| Pipeline Stage | Conversation State | Razón de Inválidez |
|----------------|-------------------|-------------------|
| entrada | financial_qualification | No aplica hasta perfilamiento completo |
| entrada | scheduling | No aplica hasta entrar en calificacion |
| entrada | completed | No aplica sin conversión |
| potencial | financial_qualification | Ya pasó esa etapa |
| agendado | interest_check | Ya se verificó interés |
| agendado | data_collection | Ya se completaron datos |
| ganado | lost | Terminal, no puede volver a lost |
| perdido | any (except lost) | Terminal, no avanza más |

---

## 13. Code Snippets de Referencia

### 13.1 PIPELINE_STAGES Definition

```python
PIPELINE_STAGES = {
    "entrada": "Lead inicial - recién recibido",
    "perfilamiento": "Recopilando información del cliente",
    "calificacion_financiera": "Validando capacidad financiera",
    "potencial": "Lead con potencial - requiere seguimiento comercial",
    "agendado": "Cita agendada",
    "ganado": "Cliente convertido",
    "perdido": "Oportunidad perdida",
}
```

### 13.2 has_basic_data Check

```python
def actualizar_pipeline_stage(lead):
    if lead.pipeline_stage == "entrada":
        has_basic_data = (
            lead.name is not None
            and (
                lead.phone is not None
                or lead.location is not None
                or lead.budget is not None
            )
        )
        if has_basic_data:
            lead.pipeline_stage = "perfilamiento"
```

### 13.3 G9 Guard Implementation

```python
def move_lead_to_stage(lead, new_stage):
    stage_order = list(PIPELINE_STAGES.keys())
    
    if new_stage not in stage_order:
        raise ValueError(f"Invalid stage: {new_stage}")
    
    if lead.pipeline_stage not in stage_order:
        raise ValueError(f"Current stage not in pipeline: {lead.pipeline_stage}")
    
    current_idx = stage_order.index(lead.pipeline_stage)
    new_idx = stage_order.index(new_stage)
    
    if new_idx < current_idx:
        raise PipelineRegressionError(
            f"Cannot regress from {lead.pipeline_stage} to {new_stage}"
        )
    
    lead.pipeline_stage = new_stage
```

### 13.4 Auto-Advance Stage

```python
def auto_advance_stage(lead):
    if lead.pipeline_stage == "perfilamiento":
        score_ok = lead.score >= 40
        budget_ok = lead.budget is not None
        location_ok = lead.location is not None
        
        if score_ok and budget_ok and location_ok:
            lead.pipeline_stage = "calificacion_financiera"
        
        elif is_hot_fast_track(lead):
            lead.pipeline_stage = "agendado"
    
    elif lead.pipeline_stage == "calificacion_financiera":
        if lead.appointment and lead.appointment.status in ("SCHEDULED", "CONFIRMED"):
            lead.pipeline_stage = "agendado"
        elif lead.qualification == "POTENCIAL":
            lead.pipeline_stage = "potencial"
        elif lead.qualification == "NO_CALIFICADO":
            lead.pipeline_stage = "perdido"
```

---

## 14. Glosario

| Término | Definición |
|---------|------------|
| Pipeline Stage | Posición comercial del lead en el funnel de ventas |
| Conversation State | Estado actual del LLM conversacional |
| LeadStatus | Nivel de "calidez" del lead (COLD, WARM, HOT) |
| TreatmentType | Estrategia de contacto (automated, manual, hold) |
| HOT Fast-Track | Bypass que permite leads calientes avanzar sin esperar criterios completos |
| G9 Guard | Regla que prohíbe retroceder en el pipeline |
| has_basic_data | Flag booleano que indica si el lead tiene datos mínimos (name + phone/location/budget) |
| auto_advance_stage() | Función que evalúa y ejecuta avances automáticos de stage |

---

## 15. Archivos Relacionados

| Archivo | Descripción |
|---------|-------------|
| `app/services/pipeline/constants.py` | Definición de PIPELINE_STAGES |
| `app/services/pipeline/stage_manager.py` | Lógica de transiciones y G9 Guard |
| `app/services/agents/qualifier.py` | QualifierAgent, etapas entrada/perfilamiento |
| `app/services/agents/scheduler.py` | SchedulerAgent, etapa calificacion_financiera |
| `app/services/agents/property_agent.py` | PropertyAgent, etapa potencial |
| `app/services/agents/follow_up.py` | FollowUpAgent, etapas agendado/seguimiento/referidos |
| `app/services/agents/supervisor.py` | AgentSupervisor, routing por stage |
| `app/models/lead.py` | Modelo Lead con pipeline_stage y lead_status |
| `tests/services/pipeline/test_stage_manager.py` | Tests unitarios para transiciones |

---

## Changelog

| Versión | Fecha | Autor | Cambios |
|---------|-------|-------|---------|
| 3.3 | 2026-04-17 | Sistema | Added: Dos ejes independientes (pipeline_stage + conversation_state). Separación de concerns. |
| 3.2 | 2026-04-10 | Sistema | Added: Hot Fast-Track completo. Requisitos y paths documentados. |
| 3.1 | 2026-04-05 | Sistema | Added: G9 Guard formalizado. PipelineRegressionError implementado. |
| 3.0 | 2026-04-01 | Sistema | Breaking: Stage `seguimiento` y `referidos` agregados entre agendado y ganado. |
| 2.5 | 2026-03-25 | Sistema | Added: TreatmentType enum. Tipos de tratamiento por stage. |
| 2.0 | 2026-03-15 | Sistema | Breaking: Stage `potencial` separado de `calificacion_financiera`. |
| 1.0 | 2026-03-01 | Sistema | Initial version. 5 stages: entrada, perfilamiento, agendado, ganado, perdido. |

---

*Este documento es parte de la documentación de arquitectura de INMO CRM.*
*Para preguntas o actualizaciones, contactar al equipo de desarrollo.*