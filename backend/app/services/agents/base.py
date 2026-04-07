"""
BaseAgent — abstract base class for all multi-agent specialists (TASK-026).
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agents.types import (
    AgentContext,
    AgentResponse,
    AgentType,
    HandoffSignal,
)

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Contract that every specialist agent must implement.

    Subclasses must define:
    - ``agent_type``: the ``AgentType`` enum value
    - ``name``: human-readable name for logging
    - ``get_system_prompt()``: returns the agent-specific LLM system prompt
    - ``should_handle()``: returns True if this agent is the right handler
    - ``process()``: core conversation logic

    The ``should_handoff()`` method is **optional** — override when the agent
    needs to pass control to another agent mid-conversation.
    """

    agent_type: AgentType
    name: str

    @abstractmethod
    def get_system_prompt(self, context: AgentContext) -> str:
        """
        Return the full system prompt for this agent, personalised to the lead context.

        The returned string is the *static* broker-level part suitable for
        Gemini Context Caching.  Dynamic lead-level context is injected by the
        LLM facade separately.
        """

    @abstractmethod
    async def should_handle(self, context: AgentContext) -> bool:
        """Return True if this agent is appropriate for the current context."""

    @abstractmethod
    async def process(
        self,
        message: str,
        context: AgentContext,
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Process an incoming lead message and return an agent response.

        This method MUST NOT raise exceptions for normal business logic errors —
        it should return an ``AgentResponse`` with a graceful message instead.
        """

    async def should_handoff(
        self,
        response: AgentResponse,
        context: AgentContext,
    ) -> Optional[HandoffSignal]:
        """
        Called after ``process()`` to determine if a handoff is needed.

        Default implementation: returns ``response.handoff`` as-is.
        Override to add custom handoff logic.
        """
        return response.handoff

    def _log(self, msg: str, level: str = "info", **kwargs) -> None:
        """Structured logging helper."""
        extra = {"agent": self.name, "agent_type": self.agent_type.value, **kwargs}
        getattr(logger, level)(f"[{self.name}] {msg}", extra=extra)

    def _inject_tone_hint(self, prompt: str, context: AgentContext) -> str:
        """
        Append a tone instruction to the prompt when the sentiment module
        has flagged this lead as frustrated or confused.

        Called at the END of each agent's get_system_prompt() return value.
        Uses a hard separator to avoid breaking prompts that end with JSON/code blocks.
        """
        tone_hint = (context.lead_data.get("sentiment") or {}).get("tone_hint")
        separator = "\n\n---\n\n"
        if tone_hint == "empathetic":
            return (
                prompt.rstrip()
                + separator
                + "## ⚠️ ALERTA DE SENTIMIENTO — TONO ESPECIAL REQUERIDO\n"
                "El cliente muestra señales de frustración o malestar. "
                "Responde con especial empatía: valida sus sentimientos, "
                "pide disculpas si corresponde, y ofrece soluciones concretas. "
                "Usa un tono cálido, pausado y cercano. Evita respuestas robóticas o genéricas.\n"
            )
        if tone_hint == "calm":
            return (
                prompt.rstrip()
                + separator
                + "## ⚠️ ALERTA DE SENTIMIENTO — SIMPLIFICA TU RESPUESTA\n"
                "El cliente está confundido. Simplifica tu lenguaje al máximo: "
                "usa frases cortas, evita términos técnicos, y ofrece explicar paso a paso. "
                "Confirma que el cliente entendió antes de continuar.\n"
            )
        return prompt

    def _inject_human_release_note(self, prompt: str, context: AgentContext) -> str:
        """Prepend the human agent's handoff note to the system prompt when the AI resumes.

        Called at the START of each agent's get_system_prompt() return so the AI
        sees the human's context before anything else. The note persists in the DB
        until the lead is re-escalated (which clears it), so it remains available
        across multiple turns after the handoff.
        """
        note = getattr(context, "human_release_note", None)
        if not note or not note.strip():
            return prompt
        return (
            f"NOTA DEL AGENTE HUMANO (contexto al retomar control de la IA): {note.strip()}\n\n"
            + prompt
        )


# ── Registry ──────────────────────────────────────────────────────────────────

_AGENT_REGISTRY: Dict[AgentType, BaseAgent] = {}


def register_agent(agent: BaseAgent) -> None:
    """Register an agent instance in the global registry."""
    _AGENT_REGISTRY[agent.agent_type] = agent


def get_agent(agent_type: AgentType) -> Optional[BaseAgent]:
    """Retrieve a registered agent by type."""
    return _AGENT_REGISTRY.get(agent_type)


def get_all_agents() -> List[BaseAgent]:
    """Return all registered agent instances."""
    return list(_AGENT_REGISTRY.values())
