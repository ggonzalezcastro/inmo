# 🐛 ERROR BACKEND: Validación de Metadata en LeadResponse

## Error Identificado

El endpoint `/api/v1/pipeline/stages/{stage}/leads` está devolviendo un **400 Bad Request** con el siguiente error:

```
1 validation error for LeadResponse
metadata
  Input should be a valid dictionary [type=dict_type, input_value=..., input_type=...]
```

## Causa

El schema `LeadResponse` en `backend/app/schemas/lead.py` está validando que `metadata` sea un diccionario, pero el modelo `Lead` en la base de datos tiene `lead_metadata` (no `metadata`), y cuando se serializa puede estar llegando como `None` o con un tipo incorrecto.

## Ubicación del Problema

**Archivo**: `backend/app/routes/pipeline.py`  
**Línea**: ~100 (en `get_leads_by_stage`)

```python
return {
    "stage": stage,
    "data": [LeadResponse.model_validate(lead) for lead in leads],
    "total": total,
    "skip": skip,
    "limit": limit
}
```

## Solución Requerida

### Opción 1: Ajustar el Schema (Recomendado)

En `backend/app/schemas/lead.py`, asegúrate de que `LeadResponse` maneje correctamente `metadata`:

```python
class LeadResponse(LeadBase):
    id: int
    status: LeadStatusEnum
    lead_score: float
    last_contacted: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    metadata: dict = {}  # Asegurar default vacío
    
    class Config:
        from_attributes = True
        
    @validator('metadata', pre=True)
    def validate_metadata(cls, v):
        if v is None:
            return {}
        if isinstance(v, dict):
            return v
        # Si viene como lead_metadata desde el modelo
        return {}
```

### Opción 2: Mapear lead_metadata a metadata

En `backend/app/routes/pipeline.py`, antes de crear `LeadResponse`:

```python
from app.schemas.lead import LeadResponse

leads_data = []
for lead in leads:
    lead_dict = {
        "id": lead.id,
        "phone": lead.phone,
        "name": lead.name,
        "email": lead.email,
        "tags": lead.tags if lead.tags else [],
        "metadata": lead.lead_metadata if lead.lead_metadata else {},  # Mapear aquí
        "status": lead.status,
        "lead_score": lead.lead_score,
        "last_contacted": lead.last_contacted,
        "created_at": lead.created_at,
        "updated_at": lead.updated_at,
    }
    leads_data.append(LeadResponse(**lead_dict))

return {
    "stage": stage,
    "data": leads_data,
    "total": total,
    "skip": skip,
    "limit": limit
}
```

### Opción 3: Usar model_dump() con alias

Si el modelo tiene `lead_metadata` pero el schema espera `metadata`:

```python
leads_data = []
for lead in leads:
    lead_dict = lead.__dict__.copy()
    if 'lead_metadata' in lead_dict:
        lead_dict['metadata'] = lead_dict.pop('lead_metadata', {}) or {}
    leads_data.append(LeadResponse(**lead_dict))
```

## Verificación

Después de aplicar el fix:

1. **Probar endpoint**:
   ```bash
   curl -H "Authorization: Bearer TOKEN" \
     http://localhost:8000/api/v1/pipeline/stages/entrada/leads
   ```

2. **Debería devolver**:
   ```json
   {
     "stage": "entrada",
     "data": [...],
     "total": 10,
     "skip": 0,
     "limit": 50
   }
   ```

3. **Sin errores 400**

## Nota Adicional

El frontend ya está filtrando parámetros vacíos (como `search=`), así que ese problema está resuelto.

---

**Este es un error del backend que necesita ser corregido para que el pipeline funcione.**

