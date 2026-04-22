"""
Deal state machine — defines allowed transitions and their guards.

Each transition can have a guard function that validates preconditions.
Guards receive (deal, db) and raise DealError if preconditions are not met.

ALLOWED_TRANSITIONS: {from_stage: {to_stage: guard_fn | None}}
"""
from datetime import datetime, timezone
from typing import Callable, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deal import Deal
from app.models.deal_document import DealDocument
from app.services.deals.exceptions import DealError
from app.services.deals.slots import get_all_required_slots_for_promesa

# Guard function type: async fn(deal, db) -> None, raises DealError if blocked
GuardFn = Callable[..., None]


async def _guard_draft_to_reserva(deal: Deal, db: AsyncSession) -> None:
    result = await db.execute(
        select(DealDocument).where(
            and_(
                DealDocument.deal_id == deal.id,
                DealDocument.slot == "comprobante_transferencia",
                DealDocument.status.in_(["recibido", "aprobado"]),
            )
        )
    )
    if not result.scalar_one_or_none():
        raise DealError(
            "Para avanzar a 'reserva' se requiere el comprobante de transferencia.",
            status_code=422,
        )


async def _guard_docs_to_aprobacion(deal: Deal, db: AsyncSession) -> None:
    """All required (non-optional) docs for promesa stage must be 'aprobado'."""
    required_slots = get_all_required_slots_for_promesa(deal.delivery_type)
    required_non_optional = [s for s in required_slots if s.required and not s.definition.optional]

    for slot_req in required_non_optional:
        for idx in range(slot_req.definition.max_count):
            result = await db.execute(
                select(DealDocument).where(
                    and_(
                        DealDocument.deal_id == deal.id,
                        DealDocument.slot == slot_req.slot_key,
                        DealDocument.slot_index == idx,
                        DealDocument.status == "aprobado",
                    )
                )
            )
            if not result.scalar_one_or_none():
                raise DealError(
                    f"Documento requerido pendiente: {slot_req.definition.label} (índice {idx}). "
                    "Todos los documentos requeridos deben estar aprobados.",
                    status_code=422,
                )


async def _guard_aprobacion_to_promesa(deal: Deal, db: AsyncSession) -> None:
    if deal.bank_review_status != "aprobado":
        raise DealError(
            "La aprobación bancaria debe estar confirmada para avanzar a redacción de promesa.",
            status_code=422,
        )
    if deal.delivery_type == "futura" and deal.jefatura_review_status != "aprobado":
        raise DealError(
            "Para entrega futura, la revisión de jefatura debe estar aprobada.",
            status_code=422,
        )


async def _guard_redaccion_to_firmada(deal: Deal, db: AsyncSession) -> None:
    result = await db.execute(
        select(DealDocument).where(
            and_(
                DealDocument.deal_id == deal.id,
                DealDocument.slot == "promesa_firmada",
                DealDocument.status == "aprobado",
            )
        )
    )
    if not result.scalar_one_or_none():
        raise DealError(
            "La promesa firmada debe estar aprobada para continuar.",
            status_code=422,
        )


async def _guard_promesa_to_escritura(deal: Deal, db: AsyncSession) -> None:
    result = await db.execute(
        select(DealDocument).where(
            and_(
                DealDocument.deal_id == deal.id,
                DealDocument.slot == "escritura",
                DealDocument.status == "aprobado",
            )
        )
    )
    if not result.scalar_one_or_none():
        raise DealError(
            "La escritura firmada debe estar aprobada para completar el deal.",
            status_code=422,
        )


ALLOWED_TRANSITIONS: dict[str, dict[str, Optional[GuardFn]]] = {
    "draft": {
        "reserva": _guard_draft_to_reserva,
        "cancelado": None,
    },
    "reserva": {
        "docs_pendientes": None,
        "cancelado": None,
    },
    "docs_pendientes": {
        "en_aprobacion_bancaria": _guard_docs_to_aprobacion,
        "cancelado": None,
    },
    "en_aprobacion_bancaria": {
        "promesa_redaccion": _guard_aprobacion_to_promesa,
        "cancelado": None,
    },
    "promesa_redaccion": {
        "promesa_firmada": _guard_redaccion_to_firmada,
        "cancelado": None,
    },
    "promesa_firmada": {
        "escritura_firmada": _guard_promesa_to_escritura,
        "cancelado": None,
    },
    "escritura_firmada": {},  # terminal — deal is complete
    "cancelado": {},          # terminal
}

_STAGE_TIMESTAMPS: dict[str, Optional[str]] = {
    "reserva": "reserva_at",
    "docs_pendientes": None,
    "en_aprobacion_bancaria": None,
    "promesa_redaccion": None,
    "promesa_firmada": "promesa_signed_at",
    "escritura_firmada": "escritura_signed_at",
    "cancelado": "cancelled_at",
}


async def transition(
    deal: Deal,
    to_stage: str,
    db: AsyncSession,
    cancellation_reason: str | None = None,
    cancellation_notes: str | None = None,
) -> None:
    """
    Validate and apply a stage transition to a deal.

    Does NOT apply side effects (Property/Lead changes) — those are in effects.py.
    Updates stage and relevant timestamps on the deal.

    Raises: DealError if transition is not allowed or guard fails.
    """
    current = deal.stage
    allowed = ALLOWED_TRANSITIONS.get(current, {})

    if to_stage not in allowed:
        raise DealError(
            f"Transición no permitida: {current} → {to_stage}",
            status_code=422,
        )

    if to_stage == "cancelado" and not cancellation_reason:
        raise DealError("Se requiere un motivo de cancelación.", status_code=422)

    guard = allowed[to_stage]
    if guard:
        await guard(deal, db)

    now = datetime.now(timezone.utc)
    deal.stage = to_stage

    ts_attr = _STAGE_TIMESTAMPS.get(to_stage)
    if ts_attr:
        setattr(deal, ts_attr, now)

    if to_stage == "cancelado":
        deal.cancellation_reason = cancellation_reason
        deal.cancellation_notes = cancellation_notes

    db.add(deal)
