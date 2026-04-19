# Property Search — Sistema de Búsqueda Híbrida

**Versión:** 1.0
**Fecha:** 2026-04-18
**Proyecto:** AI Lead Agent Pro — Inmo CRM
**Servicio:** `app/services/properties/search_service.py`

---

## 1. Descripción General

El sistema de búsqueda de propiedades combina **filtros SQL estructurados** con **búsqueda semántica por embeddings** usando **Reciprocal Rank Fusion (RRF)** para fusionar ambos rankings en un resultado final ordenada.

**Flujo completo:**

```
Lead (mensaje natural)
        │
        ▼
PropertyAgent.process()
        │
        ▼ LLM extrae parámetros con function calling
search_properties(params)
        │
        ├─ strategy="structured" → SQL filters only
        ├─ strategy="semantic"   → pgvector cosine similarity only
        └─ strategy="hybrid"     → RRF merge de ambos (DEFAULT)
        │
        ▼
[_format_property() for each result]
        │
        ▼
[dict con propiedades formateadas para el LLM]
```

---

## 2. SEARCH_PROPERTIES_TOOL

Definición de la herramienta de function calling passada al LLM:

```python
SEARCH_PROPERTIES_TOOL = {
    "name": "search_properties",
    "parameters": {
        "type": "object",
        "properties": {
            # ── SQL filters ─────────────────────────────
            "commune":         {"type": "string"},
            "city":            {"type": "string"},
            "property_type":   {"type": "string", "enum": ["departamento", "casa", "terreno", "oficina"]},
            "min_bedrooms":    {"type": "integer"},
            "max_bedrooms":    {"type": "integer"},
            "min_bathrooms":   {"type": "integer"},
            "min_price_uf":    {"type": "number"},
            "max_price_uf":    {"type": "number"},
            "min_sqm":         {"type": "number"},
            "parking":         {"type": "boolean"},
            "subsidio_eligible": {"type": "boolean"},
            # ── Semantic query ─────────────────────────
            "semantic_query":  {"type": "string"},
            # ── Strategy ───────────────────────────────
            "strategy":       {"type": "string", "enum": ["structured", "semantic", "hybrid"]},
            "limit":          {"type": "integer", "default": 5, "max": 10},
        },
        "required": ["strategy"]
    }
}
```

---

## 3. Estrategias de Búsqueda

### 3.1 `structured` — Filtros SQL

Usa filtros exactos sobre columnas de `Property`:

| Filtro | Columna SQL |
|---|---|
| `commune` | `ILIKE '%{commune}%'` |
| `property_type` | `= property_type` |
| `min_bedrooms` | `>= bedrooms` |
| `min_price_uf` | `>= price_uf` |
| `max_price_uf` | `<= price_uf` |
| `parking` | `> 0` en `parking_spots` |
| `subsidio_eligible` | `= True` |
| `min_sqm` | `>= square_meters_useful` |

Solo retorna propiedades con `status = 'available'`. Ordena por `price_uf ASC`.

### 3.2 `semantic` — Búsqueda vectorial

1. Genera embedding del `semantic_query` via Gemini `text-embedding-004`
2. Ejecuta SQL raw con operador `<=>` (cosine distance de pgvector)
3. Filtra pre-búsqueda con硬约束 opcionales (`commune`, `price_uf`, `bedrooms`)
4. Ordena por distancia coseno ASC

```sql
SELECT id, (embedding <=> :emb) AS distance
FROM properties
WHERE broker_id = :broker_id
  AND status = 'available'
  AND embedding IS NOT NULL
  AND commune ILIKE :commune   -- optional pre-filter
ORDER BY distance ASC
LIMIT 20
```

### 3.3 `hybrid` — RRF Merge (default)

Fusión de rankings de `structured` y `semantic` usando **Reciprocal Rank Fusion**:

```
RRF_score(item) = Σ  1 / (rank_item + k)  ∀ sources
```

- `k = 60` (estándar de la industria)
- `CANDIDATE_POOL = 20` candidatos por estrategia antes del merge
- `limit = 5` resultados finales (max 10)

**Normalización de scores:**

| Campo | Descripción |
|---|---|
| `_rrf_score` | Score RRF acumulado (mayor = mejor ranking) |
| `_sql_rank` | Posición en ranking SQL (1-indexed) |
| `_sem_rank` | Posición en ranking semántico (1-indexed) |
| `_sem_distance` | Distancia coseno cruda (menor = más similar) |

---

## 4. Modelo de Datos

### Tabla: `properties`

```python
class Property(Base, IdMixin, TimestampMixin):
    broker_id           # FK → brokers.id (indexed)
    name, internal_code, property_type, status
    commune, city, region, address
    latitude, longitude
    price_uf, price_clp
    bedrooms, bathrooms, parking_spots, storage_units
    square_meters_total, square_meters_useful
    floor_number, total_floors, orientation, year_built, delivery_date
    description, highlights
    amenities           # JSONB
    nearby_places      # JSONB
    images             # JSONB
    financing_options  # JSONB
    floor_plan_url, virtual_tour_url
    common_expenses_clp, subsidio_eligible
    embedding          # Vector(768) — pgvector
    published_at
    kb_entry_id        # FK → knowledge_base.id (migration source)
```

**Índices relevantes:**

| Índice | Columnas | Propósito |
|---|---|---|
| `idx_prop_broker_status` | `(broker_id, status)` | Filtrar disponibles por broker |
| `idx_prop_search` | `(broker_id, commune, bedrooms, price_uf)` | Búsqueda compuesta |
| `idx_prop_type` | `(broker_id, property_type)` | Por tipo |
| `idx_prop_price` | `(broker_id, price_uf)` | Por rango de precio |
| `idx_prop_geo` | `(latitude, longitude)` | Búsqueda geográfica |
| `idx_prop_embedding` | `IVFFlat(embedding vector_cosine_ops)` | Búsqueda vectorial |

---

## 5. Formato de Respuesta

Cada propiedad retornada incluye:

```json
{
  "id": 42,
  "name": "Depto en Las Condes",
  "internal_code": "LAS-042",
  "type": "departamento",
  "status": "available",
  "commune": "Las Condes",
  "city": "Santiago",
  "address": "Av. Apoquindo 1234",
  "price_uf": 4500,
  "price_clp": 121500000,
  "bedrooms": 3,
  "bathrooms": 2,
  "parking_spots": 2,
  "square_meters_useful": 85,
  "square_meters_total": 92,
  "floor_number": 15,
  "orientation": "nororiente",
  "highlights": "Vista panorámica, piso alto, completamente remodelado",
  "amenities": "gimnasio, piscina, quincho, salón de eventos",
  "nearby_places": "Metro Las Condes (transporte), Parque Arauco (comercial)",
  "subsidio_eligible": true,
  "common_expenses_clp": 180000,
  "virtual_tour_url": "https://...",
  "_rrf_score": 0.028,
  "_sql_rank": 1,
  "_sem_rank": 3,
  "_sem_distance": 0.23
}
```

**Campos internos (`_` prefix):** disponibles para debugging pero no mostrados al lead.

---

## 6. Fallback Chain

```
hybrid
  ├─ semantic falla → structured-only
  └─ ambos fallan → []
  
semantic
  └─ falla → structured (reintento automático)
```

---

## 7. Dependencias

| Módulo | Función |
|---|---|
| `app.models.property` | Modelo Property ORM |
| `app.services.properties.embedding` | `generate_property_query_embedding()` — Gemini text-embedding-004 |
| `app.core.cache` | Redis cache (para embeddings?) |

---

## 8. Changelog

| Fecha | Versión | Cambios |
|---|---|---|
| 2026-04-18 | 1.0 | Documento creado. Código leído de `search_service.py` (354 líneas). |
