"""add scoring_config to broker_lead_config

Revision ID: p7k8l9m0n1o2
Revises: o6j7k8l9m0n1
Create Date: 2026-03-02

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = 'p7k8l9m0n1o2'
down_revision: Union[str, None] = 'o6j7k8l9m0n1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_SCORING_CONFIG = {
    "income_tiers": [
        {"min": 3000000, "label": "Excelente", "points": 40},
        {"min": 2000000, "label": "Alto",      "points": 32},
        {"min": 1000000, "label": "Medio",     "points": 20},
        {"min": 500000,  "label": "Bajo",      "points": 10},
        {"min": 0,       "label": "Insuficiente", "points": 0}
    ],
    "dicom_clean_pts": 20,
    "dicom_has_debt_pts": 8
}


def upgrade() -> None:
    import json
    op.add_column(
        'broker_lead_configs',
        sa.Column(
            'scoring_config',
            JSONB,
            nullable=True,
            server_default=sa.text(f"'{json.dumps(DEFAULT_SCORING_CONFIG)}'::jsonb"),
        )
    )


def downgrade() -> None:
    op.drop_column('broker_lead_configs', 'scoring_config')
