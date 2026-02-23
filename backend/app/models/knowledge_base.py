"""
KnowledgeBase model — per-broker document store with pgvector embeddings (TASK-024).

Each row represents one chunk of knowledge (property listing, FAQ, policy, etc.)
associated with a broker. The ``embedding`` column stores a 768-dim vector
(Gemini text-embedding-004 default) used for semantic search.
"""
from __future__ import annotations

from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.models.base import Base, IdMixin, TimestampMixin

# Gemini text-embedding-004 outputs 768 dimensions by default.
EMBEDDING_DIM = 768


class KnowledgeBase(Base, IdMixin, TimestampMixin):
    """
    A single knowledge chunk owned by a broker.

    Fields
    ------
    broker_id   : owning broker (cascade delete)
    title       : short human-readable label (e.g. "Proyecto Torre Verde")
    content     : full text that was embedded
    embedding   : 768-dim pgvector vector
    source_type : "property" | "faq" | "policy" | "subsidy" | "custom"
    metadata    : arbitrary JSON (price, location, bedrooms, etc.)
    """

    __tablename__ = "knowledge_base"

    broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=True)
    source_type = Column(
        String(50),
        nullable=False,
        default="custom",
        server_default="custom",
    )
    kb_metadata = Column("metadata", JSONB, nullable=True)

    broker = relationship("Broker", back_populates="knowledge_base_entries")

    __table_args__ = (
        # IVFFlat index for approximate nearest-neighbour search (cosine distance)
        Index(
            "idx_knowledge_base_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"lists": 100},
        ),
        Index("idx_knowledge_base_broker_source", "broker_id", "source_type"),
    )
