"""
Tests for voice/chat skill selection by channel.

Verifies:
- BaseAgent._get_skill_for_channel() returns correct skill per channel
- Voice skills contain no emojis, no markdown bold
- Chat skills contain formatting markers
- build_context passes channel correctly
- Fallback to CHAT_SKILL when VOICE_SKILL is empty
"""
import pytest
from unittest.mock import MagicMock

from app.services.agents.types import AgentContext
from app.services.agents.base import BaseAgent
from app.services.agents.qualifier import QualifierAgent
from app.services.agents.scheduler import SchedulerAgent
from app.services.agents.follow_up import FollowUpAgent
from app.services.agents.property import PropertyAgent
from app.services.agents.prompts.skills.voice import (
    QUALIFIER_VOICE_SKILL,
    SCHEDULER_VOICE_SKILL,
    PROPERTY_VOICE_SKILL,
    FOLLOW_UP_VOICE_SKILL,
)
from app.services.agents.prompts.skills import (
    QUALIFIER_SKILL,
    SCHEDULER_SKILL,
    PROPERTY_SKILL,
    FOLLOW_UP_SKILL,
)


def make_ctx(channel: str = "chat") -> AgentContext:
    return AgentContext(
        lead_id=1,
        broker_id=1,
        pipeline_stage="entrada",
        conversation_state="GREETING",
        lead_data={"broker_name": "TestBroker", "agent_name": "Sofia"},
        message_history=[],
        channel=channel,
    )


class TestChannelSelection:
    def test_qualifier_chat_channel_returns_chat_skill(self):
        agent = QualifierAgent()
        skill = agent._get_skill_for_channel(make_ctx("chat"))
        assert skill == QUALIFIER_SKILL

    def test_qualifier_voice_channel_returns_voice_skill(self):
        agent = QualifierAgent()
        skill = agent._get_skill_for_channel(make_ctx("voice"))
        assert skill == QUALIFIER_VOICE_SKILL

    def test_scheduler_voice_skill(self):
        agent = SchedulerAgent()
        assert agent._get_skill_for_channel(make_ctx("voice")) == SCHEDULER_VOICE_SKILL
        assert agent._get_skill_for_channel(make_ctx("chat")) == SCHEDULER_SKILL

    def test_follow_up_voice_skill(self):
        agent = FollowUpAgent()
        assert agent._get_skill_for_channel(make_ctx("voice")) == FOLLOW_UP_VOICE_SKILL
        assert agent._get_skill_for_channel(make_ctx("chat")) == FOLLOW_UP_SKILL

    def test_property_voice_skill(self):
        agent = PropertyAgent()
        assert agent._get_skill_for_channel(make_ctx("voice")) == PROPERTY_VOICE_SKILL
        assert agent._get_skill_for_channel(make_ctx("chat")) == PROPERTY_SKILL

    def test_default_channel_is_chat(self):
        ctx = AgentContext(
            lead_id=1, broker_id=1, pipeline_stage="entrada",
            conversation_state="GREETING", lead_data={}, message_history=[],
        )
        assert ctx.channel == "chat"

    def test_fallback_to_chat_skill_when_voice_skill_empty(self):
        class AgentWithoutVoiceSkill(BaseAgent):
            agent_type = None
            name = "TestAgent"
            CHAT_SKILL = "chat skill content"
            VOICE_SKILL = ""  # empty

            def get_system_prompt(self, context):
                return ""

            async def process(self, message, context, db):
                pass

        agent = AgentWithoutVoiceSkill()
        skill = agent._get_skill_for_channel(make_ctx("voice"))
        assert skill == "chat skill content"

    def test_unknown_channel_defaults_to_chat_skill(self):
        ctx = make_ctx("whatsapp")
        agent = QualifierAgent()
        skill = agent._get_skill_for_channel(ctx)
        assert skill == QUALIFIER_SKILL


class TestVoiceSkillContent:
    def test_qualifier_voice_has_no_emojis(self):
        import re
        emoji_pattern = re.compile(
            "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF"
            "\U00002500-\U00002BEF\U00002702-\U000027B0]+"
        )
        assert not emoji_pattern.search(QUALIFIER_VOICE_SKILL), "Voice skill must not contain emojis"

    def test_scheduler_voice_has_no_emojis(self):
        import re
        emoji_pattern = re.compile(
            "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]+"
        )
        assert not emoji_pattern.search(SCHEDULER_VOICE_SKILL)

    def test_voice_skills_have_no_markdown_bold(self):
        for skill in [QUALIFIER_VOICE_SKILL, SCHEDULER_VOICE_SKILL,
                      PROPERTY_VOICE_SKILL, FOLLOW_UP_VOICE_SKILL]:
            assert "**" not in skill, f"Voice skill contains markdown bold: {skill[:50]}"

    def test_qualifier_voice_mentions_phone(self):
        assert "telefono" in QUALIFIER_VOICE_SKILL.lower() or "teléfono" in QUALIFIER_VOICE_SKILL.lower()

    def test_qualifier_voice_mentions_words_for_numbers(self):
        # Should instruct to say numbers in words
        assert "palabras" in QUALIFIER_VOICE_SKILL.lower() or "dos millones" in QUALIFIER_VOICE_SKILL.lower()

    def test_scheduler_voice_mentions_horarios(self):
        assert "horario" in SCHEDULER_VOICE_SKILL.lower() or "alternativas" in SCHEDULER_VOICE_SKILL.lower()


class TestBuildContextChannel:
    def test_build_context_passes_channel(self):
        from app.services.agents import build_context

        lead = MagicMock()
        lead.id = 1
        lead.pipeline_stage = "entrada"
        lead.name = "Juan"
        lead.phone = "56912345678"
        lead.email = "juan@test.com"
        lead.lead_metadata = {}
        lead.human_release_note = None

        ctx = build_context(lead, broker_id=1, channel="voice")
        assert ctx.channel == "voice"

    def test_build_context_default_channel_is_chat(self):
        from app.services.agents import build_context

        lead = MagicMock()
        lead.id = 1
        lead.pipeline_stage = "entrada"
        lead.name = "Juan"
        lead.phone = "56912345678"
        lead.email = None
        lead.lead_metadata = {}
        lead.human_release_note = None

        ctx = build_context(lead, broker_id=1)
        assert ctx.channel == "chat"
