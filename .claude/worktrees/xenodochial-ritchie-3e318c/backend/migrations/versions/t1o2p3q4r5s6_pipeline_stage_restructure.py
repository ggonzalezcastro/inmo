"""pipeline stage restructure: remove seguimiento/referidos, add potencial

Revision ID: t1o2p3q4r5s6
Revises: s0n1o2p3q4r5
Create Date: 2026-04-01 14:00:00.000000

"""
from alembic import op

revision = 't1o2p3q4r5s6'
down_revision = 's0n1o2p3q4r5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Migrate seguimiento leads to potencial (they had potential but no appointment)
    op.execute(
        "UPDATE leads SET pipeline_stage = 'potencial' WHERE pipeline_stage = 'seguimiento'"
    )
    # Migrate referidos leads to agendado (they had an appointment)
    op.execute(
        "UPDATE leads SET pipeline_stage = 'agendado' WHERE pipeline_stage = 'referidos'"
    )


def downgrade() -> None:
    # Reverse: potencial -> seguimiento, but we can't recover referidos->agendado distinction
    op.execute(
        "UPDATE leads SET pipeline_stage = 'seguimiento' WHERE pipeline_stage = 'potencial'"
    )
