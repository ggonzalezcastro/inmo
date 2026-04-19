# Knowledge Base / RAG System

**Versión:** 1.0
**Fecha:** 2025-01-20
**Módulo:** `app/services/knowledge_base/`

---

## 1. Descripción General

El sistema de Knowledge Base (KB) implementa un motor de Retrieval-Augmented Generation (RAG) para enriquecer las respuestas del agente IA con documentación específica del corredor. Cada entrada KB es un fragmento de texto indexedado mediante embeddings vectoriales (pgvector) generado por **Gemini `text-embedding-004`** (768 dimensiones).

**Flujo típico:**

```
Lead message → build_llm_prompt() → RAGService.search() → kb_block
                                                              ↓
                                                       Prompt final
                                                              ↓
                                                       Gemini AI → Respuesta
```

---

## 2. Modelo de Datos

### Tabla: `knowledge_base`

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `Integer` | PK auto-incremental |
| `broker_id` | `Integer` | FK a `brokers.id`, índice compuesto |
| `title` | `String(255)` | Título del documento |
| `content` | `Text` | Contenido completo del fragmento |
| `embedding` | `Vector(768)` | Vector de embedding Gemini |
| `source_type` | `String(50)` | Categoría del contenido |
| `metadata` | `JSONB` | Datos auxiliares (alias: `kb_metadata`) |
| `created_at` | `DateTime` | Timestamp de creación |
| `updated_at` | `DateTime` | Timestamp de actualización |

### Índices

```sql
-- Índice vectorial para búsqueda por similitud coseno
CREATE INDEX idx_knowledge_base_embedding
  ON knowledge_base USING ivfflat (embedding cosine_ops)
  WITH (lists = 100);

-- Índice compuesto para filtrado por corredor y tipo
CREATE INDEX idx_knowledge_base_broker_source
  ON knowledge_base (broker_id, source_type);
```

### JSONB `metadata` (alias `kb_metadata`)

Almacena datos auxiliares según el tipo de entrada:

```python
# property: { "property_id": int, "listing_date": str, ... }
# faq: { "question": str, "views": int, ... }
# policy: { "version": str, "effective_date": str, ... }
# subsidy: { "subsidy_type": str, "amount": int, ... }
# custom: { "source_subtype": str, ... }  # ej: "resolution"
```

---

## 3. Tipos de Fuente (`source_type`)

| Valor | Descripción | Ejemplo |
|---|---|---|
| `property` | Fichas de propiedades (en desuso, usar `/properties`) | "Departamento 3 dormitorios en Providencia" |
| `faq` | Preguntas frecuentes de los clientes | "Requisitos para pedir ficha不放" |
| `policy` | Políticas y términos de la empresa | "Política de comisiones" |
| `subsidy` | Subsidios gubernamentales (ej: bono pie 0) | "Bono de Acogida DS3" |
| `custom` | Entradas personalizadas, incluyendo resoluciones de agentes | "Resolución: rechazo de crédito por DICOM" |

---

## 4. Generación de Embeddings

### Modelo

- **Proveedor:** Gemini
- **Modelo:** `text-embedding-004`
- **Dimensiones:** 768
- **Método:** `GeminiProvider.embed_content()`

### Disparo

La generación de embedding se ejecuta **en el momento** de crear o actualizar una entrada KB:

```python
# En RAGService.add_document() y RAGService.update_document()
embedding = await GeminiProvider.embed_content(content)
```

Si el contenido no cambia en una actualización (`PUT /kb/{id}`), se **conserva el embedding existente** sin regeneración.

---

## 5. Algoritmo de Búsqueda RAG

```python
async def RAGService.search(
    db: AsyncSession,
    broker_id: int,
    query: str,
    top_k: int = 3,
    source_type: Optional[str] = None,
) -> List[KnowledgeBase]:
```

### Pasos

1. **Embedding de la consulta** — Se genera un vector de 768 dims para `query` usando Gemini.
2. **Búsqueda vectorial** — Consulta SQL con operador de similitud coseno (`<=>`):

   ```sql
   SELECT * FROM knowledge_base
   WHERE broker_id = :broker_id
     AND source_type = :source_type  -- opcional
     AND embedding <=> :query_embedding < 0.4   -- similitud > 0.6
   ORDER BY embedding <=> :query_embedding
   LIMIT :top_k;
   ```

3. **Retorno** — Lista de hasta `top_k` entradas ordenadas por similitud descendente.

### Umbral de Similitud

| Métrica | Valor |
|---|---|
| Similitud mínima aceptada | `> 0.60` |
| Valor almacenado en DB (`<=>`) | `< 0.4` (distancia coseno; 0 = idéntico) |
| `top_k` por defecto | `3` |

### Índice IVFFlat

- **Tipo:** IVFFlat (Inverted File Flat)
- **Listas:** 100
- **Operador:** `cosine_ops`
- **Función de ordenamiento:** `embedding <=> query_embedding` (menor = más similar)

---

## 6. Inyección en el Prompt

### Método

```python
async def build_llm_prompt(
    db: AsyncSession,
    broker_id: int,
    query: str,
    # ...otros params
) -> str:
    kb_block = ""
    if db and broker_id:
        chunks = await RAGService.search(db, broker_id, query, top_k=3)
        kb_block = RAGService.format_for_prompt(chunks)
    # ... construir prompt
```

### Formato de Bloque KB

```
### Knowledge Base:

[Title 1]
Content of chunk 1...

[Title 2]
Content of chunk 2...

[Title 3]
Content of chunk 3...
```

### Ubicación en el Prompt

El bloque KB se inserta **antes** de la sección de conversación, permitiendo que el modelo fundamente su respuesta en la documentación del corredor.

---

## 7. Operaciones CRUD

### Crear — `POST /kb`

```python
RAGService.add_document(
    db,
    broker_id: int,
    title: str,
    content: str,
    source_type: str,
    metadata: Optional[dict] = None,
)
```

- Valida que `source_type` sea válido.
- Genera embedding del `content`.
- Persiste en BD.

### Leer — `GET /kb`

```python
RAGService.list_documents(
    db,
    broker_id: int,
    source_type: Optional[str] = None,
    offset: int = 0,
    limit: int = 20,
) -> List[KnowledgeBase]
```

- Filtra por `broker_id` y opcionalmente por `source_type`.
- Soporta paginación con `offset`/`limit`.

### Actualizar — `PUT /kb/{id}`

```python
RAGService.update_document(
    db,
    entry_id: int,
    broker_id: int,
    **updates: title, content, source_type, metadata,
)
```

- Verifica propiedad (`broker_id`).
- Si `content` cambió → regenerar embedding.
- Si `content` no cambió → conservar embedding existente.
- Actualiza `updated_at`.

### Eliminar — `DELETE /kb/{id}`

```python
RAGService.delete_document(db, entry_id: int, broker_id: int)
```

- Verifica propiedad (`broker_id`).
- Elimina la entrada y su embedding (cascade delete).
- Retorna éxito o error 404.

---

## 8. Entradas KB de Resolución (`resolution`)

Cuando un agente libera una conversación con `trainable=True` y proporciona un `resolution_summary`, el sistema persiste la resolución como entrada KB para recuperación futura:

```python
RAGService.add_document(
    db,
    broker_id,
    title=f"Resolución: {resolution_category}",
    content=resolution_summary,
    source_type="custom",
    metadata={
        "source_subtype": "resolution",
        "lead_id": lead_id,
        "agent_id": agent_id,
        "escalated_reason": escalated_reason,
        "date": datetime.now().isoformat(),
    },
)
```

**Uso:** Permite al agente IA recuperar resoluciones similares cuando enfrenta situaciones comparables en futuras conversaciones con leads.

---

## 9. Dependencias

| Componente | Rol |
|---|---|
| `GeminiProvider.embed_content()` | Generación de embeddings |
| `pgvector` (PostgreSQL extension) | Almacenamiento y búsqueda vectorial |
| `broker_id` (FK) | Aislamiento multi-tenant |
| `RAGService.search()` | Punto de entrada para búsquedas RAG |

---

## 10. Consideraciones de Diseño

- **Multi-tenant:** Toda consulta incluye `broker_id`; no hay filtrado a nivel aplicación, es enforce a nivel SQL.
- **IVFFlat vs HNSW:** Se usa IVFFlat (100 listas) como balance entre velocidad y precisión. Para datasets pequeños (<10k vectors) es suficiente.
- **Sin re-indexación automática:** Cuando el contenido cambia, el embedding se regenera solo si `content` cambió (no se hace `UPDATE` del embedding sin cambio).
- **PII en embeddings:** El semantic cache (Redis) se encarga de skip messages con PII antes de generar embeddings; la KB almacena contenido del broker que típicamente no contiene PII.
- **Resoluciones:** Las entradas `resolution` permiten que el sistema aprenda de interacciones humanas, pero no se usan para fine-tuning en esta versión.

---

## Changelog

| Fecha | Versión | Cambios |
|---|---|---|
| 2025-01-20 | 1.0 | Creación del documento. Incluye modelo, source types, embedding generation, RAG search, prompt injection, CRUD, resolution KB entries. |
