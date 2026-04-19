"""
Project CRUD + listado con aggregates.

Endpoints:
  GET    /api/v1/projects                    — listado con aggregates
                                                (units_count/available/reserved/sold,
                                                 min/max price_uf)
  POST   /api/v1/projects                    — crear (admin)
  GET    /api/v1/projects/{id}               — detalle
  PUT    /api/v1/projects/{id}               — actualizar
  DELETE /api/v1/projects/{id}               — borrar (las propiedades asociadas
                                                quedan con project_id NULL)
  GET    /api/v1/projects/{id}/properties    — unidades del proyecto
                                                (respuesta resumida para el acordeón)
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.models.project import Project
from app.models.property import Property

logger = logging.getLogger(__name__)
router = APIRouter(tags=["projects"])

_ADMIN_ROLES = {"ADMIN", "SUPERADMIN"}


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    developer: Optional[str] = None
    status: str = "en_venta"
    commune: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    delivery_date: Optional[date] = None
    total_units: Optional[int] = None
    available_units: Optional[int] = None
    common_amenities: Optional[List[str]] = None
    images: Optional[List[Dict[str, Any]]] = None
    brochure_url: Optional[str] = None
    virtual_tour_url: Optional[str] = None
    subsidio_eligible: bool = False
    financing_options: Optional[List[str]] = None
    highlights: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    developer: Optional[str] = None
    status: Optional[str] = None
    commune: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    delivery_date: Optional[date] = None
    total_units: Optional[int] = None
    available_units: Optional[int] = None
    common_amenities: Optional[List[str]] = None
    images: Optional[List[Dict[str, Any]]] = None
    brochure_url: Optional[str] = None
    virtual_tour_url: Optional[str] = None
    subsidio_eligible: Optional[bool] = None
    financing_options: Optional[List[str]] = None
    highlights: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_admin(user: dict) -> None:
    if user.get("role") not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")


def _resolve_broker(user: dict, broker_id: Optional[int]) -> int:
    if user.get("role") == "SUPERADMIN":
        target = broker_id if broker_id is not None else user.get("broker_id")
    else:
        target = user.get("broker_id")
    if target is None:
        raise HTTPException(status_code=400, detail="broker_id requerido")
    return target


def _format(p: Project, aggregates: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    base = {
        "id": p.id,
        "broker_id": p.broker_id,
        "name": p.name,
        "code": p.code,
        "description": p.description,
        "developer": p.developer,
        "status": p.status,
        "commune": p.commune,
        "city": p.city,
        "region": p.region,
        "address": p.address,
        "latitude": float(p.latitude) if p.latitude else None,
        "longitude": float(p.longitude) if p.longitude else None,
        "delivery_date": p.delivery_date.isoformat() if p.delivery_date else None,
        "total_units": p.total_units,
        "available_units": p.available_units,
        "common_amenities": p.common_amenities,
        "images": p.images,
        "brochure_url": p.brochure_url,
        "virtual_tour_url": p.virtual_tour_url,
        "subsidio_eligible": p.subsidio_eligible,
        "financing_options": p.financing_options,
        "highlights": p.highlights,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }
    if aggregates is not None:
        base.update(aggregates)
    return base


def _format_unit_summary(prop: Property) -> Dict[str, Any]:
    """Respuesta resumida de una unidad para el acordeón."""
    return {
        "id": prop.id,
        "codigo": prop.codigo,
        "tipologia": prop.tipologia,
        "name": prop.name,
        "property_type": prop.property_type,
        "status": prop.status,
        "bedrooms": prop.bedrooms,
        "bathrooms": prop.bathrooms,
        "square_meters_useful": float(prop.square_meters_useful)
        if prop.square_meters_useful
        else None,
        "price_uf": float(prop.price_uf) if prop.price_uf else None,
        "has_offer": bool(prop.has_offer),
        "offer_price_uf": float(prop.offer_price_uf) if prop.offer_price_uf else None,
        "floor_number": prop.floor_number,
        "orientation": prop.orientation,
    }


def _aggregates_row_to_dict(row) -> Dict[str, Any]:
    return {
        "units_count": int(row.units_count or 0),
        "units_available": int(row.units_available or 0),
        "units_reserved": int(row.units_reserved or 0),
        "units_sold": int(row.units_sold or 0),
        "min_price_uf": float(row.min_price_uf) if row.min_price_uf else None,
        "max_price_uf": float(row.max_price_uf) if row.max_price_uf else None,
    }


def _empty_aggregates() -> Dict[str, Any]:
    return {
        "units_count": 0,
        "units_available": 0,
        "units_reserved": 0,
        "units_sold": 0,
        "min_price_uf": None,
        "max_price_uf": None,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_projects(
    status: Optional[str] = None,
    commune: Optional[str] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    broker_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    target_broker = _resolve_broker(current_user, broker_id)

    base = select(Project).where(Project.broker_id == target_broker)
    if status:
        base = base.where(Project.status == status)
    if commune:
        base = base.where(Project.commune.ilike(f"%{commune}%"))

    total_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(total_q)).scalar_one()

    page_q = base.order_by(Project.created_at.desc()).offset(offset).limit(limit)
    projects = (await db.execute(page_q)).scalars().all()

    proj_ids = [p.id for p in projects]
    agg_map: Dict[int, Dict[str, Any]] = {}
    if proj_ids:
        agg_q = (
            select(
                Property.project_id,
                func.count(Property.id).label("units_count"),
                func.sum(case((Property.status == "available", 1), else_=0)).label(
                    "units_available"
                ),
                func.sum(case((Property.status == "reserved", 1), else_=0)).label(
                    "units_reserved"
                ),
                func.sum(case((Property.status == "sold", 1), else_=0)).label(
                    "units_sold"
                ),
                func.min(Property.price_uf).label("min_price_uf"),
                func.max(Property.price_uf).label("max_price_uf"),
            )
            .where(
                Property.project_id.in_(proj_ids),
                Property.broker_id == target_broker,
            )
            .group_by(Property.project_id)
        )
        for row in (await db.execute(agg_q)).all():
            agg_map[row.project_id] = _aggregates_row_to_dict(row)

    items = [_format(p, agg_map.get(p.id, _empty_aggregates())) for p in projects]

    # Aggregates para "Sin proyecto" (propiedades sueltas) — se expone solo en
    # la primera página para no repetirlo al paginar.
    orphan_agg: Optional[Dict[str, Any]] = None
    if offset == 0:
        orphan_q = select(
            func.count(Property.id).label("units_count"),
            func.sum(case((Property.status == "available", 1), else_=0)).label(
                "units_available"
            ),
            func.sum(case((Property.status == "reserved", 1), else_=0)).label(
                "units_reserved"
            ),
            func.sum(case((Property.status == "sold", 1), else_=0)).label(
                "units_sold"
            ),
            func.min(Property.price_uf).label("min_price_uf"),
            func.max(Property.price_uf).label("max_price_uf"),
        ).where(
            Property.broker_id == target_broker,
            Property.project_id.is_(None),
        )
        orow = (await db.execute(orphan_q)).one()
        if orow.units_count and int(orow.units_count) > 0:
            orphan_agg = _aggregates_row_to_dict(orow)

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": items,
        "orphan_units": orphan_agg,
    }


@router.post("", status_code=201)
async def create_project(
    body: ProjectCreate,
    broker_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    target_broker = _resolve_broker(current_user, broker_id)

    project = Project(broker_id=target_broker, **body.model_dump(exclude_none=True))
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return _format(project)


@router.get("/{project_id}")
async def get_project(
    project_id: int,
    broker_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    target_broker = _resolve_broker(current_user, broker_id)
    res = await db.execute(
        select(Project).where(
            Project.id == project_id, Project.broker_id == target_broker
        )
    )
    project = res.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return _format(project)


@router.put("/{project_id}")
async def update_project(
    project_id: int,
    body: ProjectUpdate,
    broker_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    target_broker = _resolve_broker(current_user, broker_id)
    res = await db.execute(
        select(Project).where(
            Project.id == project_id, Project.broker_id == target_broker
        )
    )
    project = res.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(project, k, v)

    await db.commit()
    await db.refresh(project)
    return _format(project)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: int,
    broker_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    target_broker = _resolve_broker(current_user, broker_id)
    res = await db.execute(
        select(Project).where(
            Project.id == project_id, Project.broker_id == target_broker
        )
    )
    project = res.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)
    await db.commit()


@router.get("/{project_id}/properties")
async def get_project_properties(
    project_id: int,
    status: Optional[str] = None,
    tipologia: Optional[str] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    broker_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Lista resumida de unidades del proyecto. Pensado para el acordeón."""
    _require_admin(current_user)
    target_broker = _resolve_broker(current_user, broker_id)

    # Validar que el proyecto pertenece al broker (defensa multi-tenant).
    res = await db.execute(
        select(Project.id).where(
            Project.id == project_id, Project.broker_id == target_broker
        )
    )
    if res.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Project not found")

    q = select(Property).where(
        Property.broker_id == target_broker,
        Property.project_id == project_id,
    )
    if status:
        q = q.where(Property.status == status)
    if tipologia:
        q = q.where(Property.tipologia == tipologia)

    total_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(total_q)).scalar_one()

    q = (
        q.order_by(Property.tipologia.asc().nullslast(), Property.codigo.asc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await db.execute(q)).scalars().all()
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [_format_unit_summary(p) for p in rows],
    }
