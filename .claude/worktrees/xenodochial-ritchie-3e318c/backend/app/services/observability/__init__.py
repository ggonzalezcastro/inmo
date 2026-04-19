# app/services/observability/__init__.py
from app.services.observability.event_logger import event_logger, AgentEventLogger

__all__ = ["event_logger", "AgentEventLogger"]
