"""Use ``user`` as the canonical owner for personal Meta resources.

Revision ID: z1k2l3m4n5o6
Revises: y0j1k2l3m4n5
"""

from alembic import op
import sqlalchemy as sa


revision = "z1k2l3m4n5o6"
down_revision = "y0j1k2l3m4n5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_meta_connection_owner_user",
        "meta_connections",
        type_="check",
    )
    op.drop_constraint(
        "ck_meta_connection_owner_type",
        "meta_connections",
        type_="check",
    )
    op.drop_constraint(
        "ck_meta_asset_owner_type",
        "meta_assets",
        type_="check",
    )

    op.execute(
        sa.text(
            "UPDATE meta_connections SET owner_type = 'user' "
            "WHERE owner_type = 'executive'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE meta_assets SET owner_type = 'user' "
            "WHERE owner_type = 'executive'"
        )
    )

    op.create_check_constraint(
        "ck_meta_connection_owner_type",
        "meta_connections",
        "owner_type IN ('broker', 'user')",
    )
    op.create_check_constraint(
        "ck_meta_connection_owner_user",
        "meta_connections",
        "(owner_type = 'broker' AND owner_user_id IS NULL) OR "
        "(owner_type = 'user' AND owner_user_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_meta_asset_owner_type",
        "meta_assets",
        "owner_type IN ('broker', 'user')",
    )
    op.create_check_constraint(
        "ck_meta_asset_owner_user",
        "meta_assets",
        "(owner_type = 'broker' AND owner_user_id IS NULL) OR "
        "(owner_type = 'user' AND owner_user_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_meta_asset_owner_user",
        "meta_assets",
        type_="check",
    )
    op.drop_constraint(
        "ck_meta_asset_owner_type",
        "meta_assets",
        type_="check",
    )
    op.drop_constraint(
        "ck_meta_connection_owner_user",
        "meta_connections",
        type_="check",
    )
    op.drop_constraint(
        "ck_meta_connection_owner_type",
        "meta_connections",
        type_="check",
    )

    op.execute(
        sa.text(
            "UPDATE meta_connections SET owner_type = 'executive' "
            "WHERE owner_type = 'user'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE meta_assets SET owner_type = 'executive' "
            "WHERE owner_type = 'user'"
        )
    )

    op.create_check_constraint(
        "ck_meta_connection_owner_type",
        "meta_connections",
        "owner_type IN ('broker', 'executive')",
    )
    op.create_check_constraint(
        "ck_meta_connection_owner_user",
        "meta_connections",
        "(owner_type = 'broker' AND owner_user_id IS NULL) OR "
        "(owner_type = 'executive' AND owner_user_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_meta_asset_owner_type",
        "meta_assets",
        "owner_type IN ('broker', 'executive')",
    )
