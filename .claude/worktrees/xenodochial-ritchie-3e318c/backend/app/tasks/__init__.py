"""
Celery tasks module
Auto-imports all tasks for discovery
"""
from app.tasks import telegram_tasks
from app.tasks import scoring_tasks
from app.tasks import campaign_executor
from app.tasks import voice_tasks
from app.tasks import whatsapp_tasks
from app.tasks import sentiment_tasks
from app.tasks import dlq_tasks
from app.tasks import human_timeout_tasks
from app.tasks import alert_evaluator

__all__ = [
    "telegram_tasks",
    "scoring_tasks",
    "campaign_executor",
    "voice_tasks",
    "whatsapp_tasks",
    "sentiment_tasks",
    "dlq_tasks",
    "human_timeout_tasks",
    "alert_evaluator",
]