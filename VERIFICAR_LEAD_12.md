# 🔍 Verificar Lead ID 12 con nombre "andres"

## Métodos para Verificar

### Método 1: Desde el Frontend (Más fácil)

1. Abre el navegador en `http://localhost:5173`
2. Ve a `/dashboard`
3. Busca en la tabla de leads el ID 12
4. O usa el filtro de búsqueda para buscar "andres"

### Método 2: Desde el Backend API

Si el servidor backend está corriendo:

```bash
# Obtener lead con ID 12
curl -H "Authorization: Bearer TU_TOKEN" \
  http://localhost:8000/api/v1/leads/12

# Buscar leads con nombre "andres"
curl -H "Authorization: Bearer TU_TOKEN" \
  "http://localhost:8000/api/v1/leads?search=andres"
```

### Método 3: Desde la Base de Datos (Requiere PostgreSQL corriendo)

```bash
# Iniciar contenedor de postgres si no está corriendo
docker-compose up -d postgres

# Consultar lead con ID 12
docker-compose exec postgres psql -U lead_user -d lead_agent -c \
  "SELECT id, name, phone, email, pipeline_stage, lead_score FROM leads WHERE id = 12;"

# Buscar leads con nombre "andres"
docker-compose exec postgres psql -U lead_user -d lead_agent -c \
  "SELECT id, name, phone, email, pipeline_stage FROM leads WHERE LOWER(name) LIKE '%andres%';"
```

### Método 4: Script Python (Requiere entorno virtual activo)

```bash
cd backend
source venv/bin/activate  # o el nombre de tu venv
cd ..
python3 check_lead.py
```

## Información a Verificar

Para el lead con ID 12, verifica:
- ✅ ¿Existe el lead?
- ✅ ¿El nombre contiene "andres"?
- ✅ ¿Qué `pipeline_stage` tiene? (puede ser `NULL`)
- ✅ ¿Aparece en el pipeline del frontend?

## Nota Importante

Si el lead tiene `pipeline_stage = NULL`, **NO aparecerá en el pipeline** hasta que:
1. Se aplique el fix del backend (ver `BACKEND_PIPELINE_FIX.md`)
2. O se asigne manualmente un `pipeline_stage` al lead

## Si el Lead Existe pero No Aparece en el Pipeline

1. Verifica que el backend tenga el fix de `pipeline_stage IS NULL` para "entrada"
2. Verifica que el error de validación de `metadata` esté resuelto (ver `BACKEND_METADATA_VALIDATION_ERROR.md`)
3. Revisa la consola del navegador para ver errores

---

**El script `check_lead.py` está listo para usar cuando tengas el entorno virtual activo.**

