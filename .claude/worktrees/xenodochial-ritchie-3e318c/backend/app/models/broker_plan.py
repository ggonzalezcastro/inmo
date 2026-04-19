"""
BrokerPlan model — commercial plans with usage limits per broker.
"""
from sqlalchemy import Column, Integer, String, Boolean, Float
from app.models.base import Base, IdMixin, TimestampMixin


class BrokerPlan(Base, IdMixin, TimestampMixin):
    """
    Commercial plan definition.
    Limits set to NULL mean unlimited for that resource.
    """

    __tablename__ = "broker_plans"

    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(255), nullable=True)

    # Limits — NULL means unlimited
    max_leads = Column(Integer, nullable=True)
    max_users = Column(Integer, nullable=True)
    max_messages_per_month = Column(Integer, nullable=True)
    max_llm_cost_per_month = Column(Float, nullable=True)   # USD

    is_default = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<BrokerPlan id={self.id} name={self.name}>"
