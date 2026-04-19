"""add property list/offer pricing fields and has_offer flag

Revision ID: aa01b2c3d4e5
Revises: merge_all_heads_001, y1a2b3c4d5e6
Create Date: 2026-04-18

Adds:
- list_price_uf, list_price_clp  (precio publicado / "lista")
- offer_price_uf, offer_price_clp (precio promocional vigente)
- has_offer (Boolean, NOT NULL DEFAULT FALSE)
- partial index idx_prop_offers para listados de ofertas vigentes

Backfill: copia los precios actuales (price_uf, price_clp) a los nuevos
campos list_price_* para mantener compatibilidad de la UI sin pérdida de datos.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "aa01b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = ("merge_all_heads_001", "y1a2b3c4d5e6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("list_price_uf", sa.Numeric(12, 2), nullable=True))
    op.add_column("properties", sa.Column("list_price_clp", sa.BigInteger(), nullable=True))
    op.add_column("properties", sa.Column("offer_price_uf", sa.Numeric(12, 2), nullable=True))
    op.add_column("properties", sa.Column("offer_price_clp", sa.BigInteger(), nullable=True))
    op.add_column(
        "properties",
        sa.Column("has_offer", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # Backfill list_price_* desde los precios actuales para no romper la UI.
    op.execute(
        """
        UPDATE properties
           SET list_price_uf  = COALESCE(list_price_uf,  price_uf),
               list_price_clp = COALESCE(list_price_clp, price_clp)
        """
    )

    op.create_index(
        "idx_prop_offers",
        "properties",
        ["broker_id", "has_offer"],
        postgresql_where=sa.text("status = 'available' AND has_offer = true"),
    )


def downgrade() -> None:
    op.drop_index("idx_prop_offers", table_name="properties")
    op.drop_column("properties", "has_offer")
    op.drop_column("properties", "offer_price_clp")
    op.drop_column("properties", "offer_price_uf")
    op.drop_column("properties", "list_price_clp")
    op.drop_column("properties", "list_price_uf")
