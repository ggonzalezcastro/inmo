from celery import Celery
from celery.schedules import crontab
from app.config import settings


# Initialize Celery
celery_app = Celery("lead_agent")


# Configure Celery
celery_app.conf.broker_url = settings.CELERY_BROKER_URL
celery_app.conf.result_backend = settings.CELERY_RESULT_BACKEND
celery_app.conf.accept_content = ["json"]
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.timezone = "UTC"
celery_app.conf.enable_utc = True
celery_app.conf.task_track_started = True
celery_app.conf.task_time_limit = 30 * 60  # 30 minutes
celery_app.conf.task_soft_time_limit = 25 * 60  # 25 minutes

# ── TASK-029: Reliability settings ───────────────────────────────────────────
# Acknowledge tasks only AFTER they complete (not on delivery).
# This ensures a task is re-queued if the worker dies mid-execution.
celery_app.conf.task_acks_late = True
# Reject (not re-queue) tasks that were in progress when the worker was lost,
# so they don't loop forever; they will be caught by DLQ on_failure.
celery_app.conf.task_reject_on_worker_lost = True
# Default retry policy: 3 retries with exponential backoff (2^n seconds)
celery_app.conf.task_max_retries = 3


# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "recalculate-scores-daily": {
        "task": "app.tasks.scoring_tasks.recalculate_all_lead_scores",
        "schedule": crontab(hour=2, minute=0),  # 2 AM UTC daily
    },
    "check-trigger-campaigns": {
        "task": "app.tasks.campaign_executor.check_trigger_campaigns",
        "schedule": crontab(minute=0),  # Every hour
    },
    # ── TASK-029: DLQ alert check (every 15 min) ──────────────────────────
    "dlq-alert-check": {
        "task": "app.tasks.dlq_tasks.dlq_alert_check",
        "schedule": crontab(minute="*/15"),
    },
}


# Auto-discover tasks
celery_app.autodiscover_tasks(["app.tasks"])


@celery_app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")


if __name__ == "__main__":
    celery_app.start()

