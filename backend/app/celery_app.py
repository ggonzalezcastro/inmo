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
}


# Auto-discover tasks
celery_app.autodiscover_tasks(["app.tasks"])


@celery_app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")


if __name__ == "__main__":
    celery_app.start()

