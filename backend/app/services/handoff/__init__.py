# app/services/handoff/__init__.py
from app.services.handoff.brief_generator import generate_escalation_brief, get_latest_brief

__all__ = ["generate_escalation_brief", "get_latest_brief"]
