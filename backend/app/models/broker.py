"""
Broker model and related configuration models
"""
from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.models.base import Base, IdMixin, TimestampMixin


class Broker(Base, IdMixin, TimestampMixin):
    """Broker (real estate company) model"""
    
    __tablename__ = "brokers"
    
    name = Column(String(200), nullable=False)
    slug = Column(String(100), unique=True, nullable=True, index=True)
    # Using phone/email to match existing DB schema
    phone = Column(String(50), nullable=True)
    email = Column(String(200), nullable=True)
    # Additional fields that might exist
    logo_url = Column(String(500), nullable=True)
    website = Column(String(500), nullable=True)
    address = Column(Text, nullable=True)
    timezone = Column(String(50), nullable=True)
    currency = Column(String(10), nullable=True)
    country = Column(String(50), nullable=True)
    language = Column(String(10), nullable=True)
    subscription_plan = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    users = relationship("User", back_populates="broker", cascade="all, delete-orphan")
    prompt_config = relationship("BrokerPromptConfig", back_populates="broker", uselist=False, cascade="all, delete-orphan")
    lead_config = relationship("BrokerLeadConfig", back_populates="broker", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Broker id={self.id} name={self.name}>"


class BrokerPromptConfig(Base, IdMixin, TimestampMixin):
    """Prompt configuration for broker's AI agent"""
    
    __tablename__ = "broker_prompt_configs"
    
    broker_id = Column(Integer, ForeignKey("brokers.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    
    # Sección 1: Identidad
    agent_name = Column(String(100), default='Sofía', nullable=True)
    agent_role = Column(String(200), default='asesora inmobiliaria', nullable=True)
    identity_prompt = Column(Text, nullable=True)  # Override completo de esta sección
    
    # Sección 2: Contexto
    business_context = Column(Text, nullable=True)
    
    # Sección 3: Objetivo
    agent_objective = Column(Text, nullable=True)
    
    # Sección 4: Datos a recopilar
    data_collection_prompt = Column(Text, nullable=True)
    
    # Sección 5: Reglas
    behavior_rules = Column(Text, nullable=True)
    
    # Sección 6: Restricciones
    restrictions = Column(Text, nullable=True)
    
    # Sección 7: Situaciones especiales
    situation_handlers = Column(JSONB, nullable=True)  # {"no_interesado": "respuesta...", ...}
    
    # Sección 8: Formato
    output_format = Column(Text, nullable=True)
    
    # Override completo (ignora todas las secciones)
    full_custom_prompt = Column(Text, nullable=True)
    
    # Herramientas
    enable_appointment_booking = Column(Boolean, default=True, nullable=False)
    tools_instructions = Column(Text, nullable=True)
    
    # ⭐ NUEVO: Información de beneficios/subsidios
    benefits_info = Column(JSONB, nullable=True)
    # Ejemplo: {"bono_pie_0": {"name": "Bono Pie 0", "active": true}, ...}
    
    # ⭐ NUEVO: Requisitos específicos de calificación
    qualification_requirements = Column(JSONB, nullable=True)
    # Ejemplo: {"dicom": {"required": "clean", "min_months_clean": 12}, ...}
    
    # ⭐ NUEVO: Mensajes de seguimiento personalizados
    follow_up_messages = Column(JSONB, nullable=True)
    # Ejemplo: {"no_response_24h": "Hola {nombre}...", ...}
    
    # ⭐ NUEVO: Datos adicionales a recopilar
    additional_fields = Column(JSONB, nullable=True)
    # Ejemplo: {"age": {"required": true}, "occupation": {...}, ...}
    
    # ⭐ NUEVO: Configuración de videollamada
    meeting_config = Column(JSONB, nullable=True)
    # Ejemplo: {"platform": "google_meet", "duration_minutes": 60, ...}
    
    # ⭐ NUEVO: Plantillas de mensajes
    message_templates = Column(JSONB, nullable=True)
    # Ejemplo: {"greeting": "Hola {nombre}!", "appointment_scheduled": "✅ Listo!", ...}
    
    # Relationships
    broker = relationship("Broker", back_populates="prompt_config")
    
    def __repr__(self):
        return f"<BrokerPromptConfig broker_id={self.broker_id}>"


class BrokerLeadConfig(Base, IdMixin, TimestampMixin):
    """Lead scoring and qualification configuration for broker"""
    
    __tablename__ = "broker_lead_configs"
    
    broker_id = Column(Integer, ForeignKey("brokers.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    
    # Pesos de campos
    field_weights = Column(JSONB, default={
        "name": 10,
        "phone": 15,
        "email": 10,
        "location": 15,
        "budget": 20
    }, nullable=True)
    
    # Umbrales
    cold_max_score = Column(Integer, default=20, nullable=False)
    warm_max_score = Column(Integer, default=50, nullable=False)
    hot_min_score = Column(Integer, default=50, nullable=False)
    qualified_min_score = Column(Integer, default=75, nullable=False)
    
    # Prioridad de preguntas
    field_priority = Column(JSONB, default=["name", "phone", "email", "location", "budget"], nullable=True)
    
    # ⭐ NUEVO: Rangos de ingresos configurables
    income_ranges = Column(JSONB, default={
        "insufficient": {"min": 0, "max": 500000, "label": "Insuficiente"},
        "low": {"min": 500000, "max": 1000000, "label": "Bajo"},
        "medium": {"min": 1000000, "max": 2000000, "label": "Medio"},
        "good": {"min": 2000000, "max": 4000000, "label": "Bueno"},
        "excellent": {"min": 4000000, "max": None, "label": "Excelente"}
    }, nullable=True)
    
    # ⭐ NUEVO: Criterios de calificación configurables
    qualification_criteria = Column(JSONB, default={
        "calificado": {
            "min_monthly_income": 1000000,
            "dicom_status": ["clean"],
            "max_debt_amount": 0
        },
        "potencial": {
            "min_monthly_income": 500000,
            "dicom_status": ["clean", "has_debt"],
            "max_debt_amount": 500000
        },
        "no_calificado": {
            "conditions": [
                {"monthly_income_below": 500000},
                {"debt_amount_above": 500000}
            ]
        }
    }, nullable=True)
    
    # ⭐ NUEVO: Umbral de deuda aceptable
    max_acceptable_debt = Column(Integer, default=500000, nullable=False)
    
    # Alertas
    alert_on_hot_lead = Column(Boolean, default=True, nullable=False)
    alert_score_threshold = Column(Integer, default=70, nullable=False)
    alert_on_qualified = Column(Boolean, default=True, nullable=False)
    alert_email = Column(String(200), nullable=True)
    
    # Relationships
    broker = relationship("Broker", back_populates="lead_config")
    
    def __repr__(self):
        return f"<BrokerLeadConfig broker_id={self.broker_id}>"

