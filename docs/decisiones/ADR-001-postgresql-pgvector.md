# ADR-001: PostgreSQL + pgvector instead of separate vector DB

> Estado: Aceptada
> Fecha: 2026-04-17

## Contexto

Necesitamos almacenar embeddings para RAG (Retrieval Augmented Generation) junto con datos relacionales de leads. La base de datos debe soportar tanto consultas vectoriales (768-dimensional embeddings generados por Gemini text-embedding-004) como operaciones transaccionales normales sobre leads, agentes y brokers.

El desafío era decidir entre usar una base de datos vectorial dedicada (como Pinecone, Weaviate o Qdrant) o integrar capacidades vectoriales en la base de datos relacional existente.

## Decisión

Usar PostgreSQL con la extensión pgvector para almacenar y buscar embeddings. La tabla `knowledge_base` utiliza columnas vectoriales de 768 dimensiones, mientras que los datos de leads, agentes y brokers permanecen en tablas relacionales normales.

La configuración incluye:
- Extensión `pgvector` habilitada en PostgreSQL
- Columna `embedding vector(768)` en la tabla `knowledge_base`
- Búsqueda por similitud coseno usando operadores de pgvector
- Queries que unen datos vectoriales con metadatos relacionales

## Consecuencias

**Pros:**
- Arquitectura de base de datos única: un solo sistema para mantener, monitorear y hacer backup
- Transacciones ACID completas para operaciones que combinan datos vectoriales y relacionales
- Join nativo entre embeddings y datos de leads/agentes/brokers
- Sin complejidad de sincronización entre base de datos vectorial y relacional
- Costos de infraestructura reducidos (no hay que provisionar otro servicio)
- Herramientas de monitoreo y diagnóstico familiares para equipos con experiencia PostgreSQL

**Contras:**
- Rendimiento de búsqueda vectorial inferior comparado con bases de datos vectoriales dedicadas como Pinecone o Qdrant
- Scaling vertical requerido para grandes volúmenes de embeddings
- Menos opciones deindexación avançada comparadas con soluciones especializadas
- Configuración manual de approximative nearest neighbor (ANN) indexes requerida
