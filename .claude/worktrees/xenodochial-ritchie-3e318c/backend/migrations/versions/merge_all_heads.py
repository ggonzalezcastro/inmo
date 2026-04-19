"""Merge all heads into single head

Revision ID: merge_all_heads_001
Revises: 18bc8eda7670, 9d8a10e4b28e, p1a2b3c4d5e6, z2b3c4d5e6f7
Create Date: 2026-04-15

"""
from typing import Sequence, Union

revision: str = 'merge_all_heads_001'
down_revision: Union[str, Sequence[str], None] = (
    '18bc8eda7670',
    '9d8a10e4b28e',
    'p1a2b3c4d5e6',
    'z2b3c4d5e6f7',
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
