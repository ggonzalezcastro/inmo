"""Add knowledge_base table with pgvector (TASK-024).

Revision ID: m4h5i6j7k8l9
Revises: l3g4h5i6j7k8
Create Date: 2026-02-22

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = "m4h5i6j7k8l9"
down_revision = "l3g4h5i6j7k8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. Create knowledge_base table
    op.create_table(
        "knowledge_base",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("broker_id", sa.Integer(), sa.ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "embedding",
            sa.Text(),  # raw type; pgvector type applied below
            nullable=True,
        ),
        sa.Column("source_type", sa.String(50), nullable=False, server_default="custom"),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 3. Change embedding column to vector(768) after table creation
    op.execute("ALTER TABLE knowledge_base ALTER COLUMN embedding TYPE vector(768) USING NULL")

    # 4. Indexes
    op.create_index("idx_knowledge_base_broker_id", "knowledge_base", ["broker_id"])
    op.create_index("idx_knowledge_base_broker_source", "knowledge_base", ["broker_id", "source_type"])

    # IVFFlat index requires at least some rows; create AFTER data load.
    # We create it here but it will be a no-op on empty tables and efficient once data is loaded.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_base_embedding "
        "ON knowledge_base USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.drop_index("idx_knowledge_base_embedding", table_name="knowledge_base")
    op.drop_index("idx_knowledge_base_broker_source", table_name="knowledge_base")
    op.drop_index("idx_knowledge_base_broker_id", table_name="knowledge_base")
    op.drop_table("knowledge_base")
    # Note: we do NOT drop the vector extension as other tables might use it
