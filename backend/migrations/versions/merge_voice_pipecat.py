"""Merge voice pipecat fields into deals/projects head

Revision ID: merge_voice_pipecat
Revises: merge_heads_deals_projects, a3c5d7e9f1a2
Create Date: 2026-05-04

The voice pipecat migration (a3c5d7e9f1a2) was authored against the
post-z2b3c4d5e6f7 state, leaving alembic with two heads
(merge_heads_deals_projects and a3c5d7e9f1a2). This empty migration
merges them so `alembic upgrade head` resolves to a single head.
"""
from typing import Sequence, Union

revision: str = 'merge_voice_pipecat'
down_revision: Union[str, Sequence[str], None] = (
    'merge_heads_deals_projects',
    'a3c5d7e9f1a2',
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
