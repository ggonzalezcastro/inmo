"""merge scoring_config and campaign_fields heads

Revision ID: 8bbaff943f2a
Revises: 86655472ec75, p7k8l9m0n1o2
Create Date: 2026-03-02 19:51:17.665481

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8bbaff943f2a'
down_revision: Union[str, None] = ('86655472ec75', 'p7k8l9m0n1o2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

