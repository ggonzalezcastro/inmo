"""add_prompt_versions_table

Revision ID: l3g4h5i6j7k8
Revises: k2f3g4h5i6j7
Create Date: 2026-02-22

- Creates prompt_versions table (versioned system-prompt snapshots per broker)
- Adds prompt_version_id FK to chat_messages
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "l3g4h5i6j7k8"
down_revision = "k2f3g4h5i6j7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── prompt_versions ───────────────────────────────────────────────────────
    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("broker_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("version_tag", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sections_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["broker_id"], ["brokers.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "broker_id", "version_tag", name="uq_prompt_version_broker_tag"
        ),
    )
    op.create_index(
        "idx_prompt_versions_broker_id", "prompt_versions", ["broker_id"]
    )
    op.create_index(
        "idx_prompt_versions_broker_active",
        "prompt_versions",
        ["broker_id", "is_active"],
    )

    # ── chat_messages: add prompt_version_id ──────────────────────────────────
    op.add_column(
        "chat_messages",
        sa.Column("prompt_version_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_chat_messages_prompt_version_id",
        "chat_messages",
        "prompt_versions",
        ["prompt_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_chat_messages_prompt_version",
        "chat_messages",
        ["prompt_version_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_chat_messages_prompt_version", table_name="chat_messages")
    op.drop_constraint(
        "fk_chat_messages_prompt_version_id", "chat_messages", type_="foreignkey"
    )
    op.drop_column("chat_messages", "prompt_version_id")

    op.drop_index("idx_prompt_versions_broker_active", table_name="prompt_versions")
    op.drop_index("idx_prompt_versions_broker_id", table_name="prompt_versions")
    op.drop_table("prompt_versions")
