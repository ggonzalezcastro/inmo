"""
DealSlotCatalog — defines document slots required at each deal stage.

No SQLAlchemy or DB dependencies; pure Python data structures.
"""
from dataclasses import dataclass, field
from typing import Optional

ALLOWED_MIME_TYPES = frozenset([
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
])

SLOT_STAGE_ORDER = [
    "draft",
    "reserva",
    "docs_pendientes",
    "en_aprobacion_bancaria",
    "promesa_redaccion",
    "promesa_firmada",
    "escritura_firmada",
]


@dataclass(frozen=True)
class SlotDefinition:
    key: str
    label: str
    required_for_stage: str       # stage where this slot blocks progression
    max_count: int = 1            # number of files (e.g. 3 for liquidaciones)
    supports_co_titular: bool = False
    optional: bool = False        # if True, doesn't block stage advance
    mime_whitelist: frozenset = field(default_factory=lambda: ALLOWED_MIME_TYPES)
    # if set, slot is only required for this delivery_type
    delivery_type_filter: Optional[str] = None  # "inmediata" | "futura" | None


SLOT_DEFINITIONS: dict[str, SlotDefinition] = {
    # ── reserva ──────────────────────────────────────────────────────────────
    "comprobante_transferencia": SlotDefinition(
        key="comprobante_transferencia",
        label="Comprobante de transferencia bancaria (reserva)",
        required_for_stage="reserva",
        max_count=1,
    ),
    # ── docs_pendientes (required for promesa) ────────────────────────────────
    "ci_anverso": SlotDefinition(
        key="ci_anverso",
        label="Cédula de identidad — anverso",
        required_for_stage="docs_pendientes",
        max_count=1,
        supports_co_titular=True,
    ),
    "ci_reverso": SlotDefinition(
        key="ci_reverso",
        label="Cédula de identidad — reverso",
        required_for_stage="docs_pendientes",
        max_count=1,
        supports_co_titular=True,
    ),
    "cmf_deuda": SlotDefinition(
        key="cmf_deuda",
        label="Deuda CMF con fecha de emisión mes actual",
        required_for_stage="docs_pendientes",
        max_count=1,
    ),
    "liquidacion_sueldo": SlotDefinition(
        key="liquidacion_sueldo",
        label="Liquidación de sueldo",
        required_for_stage="docs_pendientes",
        max_count=3,
    ),
    "afp_cotizaciones": SlotDefinition(
        key="afp_cotizaciones",
        label="Certificado de Cotizaciones AFP (24 meses)",
        required_for_stage="docs_pendientes",
        max_count=1,
    ),
    "cert_matrimonio": SlotDefinition(
        key="cert_matrimonio",
        label="Certificado de Matrimonio con emisión mes actual",
        required_for_stage="docs_pendientes",
        max_count=1,
        optional=True,
    ),
    "antiguedad_laboral": SlotDefinition(
        key="antiguedad_laboral",
        label="Certificado de Antigüedad Laboral del empleador",
        required_for_stage="docs_pendientes",
        max_count=1,
    ),
    # ── en_aprobacion_bancaria ────────────────────────────────────────────────
    "pre_aprobacion_banco": SlotDefinition(
        key="pre_aprobacion_banco",
        label="Pre-aprobación bancaria",
        required_for_stage="en_aprobacion_bancaria",
        max_count=1,
        delivery_type_filter="futura",
    ),
    "aprobacion_banco": SlotDefinition(
        key="aprobacion_banco",
        label="Aprobación bancaria",
        required_for_stage="en_aprobacion_bancaria",
        max_count=1,
        delivery_type_filter="inmediata",
    ),
    # ── promesa_redaccion ─────────────────────────────────────────────────────
    "borrador_promesa": SlotDefinition(
        key="borrador_promesa",
        label="Borrador de promesa de compraventa",
        required_for_stage="promesa_redaccion",
        max_count=1,
    ),
    # ── promesa_firmada ───────────────────────────────────────────────────────
    "promesa_firmada": SlotDefinition(
        key="promesa_firmada",
        label="Promesa de compraventa firmada",
        required_for_stage="promesa_firmada",
        max_count=1,
    ),
    # ── escritura_firmada ─────────────────────────────────────────────────────
    "escritura": SlotDefinition(
        key="escritura",
        label="Escritura firmada",
        required_for_stage="escritura_firmada",
        max_count=1,
    ),
    # ── catch-all (AI intake) ─────────────────────────────────────────────────
    # Documents uploaded by the AI whose type could not be inferred from the
    # filename.  Optional so they never block stage advancement — they exist
    # only to queue them for human review.
    "sin_clasificar": SlotDefinition(
        key="sin_clasificar",
        label="Documento sin clasificar (requiere revisión)",
        required_for_stage="docs_pendientes",
        max_count=20,
        optional=True,
    ),
}


@dataclass
class SlotRequirement:
    slot_key: str
    definition: SlotDefinition
    required: bool
    co_titular_index: int = 0


def get_required_slots_for_stage(
    stage: str, delivery_type: str = "desconocida"
) -> list[SlotRequirement]:
    """Return slots required to advance INTO the given stage."""
    results: list[SlotRequirement] = []
    for slot in SLOT_DEFINITIONS.values():
        if slot.required_for_stage != stage:
            continue
        # Apply delivery_type filter: skip if filter set and doesn't match
        if slot.delivery_type_filter is not None and slot.delivery_type_filter != delivery_type:
            continue
        results.append(
            SlotRequirement(
                slot_key=slot.key,
                definition=slot,
                required=not slot.optional,
            )
        )
    return results


def get_all_required_slots_for_promesa(delivery_type: str) -> list[SlotRequirement]:
    """Return all slots required before promesa_redaccion (inclusive)."""
    cutoff = SLOT_STAGE_ORDER.index("promesa_redaccion")
    relevant_stages = set(SLOT_STAGE_ORDER[: cutoff + 1])

    results: list[SlotRequirement] = []
    for slot in SLOT_DEFINITIONS.values():
        if slot.required_for_stage not in relevant_stages:
            continue
        if slot.delivery_type_filter is not None and slot.delivery_type_filter != delivery_type:
            continue
        results.append(
            SlotRequirement(
                slot_key=slot.key,
                definition=slot,
                required=not slot.optional,
            )
        )
    return results


def is_slot_key_valid(key: str) -> bool:
    return key in SLOT_DEFINITIONS
