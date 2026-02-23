# 🐛 BUG BACKEND: Número de Teléfono Ficticio en Chat

## Problema

Cuando el usuario escribe "hola" en el chat, el backend **inmediatamente crea un lead con un número de teléfono ficticio aleatorio**.

**Código problemático** (línea ~51-57 en `backend/app/routes/chat.py`):

```python
else:
    # Create a test lead with valid phone format
    from app.schemas.lead import LeadCreate
    import random
    # Generate a valid test phone number
    test_phone = f"+569{random.randint(10000000, 99999999)}"
    lead_data = LeadCreate(
        phone=test_phone,
        name="Test User",
        tags=["test", "chat"]
    )
    lead = await LeadService.create_lead(db, lead_data)
```

## Impacto

- ❌ Muestra un número ficticio inmediatamente
- ❌ Confunde al usuario (parece que ya capturó el teléfono)
- ❌ No refleja el estado real de captura de datos

## Solución Recomendada

### Opción 1: Crear lead sin teléfono (Recomendado)

```python
else:
    # Create a test lead without phone - will be captured during conversation
    from app.schemas.lead import LeadCreate
    
    # Use a placeholder that indicates it's not a real phone
    lead_data = LeadCreate(
        phone=None,  # O usar un placeholder como "pending_capture"
        name=None,   # También sin nombre inicial
        tags=["test", "chat", "web_chat"]
    )
    lead = await LeadService.create_lead(db, lead_data)
```

**Problema**: El modelo `Lead` requiere `phone` como NOT NULL.

### Opción 2: Usar placeholder identificable

```python
else:
    # Create a test lead with identifiable placeholder
    from app.schemas.lead import LeadCreate
    
    lead_data = LeadCreate(
        phone="telegram_pending_web_chat",  # Placeholder identificable
        name=None,  # Sin nombre hasta que se capture
        tags=["test", "chat", "web_chat"]
    )
    lead = await LeadService.create_lead(db, lead_data)
```

Luego, cuando se capture el teléfono real, actualizarlo (el código ya tiene lógica para esto en línea 142-146).

### Opción 3: Permitir phone NULL en el modelo

Modificar el modelo `Lead` para permitir `phone = NULL` inicialmente:

```python
phone = Column(String(20), unique=True, nullable=True, index=True)  # nullable=True
```

Y luego actualizar cuando se capture.

## Solución Aplicada en Frontend

El frontend ahora:
- ✅ Detecta números ficticios (que empiezan con `telegram_` o `+569999`)
- ✅ No muestra números ficticios en la UI
- ✅ Muestra "Esperando que el cliente lo proporcione" en lugar del número ficticio
- ✅ Solo cuenta como "capturado" cuando es un número real

## Verificación

Después de aplicar el fix del backend:

1. Escribir "hola" en el chat
2. Verificar que NO aparezca un número de teléfono
3. Proporcionar el teléfono en la conversación
4. Verificar que SÍ aparezca cuando se capture realmente

---

**El frontend ya está preparado para no mostrar números ficticios. El backend necesita dejar de generarlos.**

