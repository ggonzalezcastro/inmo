# 🐛 BUG: Pipeline No Muestra Leads - Backend

## Problema Identificado

El endpoint `/api/v1/pipeline/stages/{stage}/leads` no devuelve leads porque el servicio `PipelineService.get_leads_by_stage` solo filtra por `pipeline_stage == stage`.

**Código actual (línea ~85 en `backend/app/services/pipeline_service.py`):**

```python
query = select(Lead).where(Lead.pipeline_stage == stage)
```

## Causa Raíz

Si los leads en la base de datos tienen `pipeline_stage = NULL` (que es el valor por defecto cuando se crean), **NO aparecerán en ninguna etapa** porque la query busca coincidencias exactas.

## Solución Requerida

Modificar `PipelineService.get_leads_by_stage` para que:

1. **Para la etapa "entrada"**: Incluya leads con `pipeline_stage IS NULL` O `pipeline_stage = "entrada"`
2. **Para otras etapas**: Incluya solo leads con `pipeline_stage = stage`

### Código Corregido

```python
@staticmethod
async def get_leads_by_stage(
    db: AsyncSession,
    stage: str,
    broker_id: Optional[int] = None,
    treatment_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
) -> tuple[List[Lead], int]:
    """Get leads in a specific pipeline stage"""
    
    if stage not in PIPELINE_STAGES:
        raise ValueError(f"Invalid pipeline stage: {stage}")
    
    # Para "entrada", incluir leads con pipeline_stage NULL o "entrada"
    if stage == "entrada":
        query = select(Lead).where(
            or_(
                Lead.pipeline_stage == None,
                Lead.pipeline_stage == "entrada"
            )
        )
        count_query = select(func.count(Lead.id)).where(
            or_(
                Lead.pipeline_stage == None,
                Lead.pipeline_stage == "entrada"
            )
        )
    else:
        query = select(Lead).where(Lead.pipeline_stage == stage)
        count_query = select(func.count(Lead.id)).where(Lead.pipeline_stage == stage)
    
    if broker_id:
        # Filtrar por broker si es necesario
        pass
    
    if treatment_type:
        query = query.where(Lead.treatment_type == treatment_type)
        count_query = count_query.where(Lead.treatment_type == treatment_type)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination
    query = query.order_by(desc(Lead.stage_entered_at)).offset(skip).limit(limit)
    
    result = await db.execute(query)
    leads = result.scalars().all()
    
    return leads, total
```

### Import Necesario

Asegúrate de tener en `backend/app/services/pipeline_service.py`:

```python
from sqlalchemy import or_
```

## Verificación

Después de aplicar el fix:

1. **Verificar en BD**:
   ```sql
   SELECT pipeline_stage, COUNT(*) 
   FROM leads 
   GROUP BY pipeline_stage;
   ```

2. **Probar endpoint**:
   ```bash
   curl -H "Authorization: Bearer TOKEN" \
     http://localhost:8000/api/v1/pipeline/stages/entrada/leads
   ```

3. **Debería devolver**:
   - Todos los leads con `pipeline_stage IS NULL`
   - Todos los leads con `pipeline_stage = "entrada"`

## Impacto

- ✅ Los leads existentes (con `pipeline_stage = NULL`) aparecerán en "entrada"
- ✅ El pipeline funcionará correctamente
- ✅ No afecta otras etapas (solo "entrada" cambia)

---

**Este es un bug del backend que necesita ser corregido para que el pipeline funcione.**


