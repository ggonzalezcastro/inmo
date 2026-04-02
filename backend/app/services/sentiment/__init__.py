"""
Sentiment Analysis module — detects lead frustration and triggers escalation.

Flow:
    inbound message
        └── Celery task (async, non-blocking)
                ├── heuristics.py  → fast keyword/pattern score
                ├── llm_analyzer.py → LLM confirmation for ambiguous/sarcasm cases
                ├── scorer.py      → sliding-window accumulated score
                └── escalation.py  → actions: tone_hint / human_mode + broadcast
"""
from app.services.sentiment.heuristics import SentimentResult, analyze_heuristics
from app.services.sentiment.scorer import ActionLevel, compute_action_level, update_sentiment_window

__all__ = [
    "SentimentResult",
    "analyze_heuristics",
    "ActionLevel",
    "compute_action_level",
    "update_sentiment_window",
]
