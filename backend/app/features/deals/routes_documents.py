"""
DealDocuments REST router.

Endpoints:
  POST   /api/deals/{deal_id}/documents                          — upload a file to a slot
  GET    /api/deals/{deal_id}/documents/{doc_id}/download        — stream file with JWT auth
  POST   /api/deals/{deal_id}/documents/{doc_id}/approve         — approve a document
  POST   /api/deals/{deal_id}/documents/{doc_id}/reject          — reject a document
  DELETE /api/deals/{deal_id}/documents/{doc_id}                 — delete a document
"""
import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.permissions import Permissions
from app.schemas.deal import DealDocumentApproveRequest, DealDocumentRejectRequest, DealDocumentRead
from app.services.deals.documents import DealDocumentService
from app.services.deals.exceptions import DealError
from app.services.deals.service import DealService
from app.services.storage.facade import FileStorageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/deals", tags=["deal-documents"])


def _base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def _deal_error_to_http(e: DealError) -> HTTPException:
    return HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/{deal_id}/documents", response_model=DealDocumentRead, status_code=201)
async def upload_document(
    deal_id: int,
    request: Request,
    file: UploadFile,
    slot: str = Form(...),
    slot_index: int = Form(0),
    co_titular_index: int = Form(0),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(Permissions.require_write_access),
):
    broker_id: int = current_user["broker_id"]
    _raw_uid = current_user.get("user_id") or current_user.get("id")
    uploader_id = int(_raw_uid) if _raw_uid is not None else None
    try:
        deal = await DealService.get(db, deal_id, broker_id)
        doc = await DealDocumentService.upload(
            db,
            deal,
            slot,
            file,
            slot_index=slot_index,
            co_titular_index=co_titular_index,
            uploaded_by_user_id=uploader_id,
        )
        download_url = DealDocumentService.build_download_url(doc, broker_id, _base_url(request))
        await db.commit()
        await db.refresh(doc)
    except DealError as e:
        await db.rollback()
        raise _deal_error_to_http(e)

    result = DealDocumentRead.model_validate(doc)
    result.download_url = download_url
    return result


@router.get("/{deal_id}/documents/{doc_id}/download")
async def download_document(
    deal_id: int,
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    broker_id: int = current_user["broker_id"]
    try:
        deal = await DealService.get(db, deal_id, broker_id)
        doc = await DealDocumentService.get_doc(db, doc_id, deal.id)
    except DealError as e:
        raise _deal_error_to_http(e)

    if not doc.storage_key:
        raise HTTPException(status_code=404, detail="No hay archivo subido para este documento.")

    logger.info("Document download: deal=%s doc=%s user=%s", deal_id, doc_id, current_user.get("id"))

    try:
        stream = await FileStorageService.open_stream(doc.storage_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Archivo no encontrado en storage.")

    filename = doc.original_filename or doc.storage_key.rsplit("/", 1)[-1]
    content_type = doc.mime_type or "application/octet-stream"

    async def _gen():
        async for chunk in stream:
            yield chunk

    return StreamingResponse(
        _gen(),
        media_type=content_type,
        headers={"Content-Disposition": f"inline; filename={filename!r}"},
    )


@router.post("/{deal_id}/documents/{doc_id}/approve", response_model=DealDocumentRead)
async def approve_document(
    deal_id: int,
    doc_id: int,
    request: Request,
    body: DealDocumentApproveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(Permissions.require_write_access),
):
    broker_id: int = current_user["broker_id"]
    _raw_uid = current_user.get("user_id") or current_user.get("id")
    reviewer_id: int = int(_raw_uid) if _raw_uid is not None else 0
    try:
        deal = await DealService.get(db, deal_id, broker_id)
        doc = await DealDocumentService.get_doc(db, doc_id, deal.id)
        doc = await DealDocumentService.approve(db, doc, deal=deal, reviewer_user_id=reviewer_id, notes=body.notes)
        await db.commit()
        await db.refresh(doc)
    except DealError as e:
        await db.rollback()
        raise _deal_error_to_http(e)

    result = DealDocumentRead.model_validate(doc)
    result.download_url = DealDocumentService.build_download_url(doc, broker_id, _base_url(request))
    return result


@router.post("/{deal_id}/documents/{doc_id}/reject", response_model=DealDocumentRead)
async def reject_document(
    deal_id: int,
    doc_id: int,
    request: Request,
    body: DealDocumentRejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(Permissions.require_write_access),
):
    broker_id: int = current_user["broker_id"]
    _raw_uid = current_user.get("user_id") or current_user.get("id")
    reviewer_id: int = int(_raw_uid) if _raw_uid is not None else 0
    try:
        deal = await DealService.get(db, deal_id, broker_id)
        doc = await DealDocumentService.get_doc(db, doc_id, deal.id)
        doc = await DealDocumentService.reject(db, doc, reviewer_user_id=reviewer_id, notes=body.notes)
        await db.commit()
        await db.refresh(doc)
    except DealError as e:
        await db.rollback()
        raise _deal_error_to_http(e)

    result = DealDocumentRead.model_validate(doc)
    result.download_url = DealDocumentService.build_download_url(doc, broker_id, _base_url(request))
    return result


@router.delete("/{deal_id}/documents/{doc_id}", status_code=204)
async def delete_document(
    deal_id: int,
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(Permissions.require_write_access),
):
    broker_id: int = current_user["broker_id"]
    try:
        deal = await DealService.get(db, deal_id, broker_id)
        doc = await DealDocumentService.get_doc(db, doc_id, deal.id)
        await DealDocumentService.delete(db, doc)
        await db.commit()
    except DealError as e:
        await db.rollback()
        raise _deal_error_to_http(e)
