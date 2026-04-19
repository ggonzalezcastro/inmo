"""add projects table + property typology/codigo/project_id

Revision ID: bb12c3d4e5f6
Revises: aa01b2c3d4e5
Create Date: 2026-04-18

Cambios:
- Crea tabla `projects` con multi-tenancy por broker_id, ubicación,
  comerciales (delivery_date, total_units, available_units), atributos
  compartidos (common_amenities, images, brochure, financing, subsidio,
  highlights), embedding 768-dim opcional.
- Renombra `properties.internal_code` → `properties.codigo`.
- Agrega `properties.project_id` FK nullable a `projects(id)` ON DELETE SET NULL.
- Agrega `properties.tipologia` (String 50).
- Crea índices nuevos para joins/listados por proyecto y tipología.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "bb12c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "aa01b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Tabla projects ───────────────────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "broker_id",
            sa.Integer(),
            sa.ForeignKey("brokers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("developer", sa.String(255), nullable=True),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default=sa.text("'en_venta'"),
        ),
        sa.Column("commune", sa.String(100), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("region", sa.String(100), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Numeric(10, 8), nullable=True),
        sa.Column("longitude", sa.Numeric(11, 8), nullable=True),
        sa.Column("delivery_date", sa.Date(), nullable=True),
        sa.Column("total_units", sa.Integer(), nullable=True),
        sa.Column("available_units", sa.Integer(), nullable=True),
        sa.Column("common_amenities", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("images", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("brochure_url", sa.Text(), nullable=True),
        sa.Column("virtual_tour_url", sa.Text(), nullable=True),
        sa.Column(
            "subsidio_eligible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("financing_options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("highlights", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("broker_id", "code", name="uq_projects_broker_code"),
    )

    op.create_index("ix_projects_broker_id", "projects", ["broker_id"])
    op.create_index("ix_projects_commune", "projects", ["commune"])
    op.create_index(
        "idx_project_broker_status", "projects", ["broker_id", "status"]
    )
    op.create_index(
        "idx_project_broker_commune", "projects", ["broker_id", "commune"]
    )

    # Embedding column (pgvector). Solo si la extensión está disponible.
    bind = op.get_bind()
    has_pgvector = bind.execute(
        sa.text(
            "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
        )
    ).scalar()
    if has_pgvector:
        op.execute("ALTER TABLE projects ADD COLUMN embedding vector(768)")
    else:
        op.add_column("projects", sa.Column("embedding", sa.Text(), nullable=True))

    # ── Properties: rename + nuevos campos + índices ─────────────────────────
    op.alter_column(
        "properties", "internal_code", new_column_name="codigo"
    )
    op.add_column(
        "properties",
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "properties", sa.Column("tipologia", sa.String(50), nullable=True)
    )

    op.create_index(
        "ix_properties_project_id", "properties", ["project_id"]
    )
    op.create_index(
        "idx_prop_broker_project", "properties", ["broker_id", "project_id"]
    )
    op.create_index(
        "idx_prop_broker_project_tipologia",
        "properties",
        ["broker_id", "project_id", "tipologia"],
    )


def downgrade() -> None:
    op.drop_index("idx_prop_broker_project_tipologia", table_name="properties")
    op.drop_index("idx_prop_broker_project", table_name="properties")
    op.drop_index("ix_properties_project_id", table_name="properties")
    op.drop_column("properties", "tipologia")
    op.drop_column("properties", "project_id")
    op.alter_column(
        "properties", "codigo", new_column_name="internal_code"
    )

    op.drop_index("idx_project_broker_commune", table_name="projects")
    op.drop_index("idx_project_broker_status", table_name="projects")
    op.drop_index("ix_projects_commune", table_name="projects")
    op.drop_index("ix_projects_broker_id", table_name="projects")
    op.drop_table("projects")
