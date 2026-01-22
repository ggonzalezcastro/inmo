# Backend: Fixes Required for Settings Page

## 🚨 Problemas Encontrados

### 1. Error CORS
```
Access to XMLHttpRequest at 'http://localhost:8000/api/broker/config' 
from origin 'http://localhost:5173' has been blocked by CORS policy: 
No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

**Solución**: El backend necesita configurar CORS para permitir solicitudes desde `http://localhost:5173`.

**En `backend/app/main.py`**:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. Error 500 en `/api/broker/config`

El endpoint `/api/broker/config` está fallando con error 500.

**Posibles causas**:
1. El usuario no tiene `broker_id` en el token JWT
2. El `broker_id` en el token no existe en la base de datos
3. Las tablas `broker_prompt_config` o `broker_lead_config` no existen
4. Hay un error al consultar la base de datos

**Verificación necesaria**:
- Asegurar que el token JWT incluya `broker_id` cuando el usuario es admin
- Verificar que el broker exista en la base de datos
- Verificar que las configuraciones existan o se creen por defecto

### 3. Endpoint `/auth/me` no existe

El frontend intenta llamar a `/auth/me` pero el endpoint no existe en el backend.

**Solución**: Crear el endpoint en `backend/app/routes/auth.py`:

```python
@router.get("/me")
async def get_current_user_info(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current authenticated user information"""
    
    user_id = current_user.get("user_id") or current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not found in token")
    
    result = await db.execute(
        select(User).where(User.id == int(user_id))
    )
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
        "broker_id": user.broker_id,
        "is_active": user.is_active
    }
```

## ✅ Checklist para Backend

- [x] Configurar CORS en `main.py` ✅ **COMPLETADO** - Ya estaba configurado correctamente
- [x] Crear endpoint `/auth/me` ✅ **COMPLETADO** - Agregado en `backend/app/routes/auth.py`
- [x] Verificar que el token JWT incluya `broker_id` para usuarios admin ✅ **COMPLETADO** - Ya implementado en login/register
- [x] Verificar que el endpoint `/api/broker/config` maneje correctamente usuarios sin `broker_id` ✅ **COMPLETADO**
- [x] Crear configuraciones por defecto si no existen para un broker ✅ **COMPLETADO**

## 📋 Estado de Implementación

### ✅ Todo Completado

1. **CORS configurado**: El middleware CORS ya está correctamente configurado en `backend/app/main.py` con los orígenes necesarios.

2. **Endpoint `/auth/me` creado**: Agregado al final de `backend/app/routes/auth.py` y retorna toda la información del usuario actual.

3. **Token JWT incluye broker_id**: Ya estaba implementado en los endpoints de login y register.

4. **Endpoint `/api/broker/config` actualizado**:
   - **Para ADMIN**: Usa automáticamente su `broker_id` (comportamiento original mantenido)
   - **Para SUPERADMIN**: 
     - Debe especificar `broker_id` como query parameter: `GET /api/broker/config?broker_id=1`
     - Si no especifica `broker_id`, retorna lista de brokers disponibles para que elija
   - **Creación automática de configuraciones**: Si no existen `BrokerPromptConfig` o `BrokerLeadConfig`, se crean automáticamente con valores por defecto

5. **Crear configuraciones por defecto automáticamente**: 
   - Implementada función `_ensure_default_configs()` que crea configuraciones por defecto si no existen
   - Se ejecuta automáticamente al acceder al endpoint `/api/broker/config`

## 🔧 Cambios Realizados

### 1. `backend/app/routes/auth.py`
- ✅ Agregado endpoint `GET /auth/me` que retorna información del usuario actual

### 2. `backend/app/routes/broker_config.py`
- ✅ Actualizado endpoint `GET /api/broker/config`:
  - Acepta parámetro opcional `broker_id` en query params
  - Maneja correctamente ADMIN (usa su broker_id) y SUPERADMIN (debe especificar broker_id)
  - Crea configuraciones por defecto automáticamente si no existen
- ✅ Creada función helper `_ensure_default_configs()` para crear configuraciones por defecto

## 📝 Uso del Endpoint

**Para ADMIN:**
```
GET /api/broker/config
```
Usa automáticamente el broker_id del admin.

**Para SUPERADMIN:**
```
GET /api/broker/config?broker_id=1
```
Debe especificar el broker_id que quiere configurar.

Si superadmin no especifica broker_id:
```
GET /api/broker/config
```
Retorna lista de brokers disponibles para elegir.

## ✅ Todos los Problemas Resueltos

