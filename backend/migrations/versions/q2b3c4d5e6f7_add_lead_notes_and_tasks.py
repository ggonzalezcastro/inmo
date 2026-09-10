"""add lead notes and follow-up tasks

Revision ID: q2b3c4d5e6f7
Revises: p1a2y3m4e5n6
Create Date: 2026-08-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "q2b3c4d5e6f7"
down_revision: Union[str, Sequence[str]] = "p1a2y3m4e5n6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lead_notes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "broker_id",
            sa.Integer(),
            sa.ForeignKey("brokers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lead_id",
            sa.Integer(),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_lead_notes_broker_id", "lead_notes", ["broker_id"])
    op.create_index("ix_lead_notes_lead_id", "lead_notes", ["lead_id"])
    op.create_index("ix_lead_notes_author_id", "lead_notes", ["author_id"])
    op.create_index("ix_lead_notes_created_at", "lead_notes", ["created_at"])
    op.create_index(
        "ix_lead_notes_broker_lead_created",
        "lead_notes",
        ["broker_id", "lead_id", "created_at"],
    )

    op.create_table(
        "lead_tasks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "broker_id",
            sa.Integer(),
            sa.ForeignKey("brokers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lead_id",
            sa.Integer(),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
        sa.Column(
            "assigned_to",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "completed_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reminder_minutes_before", sa.Integer(), nullable=True, server_default="60"),
        sa.Column("reminder_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('open', 'completed')",
            name="ck_lead_tasks_status",
        ),
        sa.CheckConstraint(
            "reminder_minutes_before IS NULL OR "
            "reminder_minutes_before IN (0, 15, 60, 1440)",
            name="ck_lead_tasks_reminder_offset",
        ),
    )
    for column in (
        "broker_id",
        "lead_id",
        "status",
        "assigned_to",
        "created_by",
        "due_at",
        "reminder_at",
    ):
        op.create_index(f"ix_lead_tasks_{column}", "lead_tasks", [column])
    op.create_index(
        "ix_lead_tasks_assignee_status_due",
        "lead_tasks",
        ["broker_id", "assigned_to", "status", "due_at"],
    )
    op.create_index(
        "ix_lead_tasks_pending_reminders",
        "lead_tasks",
        ["status", "reminder_sent_at", "reminder_at"],
    )

    # Preserve the legacy single-note field as one immutable historical entry.
    op.execute(
        sa.text(
            """
            INSERT INTO lead_notes (broker_id, lead_id, author_id, body, created_at)
            SELECT
                broker_id,
                id,
                NULL,
                notes,
                COALESCE(updated_at, created_at, NOW())
            FROM leads
            WHERE broker_id IS NOT NULL
              AND notes IS NOT NULL
              AND BTRIM(notes) <> ''
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_lead_tasks_pending_reminders", table_name="lead_tasks")
    op.drop_index("ix_lead_tasks_assignee_status_due", table_name="lead_tasks")
    for column in reversed((
        "broker_id",
        "lead_id",
        "status",
        "assigned_to",
        "created_by",
        "due_at",
        "reminder_at",
    )):
        op.drop_index(f"ix_lead_tasks_{column}", table_name="lead_tasks")
    op.drop_table("lead_tasks")

    op.drop_index("ix_lead_notes_broker_lead_created", table_name="lead_notes")
    op.drop_index("ix_lead_notes_created_at", table_name="lead_notes")
    op.drop_index("ix_lead_notes_author_id", table_name="lead_notes")
    op.drop_index("ix_lead_notes_lead_id", table_name="lead_notes")
    op.drop_index("ix_lead_notes_broker_id", table_name="lead_notes")
    op.drop_table("lead_notes")
