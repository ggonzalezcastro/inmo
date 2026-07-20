"""
Unit tests for per-purpose voice prompt instructions and greetings.

Run with:
    python -m pytest tests/services/voice/test_purpose_instructions.py -v --noconftest
"""
from app.services.agents.prompts.skills.voice.purpose_instructions import (
    PURPOSE_GREETINGS,
    PURPOSE_INSTRUCTIONS,
    get_purpose_greeting,
    get_purpose_instructions,
)

ALL_PURPOSES = [
    "calificacion_inicial",
    "calificacion_financiera",
    "confirmacion_reunion",
    "confirmacion_visita",
    "seguimiento_post_visita",
    "reactivacion",
]


class TestPurposeInstructions:
    def test_every_purpose_has_instructions(self):
        for purpose in ALL_PURPOSES:
            text = get_purpose_instructions(purpose)
            assert text, f"missing instructions for {purpose}"

    def test_every_purpose_has_greeting(self):
        for purpose in ALL_PURPOSES:
            greeting = get_purpose_greeting(purpose, "Juan")
            assert greeting, f"missing greeting for {purpose}"
            assert "Juan" in greeting

    def test_covers_call_purpose_enum(self):
        from app.models.voice_call import CallPurpose

        enum_values = {p.value for p in CallPurpose}
        assert enum_values == set(PURPOSE_INSTRUCTIONS.keys())
        assert enum_values == set(PURPOSE_GREETINGS.keys())

    def test_none_and_unknown_return_empty(self):
        assert get_purpose_instructions(None) == ""
        assert get_purpose_instructions("") == ""
        assert get_purpose_instructions("foo") == ""
        assert get_purpose_greeting(None) is None
        assert get_purpose_greeting("foo") is None

    def test_greeting_without_name(self):
        greeting = get_purpose_greeting("confirmacion_visita", "")
        assert greeting is not None
        assert greeting.startswith("Hola, soy Sofia")

    def test_no_markdown_in_voice_text(self):
        # Voice text must be plain spoken Spanish — no markdown artifacts
        for purpose in ALL_PURPOSES:
            for text in (PURPOSE_INSTRUCTIONS[purpose], PURPOSE_GREETINGS[purpose]):
                assert "*" not in text
                assert "#" not in text
                assert "- " not in text
