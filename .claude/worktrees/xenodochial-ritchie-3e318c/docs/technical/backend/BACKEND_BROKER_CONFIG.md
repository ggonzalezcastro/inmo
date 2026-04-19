# Backend: Configuración de Brokers con Prompts en BD

## 📋 Objetivo

Sistema donde cada broker puede personalizar:
1. **Prompts del agente** (almacenados en BD)
2. **Criterios de calificación** (pesos, umbrales)
3. **Alertas**
4. **Gestión de usuarios con roles**

---

## 👥 Sistema de Roles

### Roles por Broker

```
┌─────────────────────────────────────────────────────────────────┐
│                         BROKER                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  👔 ADMIN (Administrador del Broker)                           │
│  ├── Configuración del agente IA (prompts)                     │
│  ├── Configuración de calificación de leads                    │
│  ├── Gestión de usuarios del broker                            │
│  ├── Dashboard general / métricas                              │
│  └── Vista de lo que ve el agente inmobiliario                 │
│                                                                 │
│  🏠 AGENT (Agente Inmobiliario)                                │
│  ├── Ver leads asignados                                       │
│  ├── Pipeline de ventas                                        │
│  ├── Campañas                                                  │
│  ├── Chat con leads                                            │
│  └── Agendar citas                                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Permisos por Rol

| Funcionalidad | ADMIN | AGENT |
|---------------|-------|-------|
| Ver leads | ✅ (todos) | ✅ (asignados) |
| Editar leads | ✅ | ✅ (asignados) |
| Pipeline | ✅ | ✅ |
| Campañas | ✅ | ✅ (solo ver) |
| Chat con leads | ✅ | ✅ |
| Agendar citas | ✅ | ✅ |
| **Config. Agente IA** | ✅ | ❌ |
| **Config. Calificación** | ✅ | ❌ |
| **Config. Alertas** | ✅ | ❌ |
| **Gestión usuarios** | ✅ | ❌ |
| **Dashboard métricas** | ✅ | ❌ |

---

## 🎯 Estructura del System Prompt (8 secciones)

```
1. ROL/IDENTIDAD      → Quién es el agente
2. CONTEXTO           → Qué ofrece la empresa
3. OBJETIVO           → Qué debe lograr
4. DATOS A RECOPILAR  → Lista ordenada de campos
5. REGLAS             → Cómo comunicarse
6. RESTRICCIONES      → Qué NO hacer
7. HERRAMIENTAS       → Funciones disponibles
8. FORMATO            → Cómo estructurar respuestas
```

---

## 📊 Modelos de BD

### 1. brokers
```sql
CREATE TABLE brokers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    slug VARCHAR(100) UNIQUE,
    phone VARCHAR(50),
    email VARCHAR(200),
    logo_url VARCHAR(500),
    website VARCHAR(500),
    address TEXT,
    timezone VARCHAR(50),
    currency VARCHAR(10),
    country VARCHAR(50),
    language VARCHAR(10),
    subscription_plan VARCHAR(50),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);
```

### 2. broker_prompt_configs ⭐ (Prompts en BD)
```sql
CREATE TABLE broker_prompt_configs (
    id SERIAL PRIMARY KEY,
    broker_id INTEGER REFERENCES brokers(id) UNIQUE,
    
    -- Sección 1: Identidad
    agent_name VARCHAR(100) DEFAULT 'Sofía',
    agent_role VARCHAR(200) DEFAULT 'asesora inmobiliaria',
    identity_prompt TEXT,  -- Override completo de esta sección
    
    -- Sección 2: Contexto
    business_context TEXT,
    
    -- Sección 3: Objetivo
    agent_objective TEXT,
    
    -- Sección 4: Datos a recopilar
    data_collection_prompt TEXT,
    
    -- Sección 5: Reglas
    behavior_rules TEXT,
    
    -- Sección 6: Restricciones
    restrictions TEXT,
    
    -- Sección 7: Situaciones especiales
    situation_handlers JSONB,  -- {"no_interesado": "respuesta...", ...}
    
    -- Sección 8: Formato
    output_format TEXT,
    
    -- Override completo (ignora todas las secciones)
    full_custom_prompt TEXT,
    
    -- Herramientas
    enable_appointment_booking BOOLEAN DEFAULT true,
    tools_instructions TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);
```

### 3. broker_lead_configs (Calificación)
```sql
CREATE TABLE broker_lead_configs (
    id SERIAL PRIMARY KEY,
    broker_id INTEGER REFERENCES brokers(id) UNIQUE,
    
    -- Pesos de campos
    field_weights JSONB DEFAULT '{"name":10,"phone":15,"email":10,"location":15,"budget":20,"monthly_income":25,"dicom_status":20}',
    
    -- Umbrales de Score
    cold_max_score INTEGER DEFAULT 20,
    warm_max_score INTEGER DEFAULT 50,
    hot_min_score INTEGER DEFAULT 50,
    qualified_min_score INTEGER DEFAULT 75,
    
    -- Prioridad de preguntas
    field_priority JSONB DEFAULT '["name","phone","email","location","monthly_income","dicom_status","budget"]',
    
    -- ⭐ CONFIGURACIÓN DE CALIFICACIÓN FINANCIERA (NUEVO)
    
    -- Rangos de ingresos (configurable por broker)
    income_ranges JSONB DEFAULT '{
        "insufficient": {"min": 0, "max": 500000, "label": "Insuficiente"},
        "low": {"min": 500000, "max": 1000000, "label": "Bajo"},
        "medium": {"min": 1000000, "max": 2000000, "label": "Medio"},
        "good": {"min": 2000000, "max": 4000000, "label": "Bueno"},
        "excellent": {"min": 4000000, "max": null, "label": "Excelente"}
    }',
    
    -- Criterios de calificación financiera
    qualification_criteria JSONB DEFAULT '{
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
    }',
    
    -- Umbral de deuda aceptable (CLP)
    max_acceptable_debt INTEGER DEFAULT 500000,
    
    -- Alertas
    alert_on_hot_lead BOOLEAN DEFAULT true,
    alert_score_threshold INTEGER DEFAULT 70,
    alert_on_qualified BOOLEAN DEFAULT true,
    alert_email VARCHAR(200),
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);
```

### 4. Modificar tabla users
```sql
-- Agregar broker_id y actualizar role
ALTER TABLE users ADD COLUMN broker_id INTEGER REFERENCES brokers(id);

-- El campo 'role' ya existe, pero ahora tiene estos valores:
-- 'admin'  = Administrador del broker (puede configurar)
-- 'agent'  = Agente inmobiliario (solo operativo)
-- 'superadmin' = Admin del sistema (opcional, para ti)
```

### Modelo User actualizado
```python
# backend/app/models/user.py

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
import enum

class UserRole(str, enum.Enum):
    SUPERADMIN = "superadmin"  # Admin del sistema completo
    ADMIN = "admin"            # Admin del broker
    AGENT = "agent"            # Agente inmobiliario

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)  # Renombrar broker_name a name
    
    # Rol del usuario
    role = Column(String(20), default=UserRole.AGENT.value, nullable=False)
    
    # Broker al que pertenece (NULL para superadmin)
    broker_id = Column(Integer, ForeignKey("brokers.id"), nullable=True)
    
    is_active = Column(Boolean, default=True)
    
    # Relaciones
    broker = relationship("Broker", back_populates="users")
```

---

## 🏢 Endpoints de Gestión de Brokers

Los endpoints de brokers están disponibles en `/api/brokers`. El superadmin puede crear, actualizar y eliminar brokers. Los admins y agents pueden ver solo su propio broker.

### Endpoints Disponibles

```python
# backend/app/routes/brokers.py

# === BROKERS ===

POST /api/brokers
- Crear nuevo broker (solo superadmin)
- Body: { name, slug?, phone?, email?, ... }

GET /api/brokers
- Listar brokers
- Superadmin: ve todos los brokers activos
- Admin/Agent: ve solo su broker

GET /api/brokers/{broker_id}
- Obtener detalles de un broker
- Superadmin: puede ver cualquier broker
- Admin/Agent: solo su broker

PUT /api/brokers/{broker_id}
- Actualizar broker (solo superadmin)

DELETE /api/brokers/{broker_id}
- Desactivar broker (soft delete, solo superadmin)
- Establece is_active = False
```

### Crear Admin de un Broker

Para crear el admin inicial de un broker, usa el endpoint de usuarios del broker:

```python
POST /api/broker/users
- Crear usuario para el broker
- Body: { email, password, name, role: "admin" }
- Solo superadmin puede crear admins iniciales
```

### Schemas
```python
class CreateBrokerRequest(BaseModel):
    name: str           # "InmoChile S.A."
    slug: str           # "inmochile" (único, para URLs)

class CreateUserRequest(BaseModel):
    email: str
    password: str
    name: str
```

---

## 🔐 Middleware de Permisos

```python
# backend/app/middleware/permissions.py

from functools import wraps
from fastapi import HTTPException, Depends
from app.middleware.auth import get_current_user

class Permissions:
    """Decoradores para verificar permisos"""
    
    @staticmethod
    def require_admin(current_user: dict = Depends(get_current_user)):
        """Requiere rol admin o superadmin"""
        if current_user.get("role") not in ["admin", "superadmin"]:
            raise HTTPException(
                status_code=403,
                detail="Se requiere rol de administrador"
            )
        return current_user
    
    @staticmethod
    def require_same_broker(current_user: dict, broker_id: int):
        """Verifica que el usuario pertenezca al broker"""
        if current_user.get("role") == "superadmin":
            return True
        if current_user.get("broker_id") != broker_id:
            raise HTTPException(
                status_code=403,
                detail="No tienes acceso a este broker"
            )
        return True
```

### Uso en endpoints
```python
# Solo admin puede acceder a configuración
@router.put("/config/prompt")
async def update_prompt_config(
    updates: PromptConfigUpdate,
    current_user: dict = Depends(Permissions.require_admin),  # <-- Verifica rol
    db: AsyncSession = Depends(get_db)
):
    ...

# Agentes pueden ver leads (pero solo los asignados)
@router.get("/leads")
async def get_leads(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.get("role") == "agent":
        # Solo leads asignados a este agente
        leads = await get_leads_by_agent(db, current_user["id"])
    else:
        # Admin ve todos los leads del broker
        leads = await get_leads_by_broker(db, current_user["broker_id"])
    return leads
```

---

## 🔧 Servicio Principal

```python
# backend/app/services/broker_config_service.py

class BrokerConfigService:
    
    @staticmethod
    async def build_system_prompt(db, broker_id, lead_context=None) -> str:
        """Construye el prompt completo desde BD"""
        
        broker = await get_broker_with_config(db, broker_id)
        
        if broker and broker.prompt_config:
            # Si hay prompt custom completo, usarlo
            if broker.prompt_config.full_custom_prompt:
                return broker.prompt_config.full_custom_prompt
            
            # Construir desde secciones
            sections = []
            
            # 1. Identidad
            if broker.prompt_config.identity_prompt:
                sections.append(f"## ROL\n{broker.prompt_config.identity_prompt}")
            else:
                sections.append(f"## ROL\nEres {broker.prompt_config.agent_name}, {broker.prompt_config.agent_role} de {broker.name}.")
            
            # 2. Contexto
            if broker.prompt_config.business_context:
                sections.append(f"## CONTEXTO\n{broker.prompt_config.business_context}")
            else:
                sections.append("## CONTEXTO\nOfrecemos propiedades en venta y arriendo en Chile.")
            
            # 3. Objetivo
            # ... similar para cada sección
            
            return "\n\n".join(sections)
        
        return DEFAULT_SYSTEM_PROMPT
    
    @staticmethod
    async def calculate_lead_score(db, lead_data, broker_id) -> dict:
        """Calcula score usando pesos del broker"""
        
        config = await get_lead_config(db, broker_id)
        weights = config.field_weights
        
        score = 0
        if lead_data.get("name"):
            score += weights.get("name", 10)
        if lead_data.get("phone"):
            score += weights.get("phone", 15)
        if lead_data.get("email"):
            score += weights.get("email", 10)
        if lead_data.get("location"):
            score += weights.get("location", 15)
        if lead_data.get("budget"):
            score += weights.get("budget", 20)
        
        # Scoring de ingresos (usa rangos configurables)
        if lead_data.get("monthly_income"):
            income = lead_data["monthly_income"]
            income_score = BrokerConfigService._calculate_income_score(
                income, 
                config.income_ranges,
                weights.get("monthly_income", 25)
            )
            score += income_score
        
        # Scoring de DICOM
        if lead_data.get("dicom_status"):
            dicom_score = BrokerConfigService._calculate_dicom_score(
                lead_data.get("dicom_status"),
                lead_data.get("morosidad_amount", 0),
                config.max_acceptable_debt,
                weights.get("dicom_status", 20)
            )
            score += dicom_score
        
        return {"score": score, "status": determine_status(score, config)}
    
    @staticmethod
    def _calculate_income_score(income: int, income_ranges: dict, max_score: int) -> int:
        """Calcula score basado en rangos de ingreso configurables"""
        
        # Determinar en qué rango cae
        if income >= income_ranges.get("excellent", {}).get("min", 4000000):
            return max_score  # 100%
        elif income >= income_ranges.get("good", {}).get("min", 2000000):
            return int(max_score * 0.8)  # 80%
        elif income >= income_ranges.get("medium", {}).get("min", 1000000):
            return int(max_score * 0.6)  # 60%
        elif income >= income_ranges.get("low", {}).get("min", 500000):
            return int(max_score * 0.4)  # 40%
        else:
            return 0  # Insuficiente
    
    @staticmethod
    def _calculate_dicom_score(dicom_status: str, debt_amount: int, max_debt: int, max_score: int) -> int:
        """Calcula score basado en DICOM y deuda"""
        
        if dicom_status == "clean":
            return max_score  # 100%
        elif dicom_status == "has_debt":
            if debt_amount <= max_debt:
                return int(max_score * 0.5)  # 50% (deuda manejable)
            else:
                return 0  # Deuda muy alta
        else:  # unknown
            return 0
    
    @staticmethod
    async def calcular_calificacion(db, lead, broker_id) -> str:
        """
        Calcula calificación financiera usando criterios configurables del broker
        
        Returns: "CALIFICADO", "POTENCIAL", "NO_CALIFICADO"
        """
        
        config = await get_lead_config(db, broker_id)
        criteria = config.qualification_criteria
        
        metadata = lead.lead_metadata or {}
        monthly_income = metadata.get("monthly_income", 0)
        dicom_status = metadata.get("dicom_status", "unknown")
        debt_amount = metadata.get("morosidad_amount", 0)
        
        # CALIFICADO
        calificado_criteria = criteria.get("calificado", {})
        if (monthly_income >= calificado_criteria.get("min_monthly_income", 1000000) and
            dicom_status in calificado_criteria.get("dicom_status", ["clean"]) and
            debt_amount <= calificado_criteria.get("max_debt_amount", 0)):
            return "CALIFICADO"
        
        # NO_CALIFICADO (verificar primero las condiciones de rechazo)
        no_calificado_conditions = criteria.get("no_calificado", {}).get("conditions", [])
        for condition in no_calificado_conditions:
            if "monthly_income_below" in condition:
                if monthly_income < condition["monthly_income_below"]:
                    return "NO_CALIFICADO"
            if "debt_amount_above" in condition:
                if debt_amount > condition["debt_amount_above"]:
                    return "NO_CALIFICADO"
        
        # POTENCIAL (default si no es CALIFICADO ni NO_CALIFICADO)
        potencial_criteria = criteria.get("potencial", {})
        if (monthly_income >= potencial_criteria.get("min_monthly_income", 500000) and
            dicom_status in potencial_criteria.get("dicom_status", ["clean", "has_debt"]) and
            debt_amount <= potencial_criteria.get("max_debt_amount", 500000)):
            return "POTENCIAL"
        
        # Si no califica para POTENCIAL pero tampoco para NO_CALIFICADO, es POTENCIAL por defecto
        return "POTENCIAL"
    
    @staticmethod
    async def get_next_field_to_ask(db, lead_data, broker_id) -> str:
        """Siguiente campo según prioridad del broker"""
        
        config = await get_lead_config(db, broker_id)
        priority = config.field_priority  # ["name", "phone", ...]
        
        for field in priority:
            if not has_field(lead_data, field):
                return field
        return None
```

---

## 🌐 Endpoints API

### Gestión de Brokers (Superadmin)
```
POST   /api/brokers                  → Crear broker (superadmin)
GET    /api/brokers                  → Listar brokers
GET    /api/brokers/{id}             → Obtener broker
PUT    /api/brokers/{id}             → Actualizar broker (superadmin)
DELETE /api/brokers/{id}             → Desactivar broker (superadmin)
```

### Configuración del Broker (Admin)
```
GET  /api/broker/config              → Obtener toda la configuración
PUT  /api/broker/config/prompt       → Actualizar prompts (admin)
PUT  /api/broker/config/leads        → Actualizar calificación (admin)
GET  /api/broker/config/prompt/preview → Preview del prompt actual
GET  /api/broker/config/defaults     → Valores por defecto
```

### Gestión de Usuarios del Broker (Admin)
```
GET    /api/broker/users             → Listar usuarios del broker
POST   /api/broker/users             → Crear usuario del broker
PUT    /api/broker/users/{user_id}   → Actualizar usuario
DELETE /api/broker/users/{user_id}   → Desactivar usuario
```

### Schemas Pydantic
```python
class PromptConfigUpdate(BaseModel):
    agent_name: Optional[str]
    agent_role: Optional[str]
    identity_prompt: Optional[str]
    business_context: Optional[str]
    agent_objective: Optional[str]
    data_collection_prompt: Optional[str]
    behavior_rules: Optional[str]
    restrictions: Optional[str]
    situation_handlers: Optional[Dict[str, str]]
    output_format: Optional[str]
    full_custom_prompt: Optional[str]

class LeadConfigUpdate(BaseModel):
    field_weights: Optional[Dict[str, int]]
    cold_max_score: Optional[int]
    warm_max_score: Optional[int]
    hot_min_score: Optional[int]
    qualified_min_score: Optional[int]
    field_priority: Optional[List[str]]
    alert_on_hot_lead: Optional[bool]
    alert_score_threshold: Optional[int]
    alert_email: Optional[str]
```

---

## 📋 Asignación de Leads a Agentes

El modelo `Lead` ya tiene los campos necesarios:
```python
# En Lead (ya existe)
assigned_to = Column(Integer, ForeignKey("users.id"))  # ID del agente
broker_id = Column(Integer, ForeignKey("brokers.id"))  # ID del broker
```

### Lógica de Filtrado de Leads

```python
# backend/app/services/lead_service.py

async def get_leads_for_user(db: AsyncSession, user: dict) -> list:
    """
    Retorna leads según el rol del usuario:
    - superadmin: todos los leads
    - admin: todos los leads de su broker
    - agent: solo leads asignados a él
    """
    query = select(Lead)
    
    if user["role"] == "superadmin":
        # Ve todo
        pass
    elif user["role"] == "admin":
        # Solo leads de su broker
        query = query.where(Lead.broker_id == user["broker_id"])
    else:  # agent
        # Solo leads asignados a él
        query = query.where(Lead.assigned_to == user["id"])
    
    result = await db.execute(query)
    return result.scalars().all()
```

### Asignar Lead a Agente (Admin)

```python
@router.put("/leads/{lead_id}/assign")
async def assign_lead(
    lead_id: int,
    agent_id: int,
    current_user: dict = Depends(Permissions.require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Admin asigna un lead a un agente de su broker"""
    # Verificar que el agente pertenece al mismo broker
    agent = await get_user(db, agent_id)
    if agent.broker_id != current_user["broker_id"]:
        raise HTTPException(403, "El agente no pertenece a tu broker")
    
    await update_lead(db, lead_id, {"assigned_to": agent_id})
    return {"status": "assigned"}
```

### Asignación Automática (Opcional)

```python
async def auto_assign_lead(db: AsyncSession, broker_id: int, lead_id: int):
    """
    Asigna automáticamente un lead al agente con menos leads
    """
    # Obtener agentes del broker
    agents = await get_agents_by_broker(db, broker_id)
    
    if not agents:
        return None
    
    # Contar leads por agente
    agent_loads = {}
    for agent in agents:
        count = await count_leads_by_agent(db, agent.id)
        agent_loads[agent.id] = count
    
    # Asignar al que tiene menos
    least_loaded = min(agent_loads, key=agent_loads.get)
    await update_lead(db, lead_id, {"assigned_to": least_loaded})
    
    return least_loaded
```

---

## 👤 Endpoints de Gestión de Usuarios

```python
# backend/app/routes/broker_users.py

@router.get("/users")
async def get_broker_users(
    current_user: dict = Depends(Permissions.require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Lista usuarios del broker (solo admin)"""
    broker_id = current_user["broker_id"]
    users = await get_users_by_broker(db, broker_id)
    return users

@router.post("/users")
async def create_broker_user(
    user_data: CreateUserRequest,
    current_user: dict = Depends(Permissions.require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Crear usuario para el broker (solo admin)"""
    broker_id = current_user["broker_id"]
    
    # Validar que el rol sea válido (solo admin o agent)
    if user_data.role not in ["admin", "agent"]:
        raise HTTPException(400, "Rol inválido")
    
    user = await create_user(db, user_data, broker_id)
    return user

@router.put("/users/{user_id}")
async def update_broker_user(
    user_id: int,
    updates: UpdateUserRequest,
    current_user: dict = Depends(Permissions.require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Actualizar usuario del broker (solo admin)"""
    ...

@router.delete("/users/{user_id}")
async def delete_broker_user(
    user_id: int,
    current_user: dict = Depends(Permissions.require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Desactivar usuario del broker (solo admin)"""
    ...
```

### Schemas
```python
class CreateUserRequest(BaseModel):
    email: str
    password: str
    name: str
    role: str = "agent"  # "admin" o "agent"

class UpdateUserRequest(BaseModel):
    name: Optional[str]
    role: Optional[str]
    is_active: Optional[bool]
```

---

## ✅ Checklist

### Modelos
- [ ] Crear modelo `Broker`
- [ ] Crear modelo `BrokerPromptConfig`
- [ ] Crear modelo `BrokerLeadConfig`
- [ ] Actualizar modelo `User` con `broker_id` y roles

### Migración
- [ ] Crear migración para tablas de broker
- [ ] Migrar campo `role` existente a nuevos valores
- [ ] Lead ya tiene `broker_id` y `assigned_to` ✅

### Servicios
- [ ] Crear `BrokerConfigService`
- [ ] Crear middleware `Permissions`
- [ ] Actualizar `lead_service.py` con filtrado por rol

### Endpoints de Brokers
- [x] POST `/api/brokers` - Crear broker (superadmin)
- [x] GET `/api/brokers` - Listar brokers
- [x] GET `/api/brokers/{id}` - Obtener broker
- [x] PUT `/api/brokers/{id}` - Actualizar broker (superadmin)
- [x] DELETE `/api/brokers/{id}` - Desactivar broker (superadmin)

### Endpoints Admin
- [x] GET `/api/broker/config` - Ver configuración
- [x] PUT `/api/broker/config/prompt` - Actualizar prompts
- [x] PUT `/api/broker/config/leads` - Actualizar calificación
- [x] GET `/api/broker/config/prompt/preview` - Preview del prompt
- [x] GET `/api/broker/config/defaults` - Valores por defecto
- [x] GET `/api/broker/users` - Listar usuarios
- [x] POST `/api/broker/users` - Crear usuario
- [x] PUT `/api/broker/users/{id}` - Actualizar usuario
- [x] DELETE `/api/broker/users/{id}` - Desactivar usuario
- [ ] PUT `/api/v1/leads/{id}/assign` - Asignar lead a agente (pendiente)

### Integración
- [ ] Modificar `lead_context_service.py` para usar prompts de BD
- [ ] Modificar scoring para usar config de BD
- [ ] Filtrar leads por rol en `get_leads`

### Auth
- [ ] Incluir `role` y `broker_id` en el token JWT
- [ ] Actualizar `get_current_user` para incluir estos campos

---

## 🔄 Flujo Completo

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLUJO DE CONFIGURACIÓN                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1️⃣ SUPERADMIN (tú)                                            │
│     │                                                           │
│     ├── POST /api/brokers                                      │
│     │   └── Crear "InmoChile" (broker_id: 1)                   │
│     │                                                           │
│     └── POST /api/broker/users                                 │
│         └── Crear juan@inmochile.cl (role: admin, broker_id: 1)│
│                                                                 │
│  2️⃣ ADMIN DEL BROKER (Juan)                                    │
│     │                                                           │
│     ├── PUT /broker/config/prompt                              │
│     │   └── Configurar nombre, personalidad del agente IA      │
│     │                                                           │
│     ├── PUT /broker/config/leads                               │
│     │   └── Configurar pesos, umbrales, campos                 │
│     │                                                           │
│     └── POST /broker/users                                     │
│         ├── maria@inmochile.cl (role: agent)                   │
│         └── pedro@inmochile.cl (role: agent)                   │
│                                                                 │
│  3️⃣ AGENTES (María, Pedro)                                     │
│     │                                                           │
│     ├── GET /leads → Solo leads asignados a ellos              │
│     ├── GET /pipeline → Pipeline de sus leads                  │
│     └── ❌ /broker/config → 403 Forbidden                       │
│                                                                 │
│  4️⃣ LEADS ENTRANTES                                            │
│     │                                                           │
│     └── Nuevo lead llega por Telegram                          │
│         ├── Se asocia al broker (broker_id)                    │
│         ├── Se asigna a agente (auto o manual)                 │
│         └── Usa prompts/config del broker                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📝 Ejemplo de Request

```bash
PUT /api/broker/config/prompt
{
  "agent_name": "Carolina",
  "business_context": "Somos la inmobiliaria líder en Santiago. Nos especializamos en propiedades de lujo.",
  "behavior_rules": "- Sé formal\n- Usa 'usted'\n- Máximo 2 oraciones"
}
```

```bash
PUT /api/broker/config/leads
{
  "field_weights": {"name": 10, "phone": 25, "budget": 30},
  "hot_min_score": 60,
  "field_priority": ["phone", "name", "budget"]
}
```

