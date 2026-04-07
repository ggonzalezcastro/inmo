"""
Embedding generation for properties.

Generates 768-dim embeddings (Gemini text-embedding-004) for:
  - Property documents (stored in Property.embedding)
  - User search queries (used for cosine similarity at search time)

The embedding text is: description + highlights + amenities joined.
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


def _build_property_text(prop: Any) -> str:
    """
    Concatenate the rich-text fields that form the semantic document
    for a property. Mirrors what we store in the embedding column.
    """
    parts = []
    if prop.name:
        parts.append(prop.name)
    if prop.property_type:
        parts.append(prop.property_type)
    if prop.commune:
        parts.append(f"en {prop.commune}")
    if prop.description:
        parts.append(prop.description)
    if prop.highlights:
        parts.append(prop.highlights)
    if prop.amenities:
        if isinstance(prop.amenities, list):
            parts.append(", ".join(str(a) for a in prop.amenities))
        else:
            parts.append(str(prop.amenities))
    if prop.nearby_places:
        if isinstance(prop.nearby_places, list):
            nearby_str = ", ".join(
                f"{p.get('name', '')} {p.get('type', '')}" for p in prop.nearby_places
            )
            parts.append(nearby_str)
    return " ".join(p for p in parts if p.strip())


async def generate_property_embedding(prop: Any) -> Optional[List[float]]:
    """
    Generate an embedding for a property's rich-text fields.
    Returns None on failure so callers can decide whether to skip.
    """
    text = _build_property_text(prop)
    if not text.strip():
        logger.warning("Property %s has no text to embed", getattr(prop, "id", "?"))
        return None
    return await _embed(text)


async def generate_property_query_embedding(query: str) -> List[float]:
    """
    Generate an embedding for a natural-language search query.
    Raises on failure so the caller can fall back to structured search.
    """
    return await _embed(query)


async def _embed(text: str) -> List[float]:
    """Embed a string using Gemini text-embedding-004 (same as knowledge_base)."""
    from app.services.knowledge.rag_service import _embed_text
    result = await _embed_text(text)
    if result is None:
        raise RuntimeError("Embedding returned None — check GEMINI_API_KEY and connectivity")
    return result


async def embed_and_save_property(prop: Any, db: Any) -> bool:
    """
    Generate an embedding for a property and persist it.
    Returns True on success, False if embedding generation failed.
    """
    embedding = await generate_property_embedding(prop)
    if embedding is None:
        return False

    try:
        prop.embedding = embedding
        db.add(prop)
        # Caller is responsible for commit
        return True
    except Exception as exc:
        logger.warning("Failed to save embedding for property %s: %s", prop.id, exc)
        return False
