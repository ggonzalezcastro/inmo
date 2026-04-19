"""
Property — structured real-estate listings with vector embeddings.

Combines structured columns (filterable via SQL) with a 768-dim embedding
of (description + highlights + amenities) for semantic search via pgvector.

Replaces knowledge_base entries with source_type='property'. Those entries
should be migrated here so knowledge_base stays for FAQs, policies, subsidies.
"""
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql.functions import now

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    # Fallback for environments without pgvector installed
    from sqlalchemy import Text as Vector  # type: ignore

from app.models.base import Base, IdMixin, TimestampMixin


class Property(Base, IdMixin, TimestampMixin):
    """Structured real-estate property listing."""

    __tablename__ = "properties"

    # ── Tenancy ───────────────────────────────────────────────────────────────
    broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Identification ────────────────────────────────────────────────────────
    name = Column(String(255), nullable=True)
    codigo = Column(String(50), nullable=True)
    # Identificador de la unidad dentro del proyecto (ej. "Depto 502", "Casa A-12").
    # Antes se llamaba `internal_code`; renombrado al modelar proyectos.
    tipologia = Column(String(50), nullable=True)
    # Tipo de unidad reutilizable dentro de un proyecto (ej. "2D2B", "A1").
    property_type = Column(String(50), nullable=True)
    # 'departamento', 'casa', 'terreno', 'oficina'
    status = Column(String(20), nullable=False, default="available")
    # 'available', 'reserved', 'sold', 'rented'

    # ── Project association (opcional — propiedades sueltas permitidas) ──────
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Location ──────────────────────────────────────────────────────────────
    commune = Column(String(100), nullable=True, index=True)
    city = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    address = Column(Text, nullable=True)
    latitude = Column(Numeric(10, 8), nullable=True)
    longitude = Column(Numeric(11, 8), nullable=True)

    # ── Numeric attributes (SQL-filterable) ───────────────────────────────────
    price_uf = Column(Numeric(12, 2), nullable=True, index=True)
    price_clp = Column(BigInteger, nullable=True)
    # Pricing extendido — list = precio publicado, offer = precio promocional vigente.
    list_price_uf = Column(Numeric(12, 2), nullable=True)
    list_price_clp = Column(BigInteger, nullable=True)
    offer_price_uf = Column(Numeric(12, 2), nullable=True)
    offer_price_clp = Column(BigInteger, nullable=True)
    has_offer = Column(Boolean, nullable=False, default=False)
    bedrooms = Column(Integer, nullable=True, index=True)
    bathrooms = Column(Integer, nullable=True)
    parking_spots = Column(Integer, nullable=True, default=0)
    storage_units = Column(Integer, nullable=True, default=0)
    square_meters_total = Column(Numeric(10, 2), nullable=True)
    square_meters_useful = Column(Numeric(10, 2), nullable=True)
    floor_number = Column(Integer, nullable=True)
    total_floors = Column(Integer, nullable=True)
    orientation = Column(String(20), nullable=True)
    # 'norte', 'sur', 'oriente', 'poniente', 'nororiente', etc.
    year_built = Column(Integer, nullable=True)
    delivery_date = Column(Date, nullable=True)

    # ── Rich text (for semantic embedding) ───────────────────────────────────
    description = Column(Text, nullable=True)
    highlights = Column(Text, nullable=True)
    # e.g. "Luminoso, vista panorámica, recién remodelado"

    # ── JSONB attributes ──────────────────────────────────────────────────────
    amenities = Column(JSONB, nullable=True)
    # ["piscina", "gimnasio", "quincho", "salón_eventos", "áreas_verdes"]
    nearby_places = Column(JSONB, nullable=True)
    # [{"type": "metro", "name": "Ñuñoa", "distance_m": 300}]
    images = Column(JSONB, nullable=True)
    # [{"url": "...", "caption": "Living principal", "order": 1}]
    financing_options = Column(JSONB, nullable=True)
    # ["crédito_hipotecario", "leasing", "pie_en_cuotas"]

    # ── Media ─────────────────────────────────────────────────────────────────
    floor_plan_url = Column(Text, nullable=True)
    virtual_tour_url = Column(Text, nullable=True)

    # ── Financial ─────────────────────────────────────────────────────────────
    common_expenses_clp = Column(Integer, nullable=True)
    subsidio_eligible = Column(Boolean, nullable=False, default=False)

    # ── Embedding (description + highlights + amenities concatenated) ─────────
    embedding = Column(Vector(768), nullable=True)

    # ── Publication ───────────────────────────────────────────────────────────
    published_at = Column(DateTime(timezone=True), nullable=True)

    # ── Source tracking (for KB migration) ───────────────────────────────────
    kb_entry_id = Column(
        Integer,
        ForeignKey("knowledge_base.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    broker = relationship("Broker", foreign_keys=[broker_id])
    project = relationship(
        "Project", foreign_keys=[project_id], back_populates="properties"
    )

    __table_args__ = (
        Index(
            "idx_prop_broker_status",
            "broker_id",
            "status",
        ),
        Index(
            "idx_prop_broker_project",
            "broker_id",
            "project_id",
        ),
        Index(
            "idx_prop_broker_project_tipologia",
            "broker_id",
            "project_id",
            "tipologia",
        ),
        Index(
            "idx_prop_search",
            "broker_id",
            "commune",
            "bedrooms",
            "price_uf",
            postgresql_where="status = 'available'",
        ),
        Index(
            "idx_prop_type",
            "broker_id",
            "property_type",
            postgresql_where="status = 'available'",
        ),
        Index(
            "idx_prop_price",
            "broker_id",
            "price_uf",
            postgresql_where="status = 'available'",
        ),
        Index(
            "idx_prop_geo",
            "latitude",
            "longitude",
            postgresql_where="status = 'available'",
        ),
        Index(
            "idx_prop_offers",
            "broker_id",
            "has_offer",
            postgresql_where="status = 'available' AND has_offer = true",
        ),
        # IVFFlat index created in migration (not declarable via SQLAlchemy easily)
    )

    def __repr__(self) -> str:
        return (
            f"<Property id={self.id} type={self.property_type} "
            f"commune={self.commune} price_uf={self.price_uf}>"
        )
