"""
Project — desarrollo inmobiliario (edificio, condominio, loteo).

Agrupa varias `Property` (unidades) bajo un mismo proyecto. Comparte
ubicación, amenities comunes, fecha de entrega, financiamiento, brochure
y elegibilidad de subsidio. La asociación a Property es opcional, así
las propiedades sueltas (usadas, casas individuales) siguen funcionando.
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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover
    from sqlalchemy import Text as Vector  # type: ignore

from app.models.base import Base, IdMixin, TimestampMixin


class Project(Base, IdMixin, TimestampMixin):
    """Real-estate development project."""

    __tablename__ = "projects"

    # ── Tenancy ───────────────────────────────────────────────────────────────
    broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Identification ────────────────────────────────────────────────────────
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    developer = Column(String(255), nullable=True)
    status = Column(String(30), nullable=False, default="en_venta")
    # 'en_blanco', 'en_construccion', 'en_venta',
    # 'entrega_inmediata', 'terminado', 'agotado'

    # ── Location ──────────────────────────────────────────────────────────────
    commune = Column(String(100), nullable=True, index=True)
    city = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    address = Column(Text, nullable=True)
    latitude = Column(Numeric(10, 8), nullable=True)
    longitude = Column(Numeric(11, 8), nullable=True)

    # ── Comerciales ───────────────────────────────────────────────────────────
    delivery_date = Column(Date, nullable=True)
    total_units = Column(Integer, nullable=True)
    available_units = Column(Integer, nullable=True)

    # ── Atributos compartidos (heredables por las unidades) ──────────────────
    common_amenities = Column(JSONB, nullable=True)
    images = Column(JSONB, nullable=True)
    brochure_url = Column(Text, nullable=True)
    virtual_tour_url = Column(Text, nullable=True)
    subsidio_eligible = Column(Boolean, nullable=False, default=False)
    financing_options = Column(JSONB, nullable=True)
    highlights = Column(Text, nullable=True)

    # ── Embedding (descripción + amenities + highlights) ─────────────────────
    embedding = Column(Vector(768), nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    broker = relationship("Broker", foreign_keys=[broker_id])
    properties = relationship(
        "Property",
        back_populates="project",
        cascade="save-update, merge",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("broker_id", "code", name="uq_projects_broker_code"),
        Index("idx_project_broker_status", "broker_id", "status"),
        Index("idx_project_broker_commune", "broker_id", "commune"),
    )

    def __repr__(self) -> str:
        return (
            f"<Project id={self.id} name={self.name!r} "
            f"broker={self.broker_id} status={self.status}>"
        )
