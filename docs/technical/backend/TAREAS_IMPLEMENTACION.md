# 📋 Tareas de Implementación: Backend y Frontend

## 🎯 Resumen del Proyecto

Implementar un sistema multi-broker con:
1. **Prompts configurables** por broker (8 secciones en BD)
2. **Sistema de calificación financiera** (ingresos + DICOM) ⭐ **CONFIGURABLE**
3. **Pipeline integrado** con estados de calificación
4. **Roles de usuario** (superadmin, admin, agent)
5. **Herramientas de agendamiento** integradas en el prompt

### ⭐ IMPORTANTE: Configurabilidad de Criterios de Calificación

**Los rangos salariales y criterios de calificación deben ser 100% configurables por cada broker en la base de datos.**

Esto significa que cada broker puede definir:
- **Rangos de ingresos**: Qué considera "bajo", "medio", "bueno", etc.
- **Criterios CALIFICADO**: Ingreso mínimo, estado DICOM, deuda máxima aceptable
- **Criterios POTENCIAL**: Condiciones para seguimiento futuro
- **Criterios NO_CALIFICADO**: Condiciones de rechazo automático

**NO hardcodear valores como:**
- ❌ `if monthly_income >= 1000000` → Esto debe venir de `broker_lead_configs.qualification_criteria`
- ❌ `if debt_amount > 500000` → Esto debe venir de `broker_lead_configs.max_acceptable_debt`

**SÍ usar valores de la BD:**
- ✅ `config.qualification_criteria['calificado']['min_monthly_income']`
- ✅ `config.max_acceptable_debt`

---

# 🔧 TAREAS BACKEND

## 1️⃣ MODELOS Y MIGRACIONES (Alta Prioridad)

### 1.1 Crear Modelos de Broker
**Archivo:** `backend/app/models/broker.py`

```python
# Crear 3 modelos nuevos:

class Broker(Base):
    """Modelo de Broker/Inmobiliaria"""
    id, name, slug, phone, email, logo_url, website, address,
    timezone, currency, country, language, subscription_plan,
    is_active, created_at, updated_at

class BrokerPromptConfig(Base):
    """Configuración de prompts por broker (8 secciones)"""
    id, broker_id, agent_name, agent_role, identity_prompt,
    business_context, agent_objective, data_collection_prompt,
    behavior_rules, restrictions, situation_handlers (JSONB),
    output_format, full_custom_prompt, enable_appointment_booking,
    tools_instructions, created_at, updated_at

class BrokerLeadConfig(Base):
    """Configuración de calificación de leads por broker"""
    id, broker_id, field_weights (JSONB), cold_max_score,
    warm_max_score, hot_min_score, qualified_min_score,
    field_priority (JSONB), alert_on_hot_lead, 
    alert_score_threshold, alert_email, created_at
```

**Checklist:**
- [ ] Crear archivo `backend/app/models/broker.py`
- [ ] Definir clase `Broker`
- [ ] Definir clase `BrokerPromptConfig`
- [ ] Definir clase `BrokerLeadConfig`
- [ ] Agregar relaciones con `User` y `Lead`
- [ ] Exportar en `backend/app/models/__init__.py`

---

### 1.2 Actualizar Modelo User
**Archivo:** `backend/app/models/user.py`

**Cambios:**
```python
# AGREGAR:
broker_id = Column(Integer, ForeignKey("brokers.id"), nullable=True)

# ACTUALIZAR role para soportar 3 valores:
role = Column(String(20), default="agent", nullable=False)
# Valores posibles: "superadmin", "admin", "agent"

# AGREGAR relación:
broker = relationship("Broker", back_populates="users")
```

**Checklist:**
- [ ] Agregar campo `broker_id`
- [ ] Actualizar enum `UserRole` con `SUPERADMIN`, `ADMIN`, `AGENT`
- [ ] Agregar relación `broker`
- [ ] Renombrar campo `broker_name` a `name` (si existe)

---

### 1.3 Actualizar Modelo Lead - Nuevos Campos en Metadata
**Archivo:** `backend/app/models/lead.py`

**NO se modifica el modelo, solo se documentan nuevos campos en metadata:**

```python
# Nuevos campos que se guardarán en lead_metadata (JSON):
metadata = {
    # === YA EXISTENTES ===
    "location": "Las Condes",
    "budget": "3000 UF",
    "property_type": "departamento",
    "timeline": "3 meses",
    
    # === NUEVOS - CALIFICACIÓN FINANCIERA ===
    "monthly_income": 1800000,        # int - Renta líquida mensual (CLP)
    "dicom_status": "clean",          # str - "clean", "has_debt", "unknown"
    "morosidad_amount": 0,            # int - Monto de morosidad (CLP)
    "calificacion": "CALIFICADO",     # str - "CALIFICADO", "POTENCIAL", "NO_CALIFICADO"
    
    # === NUEVOS - OPCIONALES ===
    "residency_status": "residente",  # str - "residente", "extranjero"
    "purpose": "vivienda",            # str - "vivienda", "inversion"
    "bedrooms": 3,                    # int - Número de dormitorios
}
```

**Checklist:**
- [ ] NO hay que modificar el modelo (usa JSON existente)
- [ ] Documentar nuevos campos en un comentario o docstring
- [ ] Verificar que `lead_metadata` sea tipo `JSON` en la BD

---

### 1.4 Actualizar BrokerLeadConfig con Criterios Configurables
**Archivo:** `backend/app/models/broker.py`

**⭐ IMPORTANTE: Los rangos salariales y criterios de calificación deben ser configurables por broker**

```python
class BrokerLeadConfig(Base):
    """Configuración de calificación de leads por broker"""
    __tablename__ = "broker_lead_configs"
    
    id = Column(Integer, primary_key=True)
    broker_id = Column(Integer, ForeignKey("brokers.id"), unique=True)
    
    # Pesos de campos
    field_weights = Column(JSON, default={
        "name": 10, "phone": 15, "email": 10, "location": 15,
        "monthly_income": 25, "dicom_status": 20, "budget": 10
    })
    
    # Umbrales de score
    cold_max_score = Column(Integer, default=20)
    warm_max_score = Column(Integer, default=50)
    hot_min_score = Column(Integer, default=50)
    qualified_min_score = Column(Integer, default=75)
    
    # Prioridad de preguntas
    field_priority = Column(JSON, default=[
        "name", "phone", "email", "location", 
        "monthly_income", "dicom_status", "budget"
    ])
    
    # ⭐ NUEVO: Rangos de ingresos configurables
    income_ranges = Column(JSON, default={
        "insufficient": {"min": 0, "max": 500000, "label": "Insuficiente"},
        "low": {"min": 500000, "max": 1000000, "label": "Bajo"},
        "medium": {"min": 1000000, "max": 2000000, "label": "Medio"},
        "good": {"min": 2000000, "max": 4000000, "label": "Bueno"},
        "excellent": {"min": 4000000, "max": None, "label": "Excelente"}
    })
    
    # ⭐ NUEVO: Criterios de calificación configurables
    qualification_criteria = Column(JSON, default={
        "calificado": {
            "min_monthly_income": 1000000,
            "dicom_status": ["clean"],
            "max_debt_amount": 0
        },
        "potencial": {
            "min_monthly_income": 500000,
            "dicom_status": ["clean", "has_debt"],
            "max_debt_amount": 500000
        },
        "no_calificado": {
            "conditions": [
                {"monthly_income_below": 500000},
                {"debt_amount_above": 500000}
            ]
        }
    })
    
    # ⭐ NUEVO: Umbral de deuda aceptable
    max_acceptable_debt = Column(Integer, default=500000)
    
    # Alertas
    alert_on_hot_lead = Column(Boolean, default=True)
    alert_score_threshold = Column(Integer, default=70)
    alert_on_qualified = Column(Boolean, default=True)
    alert_email = Column(String(200))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
```

**Checklist:**
- [ ] Agregar campo `income_ranges` (JSONB) con rangos configurables
- [ ] Agregar campo `qualification_criteria` (JSONB) con criterios configurables
- [ ] Agregar campo `max_acceptable_debt` (Integer)
- [ ] Agregar campo `alert_on_qualified` (Boolean)

---

### 1.5 Crear Migración Principal
**Archivo:** `backend/migrations/versions/XXXXX_add_broker_system.py`

**Debe crear:**
1. Tabla `brokers`
2. Tabla `broker_prompt_configs`
3. Tabla `broker_lead_configs`
4. Agregar columna `broker_id` a tabla `users`
5. **IMPORTANTE:** Insertar datos por defecto:
   - Broker "Default Broker"
   - Configuración de prompts con las 8 secciones del documento `PROMPT_PROFESIONAL_ADAPTADO.md`
   - Configuración de scoring con pesos para `monthly_income` y `dicom_status`

**Checklist:**
- [ ] Generar migración: `alembic revision -m "add broker system"`
- [ ] Crear tablas `brokers`, `broker_prompt_configs`, `broker_lead_configs`
- [ ] Agregar `broker_id` a `users`
- [ ] Insertar broker por defecto
- [ ] Insertar configuración de prompts por defecto (copiar de `PROMPT_PROFESIONAL_ADAPTADO.md`)
- [ ] Insertar configuración de scoring por defecto
- [ ] Probar migración: `alembic upgrade head`
- [ ] Verificar rollback: `alembic downgrade -1`

---

## 2️⃣ SERVICIOS (Alta Prioridad)

### 2.1 Crear BrokerConfigService
**Archivo:** `backend/app/services/broker_config_service.py`

**Métodos a implementar:**
```python
class BrokerConfigService:
    
    @staticmethod
    async def build_system_prompt(db, broker_id, lead_context=None) -> str:
        """
        Construye el prompt completo desde las 8 secciones en BD
        Si existe full_custom_prompt, úsalo
        Si no, construye desde secciones individuales
        Incluye contexto del lead si se proporciona
        """
        pass
    
    @staticmethod
    async def get_broker_config(db, broker_id) -> dict:
        """Obtiene toda la configuración del broker"""
        pass
    
    @staticmethod
    async def update_prompt_config(db, broker_id, updates: dict):
        """Actualiza configuración de prompts"""
        pass
    
    @staticmethod
    async def update_lead_config(db, broker_id, updates: dict):
        """Actualiza configuración de calificación"""
        pass
    
    @staticmethod
    async def get_prompt_preview(db, broker_id, lead_context=None) -> str:
        """Preview del prompt para mostrar en admin"""
        pass
```

**Checklist:**
- [ ] Crear archivo `broker_config_service.py`
- [ ] Implementar `build_system_prompt()` con lógica de 8 secciones
- [ ] Implementar `get_broker_config()`
- [ ] Implementar `update_prompt_config()`
- [ ] Implementar `update_lead_config()`
- [ ] Implementar `get_prompt_preview()`
- [ ] Agregar manejo de errores
- [ ] Agregar logs

---

### 2.2 Crear PipelineService
**Archivo:** `backend/app/services/pipeline_service.py`

**Métodos a implementar:**
```python
class PipelineService:
    
    @staticmethod
    async def actualizar_pipeline_stage(db, lead: Lead):
        """
        Actualiza automáticamente el pipeline_stage según datos del lead
        
        Lógica:
        - Si no tiene nombre → "entrada"
        - Si tiene datos básicos → "perfilamiento"
        - Si score >= 40 → "calificacion_financiera"
        - Si tiene monthly_income + dicom_status:
          - Calcular calificacion
          - Si CALIFICADO → listo para "agendado" (cuando se cree cita)
          - Si POTENCIAL → "seguimiento"
          - Si NO_CALIFICADO → "perdido"
        """
        pass
    
    @staticmethod
    async def mover_pipeline_stage(db, lead_id: int, new_stage: str, user_id: int):
        """Mueve manualmente un lead a otra etapa (registro en logs)"""
        pass
    
    @staticmethod
    async def calcular_calificacion(db: AsyncSession, lead: Lead, broker_id: int) -> str:
        """
        Calcula calificación financiera usando criterios configurables del broker
        
        ⭐ IMPORTANTE: NO hardcodear valores, usar broker_lead_configs
        
        Returns: "CALIFICADO", "POTENCIAL", "NO_CALIFICADO"
        """
        
        # Obtener configuración del broker
        config = await BrokerConfigService.get_lead_config(db, broker_id)
        criteria = config.qualification_criteria
        
        metadata = lead.lead_metadata or {}
        monthly_income = metadata.get("monthly_income", 0)
        dicom_status = metadata.get("dicom_status", "unknown")
        debt_amount = metadata.get("morosidad_amount", 0)
        
        # CALIFICADO (usa criterios de la BD)
        calificado_criteria = criteria.get("calificado", {})
        if (monthly_income >= calificado_criteria.get("min_monthly_income", 1000000) and
            dicom_status in calificado_criteria.get("dicom_status", ["clean"]) and
            debt_amount <= calificado_criteria.get("max_debt_amount", 0)):
            return "CALIFICADO"
        
        # NO_CALIFICADO (verifica condiciones de rechazo)
        no_calificado_conditions = criteria.get("no_calificado", {}).get("conditions", [])
        for condition in no_calificado_conditions:
            if "monthly_income_below" in condition:
                if monthly_income < condition["monthly_income_below"]:
                    return "NO_CALIFICADO"
            if "debt_amount_above" in condition:
                if debt_amount > condition["debt_amount_above"]:
                    return "NO_CALIFICADO"
        
        # POTENCIAL (default si no es CALIFICADO ni NO_CALIFICADO)
        return "POTENCIAL"
    
    @staticmethod
    def days_in_stage(lead: Lead) -> int:
        """Calcula días que lleva el lead en su etapa actual"""
        pass
```

**Checklist:**
- [ ] Crear archivo `pipeline_service.py`
- [ ] Implementar `actualizar_pipeline_stage()`
- [ ] Implementar `mover_pipeline_stage()`
- [ ] Implementar `calcular_calificacion()` (según lógica del documento)
- [ ] Implementar `days_in_stage()`
- [ ] Agregar registro de cambios en `activity_log`

---

### 2.3 Actualizar ScoringService
**Archivo:** `backend/app/services/scoring_service.py`

**Cambios:**
```python
# AGREGAR nuevos campos al cálculo de score:

# 1. monthly_income (peso: 25 puntos)
if metadata.get("monthly_income"):
    income = metadata["monthly_income"]
    if income >= 4000000:
        score += 25  # Muy alto
    elif income >= 2000000:
        score += 20  # Alto
    elif income >= 1000000:
        score += 15  # Medio-alto
    elif income >= 500000:
        score += 10  # Medio-bajo

# 2. dicom_status (peso: 20 puntos)
if metadata.get("dicom_status") == "clean":
    score += 20
elif metadata.get("dicom_status") == "has_debt":
    if metadata.get("morosidad_amount", 0) < 500000:
        score += 10  # Deuda manejable

# Total máximo: 100 puntos
```

**Checklist:**
- [ ] Agregar cálculo de `monthly_income` al score
- [ ] Agregar cálculo de `dicom_status` al score
- [ ] Actualizar pesos de campos existentes si es necesario
- [ ] Usar configuración de `broker_lead_configs.field_weights` si existe

---

### 2.4 Actualizar LeadContextService
**Archivo:** `backend/app/services/lead_context_service.py`

**Cambios:**
```python
# En build_llm_prompt():
# 1. Intentar obtener prompt del broker si existe broker_id
if broker_id:
    system_prompt = await BrokerConfigService.build_system_prompt(
        db, broker_id, lead_context
    )
else:
    # Usar prompt por defecto

# En _build_context_summary():
# 2. Incluir nuevos campos en el resumen
if metadata.get("monthly_income"):
    info_collected.append(f"INGRESOS: ${metadata['monthly_income']:,}")

if metadata.get("dicom_status"):
    status_text = {
        "clean": "✅ Limpio",
        "has_debt": "⚠️ Con deuda",
        "unknown": "❓ Desconocido"
    }.get(metadata["dicom_status"], "")
    info_collected.append(f"DICOM: {status_text}")

if metadata.get("calificacion"):
    info_collected.append(f"CALIFICACIÓN: {metadata['calificacion']}")
```

**Checklist:**
- [ ] Integrar `BrokerConfigService.build_system_prompt()` en `build_llm_prompt()`
- [ ] Agregar `monthly_income` al context summary
- [ ] Agregar `dicom_status` al context summary
- [ ] Agregar `calificacion` al context summary
- [ ] Actualizar formato de visualización

---

### 2.5 Crear Middleware de Permisos
**Archivo:** `backend/app/middleware/permissions.py`

**Implementar:**
```python
class Permissions:
    
    @staticmethod
    def require_superadmin(current_user: dict = Depends(get_current_user)):
        """Solo superadmin"""
        if current_user.get("role") != "superadmin":
            raise HTTPException(403, "Requiere rol superadmin")
        return current_user
    
    @staticmethod
    def require_admin(current_user: dict = Depends(get_current_user)):
        """Admin o superadmin"""
        if current_user.get("role") not in ["admin", "superadmin"]:
            raise HTTPException(403, "Requiere rol admin")
        return current_user
    
    @staticmethod
    def require_same_broker(current_user: dict, broker_id: int):
        """Verifica que el usuario pertenezca al broker"""
        if current_user.get("role") == "superadmin":
            return True
        if current_user.get("broker_id") != broker_id:
            raise HTTPException(403, "No tienes acceso a este broker")
        return True
```

**Checklist:**
- [ ] Crear archivo `permissions.py`
- [ ] Implementar `require_superadmin()`
- [ ] Implementar `require_admin()`
- [ ] Implementar `require_same_broker()`

---

## 3️⃣ RUTAS/ENDPOINTS (Alta Prioridad)

### 3.1 Crear Rutas de Brokers (Superadmin)
**Archivo:** `backend/app/routes/brokers.py`

**Endpoints:**
```python
POST   /api/brokers                  # Crear broker (superadmin)
GET    /api/brokers                  # Listar brokers
GET    /api/brokers/{id}             # Obtener broker
PUT    /api/brokers/{id}             # Actualizar broker (superadmin)
DELETE /api/brokers/{id}             # Desactivar broker (superadmin)
```

**Checklist:**
- [ ] Crear archivo `brokers.py`
- [ ] Implementar POST para crear broker
- [ ] Implementar GET para listar (filtrar por rol)
- [ ] Implementar GET by ID
- [ ] Implementar PUT para actualizar
- [ ] Implementar DELETE (soft delete)
- [ ] Aplicar permisos con `Permissions.require_superadmin`

---

### 3.2 Crear Rutas de Configuración del Broker (Admin)
**Archivo:** `backend/app/routes/broker_config.py`

**Endpoints:**
```python
GET  /api/broker/config              # Obtener toda la configuración
PUT  /api/broker/config/prompt       # Actualizar prompts (admin)
PUT  /api/broker/config/leads        # Actualizar calificación (admin)
GET  /api/broker/config/prompt/preview  # Preview del prompt
GET  /api/broker/config/defaults     # Valores por defecto
```

**Checklist:**
- [ ] Crear archivo `broker_config.py`
- [ ] Implementar GET config completa
- [ ] Implementar PUT config/prompt
- [ ] Implementar PUT config/leads
- [ ] Implementar GET prompt preview
- [ ] Implementar GET defaults
- [ ] Aplicar permisos con `Permissions.require_admin`

---

### 3.3 Crear Rutas de Usuarios del Broker (Admin)
**Archivo:** `backend/app/routes/broker_users.py`

**Endpoints:**
```python
GET    /api/broker/users             # Listar usuarios del broker
POST   /api/broker/users             # Crear usuario del broker
PUT    /api/broker/users/{id}        # Actualizar usuario
DELETE /api/broker/users/{id}        # Desactivar usuario
```

**Checklist:**
- [ ] Crear archivo `broker_users.py`
- [ ] Implementar GET usuarios (filtrar por broker_id)
- [ ] Implementar POST crear usuario (validar rol)
- [ ] Implementar PUT actualizar usuario
- [ ] Implementar DELETE desactivar usuario
- [ ] Aplicar permisos con `Permissions.require_admin`

---

### 3.4 Actualizar Rutas de Leads
**Archivo:** `backend/app/routes/leads.py`

**Cambios:**
```python
# En GET /api/v1/leads:
# Filtrar según rol del usuario:
if current_user["role"] == "agent":
    # Solo leads asignados a él
    leads = await get_leads_by_agent(db, current_user["id"])
elif current_user["role"] == "admin":
    # Todos los leads del broker
    leads = await get_leads_by_broker(db, current_user["broker_id"])
else:  # superadmin
    # Todos los leads
    leads = await get_all_leads(db)

# AGREGAR endpoints:
PUT /api/v1/leads/{id}/assign        # Asignar lead a agente (admin)
PUT /api/v1/leads/{id}/pipeline      # Mover etapa manualmente
POST /api/v1/leads/{id}/recalculate  # Recalcular calificación
```

**Checklist:**
- [ ] Actualizar GET leads con filtrado por rol
- [ ] Crear PUT /assign para asignar leads
- [ ] Crear PUT /pipeline para mover etapas
- [ ] Crear POST /recalculate para recalcular calificación

---

### 3.5 Actualizar Rutas de Chat
**Archivo:** `backend/app/routes/chat.py`

**Cambios:**
```python
# En test_chat endpoint:
# 1. Obtener broker_id del lead
broker_id = lead.broker_id

# 2. Usar BrokerConfigService para build_llm_prompt
prompt = await LeadContextService.build_llm_prompt(
    lead_context=lead_context,
    new_message=message,
    db=db,
    broker_id=broker_id  # AGREGAR esto
)

# 3. Después de respuesta del LLM, actualizar pipeline automáticamente
await PipelineService.actualizar_pipeline_stage(db, lead)
```

**Checklist:**
- [ ] Pasar `broker_id` a `build_llm_prompt()`
- [ ] Llamar `actualizar_pipeline_stage()` después de cada interacción
- [ ] Extraer datos financieros del mensaje (monthly_income, dicom_status)

---

## 4️⃣ AUTENTICACIÓN Y JWT (Media Prioridad)

### 4.1 Actualizar Generación de JWT
**Archivo:** `backend/app/middleware/auth.py` o donde se genere el token

**Cambios:**
```python
# Al generar token, incluir:
token_data = {
    "user_id": user.id,
    "email": user.email,
    "role": user.role,        # AGREGAR
    "broker_id": user.broker_id  # AGREGAR
}
```

**Checklist:**
- [ ] Agregar `role` al payload del JWT
- [ ] Agregar `broker_id` al payload del JWT
- [ ] Actualizar función `get_current_user()` para retornar estos campos

---

## 5️⃣ AUTOMATIZACIONES (Baja Prioridad)

### 5.1 Hooks y Triggers

**Implementar:**
1. **Hook after_update en Lead:**
   - Llamar `PipelineService.actualizar_pipeline_stage()` automáticamente

2. **Notificaciones:**
   - Cuando `calificacion = "CALIFICADO"` → notificar al agente asignado
   - Cuando `pipeline_stage = "agendado"` → enviar email de confirmación

3. **Scheduler:**
   - Alertas de estancamiento (leads > 7 días en perfilamiento)
   - Seguimientos programados para leads POTENCIAL

**Checklist:**
- [ ] Crear hook after_update en Lead
- [ ] Implementar notificaciones push/email
- [ ] Crear scheduler con Celery para alertas
- [ ] Programar seguimientos automáticos

---

## 6️⃣ SCHEMAS PYDANTIC (Media Prioridad)

### 6.1 Crear Schemas de Broker
**Archivo:** `backend/app/schemas/broker.py`

```python
class BrokerCreate(BaseModel):
    name: str
    slug: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    # ... otros campos

class BrokerResponse(BaseModel):
    id: int
    name: str
    slug: str
    is_active: bool
    created_at: datetime
    # ... otros campos

class PromptConfigUpdate(BaseModel):
    agent_name: Optional[str]
    business_context: Optional[str]
    behavior_rules: Optional[str]
    # ... otros campos de las 8 secciones

class LeadConfigUpdate(BaseModel):
    field_weights: Optional[Dict[str, int]]
    cold_max_score: Optional[int]
    # ... otros campos
```

**Checklist:**
- [ ] Crear `BrokerCreate`
- [ ] Crear `BrokerResponse`
- [ ] Crear `PromptConfigUpdate`
- [ ] Crear `LeadConfigUpdate`
- [ ] Crear `UserCreateByAdmin`

---

# 🎨 TAREAS FRONTEND

## 1️⃣ AUTENTICACIÓN Y ROLES (Alta Prioridad)

### 1.1 Actualizar Estado de Autenticación
**Archivo:** `frontend/src/store/authSlice.js`

**Cambios:**
```javascript
// Guardar role y broker_id del JWT
const authSlice = createSlice({
  name: 'auth',
  initialState: {
    user: null,
    token: null,
    role: null,        // AGREGAR
    broker_id: null,   // AGREGAR
  },
  reducers: {
    setCredentials: (state, action) => {
      const { token, user } = action.payload;
      state.token = token;
      state.user = user;
      state.role = user.role;           // AGREGAR
      state.broker_id = user.broker_id; // AGREGAR
    },
  },
});
```

**Checklist:**
- [ ] Agregar `role` al estado
- [ ] Agregar `broker_id` al estado
- [ ] Actualizar `setCredentials` para guardar estos campos
- [ ] Decodificar JWT para extraer role y broker_id

---

### 1.2 Crear ProtectedRoute
**Archivo:** `frontend/src/components/ProtectedRoute.jsx`

```jsx
export function ProtectedRoute({ children, allowedRoles = [] }) {
  const { user, role, isLoading } = useAuth();
  
  if (isLoading) return <div>Cargando...</div>;
  if (!user) return <Navigate to="/login" />;
  
  // Verificar rol
  if (allowedRoles.length > 0 && !allowedRoles.includes(role)) {
    return <Navigate to="/leads" />;
  }
  
  return children;
}
```

**Checklist:**
- [ ] Crear componente `ProtectedRoute`
- [ ] Verificar roles permitidos
- [ ] Redirigir si no tiene permiso

---

### 1.3 Actualizar NavBar con Filtrado por Rol
**Archivo:** `frontend/src/components/NavBar.jsx`

**Cambios:**
```javascript
const navigation = [
  { name: 'Dashboard', href: '/dashboard', roles: ['admin'] },
  { name: 'Leads', href: '/leads', roles: ['admin', 'agent'] },
  { name: 'Pipeline', href: '/pipeline', roles: ['admin', 'agent'] },
  { name: 'Campañas', href: '/campaigns', roles: ['admin', 'agent'] },
  { name: 'Configuración', href: '/settings', roles: ['admin'] },
  { name: 'Usuarios', href: '/users', roles: ['admin'] },
];

// Filtrar según rol del usuario
const userNav = navigation.filter(item => 
  item.roles.includes(currentUser.role)
);
```

**Checklist:**
- [ ] Definir navegación con roles
- [ ] Filtrar opciones según rol del usuario
- [ ] Mostrar icono distintivo para admin

---

## 2️⃣ PÁGINAS DE ADMINISTRACIÓN (Alta Prioridad)

### 2.1 Crear Página de Configuración
**Archivo:** `frontend/src/pages/SettingsPage.jsx`

**Estructura:**
```jsx
<SettingsPage>
  <Tabs>
    <Tab value="agent" label="🤖 Agente">
      <AgentConfigTab />
    </Tab>
    <Tab value="leads" label="📊 Calificación">
      <LeadConfigTab />
    </Tab>
    <Tab value="alerts" label="🔔 Alertas">
      <AlertsConfigTab />
    </Tab>
  </Tabs>
</SettingsPage>
```

**Checklist:**
- [ ] Crear `SettingsPage.jsx`
- [ ] Implementar sistema de tabs
- [ ] Cargar configuración al montar: `GET /api/broker/config`
- [ ] Manejar loading y errores

---

### 2.2 Crear Tab de Configuración del Agente
**Archivo:** `frontend/src/components/AgentConfigTab.jsx`

**Campos:**
```jsx
<AgentConfigTab>
  {/* Identidad */}
  <Input label="Nombre del agente" value={agent_name} />
  <Input label="Rol" value={agent_role} />
  
  {/* Contexto */}
  <Textarea label="Contexto del negocio" value={business_context} />
  
  {/* Reglas */}
  <Textarea label="Reglas de comunicación" value={behavior_rules} />
  
  {/* Restricciones */}
  <Textarea label="Restricciones" value={restrictions} />
  
  {/* Herramientas */}
  <Checkbox label="Permitir agendar citas" checked={enable_appointment_booking} />
  
  {/* Acciones */}
  <Button onClick={handlePreview}>Vista Previa</Button>
  <Button onClick={handleSave}>Guardar</Button>
</AgentConfigTab>
```

**API:**
- GET `/api/broker/config` - cargar datos
- PUT `/api/broker/config/prompt` - guardar cambios
- GET `/api/broker/config/prompt/preview` - preview

**Checklist:**
- [ ] Crear `AgentConfigTab.jsx`
- [ ] Formulario con todos los campos de las 8 secciones
- [ ] Implementar vista previa del prompt
- [ ] Guardar cambios con PUT
- [ ] Mostrar feedback de éxito/error

---

### 2.3 Crear Tab de Calificación de Leads
**Archivo:** `frontend/src/components/LeadConfigTab.jsx`

**Secciones:**
```jsx
<LeadConfigTab>
  {/* 1. Pesos de campos */}
  <Section title="Importancia de Datos">
    <Slider label="📞 Teléfono" value={weights.phone} max={50} />
    <Slider label="💰 Ingresos Mensuales" value={weights.monthly_income} max={50} />
    <Slider label="📊 DICOM" value={weights.dicom_status} max={50} />
    <Slider label="📍 Ubicación" value={weights.location} max={50} />
    {/* ... más sliders */}
  </Section>
  
  {/* 2. Umbrales */}
  <Section title="Umbrales de Calificación">
    <Input label="COLD hasta" value={cold_max_score} type="number" />
    <Input label="WARM hasta" value={warm_max_score} type="number" />
    <Input label="HOT desde" value={hot_min_score} type="number" />
  </Section>
  
  {/* 3. Prioridad */}
  <Section title="Prioridad de Preguntas">
    <DragDropList items={field_priority} onReorder={handleReorder} />
  </Section>
  
  <Button onClick={handleSave}>Guardar</Button>
</LeadConfigTab>
```

**API:**
- PUT `/api/broker/config/leads` - guardar configuración

**Checklist:**
- [ ] Crear `LeadConfigTab.jsx`
- [ ] Implementar sliders para pesos
- [ ] Implementar inputs para umbrales
- [ ] Implementar drag & drop para prioridad (o botones up/down)
- [ ] Guardar cambios
- [ ] Validar que umbrales estén en orden

---

### 2.4 Crear Tab de Alertas
**Archivo:** `frontend/src/components/AlertsConfigTab.jsx`

**Campos:**
```jsx
<AlertsConfigTab>
  <Checkbox 
    label="Notificarme cuando un lead llegue a HOT"
    checked={alert_on_hot_lead}
  />
  
  <Input 
    label="Umbral de score"
    value={alert_score_threshold}
    type="number"
  />
  
  <Input 
    label="Email para notificaciones"
    value={alert_email}
    type="email"
  />
  
  <Button onClick={handleSave}>Guardar</Button>
</AlertsConfigTab>
```

**Checklist:**
- [ ] Crear `AlertsConfigTab.jsx`
- [ ] Campos para alertas
- [ ] Guardar con PUT `/api/broker/config/leads`

---

### 2.5 Crear Página de Gestión de Usuarios
**Archivo:** `frontend/src/pages/UsersPage.jsx`

**Estructura:**
```jsx
<UsersPage>
  <Header>
    <h1>👤 Usuarios del Equipo</h1>
    <Button onClick={() => setShowModal(true)}>+ Nuevo Usuario</Button>
  </Header>
  
  <UserList>
    {users.map(user => (
      <UserCard key={user.id}>
        <div>{user.email}</div>
        <div>{user.name}</div>
        <Badge>{user.role}</Badge>
        <Button onClick={() => handleEdit(user)}>Editar</Button>
        <Button onClick={() => handleDeactivate(user.id)}>Desactivar</Button>
      </UserCard>
    ))}
  </UserList>
  
  {showModal && <UserModal onSave={handleCreate} onClose={() => setShowModal(false)} />}
</UsersPage>
```

**API:**
- GET `/api/broker/users` - listar usuarios
- POST `/api/broker/users` - crear usuario
- PUT `/api/broker/users/{id}` - actualizar usuario
- DELETE `/api/broker/users/{id}` - desactivar usuario

**Checklist:**
- [ ] Crear `UsersPage.jsx`
- [ ] Listar usuarios del broker
- [ ] Modal para crear/editar usuarios
- [ ] Selección de rol (admin/agent)
- [ ] Confirmación antes de desactivar

---

## 3️⃣ PIPELINE Y LEADS (Alta Prioridad)

### 3.1 Actualizar Pipeline Board
**Archivo:** `frontend/src/components/PipelineBoard.jsx`

**Cambios:**
```jsx
// Actualizar columnas del pipeline:
const columns = [
  { id: 'entrada', name: '🆕 Entrada', color: 'gray' },
  { id: 'perfilamiento', name: '📋 Perfilamiento', color: 'blue' },
  { id: 'calificacion_financiera', name: '💰 Calificación', color: 'yellow' },
  { id: 'agendado', name: '📅 Agendado', color: 'green' },
  { id: 'seguimiento', name: '🔄 Seguimiento', color: 'orange' },
  { id: 'ganado', name: '✅ Ganado', color: 'green' },
  { id: 'perdido', name: '❌ Perdido', color: 'red' },
];

// En cada lead card, mostrar:
<LeadCard>
  <div>{lead.name}</div>
  <StatusBadge status={lead.status} />  {/* cold/warm/hot */}
  <CalificacionBadge calificacion={lead.metadata.calificacion} />  {/* NUEVO */}
  <div>{lead.metadata.location}</div>
  <div>{lead.metadata.monthly_income && `$${lead.metadata.monthly_income.toLocaleString()}`}</div>
</LeadCard>
```

**Checklist:**
- [ ] Actualizar columnas del pipeline según nuevas etapas
- [ ] Agregar badge de `calificacion` (CALIFICADO/POTENCIAL/NO_CALIFICADO)
- [ ] Mantener badge de `status` (temperatura)
- [ ] Implementar drag & drop entre columnas (opcional)
- [ ] Llamar PUT `/api/v1/leads/{id}/pipeline` al mover

---

### 3.2 Actualizar Lead Detail
**Archivo:** `frontend/src/components/LeadDetail.jsx` o `LeadCard.jsx`

**Agregar sección:**
```jsx
<Section title="💰 Calificación Financiera">
  <InfoRow label="Ingresos mensuales">
    {lead.metadata.monthly_income 
      ? `$${lead.metadata.monthly_income.toLocaleString()}`
      : 'No registrado'
    }
  </InfoRow>
  
  <InfoRow label="Estado DICOM">
    <DicomBadge status={lead.metadata.dicom_status} />
    {lead.metadata.morosidad_amount > 0 && 
      <span> - Deuda: ${lead.metadata.morosidad_amount.toLocaleString()}</span>
    }
  </InfoRow>
  
  <InfoRow label="Calificación">
    <CalificacionBadge large calificacion={lead.metadata.calificacion} />
  </InfoRow>
</Section>
```

**Checklist:**
- [ ] Agregar sección "Calificación Financiera"
- [ ] Mostrar `monthly_income`
- [ ] Mostrar `dicom_status` con badge visual
- [ ] Mostrar `morosidad_amount` si existe
- [ ] Mostrar `calificacion` con badge destacado
- [ ] Timeline de cambios de etapa (opcional)

---

### 3.3 Actualizar Filtros de Leads
**Archivo:** `frontend/src/components/LeadFilters.jsx`

**Agregar filtros:**
```jsx
<LeadFilters>
  {/* Filtros existentes */}
  <Select label="Status" value={statusFilter} options={['cold','warm','hot']} />
  
  {/* NUEVOS filtros */}
  <Select 
    label="Etapa del Pipeline" 
    value={pipelineFilter}
    options={[
      'entrada', 'perfilamiento', 'calificacion_financiera',
      'agendado', 'seguimiento', 'ganado', 'perdido'
    ]}
  />
  
  <Select 
    label="Calificación"
    value={calificacionFilter}
    options={['CALIFICADO', 'POTENCIAL', 'NO_CALIFICADO']}
  />
  
  {/* Vista rápida */}
  <Button onClick={() => applyFilter({ 
    calificacion: 'CALIFICADO', 
    pipeline_stage: 'calificacion_financiera' 
  })}>
    🎯 Listos para Agendar
  </Button>
</LeadFilters>
```

**Checklist:**
- [ ] Agregar filtro por `pipeline_stage`
- [ ] Agregar filtro por `calificacion`
- [ ] Agregar botón "Listos para Agendar" (CALIFICADO + no agendado)
- [ ] Aplicar filtros en la query de leads

---

### 3.4 Implementar Asignación de Leads (Solo Admin)
**Archivo:** `frontend/src/components/LeadTable.jsx`

**Si es Admin:**
```jsx
<LeadTable>
  {leads.map(lead => (
    <tr key={lead.id}>
      <td>{lead.name}</td>
      <td>{lead.phone}</td>
      <td>
        {/* Solo visible para admin */}
        {role === 'admin' && (
          <AssignmentDropdown
            lead={lead}
            agents={agents}
            onAssign={(leadId, agentId) => 
              api.put(`/api/v1/leads/${leadId}/assign`, { agent_id: agentId })
            }
          />
        )}
      </td>
    </tr>
  ))}
</LeadTable>
```

**Si es Agent:**
```jsx
// Ver solo leads asignados a él
// Título: "Mis Leads" en lugar de "Leads"
<h1>🏠 Mis Leads</h1>
```

**Checklist:**
- [ ] Crear componente `AssignmentDropdown`
- [ ] Mostrar solo para admin
- [ ] Listar agentes del broker
- [ ] Llamar PUT `/api/v1/leads/{id}/assign`
- [ ] Actualizar lista después de asignar
- [ ] Mostrar "Mis Leads" para agents

---

## 4️⃣ COMPONENTES REUTILIZABLES (Media Prioridad)

### 4.1 Crear Badges Visuales

**Archivos:** `frontend/src/components/ui/`

```jsx
// StatusBadge.jsx - Temperatura (cold/warm/hot)
<StatusBadge status="hot" />
// 🔥 HOT (rojo), 🌡️ WARM (amarillo), 🔵 COLD (azul)

// CalificacionBadge.jsx - Calificación financiera
<CalificacionBadge calificacion="CALIFICADO" />
// ✅ CALIFICADO (verde), ⚠️ POTENCIAL (amarillo), ❌ NO_CALIFICADO (rojo)

// DicomBadge.jsx - Estado DICOM
<DicomBadge status="clean" />
// ✅ Limpio, ⚠️ Con deuda, ❓ Desconocido
```

**Checklist:**
- [ ] Crear `StatusBadge.jsx`
- [ ] Crear `CalificacionBadge.jsx`
- [ ] Crear `DicomBadge.jsx`
- [ ] Usar colores consistentes (verde/amarillo/rojo)

---

### 4.2 Crear Componente de Tabs
**Archivo:** `frontend/src/components/ui/Tabs.jsx`

```jsx
<Tabs value={activeTab} onChange={setActiveTab}>
  <Tab value="agent" label="🤖 Agente" />
  <Tab value="leads" label="📊 Calificación" />
</Tabs>
```

**Checklist:**
- [ ] Crear componente `Tabs`
- [ ] Crear componente `Tab`
- [ ] Manejar cambio de tab activo

---

## 5️⃣ SERVICIOS API (Media Prioridad)

### 5.1 Actualizar API Service
**Archivo:** `frontend/src/services/api.js`

**Agregar endpoints:**
```javascript
// Brokers (superadmin)
export const brokers = {
  list: () => api.get('/brokers'),
  create: (data) => api.post('/brokers', data),
  get: (id) => api.get(`/brokers/${id}`),
  update: (id, data) => api.put(`/brokers/${id}`, data),
  delete: (id) => api.delete(`/brokers/${id}`),
};

// Configuración del broker (admin)
export const brokerConfig = {
  get: () => api.get('/broker/config'),
  updatePrompt: (data) => api.put('/broker/config/prompt', data),
  updateLeads: (data) => api.put('/broker/config/leads', data),
  previewPrompt: () => api.get('/broker/config/prompt/preview'),
  getDefaults: () => api.get('/broker/config/defaults'),
};

// Usuarios del broker (admin)
export const brokerUsers = {
  list: () => api.get('/broker/users'),
  create: (data) => api.post('/broker/users', data),
  update: (id, data) => api.put(`/broker/users/${id}`, data),
  delete: (id) => api.delete(`/broker/users/${id}`),
};

// Leads - actualizar
export const leads = {
  // ... existentes
  assign: (id, agentId) => api.put(`/v1/leads/${id}/assign`, { agent_id: agentId }),
  movePipeline: (id, stage) => api.put(`/v1/leads/${id}/pipeline`, { stage }),
  recalculate: (id) => api.post(`/v1/leads/${id}/recalculate`),
};
```

**Checklist:**
- [ ] Agregar endpoints de brokers
- [ ] Agregar endpoints de broker config
- [ ] Agregar endpoints de broker users
- [ ] Agregar endpoints de leads (assign, movePipeline, recalculate)

---

## 6️⃣ RUTAS Y NAVEGACIÓN (Media Prioridad)

### 6.1 Actualizar App.jsx con Nuevas Rutas
**Archivo:** `frontend/src/App.jsx`

```jsx
<Routes>
  {/* Rutas existentes */}
  <Route path="/login" element={<Login />} />
  <Route path="/leads" element={<ProtectedRoute><LeadsPage /></ProtectedRoute>} />
  <Route path="/pipeline" element={<ProtectedRoute><PipelineBoard /></ProtectedRoute>} />
  
  {/* NUEVAS rutas - Solo Admin */}
  <Route 
    path="/settings" 
    element={
      <ProtectedRoute allowedRoles={['admin']}>
        <SettingsPage />
      </ProtectedRoute>
    } 
  />
  
  <Route 
    path="/users" 
    element={
      <ProtectedRoute allowedRoles={['admin']}>
        <UsersPage />
      </ProtectedRoute>
    } 
  />
  
  {/* NUEVA ruta - Solo Superadmin (futuro) */}
  <Route 
    path="/admin/brokers" 
    element={
      <ProtectedRoute allowedRoles={['superadmin']}>
        <BrokersPage />
      </ProtectedRoute>
    } 
  />
</Routes>
```

**Checklist:**
- [ ] Agregar ruta `/settings` (solo admin)
- [ ] Agregar ruta `/users` (solo admin)
- [ ] Agregar ruta `/admin/brokers` (solo superadmin, opcional)
- [ ] Proteger todas las rutas con `ProtectedRoute`

---

# 📊 PRIORIZACIÓN Y ORDEN DE IMPLEMENTACIÓN

## FASE 1: FUNDAMENTOS (Semana 1-2)
**Backend:**
1. ✅ Crear modelos de Broker (broker.py)
2. ✅ Actualizar modelo User
3. ✅ Crear migración principal
4. ✅ Crear BrokerConfigService básico
5. ✅ Crear middleware de Permisos
6. ✅ Actualizar JWT con role y broker_id

**Frontend:**
1. ✅ Actualizar estado de auth (role, broker_id)
2. ✅ Crear ProtectedRoute
3. ✅ Actualizar NavBar con filtrado por rol

**Testing:**
- [ ] Crear broker default
- [ ] Crear admin de prueba
- [ ] Crear agent de prueba
- [ ] Verificar que el filtrado de navegación funciona

---

## FASE 2: CONFIGURACIÓN (Semana 2-3)
**Backend:**
1. ✅ Crear rutas de broker config
2. ✅ Completar BrokerConfigService.build_system_prompt()
3. ✅ Integrar en LeadContextService
4. ✅ Crear rutas de broker users

**Frontend:**
1. ✅ Crear SettingsPage con tabs
2. ✅ Crear AgentConfigTab
3. ✅ Crear LeadConfigTab
4. ✅ Crear AlertsConfigTab
5. ✅ Crear UsersPage

**Testing:**
- [ ] Configurar prompts desde el admin panel
- [ ] Ver preview del prompt
- [ ] Configurar pesos de scoring
- [ ] Crear usuarios agent desde admin

---

## FASE 3: PIPELINE Y CALIFICACIÓN (Semana 3-4)
**Backend:**
1. ✅ Crear PipelineService
2. ✅ Actualizar ScoringService con nuevos campos
3. ✅ Crear endpoints de pipeline
4. ✅ Integrar actualización automática de pipeline

**Frontend:**
1. ✅ Actualizar Pipeline Board con nuevas etapas
2. ✅ Agregar badges de calificación
3. ✅ Crear sección de calificación financiera en lead detail
4. ✅ Agregar filtros de pipeline y calificación
5. ✅ Implementar asignación de leads (admin)

**Testing:**
- [ ] Probar flujo completo: entrada → perfilamiento → calificación → agendado
- [ ] Verificar cálculo de calificación (CALIFICADO/POTENCIAL/NO_CALIFICADO)
- [ ] Verificar transiciones automáticas de pipeline
- [ ] Asignar leads desde admin

---

## FASE 4: AUTOMATIZACIONES (Semana 4-5)
**Backend:**
1. ✅ Implementar hooks after_update
2. ✅ Crear notificaciones
3. ✅ Crear scheduler para alertas
4. ✅ Programar seguimientos automáticos

**Testing:**
- [ ] Verificar notificaciones cuando lead es CALIFICADO
- [ ] Verificar alertas de estancamiento
- [ ] Verificar seguimientos programados

---

# 🎓 RESUMEN EJECUTIVO

## Backend: 6 Áreas Principales
1. **Modelos** (3 nuevos: Broker, BrokerPromptConfig, BrokerLeadConfig)
2. **Servicios** (3 nuevos: BrokerConfigService, PipelineService, Permissions)
3. **Rutas** (3 archivos: brokers, broker_config, broker_users + actualizar leads, chat)
4. **Auth** (Actualizar JWT con role y broker_id)
5. **Scoring** (Agregar monthly_income y dicom_status al cálculo)
6. **Automatizaciones** (Hooks, notificaciones, scheduler)

## Frontend: 5 Áreas Principales
1. **Auth y Roles** (ProtectedRoute, filtrado de navegación)
2. **Páginas Admin** (SettingsPage, UsersPage)
3. **Pipeline** (Actualizar board, agregar badges, filtros)
4. **Leads** (Calificación financiera, asignación)
5. **Componentes UI** (Badges, Tabs, modals)

## Estimación de Tiempo
- **Backend:** 3-4 semanas (1 desarrollador fulltime)
- **Frontend:** 2-3 semanas (1 desarrollador fulltime)
- **Testing e Integración:** 1 semana
- **Total:** 6-8 semanas

## Dependencias Críticas
1. Backend debe terminar Fase 1 antes que Frontend empiece Fase 2
2. Pipeline Service debe estar listo antes de actualizar Pipeline Board
3. BrokerConfigService debe estar listo antes de SettingsPage

---

# ✅ CRITERIOS DE ACEPTACIÓN

## Backend
- [ ] Se pueden crear brokers y usuarios con roles
- [ ] Admin puede configurar prompts desde la BD
- [ ] Los prompts se construyen dinámicamente desde las 8 secciones
- [ ] El scoring incluye monthly_income y dicom_status
- [ ] El pipeline se actualiza automáticamente según los datos
- [ ] La calificación (CALIFICADO/POTENCIAL/NO_CALIFICADO) se calcula correctamente
- [ ] Los agents solo ven leads asignados
- [ ] Los admins ven todos los leads del broker

## Frontend
- [ ] Admin ve opciones de Configuración y Usuarios
- [ ] Agent solo ve Leads, Pipeline, Campañas
- [ ] Se pueden configurar las 8 secciones del prompt
- [ ] Se pueden configurar pesos y umbrales de scoring
- [ ] El pipeline muestra las nuevas etapas correctamente
- [ ] Se muestran badges de calificación (CALIFICADO/POTENCIAL/NO_CALIFICADO)
- [ ] Admin puede asignar leads a agentes
- [ ] Se muestra información de calificación financiera en lead detail

---

**Documentos de Referencia:**
- `BACKEND_BROKER_CONFIG.md`
- `FRONTEND_BROKER_CONFIG.md`
- `PROMPT_PROFESIONAL_ADAPTADO.md`
- `INTEGRACION_PIPELINE_CALIFICACION.md`

