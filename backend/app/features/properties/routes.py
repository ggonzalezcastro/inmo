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
from app.models.user import User, UserRole
from app.models.property import Property

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/properties", tags=["properties"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class PropertyCreate(BaseModel):
    name: Optional[str] = None
    internal_code: Optional[str] = None
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


class PropertyUpdate(PropertyCreate):
    pass


class PropertySearchRequest(BaseModel):
    commune: Optional[str] = None
    city: Optional[str] = None
    property_type: Optional[str] = None
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

def _require_admin(user: User) -> None:
    if user.role not in (UserRole.ADMIN, UserRole.SUPERADMIN):
        raise HTTPException(status_code=403, detail="Admin access required")


def _get_broker_id(user: User) -> int:
    if user.role == UserRole.SUPERADMIN and user.broker_id is None:
        raise HTTPException(status_code=400, detail="Provide broker_id as query param")
    return user.broker_id


def _format(prop: Property) -> Dict[str, Any]:
    return {
        "id": prop.id,
        "broker_id": prop.broker_id,
        "name": prop.name,
        "internal_code": prop.internal_code,
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
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    broker_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    target_broker = broker_id if current_user.role == UserRole.SUPERADMIN and broker_id else current_user.broker_id

    q = select(Property).where(Property.broker_id == target_broker)
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
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    target_broker = broker_id if current_user.role == UserRole.SUPERADMIN and broker_id else current_user.broker_id

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
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    result = await db.execute(
        select(Property).where(
            Property.id == property_id,
            Property.broker_id == current_user.broker_id if current_user.role != UserRole.SUPERADMIN else True,
        )
    )
    prop = result.scalar_one_or_none()
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")
    return _format(prop)


@router.put("/{property_id}")
async def update_property(
    property_id: int,
    body: PropertyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    result = await db.execute(select(Property).where(Property.id == property_id))
    prop = result.scalar_one_or_none()
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")

    update_data = body.model_dump(exclude_none=True)
    needs_reembed = any(k in update_data for k in ("description", "highlights", "amenities", "nearby_places"))

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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    result = await db.execute(select(Property).where(Property.id == property_id))
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
    current_user: User = Depends(get_current_user),
):
    """Hybrid property search endpoint — usable by all authenticated users."""
    target_broker = broker_id if current_user.role == UserRole.SUPERADMIN and broker_id else current_user.broker_id
    from app.services.properties.search_service import execute_property_search
    results = await execute_property_search(body.model_dump(exclude_none=True), db, target_broker)
    return {"count": len(results), "results": results}


@router.post("/import-from-kb", status_code=202)
async def import_from_kb(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    One-time migration: move knowledge_base entries with source_type='property'
    to the new properties table.
    """
    if current_user.role != UserRole.SUPERADMIN:
        raise HTTPException(status_code=403, detail="Superadmin only")

    from app.models.knowledge_base import KnowledgeBase
    from app.services.properties.embedding import embed_and_save_property

    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.source_type == "property")
    )
    kb_entries = result.scalars().all()

    migrated = 0
    errors = 0
    for entry in kb_entries:
        try:
            meta = entry.kb_metadata or {}
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

    await db.commit()
    return {"migrated": migrated, "errors": errors, "total": len(kb_entries)}
