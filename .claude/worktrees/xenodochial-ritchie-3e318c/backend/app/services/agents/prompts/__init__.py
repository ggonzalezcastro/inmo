"""
Agent-specific system prompt templates.

Each prompt is a Python string that can include {broker_name} and {agent_name}
placeholders.  In production these should be loaded from the broker's
PromptVersion table (see routes_config.py) so they can be versioned
independently per broker.
"""
from app.services.agents.prompts.qualifier_prompt import QUALIFIER_SYSTEM_PROMPT
from app.services.agents.prompts.scheduler_prompt import SCHEDULER_SYSTEM_PROMPT
from app.services.agents.prompts.follow_up_prompt import FOLLOW_UP_SYSTEM_PROMPT

__all__ = [
    "QUALIFIER_SYSTEM_PROMPT",
    "SCHEDULER_SYSTEM_PROMPT",
    "FOLLOW_UP_SYSTEM_PROMPT",
]
