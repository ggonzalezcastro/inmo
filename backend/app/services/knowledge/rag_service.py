"""
RAG (Retrieval-Augmented Generation) service (TASK-024).

Provides semantic search over the per-broker KnowledgeBase table using
pgvector cosine similarity on Gemini text-embedding-004 embeddings.

Usage (in LLM prompt builder)
------------------------------
    from app.services.knowledge.rag_service import RAGService

    chunks = await RAGService.search(db, broker_id=1, query="¿Cuánto cuesta Torre Verde?", top_k=3)
    context_block = RAGService.format_for_prompt(chunks)
    # Inject context_block into the system prompt
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase, EMBEDDING_DIM

logger = logging.getLogger(__name__)

# Maximum number of KB chunks injected per LLM call
DEFAULT_TOP_K = 3
# Minimum similarity score to include a chunk (0 = exact opposite, 1 = identical)
MIN_SIMILARITY = 0.60


async def _embed_text(text_input: str) -> Optional[List[float]]:
    """Return a 768-dim embedding vector for ``text_input`` using Gemini."""
    try:
        from app.config import settings
        from google import genai
        from google.genai import types as genai_types

        if not settings.GEMINI_API_KEY:
            return None

        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        def _sync_embed() -> List[float]:
            resp = client.models.embed_content(
                model="text-embedding-004",
                contents=text_input,
            )
            # Depending on SDK version the embedding may be nested
            if hasattr(resp, "embeddings") and resp.embeddings:
                return resp.embeddings[0].values
            if hasattr(resp, "embedding"):
                return resp.embedding.values
            return []

        return await asyncio.to_thread(_sync_embed)

    except Exception as exc:
        logger.warning("[RAG] Embedding failed: %s", exc)
        return None


class RAGService:
    """Semantic search over the knowledge base."""

    # ── Search ────────────────────────────────────────────────────────────────

    @staticmethod
    async def search(
        db: AsyncSession,
        broker_id: int,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        source_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return up to ``top_k`` KB chunks most semantically similar to ``query``.

        Each result dict: {id, title, content, source_type, similarity, metadata}
        """
        query_embedding = await _embed_text(query)
        if not query_embedding:
            logger.debug("[RAG] No embedding for query — skipping KB search")
            return []

        # Build the vector similarity query
        vec_literal = "[" + ",".join(str(v) for v in query_embedding) + "]"
        where_clause = "broker_id = :broker_id AND embedding IS NOT NULL"
        params: dict = {"broker_id": broker_id, "top_k": top_k, "min_sim": MIN_SIMILARITY}

        if source_type:
            where_clause += " AND source_type = :source_type"
            params["source_type"] = source_type

        sql = text(f"""
            SELECT id, title, content, source_type, metadata,
                   1 - (embedding <=> '{vec_literal}'::vector) AS similarity
            FROM knowledge_base
            WHERE {where_clause}
              AND 1 - (embedding <=> '{vec_literal}'::vector) >= :min_sim
            ORDER BY embedding <=> '{vec_literal}'::vector
            LIMIT :top_k
        """)

        try:
            result = await db.execute(sql, params)
            rows = result.fetchall()
            return [
                {
                    "id": r.id,
                    "title": r.title,
                    "content": r.content,
                    "source_type": r.source_type,
                    "metadata": r.metadata,
                    "similarity": round(float(r.similarity), 4),
                }
                for r in rows
            ]
        except Exception as exc:
            logger.error("[RAG] Search query failed: %s", exc)
            return []

    # ── Format for LLM ────────────────────────────────────────────────────────

    @staticmethod
    def format_for_prompt(chunks: List[Dict]) -> str:
        """
        Convert retrieved chunks to a compact block for injection into the LLM prompt.

        Returns an empty string when ``chunks`` is empty.
        """
        if not chunks:
            return ""

        lines = ["--- INFORMACIÓN RELEVANTE (base de conocimiento) ---"]
        for i, chunk in enumerate(chunks, 1):
            lines.append(
                f"[{i}] {chunk['title']} (similitud: {chunk['similarity']:.0%})\n{chunk['content']}"
            )
        lines.append("--- FIN INFORMACIÓN ---")
        return "\n\n".join(lines)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    @staticmethod
    async def add_document(
        db: AsyncSession,
        *,
        broker_id: int,
        title: str,
        content: str,
        source_type: str = "custom",
        metadata: Optional[Dict] = None,
    ) -> KnowledgeBase:
        """
        Embed ``content`` with Gemini and insert a new KB entry.

        Returns the persisted KnowledgeBase row.
        """
        embedding = await _embed_text(content)

        entry = KnowledgeBase(
            broker_id=broker_id,
            title=title,
            content=content,
            source_type=source_type,
            kb_metadata=metadata,
        )

        if embedding:
            # Store as pgvector-compatible string
            entry.embedding = embedding
        else:
            logger.warning("[RAG] No embedding generated for doc '%s' — stored without vector", title)

        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry

    @staticmethod
    async def update_document(
        db: AsyncSession,
        entry_id: int,
        broker_id: int,
        **fields,
    ) -> Optional[KnowledgeBase]:
        """Update fields of an existing KB entry, re-embedding if content changed."""
        result = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == entry_id,
                KnowledgeBase.broker_id == broker_id,
            )
        )
        entry = result.scalars().first()
        if not entry:
            return None

        if "content" in fields and fields["content"] != entry.content:
            embedding = await _embed_text(fields["content"])
            if embedding:
                entry.embedding = embedding

        for key, value in fields.items():
            if hasattr(entry, key):
                setattr(entry, key, value)
            elif key == "metadata":
                entry.kb_metadata = value

        await db.commit()
        await db.refresh(entry)
        return entry

    @staticmethod
    async def delete_document(db: AsyncSession, entry_id: int, broker_id: int) -> bool:
        """Delete a KB entry. Returns True if found and deleted."""
        result = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == entry_id,
                KnowledgeBase.broker_id == broker_id,
            )
        )
        entry = result.scalars().first()
        if not entry:
            return False
        await db.delete(entry)
        await db.commit()
        return True

    @staticmethod
    async def list_documents(
        db: AsyncSession,
        broker_id: int,
        source_type: Optional[str] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> List[Dict]:
        """List KB entries for a broker (without embedding vectors)."""
        q = select(
            KnowledgeBase.id,
            KnowledgeBase.title,
            KnowledgeBase.content,
            KnowledgeBase.source_type,
            KnowledgeBase.kb_metadata,
            KnowledgeBase.created_at,
        ).where(KnowledgeBase.broker_id == broker_id)

        if source_type:
            q = q.where(KnowledgeBase.source_type == source_type)

        q = q.order_by(KnowledgeBase.id.desc()).offset(offset).limit(limit)
        result = await db.execute(q)
        return [dict(r._mapping) for r in result.fetchall()]
