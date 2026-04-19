"""add llm_calls table

Revision ID: k2f3g4h5i6j7
Revises: j1e2f3g4h5i6
Create Date: 2026-02-21

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "k2f3g4h5i6j7"
down_revision = "j1e2f3g4h5i6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_calls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "broker_id",
            sa.Integer(),
            sa.ForeignKey("brokers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "lead_id",
            sa.Integer(),
            sa.ForeignKey("leads.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model", sa.String(60), nullable=False),
        sa.Column("call_type", sa.String(30), nullable=False),
        sa.Column("used_fallback", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Single-column indexes
    op.create_index("ix_llm_calls_id", "llm_calls", ["id"])
    op.create_index("ix_llm_calls_broker_id", "llm_calls", ["broker_id"])
    op.create_index("ix_llm_calls_lead_id", "llm_calls", ["lead_id"])
    op.create_index("ix_llm_calls_provider", "llm_calls", ["provider"])
    op.create_index("ix_llm_calls_call_type", "llm_calls", ["call_type"])
    op.create_index("ix_llm_calls_created_at", "llm_calls", ["created_at"])
    # Composite indexes for common queries
    op.create_index(
        "idx_llm_calls_broker_created", "llm_calls", ["broker_id", "created_at"]
    )
    op.create_index(
        "idx_llm_calls_provider_model", "llm_calls", ["provider", "model"]
    )


def downgrade() -> None:
    op.drop_index("idx_llm_calls_provider_model", table_name="llm_calls")
    op.drop_index("idx_llm_calls_broker_created", table_name="llm_calls")
    op.drop_index("ix_llm_calls_created_at", table_name="llm_calls")
    op.drop_index("ix_llm_calls_call_type", table_name="llm_calls")
    op.drop_index("ix_llm_calls_provider", table_name="llm_calls")
    op.drop_index("ix_llm_calls_lead_id", table_name="llm_calls")
    op.drop_index("ix_llm_calls_broker_id", table_name="llm_calls")
    op.drop_index("ix_llm_calls_id", table_name="llm_calls")
    op.drop_table("llm_calls")
