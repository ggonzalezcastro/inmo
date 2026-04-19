# Integración Pipeline + Calificación + Status

## 📋 Problema

Tenemos 3 conceptos distintos que necesitan trabajar juntos:

1. **`status`** (LeadStatus): cold, warm, hot, converted, lost
   - Representa la "temperatura" del lead basada en score automático
   - Se calcula por comportamiento y datos recopilados

2. **`pipeline_stage`**: entrada, perfilamiento, calificacion_financiera, agendado, seguimiento, referidos, ganado, perdido
   - Representa la etapa del proceso de venta
   - Se mueve manualmente o automáticamente por el flujo

3. **`metadata.calificacion`** (NUEVO): CALIFICADO, POTENCIAL, NO_CALIFICADO
   - Representa el resultado de la evaluación financiera
   - Se determina por ingresos + DICOM

---

## 🎯 Propuesta de Integración

### Diferencias Clave

| Concepto | Qué Mide | Cómo se Actualiza | Cuándo se Usa |
|----------|----------|-------------------|---------------|
| **status** | Temperatura/Interés | Automático (scoring) | Para priorizar contacto |
| **pipeline_stage** | Etapa del proceso | Manual/Automático (flujo) | Para organizar trabajo |
| **calificacion** | Viabilidad financiera | Automático (al completar datos) | Para decidir siguiente acción |

---

## 🔄 Flujo Completo del Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                      FLUJO DEL LEAD                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1️⃣ ENTRADA                                                     │
│     pipeline_stage: "entrada"                                   │
│     status: cold (score: 0-20)                                  │
│     calificacion: null                                          │
│     ┌───────────────────────────────────────────────┐           │
│     │ Lead nuevo llega (Telegram, Web, WhatsApp)   │           │
│     │ Solo tiene: teléfono/chat_id                 │           │
│     └───────────────────────────────────────────────┘           │
│                          ↓                                      │
│                                                                 │
│  2️⃣ PERFILAMIENTO                                               │
│     pipeline_stage: "perfilamiento"                             │
│     status: warm (score: 21-50)                                 │
│     calificacion: null                                          │
│     ┌───────────────────────────────────────────────┐           │
│     │ Recopilando datos básicos:                   │           │
│     │ - Nombre                                      │           │
│     │ - Email                                       │           │
│     │ - Ubicación de interés                        │           │
│     │ - Tipo de propiedad                           │           │
│     └───────────────────────────────────────────────┘           │
│                          ↓                                      │
│         (cuando score >= 40 y tiene datos básicos)             │
│                          ↓                                      │
│                                                                 │
│  3️⃣ CALIFICACIÓN FINANCIERA                                     │
│     pipeline_stage: "calificacion_financiera"                   │
│     status: warm/hot (score: 40-100)                            │
│     calificacion: EN_PROCESO → se calculará al final            │
│     ┌───────────────────────────────────────────────┐           │
│     │ Recopilando datos financieros:               │           │
│     │ - Renta líquida mensual (monthly_income)     │           │
│     │ - Situación DICOM (dicom_status)             │           │
│     │ - Monto morosidad (si aplica)                │           │
│     │ - Presupuesto                                 │           │
│     └───────────────────────────────────────────────┘           │
│                          ↓                                      │
│         (cuando tiene monthly_income + dicom_status)            │
│                          ↓                                      │
│             SE EJECUTA LÓGICA DE CALIFICACIÓN                   │
│                          ↓                                      │
│                    ┌─────┴─────┐                                │
│                    │           │                                │
│       ┌────────────┴─┐    ┌────┴──────────┐    ┌──────────┐   │
│       │ CALIFICADO   │    │  POTENCIAL    │    │    NO    │   │
│       └──────┬───────┘    └───────┬───────┘    │CALIFICADO│   │
│              │                    │             └────┬─────┘   │
│              │                    │                  │         │
│              ↓                    ↓                  ↓         │
│                                                                 │
│  4️⃣A AGENDADO (si CALIFICADO)                                  │
│     pipeline_stage: "agendado"                                  │
│     status: hot (score: 70-100)                                 │
│     calificacion: "CALIFICADO"                                  │
│     ┌───────────────────────────────────────────────┐           │
│     │ ✅ Ingresos adecuados (>= 1M)                 │           │
│     │ ✅ DICOM limpio o deuda < 500k                │           │
│     │ → Se ofrece agendar cita                      │           │
│     │ → Usa herramientas de agendamiento            │           │
│     └───────────────────────────────────────────────┘           │
│                          ↓                                      │
│           (después de la cita)                                  │
│                          ↓                                      │
│                    ┌─────┴─────┐                                │
│                    │           │                                │
│              ┌─────┴─────┐  ┌──┴────────┐                       │
│              │  GANADO   │  │  PERDIDO  │                       │
│              └───────────┘  └───────────┘                       │
│                                                                 │
│  4️⃣B SEGUIMIENTO (si POTENCIAL)                                │
│     pipeline_stage: "seguimiento"                               │
│     status: warm (score: 40-69)                                 │
│     calificacion: "POTENCIAL"                                   │
│     ┌───────────────────────────────────────────────┐           │
│     │ ⚠️ Situación mejorable:                       │           │
│     │ - Ingresos medios (500k-1M)                   │           │
│     │ - DICOM con deuda manejable                   │           │
│     │ - Falta información                           │           │
│     │ → Se programa seguimiento en X meses          │           │
│     │ → Se envían campañas educativas               │           │
│     └───────────────────────────────────────────────┘           │
│                          ↓                                      │
│           (se contacta en 1-3 meses)                            │
│                          ↓                                      │
│              ┌───────────────────────┐                          │
│              │ Re-evaluar situación  │                          │
│              │ Volver a etapa 3      │                          │
│              └───────────────────────┘                          │
│                                                                 │
│  4️⃣C PERDIDO (si NO_CALIFICADO)                                │
│     pipeline_stage: "perdido"                                   │
│     status: lost                                                │
│     calificacion: "NO_CALIFICADO"                               │
│     ┌───────────────────────────────────────────────┐           │
│     │ ❌ No viable actualmente:                     │           │
│     │ - Ingresos muy bajos (< 500k)                 │           │
│     │ - DICOM con morosidad alta (> 500k)           │           │
│     │ → Se agradece y se archiva                    │           │
│     │ → Se puede reactivar si mejora situación      │           │
│     └───────────────────────────────────────────────┘           │
│                                                                 │
│  5️⃣ REFERIDOS (opcional)                                        │
│     pipeline_stage: "referidos"                                 │
│     status: converted                                           │
│     calificacion: "CALIFICADO"                                  │
│     ┌───────────────────────────────────────────────┐           │
│     │ Cliente satisfecho refiere a otros            │           │
│     └───────────────────────────────────────────────┘           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Tabla de Estados Combinados

| Pipeline Stage | Status Típico | Calificación | Siguiente Acción |
|----------------|---------------|--------------|------------------|
| entrada | cold | null | Iniciar conversación, obtener nombre |
| perfilamiento | warm | null | Recopilar datos básicos (email, ubicación, presupuesto) |
| calificacion_financiera | warm/hot | EN_PROCESO | Recopilar monthly_income y dicom_status |
| agendado | hot | CALIFICADO | Agendar cita, preparar visita |
| seguimiento | warm | POTENCIAL | Programar follow-up en 1-3 meses |
| ganado | converted | CALIFICADO | Celebrar 🎉, pedir referidos |
| perdido | lost | NO_CALIFICADO o POTENCIAL | Archivar, permitir reactivación |
| referidos | converted | CALIFICADO | Capturar nuevos leads |

---

## 🤖 Lógica de Transición Automática

### Función: `actualizar_pipeline_stage(lead)`

```python
async def actualizar_pipeline_stage(db: AsyncSession, lead: Lead):
    """
    Actualiza automáticamente el pipeline_stage según los datos del lead
    """
    metadata = lead.lead_metadata or {}
    
    # 1. Si acaba de llegar (no tiene nombre) → entrada
    if not lead.name or lead.name in ["User", "Test User"]:
        if lead.pipeline_stage != "entrada":
            lead.pipeline_stage = "entrada"
            lead.stage_entered_at = datetime.now(timezone.utc)
            return
    
    # 2. Si tiene datos básicos pero no financieros → perfilamiento
    has_basic_data = (
        lead.name and 
        lead.email and 
        metadata.get("location")
    )
    has_financial_data = (
        metadata.get("monthly_income") and 
        metadata.get("dicom_status")
    )
    
    if has_basic_data and not has_financial_data:
        if lead.pipeline_stage not in ["perfilamiento", "calificacion_financiera"]:
            lead.pipeline_stage = "perfilamiento"
            lead.stage_entered_at = datetime.now(timezone.utc)
            return
    
    # 3. Si tiene datos básicos y score >= 40 → calificacion_financiera
    if has_basic_data and lead.lead_score >= 40 and not has_financial_data:
        if lead.pipeline_stage != "calificacion_financiera":
            lead.pipeline_stage = "calificacion_financiera"
            lead.stage_entered_at = datetime.now(timezone.utc)
            return
    
    # 4. Si tiene datos financieros completos → calcular calificación y mover
    if has_financial_data:
        # Calcular calificación
        calificacion = calcular_calificacion(lead)
        metadata["calificacion"] = calificacion
        lead.lead_metadata = metadata
        
        # Mover según resultado
        if calificacion == "CALIFICADO":
            # Solo mover a "agendado" si realmente se agenda una cita
            # Por ahora, mantener en calificacion_financiera hasta que confirme
            pass
        
        elif calificacion == "POTENCIAL":
            if lead.pipeline_stage != "seguimiento":
                lead.pipeline_stage = "seguimiento"
                lead.status = "warm"
                lead.stage_entered_at = datetime.now(timezone.utc)
        
        elif calificacion == "NO_CALIFICADO":
            if lead.pipeline_stage != "perdido":
                lead.pipeline_stage = "perdido"
                lead.status = "lost"
                lead.stage_entered_at = datetime.now(timezone.utc)
    
    await db.commit()


def calcular_calificacion(lead: Lead) -> str:
    """
    Calcula la calificación financiera del lead
    
    Returns: "CALIFICADO", "POTENCIAL", "NO_CALIFICADO"
    """
    metadata = lead.lead_metadata or {}
    
    monthly_income = metadata.get("monthly_income", 0)
    dicom_status = metadata.get("dicom_status", "unknown")
    morosidad_amount = metadata.get("morosidad_amount", 0)
    
    # CALIFICADO: Buenos ingresos + DICOM limpio
    if monthly_income >= 1000000 and dicom_status == "clean":
        return "CALIFICADO"
    
    # POTENCIAL: Situación mejorable
    if monthly_income >= 500000:
        if dicom_status == "clean":
            return "POTENCIAL"  # Ingresos justos pero sin deudas
        elif dicom_status == "has_debt" and morosidad_amount < 500000:
            return "POTENCIAL"  # Deuda manejable
    
    if monthly_income >= 1000000 and dicom_status == "has_debt" and morosidad_amount < 500000:
        return "POTENCIAL"  # Buenos ingresos con deuda manejable
    
    # NO_CALIFICADO: Situación difícil
    if monthly_income < 500000:
        return "NO_CALIFICADO"
    
    if morosidad_amount >= 500000:
        return "NO_CALIFICADO"
    
    # Default: Si falta información
    if dicom_status == "unknown":
        return "POTENCIAL"
    
    return "POTENCIAL"
```

---

## 🎨 Visualización en Frontend

### Pipeline Board - Estados Combinados

```
┌──────────────────────────────────────────────────────────────────┐
│                        PIPELINE BOARD                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  🆕 ENTRADA    📋 PERFILAMIENTO    💰 CALIFICACIÓN    📅 AGENDADO│
│  ┌─────────┐  ┌──────────────┐    ┌──────────────┐  ┌─────────┐│
│  │ Juan    │  │ María 🔥     │    │ Pedro 🌡️    │  │ Ana ✅  ││
│  │ cold    │  │ warm         │    │ hot          │  │ hot     ││
│  │ ---     │  │ ---          │    │ POTENCIAL    │  │CALIFICADO│
│  └─────────┘  └──────────────┘    └──────────────┘  └─────────┘│
│                                                                  │
│  🔄 SEGUIMIENTO    🎯 REFERIDOS    ✅ GANADO      ❌ PERDIDO     │
│  ┌──────────────┐  ┌───────────┐  ┌──────────┐  ┌────────────┐│
│  │ Carlos ⚠️    │  │ Luis 🎉   │  │ Sofia 🏆 │  │ Diego 😞   ││
│  │ warm         │  │ converted │  │ converted│  │ lost       ││
│  │ POTENCIAL    │  │CALIFICADO │  │CALIFICADO│  │NO_CALIFICADO│
│  └──────────────┘  └───────────┘  └──────────┘  └────────────┘│
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Lead Card - Información Combinada

```
┌────────────────────────────────────────────────────────────┐
│  📇 Juan Pérez                              🔥 HOT (85pts) │
│  +56912345678 | juan@email.com                            │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  📍 Ubicación: Las Condes                                 │
│  💰 Ingresos: $1.800.000/mes                              │
│  📊 DICOM: Limpio ✅                                       │
│                                                            │
│  🎯 Calificación: CALIFICADO ✅                           │
│  📂 Pipeline: calificacion_financiera → agendado          │
│                                                            │
│  🕐 Última interacción: Hace 2 horas                      │
│  👤 Asignado a: María González                            │
│                                                            │
│  [Agendar Cita]  [Ver Historial]  [Editar]               │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## 🔄 Transiciones Manuales (Admin/Agent)

Los agentes pueden mover leads manualmente entre etapas:

### Transiciones Permitidas

| Desde | Hacia | Cuándo |
|-------|-------|--------|
| entrada | perfilamiento | Manualmente si se obtuvo info básica |
| perfilamiento | calificacion_financiera | Manualmente si score >= 40 |
| calificacion_financiera | agendado | Cuando se crea una cita |
| agendado | ganado | Después de cita exitosa |
| agendado | perdido | Si no se concreta |
| seguimiento | calificacion_financiera | Para re-evaluar después de X meses |
| seguimiento | perdido | Si ya no hay interés |
| perdido | perfilamiento | Si se reactiva el lead |
| ganado | referidos | Si el cliente refiere a otros |

---

## 📝 Campos en el Modelo Lead

### Campos Existentes
```python
# Status (temperatura automática por scoring)
status: str  # "cold", "warm", "hot", "converted", "lost"

# Pipeline (etapa del proceso)
pipeline_stage: str  # "entrada", "perfilamiento", "calificacion_financiera", 
                     # "agendado", "seguimiento", "referidos", "ganado", "perdido"
stage_entered_at: datetime  # Timestamp de entrada a la etapa actual

# Score
lead_score: float  # 0-100
```

### Campos Nuevos en Metadata
```python
lead_metadata = {
    # Datos básicos (perfilamiento)
    "location": "Las Condes",
    "budget": "3000 UF",
    "property_type": "departamento",
    "timeline": "3 meses",
    
    # Datos financieros (calificacion_financiera)
    "monthly_income": 1800000,  # NUEVO
    "dicom_status": "clean",    # NUEVO: "clean", "has_debt", "unknown"
    "morosidad_amount": 0,      # NUEVO: monto si tiene deuda
    
    # Resultado de calificación
    "calificacion": "CALIFICADO",  # NUEVO: "CALIFICADO", "POTENCIAL", "NO_CALIFICADO"
    
    # Otros
    "residency_status": "residente",  # "residente", "extranjero"
    "purpose": "vivienda",            # "vivienda", "inversion"
}
```

---

## 🎯 Prioridad de Contacto

Combina `status` + `pipeline_stage` + `calificacion` para priorizar:

### Reglas de Prioridad

1. **URGENTE** (contactar HOY)
   - pipeline_stage = "agendado" + status = "hot" + calificacion = "CALIFICADO"
   - Tiene cita próxima

2. **ALTA** (contactar en 24h)
   - pipeline_stage = "calificacion_financiera" + status = "hot" + calificacion = "CALIFICADO"
   - Listo para agendar pero aún no tiene cita

3. **MEDIA** (contactar en 2-3 días)
   - pipeline_stage = "perfilamiento" + status = "warm"
   - Falta completar datos
   - pipeline_stage = "seguimiento" + calificacion = "POTENCIAL"
   - Necesita seguimiento en X tiempo

4. **BAJA** (contactar cuando haya tiempo)
   - pipeline_stage = "entrada" + status = "cold"
   - Apenas está iniciando

5. **ARCHIVADO** (no contactar)
   - pipeline_stage = "perdido" + calificacion = "NO_CALIFICADO"
   - pipeline_stage = "ganado"

---

## 🔔 Automatizaciones y Alertas

### Triggers Automáticos

```python
# 1. Lead pasa a CALIFICADO → Notificar al agente asignado
if metadata.get("calificacion") == "CALIFICADO" and lead.assigned_to:
    notify_agent(lead.assigned_to, f"Lead {lead.name} está CALIFICADO para agendar")

# 2. Lead llega a pipeline_stage "agendado" → Enviar email de confirmación
if lead.pipeline_stage == "agendado" and lead.email:
    send_appointment_confirmation_email(lead)

# 3. Lead pasa a POTENCIAL → Programar seguimiento en 1-3 meses
if metadata.get("calificacion") == "POTENCIAL":
    schedule_followup(lead, days=60)  # 2 meses

# 4. Lead lleva más de 7 días en "perfilamiento" → Alerta de estancamiento
if lead.pipeline_stage == "perfilamiento" and days_in_stage(lead) > 7:
    alert_admin(f"Lead {lead.name} lleva {days_in_stage(lead)} días sin avanzar")
```

---

## ✅ Checklist de Implementación

### Backend

- [ ] **Actualizar `lead.py` modelo:**
  - [ ] Agregar `metadata.monthly_income`
  - [ ] Agregar `metadata.dicom_status`
  - [ ] Agregar `metadata.morosidad_amount`
  - [ ] Agregar `metadata.calificacion`

- [ ] **Crear `pipeline_service.py`:**
  - [ ] `actualizar_pipeline_stage(lead)` → Automático
  - [ ] `mover_pipeline_stage(lead, new_stage)` → Manual
  - [ ] `calcular_calificacion(lead)` → Evalúa financieramente
  - [ ] `days_in_stage(lead)` → Días en etapa actual

- [ ] **Actualizar `scoring_service.py`:**
  - [ ] Incluir `monthly_income` en cálculo de score
  - [ ] Incluir `dicom_status` en cálculo de score

- [ ] **Crear endpoints:**
  - [ ] `PUT /api/v1/leads/{id}/pipeline` → Mover etapa manualmente
  - [ ] `POST /api/v1/leads/{id}/recalculate` → Recalcular calificación

- [ ] **Automatizaciones:**
  - [ ] Hook after_update en Lead → llamar `actualizar_pipeline_stage`
  - [ ] Notificaciones cuando calificacion = "CALIFICADO"
  - [ ] Scheduler para alertas de estancamiento

### Frontend

- [ ] **Pipeline Board:**
  - [ ] Mostrar columnas según pipeline_stage
  - [ ] Mostrar badge de calificacion en cada lead card
  - [ ] Mostrar badge de status (temperatura)
  - [ ] Drag & drop para mover entre etapas

- [ ] **Lead Detail:**
  - [ ] Sección de "Calificación Financiera"
  - [ ] Mostrar monthly_income, dicom_status, morosidad_amount
  - [ ] Indicador visual de calificacion (verde/amarillo/rojo)
  - [ ] Timeline de cambios de etapa

- [ ] **Filtros:**
  - [ ] Filtrar por pipeline_stage
  - [ ] Filtrar por calificacion
  - [ ] Filtrar por status
  - [ ] Vista "Listos para agendar" (CALIFICADO + no agendado)

---

## 🎓 Resumen Conceptual

**3 dimensiones de un Lead:**

1. **🌡️ Temperatura (status)**: Qué tan "caliente" está (interés/engagement)
   - Se calcula automáticamente por scoring
   - cold → warm → hot → converted/lost

2. **📍 Etapa (pipeline_stage)**: En qué parte del proceso está
   - Se mueve por flujo del negocio
   - entrada → perfilamiento → calificacion_financiera → agendado → ganado/perdido/seguimiento

3. **✅ Viabilidad (calificacion)**: Puede comprar financieramente
   - Se determina en la etapa de calificacion_financiera
   - CALIFICADO / POTENCIAL / NO_CALIFICADO

**Los 3 conceptos son independientes pero se complementan:**
- Un lead puede ser "hot" (alta temperatura) pero "NO_CALIFICADO" (sin capacidad financiera)
- Un lead puede ser "warm" (mediana temperatura) y "CALIFICADO" (con capacidad financiera)
- La combinación de los 3 determina la prioridad y siguiente acción



