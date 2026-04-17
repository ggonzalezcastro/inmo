"""Tests for _regex_extract_fields fallback in LLM facade."""
import pytest
from app.services.llm.facade import _regex_extract_fields


class TestRegexExtractFields:
    """Verify regex fallback extracts name, phone, email from raw messages."""

    # ── Phone extraction ─────────────────────────────────────────────────

    def test_phone_nine_digits(self):
        result = _regex_extract_fields("mi numero es 954100504")
        assert result.get("phone") == "+56954100504"

    def test_phone_with_country_code(self):
        result = _regex_extract_fields("telefono 56954100504")
        assert result.get("phone") == "+56954100504"

    def test_phone_with_plus(self):
        result = _regex_extract_fields("llámame al +56954100504")
        assert result.get("phone") == "+56954100504"

    def test_phone_with_spaces(self):
        result = _regex_extract_fields("mi cel es 9 5410 0504")
        assert result.get("phone") == "+56954100504"

    def test_no_phone(self):
        result = _regex_extract_fields("hola, busco departamento")
        assert "phone" not in result

    # ── Name extraction ──────────────────────────────────────────────────

    def test_name_me_llamo(self):
        result = _regex_extract_fields("me llamo gabriel gonzalez")
        assert result.get("name") == "gabriel gonzalez"

    def test_name_soy(self):
        result = _regex_extract_fields("soy María Fernanda")
        assert result.get("name") == "María Fernanda"

    def test_name_mi_nombre_es(self):
        result = _regex_extract_fields("mi nombre es Juan Pérez")
        assert result.get("name") == "Juan Pérez"

    def test_name_comma_pattern(self):
        result = _regex_extract_fields("gabriel gonzalez, y mi numero es 954100504")
        assert result.get("name") == "gabriel gonzalez"

    def test_name_does_not_capture_noise(self):
        """Should stop at noise words like 'y', 'mi', 'numero'."""
        result = _regex_extract_fields("soy Gabriel y mi numero es 954100504")
        assert result.get("name") == "Gabriel"

    def test_no_name_from_greeting(self):
        result = _regex_extract_fields("hola, busco casa en maipu")
        assert "name" not in result

    # ── Email extraction ─────────────────────────────────────────────────

    def test_email_simple(self):
        result = _regex_extract_fields("mi correo es juan@gmail.com")
        assert result.get("email") == "juan@gmail.com"

    def test_no_email(self):
        result = _regex_extract_fields("no tengo correo")
        assert "email" not in result

    # ── Combined extraction ──────────────────────────────────────────────

    def test_combined_name_phone(self):
        result = _regex_extract_fields("gabriel gonzalez, y mi numero es 56954100504")
        assert result.get("name") == "gabriel gonzalez"
        assert result.get("phone") == "+56954100504"

    def test_combined_all_fields(self):
        result = _regex_extract_fields(
            "me llamo Carlos Ruiz, mi cel es 912345678 y mi email carlos@test.cl"
        )
        assert result.get("name") == "Carlos Ruiz"
        assert result.get("phone") == "+56912345678"
        assert result.get("email") == "carlos@test.cl"

    def test_empty_message(self):
        result = _regex_extract_fields("")
        assert result == {}

    def test_no_data_message(self):
        result = _regex_extract_fields("hola, tienes propiedades en maipu")
        assert "name" not in result
        assert "phone" not in result
