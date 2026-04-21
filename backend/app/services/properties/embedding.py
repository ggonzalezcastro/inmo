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

    Si la property pertenece a un Project, prependea contexto del proyecto
    (nombre, developer, descripción, amenities comunes, highlights) para
    enriquecer el embedding y que la búsqueda semántica considere atributos
    heredados (ej. "edificio con piscina y gimnasio en Ñuñoa").
    """
    parts = []

    project = getattr(prop, "project", None)
    if project is not None:
        if getattr(project, "name", None):
            parts.append(f"Proyecto {project.name}")
        if getattr(project, "developer", None):
            parts.append(f"de {project.developer}")
        if getattr(project, "description", None):
            parts.append(project.description)
        if getattr(project, "highlights", None):
            parts.append(project.highlights)
        common = getattr(project, "common_amenities", None)
        if common:
            if isinstance(common, list):
                parts.append("Amenities: " + ", ".join(str(a) for a in common))
            else:
                parts.append(f"Amenities: {common}")

    if prop.name:
        parts.append(prop.name)
    if getattr(prop, "tipologia", None):
        parts.append(f"tipología {prop.tipologia}")
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
    return " ".join(p for p in parts if p and str(p).strip())


async def generate_property_embedding(prop: Any) -> Optional[List[float]]:
    """
    Generate an embedding for a property's rich-text fields.
    Returns None on failure so callers can decide whether to skip.
    """
    text = _build_property_text(prop)
    if not text.strip():
        logger.warning("Property %s has no text to embed", getattr(prop, "id", "?"))
        return None
    embedding, _ = await _embed(text)
    return embedding


async def generate_property_query_embedding(query: str) -> tuple[List[float], int]:
    """
    Generate an embedding for a natural-language search query.
    Returns (embedding, prompt_tokens). Raises on failure so caller can fall back.
    """
    return await _embed(query)


async def _embed(text: str) -> tuple[List[float], int]:
    """Returns (embedding_vector, prompt_tokens) using Gemini text-embedding-004."""
    from app.services.knowledge.rag_service import _embed_text
    result, tokens = await _embed_text(text)
    if result is None:
        raise RuntimeError("Embedding returned None — check OPENROUTER_API_KEY and connectivity")
    return result, tokens


async def embed_and_save_property(prop: Any, db: Any) -> bool:
    """
    Generate an embedding for a property and persist it.
    Returns True on success, False if embedding generation failed.

    Si la property tiene `project_id` pero el relationship no está hidratado
    (caso típico al crear/actualizar), lo carga sincrónicamente para que el
    embedding incluya el contexto del proyecto.
    """
    if prop.project_id is not None and getattr(prop, "project", None) is None:
        try:
            from app.models.project import Project
            from sqlalchemy import select as _select
            res = await db.execute(_select(Project).where(Project.id == prop.project_id))
            prop.project = res.scalar_one_or_none()
        except Exception as exc:
            logger.warning("No se pudo cargar el proyecto %s para embedding: %s", prop.project_id, exc)

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
