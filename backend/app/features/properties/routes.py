"""
Property CRUD + search routes.

Endpoints:
  GET    /api/v1/properties         — list with filters (admin)
  POST   /api/v1/properties         — create + auto-embed (admin)
  GET    /api/v1/properties/{id}    — detail (admin)
  PUT    /api/v1/properties/{id}    — update + re-embed (admin)
  DELETE /api/v1/properties/{id}    — soft-delete (admin)
  POST   /api/v1/properties/search  — hybrid search (all auth)
  POST   /api/v1/properties/import-from-kb — one-time KB migration (superadmin)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.models.property import Property

logger = logging.getLogger(__name__)
router = APIRouter(tags=["properties"])

_ADMIN_ROLES = {"ADMIN", "SUPERADMIN"}


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class PropertyCreate(BaseModel):
    name: Optional[str] = None
    codigo: Optional[str] = None
    tipologia: Optional[str] = None
    project_id: Optional[int] = None
    property_type: Optional[str] = None
    status: str = "available"
    commune: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    price_uf: Optional[float] = None
    price_clp: Optional[int] = None
    list_price_uf: Optional[float] = None
    list_price_clp: Optional[int] = None
    offer_price_uf: Optional[float] = None
    offer_price_clp: Optional[int] = None
    has_offer: bool = False
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    parking_spots: Optional[int] = 0
    storage_units: Optional[int] = 0
    square_meters_total: Optional[float] = None
    square_meters_useful: Optional[float] = None
    floor_number: Optional[int] = None
    total_floors: Optional[int] = None
    orientation: Optional[str] = None
    year_built: Optional[int] = None
    description: Optional[str] = None
    highlights: Optional[str] = None
    amenities: Optional[List[str]] = None
    nearby_places: Optional[List[Dict[str, Any]]] = None
    images: Optional[List[Dict[str, Any]]] = None
    financing_options: Optional[List[str]] = None
    floor_plan_url: Optional[str] = None
    virtual_tour_url: Optional[str] = None
    common_expenses_clp: Optional[int] = None
    subsidio_eligible: bool = False


class PropertyUpdate(BaseModel):
    name: Optional[str] = None
    codigo: Optional[str] = None
    tipologia: Optional[str] = None
    project_id: Optional[int] = None
    property_type: Optional[str] = None
    status: Optional[str] = None
    commune: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    price_uf: Optional[float] = None
    price_clp: Optional[int] = None
    list_price_uf: Optional[float] = None
    list_price_clp: Optional[int] = None
    offer_price_uf: Optional[float] = None
    offer_price_clp: Optional[int] = None
    has_offer: Optional[bool] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    parking_spots: Optional[int] = None
    storage_units: Optional[int] = None
    square_meters_total: Optional[float] = None
    square_meters_useful: Optional[float] = None
    floor_number: Optional[int] = None
    total_floors: Optional[int] = None
    orientation: Optional[str] = None
    year_built: Optional[int] = None
    description: Optional[str] = None
    highlights: Optional[str] = None
    amenities: Optional[List[str]] = None
    nearby_places: Optional[List[Dict[str, Any]]] = None
    images: Optional[List[Dict[str, Any]]] = None
    financing_options: Optional[List[str]] = None
    floor_plan_url: Optional[str] = None
    virtual_tour_url: Optional[str] = None
    common_expenses_clp: Optional[int] = None
    subsidio_eligible: Optional[bool] = None


class PropertySearchRequest(BaseModel):
    commune: Optional[str] = None
    city: Optional[str] = None
    property_type: Optional[str] = None
    project_id: Optional[int] = None
    tipologia: Optional[str] = None
    min_bedrooms: Optional[int] = None
    max_bedrooms: Optional[int] = None
    min_bathrooms: Optional[int] = None
    min_price_uf: Optional[float] = None
    max_price_uf: Optional[float] = None
    min_sqm: Optional[float] = None
    parking: Optional[bool] = None
    subsidio_eligible: Optional[bool] = None
    semantic_query: Optional[str] = None
    strategy: str = "hybrid"
    limit: int = Field(default=5, ge=1, le=10)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_admin(user: dict) -> None:
    if user.get("role") not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")


def _get_broker_id(user: dict) -> int:
    if user.get("role") == "SUPERADMIN" and user.get("broker_id") is None:
        raise HTTPException(status_code=400, detail="Provide broker_id as query param")
    return user.get("broker_id")


def _format(prop: Property) -> Dict[str, Any]:
    project_summary = None
    if prop.project_id is not None and getattr(prop, "project", None) is not None:
        project_summary = {
            "id": prop.project.id,
            "name": prop.project.name,
            "code": prop.project.code,
            "commune": prop.project.commune,
        }
    return {
        "id": prop.id,
        "broker_id": prop.broker_id,
        "name": prop.name,
        "codigo": prop.codigo,
        "tipologia": prop.tipologia,
        "project_id": prop.project_id,
        "project": project_summary,
        "property_type": prop.property_type,
        "status": prop.status,
        "commune": prop.commune,
        "city": prop.city,
        "region": prop.region,
        "address": prop.address,
        "latitude": float(prop.latitude) if prop.latitude else None,
        "longitude": float(prop.longitude) if prop.longitude else None,
        "price_uf": float(prop.price_uf) if prop.price_uf else None,
        "price_clp": prop.price_clp,
        "list_price_uf": float(prop.list_price_uf) if prop.list_price_uf else None,
        "list_price_clp": prop.list_price_clp,
        "offer_price_uf": float(prop.offer_price_uf) if prop.offer_price_uf else None,
        "offer_price_clp": prop.offer_price_clp,
        "has_offer": bool(prop.has_offer),
        "bedrooms": prop.bedrooms,
        "bathrooms": prop.bathrooms,
        "parking_spots": prop.parking_spots,
        "storage_units": prop.storage_units,
        "square_meters_total": float(prop.square_meters_total) if prop.square_meters_total else None,
        "square_meters_useful": float(prop.square_meters_useful) if prop.square_meters_useful else None,
        "floor_number": prop.floor_number,
        "total_floors": prop.total_floors,
        "orientation": prop.orientation,
        "year_built": prop.year_built,
        "description": prop.description,
        "highlights": prop.highlights,
        "amenities": prop.amenities,
        "nearby_places": prop.nearby_places,
        "images": prop.images,
        "financing_options": prop.financing_options,
        "floor_plan_url": prop.floor_plan_url,
        "virtual_tour_url": prop.virtual_tour_url,
        "common_expenses_clp": prop.common_expenses_clp,
        "subsidio_eligible": prop.subsidio_eligible,
        "published_at": prop.published_at.isoformat() if prop.published_at else None,
        "created_at": prop.created_at.isoformat() if prop.created_at else None,
        "updated_at": prop.updated_at.isoformat() if prop.updated_at else None,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_properties(
    status: Optional[str] = None,
    property_type: Optional[str] = None,
    commune: Optional[str] = None,
    min_price_uf: Optional[float] = None,
    max_price_uf: Optional[float] = None,
    min_bedrooms: Optional[int] = None,
    has_offer: Optional[bool] = None,
    project_id: Optional[int] = None,
    tipologia: Optional[str] = None,
    no_project: Optional[bool] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    broker_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    target_broker = broker_id if current_user.get("role") == "SUPERADMIN" and broker_id else current_user.get("broker_id")

    from sqlalchemy.orm import selectinload
    q = (
        select(Property)
        .where(Property.broker_id == target_broker)
        .options(selectinload(Property.project))
    )
    if status:
        q = q.where(Property.status == status)
    if property_type:
        q = q.where(Property.property_type == property_type)
    if commune:
        q = q.where(Property.commune.ilike(f"%{commune}%"))
    if min_price_uf is not None:
        q = q.where(Property.price_uf >= min_price_uf)
    if max_price_uf is not None:
        q = q.where(Property.price_uf <= max_price_uf)
    if min_bedrooms is not None:
        q = q.where(Property.bedrooms >= min_bedrooms)
    if has_offer is not None:
        q = q.where(Property.has_offer == has_offer)
    if project_id is not None:
        q = q.where(Property.project_id == project_id)
    if tipologia:
        q = q.where(Property.tipologia == tipologia)
    if no_project:
        q = q.where(Property.project_id.is_(None))

    total_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(total_q)).scalar_one()

    q = q.order_by(Property.created_at.desc()).offset(offset).limit(limit)
    props = (await db.execute(q)).scalars().all()

    return {"total": total, "offset": offset, "limit": limit, "items": [_format(p) for p in props]}


@router.post("", status_code=201)
async def create_property(
    body: PropertyCreate,
    broker_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    target_broker = broker_id if current_user.get("role") == "SUPERADMIN" and broker_id else current_user.get("broker_id")

    prop = Property(broker_id=target_broker, **body.model_dump(exclude_none=True))
    db.add(prop)
    await db.flush()

    # Generate embedding asynchronously (don't block on failure)
    try:
        from app.services.properties.embedding import embed_and_save_property
        await embed_and_save_property(prop, db)
    except Exception as exc:
        logger.warning("Embedding failed for new property %d: %s", prop.id, exc)

    await db.commit()
    await db.refresh(prop)
    return _format(prop)


@router.get("/{property_id}")
async def get_property(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    from sqlalchemy.orm import selectinload
    q = select(Property).options(selectinload(Property.project)).where(
        Property.id == property_id,
    )
    if current_user.get("role") != "SUPERADMIN":
        q = q.where(Property.broker_id == current_user.get("broker_id"))
    result = await db.execute(q)
    prop = result.scalar_one_or_none()
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")
    return _format(prop)


@router.put("/{property_id}")
async def update_property(
    property_id: int,
    body: PropertyUpdate,
    broker_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    target_broker = broker_id if current_user.get("role") == "SUPERADMIN" and broker_id else current_user.get("broker_id")
    q = select(Property).where(Property.id == property_id, Property.broker_id == target_broker)
    result = await db.execute(q)
    prop = result.scalar_one_or_none()
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")

    update_data = body.model_dump(exclude_unset=True)
    needs_reembed = any(
        k in update_data
        for k in ("description", "highlights", "amenities", "nearby_places", "project_id", "tipologia")
    )

    for k, v in update_data.items():
        setattr(prop, k, v)

    if needs_reembed:
        try:
            from app.services.properties.embedding import embed_and_save_property
            await embed_and_save_property(prop, db)
        except Exception as exc:
            logger.warning("Re-embedding failed for property %d: %s", prop.id, exc)

    await db.commit()
    await db.refresh(prop)
    return _format(prop)


@router.delete("/{property_id}", status_code=204)
async def delete_property(
    property_id: int,
    broker_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    target_broker = broker_id if current_user.get("role") == "SUPERADMIN" and broker_id else current_user.get("broker_id")
    result = await db.execute(
        select(Property).where(Property.id == property_id, Property.broker_id == target_broker)
    )
    prop = result.scalar_one_or_none()
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")
    prop.status = "archived"
    await db.commit()


@router.post("/search")
async def search_properties(
    body: PropertySearchRequest,
    broker_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Hybrid property search endpoint — usable by all authenticated users."""
    target_broker = broker_id if current_user.get("role") == "SUPERADMIN" and broker_id else current_user.get("broker_id")
    from app.services.properties.search_service import execute_property_search
    results = await execute_property_search(body.model_dump(exclude_none=True), db, target_broker)
    return {"count": len(results), "results": results}


@router.post("/generate-sample", status_code=201)
async def generate_sample_properties(
    count: int = Query(10, ge=1, le=50),
    project_count: int = Query(2, ge=0, le=10),
    broker_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Genera N propiedades de prueba con datos chilenos coherentes y embeddings.

    Si `project_count` > 0, también crea ese número de proyectos demo y
    distribuye las propiedades generadas entre ellos (con tipologías
    coherentes). Si project_count=0, genera propiedades sueltas como antes.

    Admin only. Pensado para poblar rápido el catálogo de un broker en demos /
    entornos de desarrollo. Cada propiedad pasa por el pipeline normal de
    embedding (Gemini text-embedding-004); fallos individuales se loggean
    pero no abortan el batch.
    """
    _require_admin(current_user)
    target_broker = broker_id if current_user.get("role") == "SUPERADMIN" and broker_id else current_user.get("broker_id")
    if target_broker is None:
        raise HTTPException(status_code=400, detail="broker_id requerido")

    from app.services.properties.generator import (
        generate_random_properties,
        generate_random_property,
        generate_random_projects,
    )
    from app.services.properties.embedding import embed_and_save_property

    created_project_ids: List[int] = []
    projects: List = []
    if project_count > 0:
        projects = generate_random_projects(target_broker, count=project_count)
        for proj in projects:
            db.add(proj)
        await db.flush()
        created_project_ids = [p.id for p in projects]

    if projects:
        # Distribuye las properties entre los proyectos (round-robin).
        props = [
            generate_random_property(target_broker, project=projects[i % len(projects)])
            for i in range(count)
        ]
    else:
        props = generate_random_properties(target_broker, count=count)

    created_ids: List[int] = []
    embed_failures = 0

    for prop in props:
        db.add(prop)
        await db.flush()
        created_ids.append(prop.id)
        try:
            await embed_and_save_property(prop, db)
        except Exception as exc:
            embed_failures += 1
            logger.warning("Embedding falló para propiedad generada %d: %s", prop.id, exc)

    await db.commit()
    return {
        "created": len(created_ids),
        "ids": created_ids,
        "embed_failures": embed_failures,
        "projects_created": len(created_project_ids),
        "project_ids": created_project_ids,
    }


@router.get("/migration-status")
async def migration_status(
    broker_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Show how many KB property entries have been migrated vs. pending."""
    if current_user.get("role") != "SUPERADMIN":
        raise HTTPException(status_code=403, detail="Superadmin only")

    from app.models.knowledge_base import KnowledgeBase
    from sqlalchemy import func as sa_func

    kb_q = select(func.count()).select_from(KnowledgeBase).where(KnowledgeBase.source_type == "property")
    if broker_id:
        kb_q = kb_q.where(KnowledgeBase.broker_id == broker_id)
    total_kb = (await db.execute(kb_q)).scalar_one()

    migrated_q = select(func.count()).select_from(Property).where(Property.kb_entry_id.isnot(None))
    if broker_id:
        migrated_q = migrated_q.where(Property.broker_id == broker_id)
    migrated = (await db.execute(migrated_q)).scalar_one()

    return {
        "total_kb_property_entries": total_kb,
        "migrated_count": migrated,
        "unmigrated_count": total_kb - migrated,
    }


@router.post("/import-from-kb", status_code=202)
async def import_from_kb(
    broker_id: Optional[int] = None,
    dry_run: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Idempotent migration: move knowledge_base entries with source_type='property'
    to the new properties table. Safe to run multiple times — existing entries
    (matched by kb_entry_id) are skipped.

    Optional params:
    - broker_id: restrict migration to a specific broker (superadmin only)
    - dry_run: preview what would be migrated without creating records
    """
    if current_user.get("role") != "SUPERADMIN":
        raise HTTPException(status_code=403, detail="Superadmin only")

    from app.models.knowledge_base import KnowledgeBase
    from app.services.properties.embedding import embed_and_save_property

    kb_q = select(KnowledgeBase).where(KnowledgeBase.source_type == "property")
    if broker_id:
        kb_q = kb_q.where(KnowledgeBase.broker_id == broker_id)
    kb_entries = (await db.execute(kb_q)).scalars().all()

    # Fetch already-migrated kb_entry_ids to skip duplicates
    existing_ids_q = select(Property.kb_entry_id).where(Property.kb_entry_id.isnot(None))
    if broker_id:
        existing_ids_q = existing_ids_q.where(Property.broker_id == broker_id)
    already_migrated = {row for row in (await db.execute(existing_ids_q)).scalars().all()}

    migrated = 0
    skipped = 0
    errors = 0
    preview = []

    for entry in kb_entries:
        if entry.id in already_migrated:
            skipped += 1
            continue

        meta = entry.kb_metadata or {}
        if dry_run:
            preview.append({
                "kb_entry_id": entry.id,
                "broker_id": entry.broker_id,
                "name": entry.title,
                "commune": meta.get("commune") or meta.get("location"),
                "price_uf": meta.get("price_uf") or meta.get("price"),
            })
            migrated += 1
            continue

        try:
            prop = Property(
                broker_id=entry.broker_id,
                name=entry.title,
                description=entry.content,
                property_type=meta.get("property_type"),
                commune=meta.get("commune") or meta.get("location"),
                price_uf=meta.get("price_uf") or meta.get("price"),
                bedrooms=meta.get("bedrooms"),
                bathrooms=meta.get("bathrooms"),
                amenities=meta.get("amenities"),
                status="available",
                kb_entry_id=entry.id,
            )
            db.add(prop)
            await db.flush()
            await embed_and_save_property(prop, db)
            migrated += 1
        except Exception as exc:
            logger.warning("Failed to migrate KB entry %d: %s", entry.id, exc)
            errors += 1

    if not dry_run:
        await db.commit()

    response = {
        "dry_run": dry_run,
        "total_kb_entries": len(kb_entries),
        "migrated": migrated,
        "skipped_already_exists": skipped,
        "errors": errors,
    }
    if dry_run:
        response["preview"] = preview
    return response
