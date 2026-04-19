"""add google calendar per broker

Revision ID: q8l9m0n1o2p3
Revises: p7k8l9m0n1o2
Create Date: 2026-03-30

Adds per-broker Google Calendar OAuth credentials to broker_prompt_configs:
  - google_refresh_token: encrypted refresh token
  - google_calendar_id: calendar ID (default "primary")
  - google_calendar_email: the connected Gmail address (for display)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'q8l9m0n1o2p3'
down_revision = ('p7k8l9m0n1o2', '8bbaff943f2a')
branch_labels = None
depends_on = None


def column_exists(table, column):
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    return result.first() is not None


def upgrade():
    if not column_exists("broker_prompt_configs", "google_refresh_token"):
        op.add_column(
            "broker_prompt_configs",
            sa.Column("google_refresh_token", sa.Text(), nullable=True),
        )
    if not column_exists("broker_prompt_configs", "google_calendar_id"):
        op.add_column(
            "broker_prompt_configs",
            sa.Column("google_calendar_id", sa.String(255), nullable=True),
        )
    if not column_exists("broker_prompt_configs", "google_calendar_email"):
        op.add_column(
            "broker_prompt_configs",
            sa.Column("google_calendar_email", sa.String(255), nullable=True),
        )


def downgrade():
    op.drop_column("broker_prompt_configs", "google_calendar_email")
    op.drop_column("broker_prompt_configs", "google_calendar_id")
    op.drop_column("broker_prompt_configs", "google_refresh_token")
