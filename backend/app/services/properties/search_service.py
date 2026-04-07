"""
PropertySearchService — hybrid property search with Reciprocal Rank Fusion (RRF).

Combines:
  - Structured SQL filters (commune, bedrooms, price, parking, etc.)
  - Semantic embedding search via pgvector cosine distance
  - RRF merge (k=60, industry standard) for ranking fusion

The LLM extracts structured parameters from natural language via function calling.
This service executes the actual search given those parameters.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# RRF constant (k=60 is the widely adopted standard)
_RRF_K = 60
_DEFAULT_LIMIT = 5
_MAX_LIMIT = 10
_CANDIDATE_POOL = 20  # candidates per strategy before RRF merge


# ── Function calling tool definition ─────────────────────────────────────────

SEARCH_PROPERTIES_TOOL = {
    "name": "search_properties",
    "description": (
        "Busca propiedades disponibles para el lead según sus criterios. "
        "Usa filtros estructurados para requisitos exactos (dormitorios, precio, comuna) "
        "y búsqueda semántica para preferencias cualitativas "
        "(luminoso, vista, cerca de parque, barrio tranquilo)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            # ── SQL filters ──────────────────────────────────────────────────
            "commune": {
                "type": "string",
                "description": "Comuna o barrio (ej: Ñuñoa, Providencia, Las Condes)",
            },
            "city": {
                "type": "string",
                "description": "Ciudad (ej: Santiago, Viña del Mar)",
            },
            "property_type": {
                "type": "string",
                "enum": ["departamento", "casa", "terreno", "oficina"],
                "description": "Tipo de propiedad",
            },
            "min_bedrooms": {
                "type": "integer",
                "description": "Número mínimo de dormitorios",
            },
            "max_bedrooms": {"type": "integer"},
            "min_bathrooms": {"type": "integer"},
            "min_price_uf": {"type": "number"},
            "max_price_uf": {"type": "number"},
            "min_sqm": {
                "type": "number",
                "description": "Metros cuadrados útiles mínimos",
            },
            "parking": {
                "type": "boolean",
                "description": "Requiere al menos 1 estacionamiento",
            },
            "subsidio_eligible": {
                "type": "boolean",
                "description": "Solo propiedades con subsidio disponible",
            },
            # ── Semantic query ───────────────────────────────────────────────
            "semantic_query": {
                "type": "string",
                "description": (
                    "Preferencias cualitativas en lenguaje natural: "
                    "'luminoso con vista al cerro, cerca del metro, "
                    "barrio tranquilo con áreas verdes'"
                ),
            },
            # ── Strategy ─────────────────────────────────────────────────────
            "strategy": {
                "type": "string",
                "enum": ["structured", "semantic", "hybrid"],
                "description": (
                    "structured: solo filtros SQL. "
                    "semantic: solo similitud de embedding. "
                    "hybrid: combina ambos con RRF (recomendado)."
                ),
            },
            "limit": {
                "type": "integer",
                "description": "Máximo de resultados a devolver (1-10)",
                "default": 5,
            },
        },
        "required": ["strategy"],
    },
}


async def execute_property_search(
    params: Dict[str, Any],
    db: AsyncSession,
    broker_id: int,
) -> List[Dict[str, Any]]:
    """
    Execute a property search and return ranked results.

    Supports three strategies:
    - structured: SQL-only with filters
    - semantic: embedding cosine similarity only
    - hybrid: RRF merge of both ranked lists
    """
    from app.models.property import Property
    from app.services.properties.embedding import generate_property_query_embedding

    strategy = params.get("strategy", "hybrid")
    limit = min(int(params.get("limit", _DEFAULT_LIMIT)), _MAX_LIMIT)

    sql_results: List[Property] = []
    semantic_results: List[tuple] = []  # (Property, distance)

    # ── STEP 1: Structured SQL search ────────────────────────────────────────
    if strategy in ("structured", "hybrid"):
        sql_results = await _structured_search(params, db, broker_id)

    # ── STEP 2: Semantic embedding search ────────────────────────────────────
    if strategy in ("semantic", "hybrid") and params.get("semantic_query"):
        try:
            query_embedding = await generate_property_query_embedding(
                params["semantic_query"]
            )
            semantic_results = await _semantic_search(
                query_embedding, db, broker_id, params
            )
        except Exception as exc:
            logger.warning("Semantic search failed, falling back to structured: %s", exc)
            if strategy == "semantic":
                strategy = "structured"
                if not sql_results:
                    sql_results = await _structured_search(params, db, broker_id)

    # ── STEP 3: RRF merge ────────────────────────────────────────────────────
    if strategy == "hybrid" and sql_results and semantic_results:
        return await _rrf_merge(sql_results, semantic_results, limit, db)

    if strategy == "structured" or (strategy == "hybrid" and not semantic_results):
        return [_format_property(p) for p in sql_results[:limit]]

    if strategy == "semantic":
        return [
            _format_property(prop, semantic_distance=dist)
            for prop, dist in semantic_results[:limit]
        ]

    return []


async def _structured_search(
    params: Dict[str, Any],
    db: AsyncSession,
    broker_id: int,
) -> List[Any]:
    """Build and execute a parametric SQL query."""
    from app.models.property import Property

    query = select(Property).where(
        Property.broker_id == broker_id,
        Property.status == "available",
    )

    if params.get("commune"):
        query = query.where(Property.commune.ilike(f"%{params['commune']}%"))
    if params.get("city"):
        query = query.where(Property.city.ilike(f"%{params['city']}%"))
    if params.get("property_type"):
        query = query.where(Property.property_type == params["property_type"])
    if params.get("min_bedrooms") is not None:
        query = query.where(Property.bedrooms >= params["min_bedrooms"])
    if params.get("max_bedrooms") is not None:
        query = query.where(Property.bedrooms <= params["max_bedrooms"])
    if params.get("min_bathrooms") is not None:
        query = query.where(Property.bathrooms >= params["min_bathrooms"])
    if params.get("min_price_uf") is not None:
        query = query.where(Property.price_uf >= params["min_price_uf"])
    if params.get("max_price_uf") is not None:
        query = query.where(Property.price_uf <= params["max_price_uf"])
    if params.get("min_sqm") is not None:
        query = query.where(Property.square_meters_useful >= params["min_sqm"])
    if params.get("parking"):
        query = query.where(Property.parking_spots > 0)
    if params.get("subsidio_eligible"):
        query = query.where(Property.subsidio_eligible.is_(True))

    query = query.order_by(Property.price_uf.asc()).limit(_CANDIDATE_POOL)
    result = await db.execute(query)
    return list(result.scalars().all())


async def _semantic_search(
    query_embedding: List[float],
    db: AsyncSession,
    broker_id: int,
    params: Dict[str, Any],
) -> List[tuple]:
    """Execute cosine similarity search via pgvector."""
    from app.models.property import Property

    # Build optional filter clauses for pre-filtering before vector similarity.
    # This prevents returning properties that clearly don't match hard constraints.
    extra_filters = []
    bind_params: Dict[str, Any] = {"broker_id": broker_id, "lim": _CANDIDATE_POOL}

    if params.get("commune"):
        extra_filters.append("AND commune ILIKE :commune")
        bind_params["commune"] = f"%{params['commune']}%"
    if params.get("min_price_uf") is not None:
        extra_filters.append("AND price_uf >= :min_uf")
        bind_params["min_uf"] = params["min_price_uf"]
    if params.get("max_price_uf") is not None:
        extra_filters.append("AND price_uf <= :max_uf")
        bind_params["max_uf"] = params["max_price_uf"]
    if params.get("min_bedrooms") is not None:
        extra_filters.append("AND bedrooms >= :min_beds")
        bind_params["min_beds"] = params["min_bedrooms"]

    extra_sql = " ".join(extra_filters)

    # Use raw SQL for pgvector cosine distance operator <=>
    sql = text(f"""
        SELECT id, (embedding <=> :emb) AS distance
        FROM properties
        WHERE broker_id = :broker_id
          AND status = 'available'
          AND embedding IS NOT NULL
          {extra_sql}
        ORDER BY distance ASC
        LIMIT :lim
    """)
    bind_params["emb"] = str(query_embedding)
    rows = await db.execute(sql, bind_params)
    rows = rows.fetchall()

    if not rows:
        return []

    prop_ids = [r[0] for r in rows]
    dist_map = {r[0]: r[1] for r in rows}

    from sqlalchemy import in_
    props = (await db.execute(
        select(Property).where(Property.id.in_(prop_ids))
    )).scalars().all()

    # Preserve cosine distance ordering
    prop_map = {p.id: p for p in props}
    return [
        (prop_map[pid], dist_map[pid])
        for pid in prop_ids
        if pid in prop_map
    ]


async def _rrf_merge(
    sql_results: List[Any],
    semantic_results: List[tuple],
    limit: int,
    db: AsyncSession,
) -> List[Dict[str, Any]]:
    """Apply Reciprocal Rank Fusion and return top-N formatted results."""
    sql_ranks = {p.id: rank + 1 for rank, p in enumerate(sql_results)}
    sem_ranks = {prop.id: rank + 1 for rank, (prop, _) in enumerate(semantic_results)}
    sem_dist = {prop.id: dist for prop, dist in semantic_results}

    # Build property map from already-fetched objects — no extra DB query needed
    prop_map = {p.id: p for p in sql_results}
    prop_map.update({prop.id: prop for prop, _ in semantic_results})

    all_ids = set(sql_ranks) | set(sem_ranks)
    rrf_scores: Dict[int, float] = {}
    for pid in all_ids:
        score = 0.0
        if pid in sql_ranks:
            score += 1.0 / (sql_ranks[pid] + _RRF_K)
        if pid in sem_ranks:
            score += 1.0 / (sem_ranks[pid] + _RRF_K)
        rrf_scores[pid] = score

    sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)[:limit]

    return [
        _format_property(
            prop_map[pid],
            rrf_score=rrf_scores[pid],
            sql_rank=sql_ranks.get(pid),
            sem_rank=sem_ranks.get(pid),
            semantic_distance=sem_dist.get(pid),
        )
        for pid in sorted_ids
        if pid in prop_map
    ]


def _format_property(
    prop: Any,
    rrf_score: Optional[float] = None,
    sql_rank: Optional[int] = None,
    sem_rank: Optional[int] = None,
    semantic_distance: Optional[float] = None,
) -> Dict[str, Any]:
    """Format a Property ORM object into a dict for the LLM."""
    amenities = prop.amenities or []
    nearby = prop.nearby_places or []

    amenities_str = ", ".join(amenities[:8]) if isinstance(amenities, list) else str(amenities)
    nearby_str = ", ".join(
        f"{p.get('name','?')} ({p.get('type','?')})" for p in nearby[:4]
    ) if isinstance(nearby, list) else str(nearby)

    result = {
        "id": prop.id,
        "name": prop.name or f"Propiedad #{prop.id}",
        "internal_code": prop.internal_code,
        "type": prop.property_type,
        "status": prop.status,
        "commune": prop.commune,
        "city": prop.city,
        "address": prop.address,
        "price_uf": float(prop.price_uf) if prop.price_uf else None,
        "price_clp": prop.price_clp,
        "bedrooms": prop.bedrooms,
        "bathrooms": prop.bathrooms,
        "parking_spots": prop.parking_spots,
        "square_meters_useful": float(prop.square_meters_useful) if prop.square_meters_useful else None,
        "square_meters_total": float(prop.square_meters_total) if prop.square_meters_total else None,
        "floor_number": prop.floor_number,
        "orientation": prop.orientation,
        "highlights": prop.highlights,
        "amenities": amenities_str,
        "nearby_places": nearby_str,
        "subsidio_eligible": prop.subsidio_eligible,
        "common_expenses_clp": prop.common_expenses_clp,
        "virtual_tour_url": prop.virtual_tour_url,
        # Search metadata
        "_rrf_score": rrf_score,
        "_sql_rank": sql_rank,
        "_sem_rank": sem_rank,
        "_sem_distance": semantic_distance,
    }
    return result
