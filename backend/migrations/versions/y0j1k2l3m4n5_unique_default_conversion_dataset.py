"""Allow only one selected conversion dataset per broker.

Revision ID: y0j1k2l3m4n5
Revises: x9i0j1k2l3m4
"""

from alembic import op
import sqlalchemy as sa


revision = "y0j1k2l3m4n5"
down_revision = "x9i0j1k2l3m4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (PARTITION BY broker_id ORDER BY id) AS position
            FROM meta_assets
            WHERE is_default = true AND asset_type = 'pixel'
        )
        UPDATE meta_assets
        SET is_default = false
        WHERE id IN (SELECT id FROM ranked WHERE position > 1)
    """))
    condition = sa.text("is_default = true AND asset_type = 'pixel'")
    op.create_index(
        "uq_meta_assets_default_conversion_dataset",
        "meta_assets",
        ["broker_id"],
        unique=True,
        postgresql_where=condition,
        sqlite_where=condition,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_meta_assets_default_conversion_dataset",
        table_name="meta_assets",
    )
