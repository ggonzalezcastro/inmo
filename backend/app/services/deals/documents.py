"""
DealDocumentService — manages file uploads and review workflow for Deal documents.
"""
import uuid
from datetime import datetime, timezone

from fastapi import UploadFile
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_log import ActivityLog
from app.models.audit_log import AuditLog
from app.models.broker import BrokerLeadConfig
from app.models.deal import Deal
from app.models.deal_document import DealDocument
from app.services.deals.exceptions import DealError
from app.services.deals.metrics import record_document_uploaded
from app.services.deals.slots import SLOT_DEFINITIONS, is_slot_key_valid
from app.services.storage.facade import FileStorageService
from app.services.storage.validation import FileValidationError, get_file_extension, validate_upload


class DealDocumentService:

    @staticmethod
    async def upload(
        db: AsyncSession,
        deal: Deal,
        slot: str,
        file: UploadFile,
        slot_index: int = 0,
        co_titular_index: int = 0,
        uploaded_by_user_id: int | None = None,
        uploaded_by_ai: bool = False,
        base_url: str = "",
    ) -> DealDocument:
        """
        Upload a file to a deal's document slot.

        - Validates slot key exists in SLOT_DEFINITIONS
        - If uploaded_by_ai=True, checks BrokerLeadConfig.ai_can_upload_deal_files
        - Validates file (mime, size, sha256) via validate_upload()
        - Stores file via FileStorageService
        - Creates DealDocument with status="recibido"
        - AI uploads always land in "recibido" (never auto-approved)
        """
        if not is_slot_key_valid(slot):
            raise DealError(f"Slot de documento inválido: '{slot}'", status_code=400)

        if uploaded_by_ai:
            result = await db.execute(
                select(BrokerLeadConfig).where(BrokerLeadConfig.broker_id == deal.broker_id)
            )
            config = result.scalar_one_or_none()
            if not config or not config.ai_can_upload_deal_files:
                raise DealError(
                    "La IA no tiene permiso para subir documentos en este broker.",
                    status_code=403,
                )

        try:
            file_bytes, mime_type, sha256 = await validate_upload(file, slot)
        except FileValidationError as e:
            raise DealError(e.message, status_code=e.status_code)

        doc_uuid = str(uuid.uuid4())
        ext = get_file_extension(mime_type)
        storage_key = FileStorageService.make_key(deal.broker_id, deal.id, doc_uuid, ext)

        await FileStorageService.upload(file_bytes, storage_key, mime_type)

        now = datetime.now(timezone.utc)
        doc = DealDocument(
            deal_id=deal.id,
            slot=slot,
            slot_index=slot_index,
            co_titular_index=co_titular_index,
            status="recibido",
            storage_key=storage_key,
            original_filename=file.filename,
            mime_type=mime_type,
            size_bytes=len(file_bytes),
            sha256=sha256,
            uploaded_by_user_id=uploaded_by_user_id,
            uploaded_by_ai=uploaded_by_ai,
            uploaded_at=now,
        )
        db.add(doc)
        await db.flush()

        db.add(ActivityLog(
            lead_id=deal.lead_id,
            action_type="deal_document_uploaded",
            details={
                "deal_id": deal.id,
                "doc_id": doc.id,
                "slot": slot,
                "slot_index": slot_index,
                "co_titular_index": co_titular_index,
                "original_filename": file.filename,
                "mime_type": mime_type,
                "uploaded_by_user_id": uploaded_by_user_id,
                "uploaded_by_ai": uploaded_by_ai,
                "broker_id": deal.broker_id,
            },
            timestamp=now,
        ))

        record_document_uploaded(slot=slot, actor_type="ai" if uploaded_by_ai else "user")
        return doc

    @staticmethod
    async def approve(
        db: AsyncSession,
        doc: DealDocument,
        deal: Deal,
        reviewer_user_id: int,
        notes: str | None = None,
    ) -> DealDocument:
        """Approve a document. Status: recibido → aprobado."""
        if doc.status == "aprobado":
            return doc  # idempotent
        if doc.storage_key is None:
            raise DealError("No hay archivo subido para este documento.", status_code=400)

        prev_status = doc.status
        now = datetime.now(timezone.utc)

        doc.status = "aprobado"
        doc.reviewed_by_user_id = reviewer_user_id
        doc.reviewed_at = now
        doc.review_notes = notes
        db.add(doc)

        db.add(ActivityLog(
            lead_id=deal.lead_id,
            action_type="deal_document_approved",
            details={
                "deal_id": deal.id,
                "doc_id": doc.id,
                "slot": doc.slot,
                "broker_id": deal.broker_id,
                "reviewer_user_id": reviewer_user_id,
                "notes": notes,
            },
            timestamp=now,
        ))

        db.add(AuditLog(
            user_id=reviewer_user_id,
            broker_id=deal.broker_id,
            action="approve",
            resource_type="deal_document",
            resource_id=doc.id,
            changes={
                "status": {"before": prev_status, "after": "aprobado"},
                "notes": notes,
            },
            timestamp=now,
        ))

        return doc

    @staticmethod
    async def reject(
        db: AsyncSession,
        doc: DealDocument,
        deal: Deal,
        reviewer_user_id: int,
        notes: str,  # required for rejection
    ) -> DealDocument:
        """
        Reject a document. Status → rechazado.
        Does NOT delete the file (kept for audit). Allows re-upload.
        """
        prev_status = doc.status
        now = datetime.now(timezone.utc)

        doc.status = "rechazado"
        doc.reviewed_by_user_id = reviewer_user_id
        doc.reviewed_at = now
        doc.review_notes = notes
        db.add(doc)

        db.add(ActivityLog(
            lead_id=deal.lead_id,
            action_type="deal_document_rejected",
            details={
                "deal_id": deal.id,
                "doc_id": doc.id,
                "slot": doc.slot,
                "broker_id": deal.broker_id,
                "reviewer_user_id": reviewer_user_id,
                "notes": notes,
            },
            timestamp=now,
        ))

        db.add(AuditLog(
            user_id=reviewer_user_id,
            broker_id=deal.broker_id,
            action="reject",
            resource_type="deal_document",
            resource_id=doc.id,
            changes={
                "status": {"before": prev_status, "after": "rechazado"},
                "notes": notes,
            },
            timestamp=now,
        ))

        return doc

    @staticmethod
    async def delete(
        db: AsyncSession,
        doc: DealDocument,
    ) -> None:
        """Delete a document record and its file from storage."""
        if doc.storage_key:
            try:
                await FileStorageService.delete(doc.storage_key)
            except FileNotFoundError:
                pass  # already gone
        await db.delete(doc)

    @staticmethod
    async def get_doc(
        db: AsyncSession,
        doc_id: int,
        deal_id: int,
    ) -> DealDocument:
        """Get a single document, verifying it belongs to the deal."""
        result = await db.execute(
            select(DealDocument).where(
                and_(DealDocument.id == doc_id, DealDocument.deal_id == deal_id)
            )
        )
        doc = result.scalar_one_or_none()
        if not doc:
            raise DealError(f"Documento {doc_id} no encontrado.", status_code=404)
        return doc

    @staticmethod
    def build_download_url(doc: DealDocument, broker_id: int, base_url: str) -> str | None:
        """Generate a signed download URL for a document, or None if no file.

        TODO: When routes_documents.py is created, add an AuditLog entry
        (action="download", resource_type="deal_document") in the GET /download
        endpoint handler so document downloads are tracked for compliance.
        """
        if not doc.storage_key:
            return None
        return FileStorageService.sign_download_url(doc.storage_key, broker_id, base_url)
