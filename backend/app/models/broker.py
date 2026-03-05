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
    contact_phone = Column(String(50), nullable=True)
    contact_email = Column(String(200), nullable=True)
    business_hours = Column(String(100), nullable=True)
    service_zones = Column(JSONB, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    users = relationship("User", back_populates="broker", cascade="all, delete-orphan")
    prompt_config = relationship("BrokerPromptConfig", back_populates="broker", uselist=False, cascade="all, delete-orphan")
    lead_config = relationship("BrokerLeadConfig", back_populates="broker", uselist=False, cascade="all, delete-orphan")
    voice_config = relationship("BrokerVoiceConfig", back_populates="broker", uselist=False, cascade="all, delete-orphan")
    chat_config = relationship("BrokerChatConfig", back_populates="broker", uselist=False, cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="broker", cascade="all, delete-orphan")
    prompt_versions = relationship("PromptVersion", back_populates="broker", cascade="all, delete-orphan")
    knowledge_base_entries = relationship("KnowledgeBase", back_populates="broker", cascade="all, delete-orphan")

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
        "name": 10, "phone": 15, "email": 10, "location": 15, "budget": 20
    }, nullable=True)
    
    # Umbrales de score
    cold_max_score = Column(Integer, default=20, nullable=False)
    warm_max_score = Column(Integer, default=50, nullable=False)
    hot_min_score = Column(Integer, default=50, nullable=False)
    qualified_min_score = Column(Integer, default=75, nullable=False)
    
    # Prioridad de preguntas
    field_priority = Column(JSONB, default=["name", "phone", "email", "location", "budget"], nullable=True)
    
    # Criterios de calificación financiera (columna nueva — ver migración add_qualification_criteria)
    qualification_criteria = Column(JSONB, nullable=True)
    
    # Umbral de deuda aceptable (columna nueva — ver migración add_qualification_criteria)
    max_acceptable_debt = Column(Integer, default=0, nullable=True)
    
    # Configuración del score por tramos de sueldo y DICOM (ver migración add_scoring_config)
    scoring_config = Column(JSONB, nullable=True)
    
    # Alertas
    alert_on_hot_lead = Column(Boolean, default=True, nullable=False)
    alert_score_threshold = Column(Integer, default=70, nullable=False)
    alert_on_qualified = Column(Boolean, default=True, nullable=True)
    alert_email = Column(String(200), nullable=True)
    
    # Relationships
    broker = relationship("Broker", back_populates="lead_config")
    
    def __repr__(self):
        return f"<BrokerLeadConfig broker_id={self.broker_id}>"

