# 🔍 Debug: Pipeline No Muestra Leads

## Problema
El Dashboard muestra leads correctamente, pero el Pipeline no muestra ningún lead.

## Análisis

### Dashboard (Funciona ✅)
- Usa: `GET /api/v1/leads` 
- Endpoint: `leadsAPI.getAll()`
- Funciona correctamente

### Pipeline (No funciona ❌)
- Usa: `GET /api/v1/pipeline/stages/{stage}/leads`
- Endpoint: `pipelineAPI.getLeadsByStage(stage, filters)`
- No muestra leads

## Endpoint del Backend

El endpoint existe en `backend/app/routes/pipeline.py`:

```python
@router.get("/stages/{stage}/leads")
async def get_leads_by_stage(
    stage: str,
    treatment_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get leads in a specific pipeline stage"""
    
    leads, total = await PipelineService.get_leads_by_stage(
        db=db,
        stage=stage,
        treatment_type=treatment_type,
        skip=skip,
        limit=limit
    )
    
    return {
        "stage": stage,
        "data": [LeadResponse.model_validate(lead) for lead in leads],
        "total": total,
        "skip": skip,
        "limit": limit
    }
```

## Posibles Causas

### 1. Leads sin `pipeline_stage` asignado
**Problema**: Los leads en la base de datos pueden tener `pipeline_stage = NULL`

**Solución Backend**: El servicio `PipelineService.get_leads_by_stage` debe:
- Si `stage = "entrada"`, devolver leads con `pipeline_stage IS NULL` o `pipeline_stage = "entrada"`
- Para otros stages, devolver solo leads con `pipeline_stage = stage`

### 2. Error en PipelineService
**Verificar**: `backend/app/services/pipeline_service.py`
- Método `get_leads_by_stage` debe filtrar correctamente por `pipeline_stage`
- Debe manejar el caso de `pipeline_stage IS NULL` como "entrada"

### 3. Estructura de respuesta diferente
**Verificar**: El backend devuelve:
```json
{
  "stage": "entrada",
  "data": [...],
  "total": 10,
  "skip": 0,
  "limit": 50
}
```

El frontend espera: `response.data.data`

## Cambios Aplicados en Frontend

1. ✅ Agregado logging detallado en consola
2. ✅ Manejo de errores mejorado (no falla si una etapa falla)
3. ✅ Debug info visible en la UI
4. ✅ Validación de arrays antes de renderizar

## Próximos Pasos

### Para el Backend (Agente):
1. **Verificar PipelineService.get_leads_by_stage**:
   - ¿Filtra correctamente por `pipeline_stage`?
   - ¿Maneja `pipeline_stage IS NULL` como "entrada"?

2. **Verificar datos en BD**:
   ```sql
   SELECT pipeline_stage, COUNT(*) 
   FROM leads 
   GROUP BY pipeline_stage;
   ```
   - Si todos son `NULL`, el problema es que no se asignan stages
   - Si hay stages pero no aparecen, el problema es el filtro

3. **Probar endpoint manualmente**:
   ```bash
   curl -H "Authorization: Bearer TOKEN" \
     http://localhost:8000/api/v1/pipeline/stages/entrada/leads
   ```

### Para el Frontend:
- Revisar consola del navegador para ver los logs
- Verificar Network tab para ver las respuestas del backend
- El debug info muestra cuántos leads se cargaron por etapa

## Logs Esperados en Consola

Si todo funciona, deberías ver:
```
🔍 Fetching leads for all stages with filters: {...}
✅ Stage entrada: {stage: "entrada", data: [...], total: 10, ...}
📊 Stage entrada: 10 leads loaded
✅ Total leads loaded across all stages: 50
```

Si hay errores:
```
❌ Error fetching leads for stage entrada: {...}
```

---

**El frontend está listo con logging detallado. El problema probablemente está en el backend (PipelineService o datos sin pipeline_stage).**


