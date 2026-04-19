"""
Sliding-window frustration scorer.

Maintains a rolling window of per-message sentiment scores and computes
a weighted accumulated score. Determines the action level:

    NONE        → score below tone threshold (do nothing)
    ADAPT_TONE  → score between tone and escalate thresholds (soften Sofía's tone)
    ESCALATE    → score above escalate threshold (pause Sofía, notify broker)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from functools import lru_cache
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

# ── Config defaults (overridable via env vars) ─────────────────────────────────

def _tone_threshold() -> float:
    return float(getattr(settings, "SENTIMENT_TONE_THRESHOLD", 0.4))

def _escalate_threshold() -> float:
    return float(getattr(settings, "SENTIMENT_ESCALATE_THRESHOLD", 0.7))

def _history_window() -> int:
    return int(getattr(settings, "SENTIMENT_HISTORY_WINDOW", 3))

# Weights: exponential decay, normalised to sum=1 for any window size
@lru_cache(maxsize=16)
def _get_weights(n: int) -> list[float]:
    """Generate exponential decay weights for a window of size n.
    Most recent message (index 0) gets the highest weight.
    """
    raw = [0.5 ** (i + 1) for i in range(n)]
    total = sum(raw)
    return [w / total for w in raw]


# ── Action level ──────────────────────────────────────────────────────────────

class ActionLevel(str, Enum):
    NONE = "none"           # No action needed
    ADAPT_TONE = "adapt_tone"  # Sofía should be more empathetic
    ESCALATE = "escalate"   # Pause Sofía, notify broker


# ── Sentiment metadata structure ──────────────────────────────────────────────

def empty_sentiment() -> Dict[str, Any]:
    """Return a fresh sentiment sub-dict for lead_metadata."""
    return {
        "frustration_score": 0.0,
        "message_scores": [],       # List of {score, emotions, ts}
        "tone_hint": None,          # "empathetic" | "calm" | None
        "escalated": False,
        "escalated_at": None,
    }


# ── Core functions ────────────────────────────────────────────────────────────

def update_sentiment_window(
    current_sentiment: Optional[Dict[str, Any]],
    new_score: float,
    new_emotions: List[str],
) -> Dict[str, Any]:
    """
    Add a new per-message score to the sliding window and recompute
    the accumulated frustration_score.

    Returns the updated sentiment dict (does NOT mutate input).
    """
    window_size = _history_window()
    sentiment = dict(current_sentiment) if current_sentiment else empty_sentiment()

    # Add new entry to window
    history: List[Dict] = list(sentiment.get("message_scores", []))
    history.insert(0, {
        "score": new_score,
        "emotions": new_emotions,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    history = history[:window_size]  # keep only last N

    # Weighted average (most recent first) with dynamic decay weights
    weights = _get_weights(len(history))
    total_weight = sum(weights)
    weighted_sum = sum(h["score"] * w for h, w in zip(history, weights))
    accumulated = weighted_sum / total_weight if total_weight > 0 else 0.0

    sentiment["message_scores"] = history
    sentiment["frustration_score"] = round(min(1.0, max(0.0, accumulated)), 4)

    return sentiment


def compute_action_level(
    sentiment: Dict[str, Any],
) -> ActionLevel:
    """
    Determine what action to take based on the accumulated frustration_score.

    Returns ActionLevel enum value.
    """
    score = sentiment.get("frustration_score", 0.0)
    already_escalated = sentiment.get("escalated", False)

    if already_escalated:
        # Already escalated — don't act again
        return ActionLevel.NONE

    if score >= _escalate_threshold():
        return ActionLevel.ESCALATE

    if score >= _tone_threshold():
        # Determine which tone hint based on dominant emotion
        return ActionLevel.ADAPT_TONE

    # Score dropped below tone threshold — ensure tone_hint is cleared
    return ActionLevel.NONE


def resolve_tone_hint(sentiment: Dict[str, Any]) -> Optional[str]:
    """
    Based on the most recent message emotions, return the appropriate tone hint.

    "calm"        → when confusion is the dominant emotion
    "empathetic"  → for frustration, sarcasm, abandonment threat
    None          → when score is below threshold
    """
    score = sentiment.get("frustration_score", 0.0)
    if score < _tone_threshold():
        return None

    # Gather all recent emotions
    recent_emotions: List[str] = []
    for entry in sentiment.get("message_scores", [])[:2]:  # last 2 messages
        recent_emotions.extend(entry.get("emotions", []))

    if "confusion" in recent_emotions and "abandonment_threat" not in recent_emotions:
        return "calm"

    return "empathetic"
