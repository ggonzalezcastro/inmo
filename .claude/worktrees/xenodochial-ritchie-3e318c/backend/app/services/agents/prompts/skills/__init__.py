"""Agent skill documents — specialised knowledge injected per agent."""
from app.services.agents.prompts.skills.qualifier_skill import QUALIFIER_SKILL
from app.services.agents.prompts.skills.scheduler_skill import SCHEDULER_SKILL
from app.services.agents.prompts.skills.property_skill import PROPERTY_SKILL
from app.services.agents.prompts.skills.follow_up_skill import FOLLOW_UP_SKILL

__all__ = [
    "QUALIFIER_SKILL",
    "SCHEDULER_SKILL",
    "PROPERTY_SKILL",
    "FOLLOW_UP_SKILL",
]
