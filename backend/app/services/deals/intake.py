"""
Deal document intake — handles file attachments from AI chat.

Called by the chat orchestrator when:
  1. Incoming message has a file/media attachment
  2. Broker has ai_can_upload_deal_files=True
  3. Lead has an active Deal (not cancelled/completed)

Files are attached with status="recibido", slot inferred or "sin_clasificar".
Always requires human approval — AI never auto-approves.
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deal_document import DealDocument  # noqa: F401 — re-exported for callers
from app.services.deals.service import DealService

logger = logging.getLogger(__name__)

# Stages considered "terminal" — no new documents should be attached.
_INACTIVE_STAGES = frozenset({"cancelado", "escritura_firmada"})


async def process_ai_file_attachment(
    db: AsyncSession,
    broker_id: int,
    lead_id: int,
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    broker_lead_config: "object | None" = None,
) -> "DealDocument | None":
    """
    Process a file attachment received from a lead via chat.

    Returns the created DealDocument, or None if no active deal exists
    or AI uploads are disabled for this broker.
    """
    # 1. Check if AI uploads are enabled
    if not broker_lead_config or not getattr(broker_lead_config, "ai_can_upload_deal_files", False):
        return None

    # 2. Find active deal for this lead (not cancelled, not escritura_firmada)
    deals = await DealService.list_deals(
        db, broker_id, lead_id=lead_id, limit=10
    )
    active_deal = next(
        (d for d in deals if d.stage not in _INACTIVE_STAGES),
        None,
    )
    if not active_deal:
        return None

    # 3. Infer slot (keyword heuristic first, LLM fallback)
    slot = await _infer_slot(filename, mime_type)

    # 4. Build a minimal UploadFile-compatible wrapper from the raw bytes
    file_obj = _make_upload_file(file_bytes, filename, mime_type)

    # 5. Upload via DealDocumentService (status="recibido", never auto-approved)
    from app.services.deals.documents import DealDocumentService
    try:
        doc = await DealDocumentService.upload(
            db=db,
            deal=active_deal,
            slot=slot,
            file=file_obj,
            uploaded_by_ai=True,
            base_url="",
        )
        logger.info(
            "[DealIntake] Uploaded doc id=%s slot=%s deal_id=%s lead_id=%s",
            doc.id, slot, active_deal.id, lead_id,
        )
        return doc
    except Exception as exc:
        logger.warning("[DealIntake] AI file intake failed (non-fatal): %s", exc)
        return None


async def _infer_slot(filename: str, mime_type: str) -> str:
    """Try keyword heuristic first, then LLM if result is 'sin_clasificar'."""
    slot = _infer_slot_from_filename(filename, mime_type)
    if slot != "sin_clasificar":
        return slot

    try:
        from app.services.agents.tools.deal_doc_tools import infer_doc_slot_with_llm
        slot = await infer_doc_slot_with_llm(filename, mime_type)
    except Exception:
        pass  # Stay with sin_clasificar

    return slot


def _infer_slot_from_filename(filename: str, mime_type: str) -> str:
    """
    Simple heuristic slot inference from filename.
    Returns a slot key or "sin_clasificar" if no hint matches.
    """
    filename_lower = filename.lower()

    hints = {
        "ci_anverso": ["cedula", "cédula", "dni", " ci ", "ci_", "_ci", "anverso"],
        "ci_reverso": ["reverso"],
        "cmf_deuda": ["cmf", "deuda_cmf", "boletin_cmf"],
        "liquidacion_sueldo": ["liquidacion", "liquidación", "sueldo", "remuneracion"],
        "afp_cotizaciones": ["afp", "cotizacion", "cotización"],
        "cert_matrimonio": ["matrimonio", "certificado_matrimonio"],
        "antiguedad_laboral": ["antiguedad", "antigüedad", "laboral", "empleador"],
        "comprobante_transferencia": ["comprobante", "transferencia", "deposito", "depósito"],
        "escritura": ["escritura"],
        "promesa_firmada": ["promesa"],
        "aprobacion_banco": ["banco", "aprobacion", "aprobación", "credito", "crédito"],
    }

    for slot_key, keywords in hints.items():
        if any(kw in filename_lower for kw in keywords):
            return slot_key

    return "sin_clasificar"


def _make_upload_file(data: bytes, filename: str, content_type: str):
    """Create a minimal UploadFile-compatible object from raw bytes."""

    class BytesUploadFile:
        def __init__(self, data: bytes, filename: str, content_type: str) -> None:
            self._data = data
            self.filename = filename
            self.content_type = content_type

        async def read(self, n: int = -1) -> bytes:
            return self._data if n < 0 else self._data[:n]

    return BytesUploadFile(data, filename, content_type)
