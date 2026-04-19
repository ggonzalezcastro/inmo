"""
Unit tests for the sentiment analysis module.

Run with:
    .venv/bin/python -m pytest tests/services/test_sentiment.py -v --noconftest
"""
import pytest

from app.services.sentiment.heuristics import SentimentResult, analyze_heuristics
from app.services.sentiment.scorer import (
    ActionLevel,
    compute_action_level,
    empty_sentiment,
    resolve_tone_hint,
    update_sentiment_window,
)


# ── Heuristic tests ────────────────────────────────────────────────────────────

class TestAnalyzeHeuristics:
    """Test the keyword/pattern based analyzer."""

    # ── Clearly positive / neutral ─────────────────────────────────────────────

    def test_empty_message(self):
        result = analyze_heuristics("")
        assert result.score == 0.0
        assert result.needs_llm is False

    def test_whitespace_only(self):
        result = analyze_heuristics("   ")
        assert result.score == 0.0

    def test_positive_thanks(self):
        result = analyze_heuristics("Muchas gracias por la información!")
        assert result.score < 0.2
        assert result.needs_llm is False

    def test_positive_interest(self):
        result = analyze_heuristics("Sí me interesa saber más sobre el proyecto")
        assert result.score < 0.2

    def test_neutral_question(self):
        result = analyze_heuristics("¿Cuántos dormitorios tiene el departamento?")
        assert result.score < 0.3

    def test_entendido(self):
        result = analyze_heuristics("Entendido, gracias por explicarme")
        assert result.score < 0.2

    # ── Abandonment threat ─────────────────────────────────────────────────────

    def test_explicit_abandonment(self):
        result = analyze_heuristics("Voy a buscar en otra inmobiliaria, chao")
        assert result.score >= 0.7
        assert "abandonment_threat" in result.emotions

    def test_abandonment_ya_no_me_interesa(self):
        result = analyze_heuristics("Ya no me interesa más, lo olvido")
        assert result.score >= 0.6
        assert "abandonment_threat" in result.emotions

    def test_abandonment_mala_experiencia(self):
        result = analyze_heuristics("Pésimo servicio, mala experiencia, no vuelvo")
        assert result.score >= 0.65
        assert "abandonment_threat" in result.emotions

    def test_abandonment_me_canse(self):
        result = analyze_heuristics("Ya me cansé de esperar, hasta aquí no más")
        assert result.score >= 0.55

    def test_abandonment_buscare_otro_corredor(self):
        result = analyze_heuristics("Buscaré en otro corredor de propiedades")
        assert result.score >= 0.7
        assert "abandonment_threat" in result.emotions

    # ── Confusion ─────────────────────────────────────────────────────────────

    def test_confusion_no_entiendo(self):
        result = analyze_heuristics("No entiendo nada de lo que me están explicando")
        assert result.score >= 0.35
        assert "confusion" in result.emotions

    def test_confusion_me_perdi(self):
        result = analyze_heuristics("Me perdí, de qué estás hablando?")
        assert result.score >= 0.35
        assert "confusion" in result.emotions

    def test_confusion_multiple_question_marks(self):
        result = analyze_heuristics("Qué significa DICOM???")
        assert result.score >= 0.25

    def test_confusion_no_queda_claro(self):
        result = analyze_heuristics("No me queda claro cómo funciona el proceso")
        assert result.score >= 0.30
        assert "confusion" in result.emotions

    # ── Frustration ───────────────────────────────────────────────────────────

    def test_frustration_estoy_enojado(self):
        result = analyze_heuristics("Estoy enojado, llevan mucho tiempo sin responderme")
        assert result.score >= 0.65
        assert "frustration" in result.emotions

    def test_frustration_que_lata(self):
        result = analyze_heuristics("Qué lata este proceso, es súper lento")
        assert result.score >= 0.30
        assert "frustration" in result.emotions

    def test_frustration_que_fome(self):
        result = analyze_heuristics("Qué fome todo esto")
        assert result.score >= 0.25

    def test_frustration_que_penca(self):
        result = analyze_heuristics("Qué penca el servicio")
        assert result.score >= 0.25

    def test_frustration_muy_lento(self):
        result = analyze_heuristics("Están tardando demasiado en responderme")
        assert result.score >= 0.30

    def test_frustration_uppercase(self):
        result = analyze_heuristics("ESTO ES UNA PÉRDIDA DE TIEMPO")
        assert result.score >= 0.30

    # ── Sarcasm (always needs LLM) ─────────────────────────────────────────────

    def test_sarcasm_claro_con_puntos(self):
        result = analyze_heuristics("Claro... como siempre, esperando")
        assert "sarcasm" in result.emotions
        assert result.needs_llm is True

    def test_sarcasm_si_seguro(self):
        result = analyze_heuristics("Sí, seguro que me van a llamar")
        assert result.needs_llm is True

    # ── Edge cases ─────────────────────────────────────────────────────────────

    def test_emojis_only(self):
        result = analyze_heuristics("😊👍")
        assert result.score < 0.3

    def test_single_word(self):
        result = analyze_heuristics("ok")
        assert result.score < 0.2

    def test_mixed_positive_and_negative(self):
        # "Entendido" dampens the score
        result = analyze_heuristics("Entendido, aunque me parece un poco lento el proceso")
        assert result.score < 0.5  # dampened by "entendido"

    def test_chilean_no_vuelvo(self):
        result = analyze_heuristics("Terrible la atención, nunca más con ustedes")
        assert result.score >= 0.65
        assert "abandonment_threat" in result.emotions


# ── Scorer tests ───────────────────────────────────────────────────────────────

class TestUpdateSentimentWindow:
    """Test the sliding window accumulator."""

    def test_empty_window_first_score(self):
        sentiment = update_sentiment_window(None, 0.8, ["frustration"])
        assert sentiment["frustration_score"] == 0.8
        assert len(sentiment["message_scores"]) == 1

    def test_window_keeps_last_n(self):
        sentiment = None
        for i in range(5):
            sentiment = update_sentiment_window(sentiment, 0.5, [])
        assert len(sentiment["message_scores"]) == 3  # window_size default=3

    def test_weighted_average_recent_dominates(self):
        # High scores then one low score — recent low score should reduce total
        sentiment = None
        sentiment = update_sentiment_window(sentiment, 0.9, ["frustration"])  # oldest
        sentiment = update_sentiment_window(sentiment, 0.8, ["frustration"])
        sentiment = update_sentiment_window(sentiment, 0.1, [])  # most recent (weight=0.5)

        # Most recent (0.1) has 0.5 weight, so score should be pulled down
        assert sentiment["frustration_score"] < 0.6

    def test_accumulates_high_scores(self):
        sentiment = None
        for _ in range(3):
            sentiment = update_sentiment_window(sentiment, 0.85, ["abandonment_threat"])
        assert sentiment["frustration_score"] >= 0.7

    def test_neutral_scores_produce_low_accumulation(self):
        sentiment = None
        for _ in range(3):
            sentiment = update_sentiment_window(sentiment, 0.05, [])
        assert sentiment["frustration_score"] < 0.15

    def test_score_clamped_to_1(self):
        sentiment = None
        for _ in range(3):
            sentiment = update_sentiment_window(sentiment, 1.5, ["frustration"])  # intentionally > 1
        assert sentiment["frustration_score"] <= 1.0

    def test_score_clamped_to_0(self):
        sentiment = None
        for _ in range(3):
            sentiment = update_sentiment_window(sentiment, -0.5, [])
        assert sentiment["frustration_score"] >= 0.0


class TestComputeActionLevel:
    """Test action level determination."""

    def test_low_score_is_none(self):
        sentiment = {"frustration_score": 0.2, "escalated": False}
        assert compute_action_level(sentiment) == ActionLevel.NONE

    def test_medium_score_is_adapt_tone(self):
        sentiment = {"frustration_score": 0.55, "escalated": False}
        assert compute_action_level(sentiment) == ActionLevel.ADAPT_TONE

    def test_high_score_is_escalate(self):
        sentiment = {"frustration_score": 0.75, "escalated": False}
        assert compute_action_level(sentiment) == ActionLevel.ESCALATE

    def test_already_escalated_returns_none(self):
        # Even with high score, if already escalated do nothing
        sentiment = {"frustration_score": 0.95, "escalated": True}
        assert compute_action_level(sentiment) == ActionLevel.NONE

    def test_exactly_at_tone_threshold(self):
        sentiment = {"frustration_score": 0.40, "escalated": False}
        assert compute_action_level(sentiment) == ActionLevel.ADAPT_TONE

    def test_exactly_at_escalate_threshold(self):
        sentiment = {"frustration_score": 0.70, "escalated": False}
        assert compute_action_level(sentiment) == ActionLevel.ESCALATE

    def test_below_tone_threshold(self):
        sentiment = {"frustration_score": 0.39, "escalated": False}
        assert compute_action_level(sentiment) == ActionLevel.NONE


class TestResolveToneHint:
    """Test tone hint resolution."""

    def test_confusion_dominant_returns_calm(self):
        sentiment = {
            "frustration_score": 0.5,
            "message_scores": [
                {"score": 0.5, "emotions": ["confusion"]},
                {"score": 0.4, "emotions": ["confusion"]},
            ],
        }
        assert resolve_tone_hint(sentiment) == "calm"

    def test_abandonment_returns_empathetic(self):
        sentiment = {
            "frustration_score": 0.6,
            "message_scores": [
                {"score": 0.6, "emotions": ["abandonment_threat"]},
            ],
        }
        assert resolve_tone_hint(sentiment) == "empathetic"

    def test_low_score_returns_none(self):
        sentiment = {
            "frustration_score": 0.2,
            "message_scores": [],
        }
        assert resolve_tone_hint(sentiment) is None

    def test_mixed_emotions_with_abandonment_returns_empathetic(self):
        sentiment = {
            "frustration_score": 0.55,
            "message_scores": [
                {"score": 0.55, "emotions": ["confusion", "abandonment_threat"]},
            ],
        }
        # abandonment_threat overrides confusion → empathetic
        assert resolve_tone_hint(sentiment) == "empathetic"


class TestEmptySentiment:
    """Test the empty_sentiment factory."""

    def test_returns_valid_structure(self):
        s = empty_sentiment()
        assert s["frustration_score"] == 0.0
        assert s["message_scores"] == []
        assert s["tone_hint"] is None
        assert s["escalated"] is False
        assert s["escalated_at"] is None
