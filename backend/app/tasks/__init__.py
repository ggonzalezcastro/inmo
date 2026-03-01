"""
Celery tasks module
Auto-imports all tasks for discovery
"""
from app.tasks import telegram_tasks
from app.tasks import scoring_tasks
from app.tasks import campaign_executor
from app.tasks import voice_tasks
from app.tasks import whatsapp_tasks

__all__ = [
    "telegram_tasks",
    "scoring_tasks",
    "campaign_executor",
    "voice_tasks",
    "whatsapp_tasks",
]



