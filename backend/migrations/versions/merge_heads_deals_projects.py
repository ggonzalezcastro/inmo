"""Merge deals and projects heads into single head

Revision ID: merge_heads_deals_projects
Revises: bb12c3d4e5f6, f1e2d3c4b5a6
Create Date: 2026-04-22

"""
from typing import Sequence, Union

revision: str = 'merge_heads_deals_projects'
down_revision: Union[str, Sequence[str], None] = ('bb12c3d4e5f6', 'f1e2d3c4b5a6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
