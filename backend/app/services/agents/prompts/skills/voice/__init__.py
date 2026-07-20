"""Voice skill documents — channel-specific variants without emojis or markdown formatting."""
from app.services.agents.prompts.skills.voice.qualifier_voice import QUALIFIER_VOICE_SKILL
from app.services.agents.prompts.skills.voice.scheduler_voice import SCHEDULER_VOICE_SKILL
from app.services.agents.prompts.skills.voice.property_voice import PROPERTY_VOICE_SKILL
from app.services.agents.prompts.skills.voice.follow_up_voice import FOLLOW_UP_VOICE_SKILL

__all__ = [
    "QUALIFIER_VOICE_SKILL",
    "SCHEDULER_VOICE_SKILL",
    "PROPERTY_VOICE_SKILL",
    "FOLLOW_UP_VOICE_SKILL",
]
