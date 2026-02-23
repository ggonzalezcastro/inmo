"""
Knowledge Base CRUD API (TASK-024).

Endpoints
---------
    GET    /api/v1/kb                          — list documents
    POST   /api/v1/kb                          — add document (auto-embeds)
    GET    /api/v1/kb/search?q=...             — semantic search
    PUT    /api/v1/kb/{id}                     — update document
    DELETE /api/v1/kb/{id}                     — delete document
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.services.knowledge.rag_service import RAGService

router = APIRouter()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    source_type: str = Field("custom", pattern=r"^(property|faq|policy|subsidy|custom)$")
    metadata: Optional[dict] = None
    broker_id: Optional[int] = None  # SUPERADMIN only


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = Field(None, min_length=1)
    source_type: Optional[str] = Field(None, pattern=r"^(property|faq|policy|subsidy|custom)$")
    metadata: Optional[dict] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_broker(current_user: dict, target_broker_id: Optional[int]) -> int:
    role = (current_user.get("role") or "").upper()
    user_broker_id = current_user.get("broker_id")

    if role == "SUPERADMIN":
        if not target_broker_id:
            raise HTTPException(422, "broker_id required for superadmin")
        return target_broker_id

    if not user_broker_id:
        raise HTTPException(403, "No broker associated with user")

    if target_broker_id and target_broker_id != user_broker_id:
        raise HTTPException(403, "Access denied")

    return user_broker_id


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_documents(
    broker_id: Optional[int] = Query(None),
    source_type: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List knowledge base documents for a broker."""
    effective_broker_id = _resolve_broker(current_user, broker_id)
    docs = await RAGService.list_documents(
        db,
        broker_id=effective_broker_id,
        source_type=source_type,
        offset=offset,
        limit=limit,
    )
    return {"broker_id": effective_broker_id, "total": len(docs), "items": docs}


@router.post("", status_code=201)
async def add_document(
    body: DocumentCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Add a document to the knowledge base.

    The document is automatically embedded with Gemini text-embedding-004
    and stored with a pgvector column for semantic search.
    """
    effective_broker_id = _resolve_broker(current_user, body.broker_id)
    entry = await RAGService.add_document(
        db,
        broker_id=effective_broker_id,
        title=body.title,
        content=body.content,
        source_type=body.source_type,
        metadata=body.metadata,
    )
    return {
        "id": entry.id,
        "broker_id": entry.broker_id,
        "title": entry.title,
        "source_type": entry.source_type,
        "has_embedding": entry.embedding is not None,
        "created_at": entry.created_at.isoformat(),
    }


@router.get("/search")
async def search_kb(
    q: str = Query(..., min_length=2, description="Search query"),
    broker_id: Optional[int] = Query(None),
    source_type: Optional[str] = Query(None),
    top_k: int = Query(3, ge=1, le=10),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Semantic search over the knowledge base.

    Returns top-K chunks sorted by cosine similarity.
    Minimum similarity threshold: 0.60.
    """
    effective_broker_id = _resolve_broker(current_user, broker_id)
    results = await RAGService.search(
        db,
        broker_id=effective_broker_id,
        query=q,
        top_k=top_k,
        source_type=source_type,
    )
    return {"broker_id": effective_broker_id, "query": q, "results": results}


@router.put("/{entry_id}")
async def update_document(
    entry_id: int,
    body: DocumentUpdate,
    broker_id: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a knowledge base document.

    If ``content`` is changed, the embedding is automatically recomputed.
    """
    effective_broker_id = _resolve_broker(current_user, broker_id)
    updated = await RAGService.update_document(
        db,
        entry_id=entry_id,
        broker_id=effective_broker_id,
        **body.model_dump(exclude_none=True),
    )
    if not updated:
        raise HTTPException(404, f"Document {entry_id} not found")
    return {
        "id": updated.id,
        "title": updated.title,
        "source_type": updated.source_type,
        "has_embedding": updated.embedding is not None,
        "updated_at": updated.updated_at.isoformat(),
    }


@router.delete("/{entry_id}")
async def delete_document(
    entry_id: int,
    broker_id: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a knowledge base document."""
    effective_broker_id = _resolve_broker(current_user, broker_id)
    ok = await RAGService.delete_document(db, entry_id=entry_id, broker_id=effective_broker_id)
    if not ok:
        raise HTTPException(404, f"Document {entry_id} not found")
    return {"status": "deleted", "id": entry_id}
