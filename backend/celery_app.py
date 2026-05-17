import os
import time
from celery import Celery
from celery.schedules import crontab
from celery.signals import task_prerun, task_postrun, task_failure

from services.logger import log

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "firewatch",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "workers.documents",
        "workers.weather",
        "workers.features",
        "workers.risk",
        "workers.backup",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Almaty",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "workers.documents.*": {"queue": "documents"},
        "workers.weather.*": {"queue": "weather"},
        "workers.features.*": {"queue": "features"},
        "workers.risk.*": {"queue": "risk"},
        "workers.backup.*": {"queue": "backup"},
    },
)

_TASK_START_TIMES: dict[str, float] = {}


@task_prerun.connect
def on_task_prerun(task_id: str, task: object, **kwargs) -> None:
    _TASK_START_TIMES[task_id] = time.monotonic()
    log.info("celery_task_start", task_name=getattr(task, "name", str(task)), task_id=task_id)


@task_postrun.connect
def on_task_postrun(task_id: str, task: object, **kwargs) -> None:
    start = _TASK_START_TIMES.pop(task_id, None)
    duration_ms = round((time.monotonic() - start) * 1000) if start is not None else None
    log.info(
        "celery_task_success",
        task_name=getattr(task, "name", str(task)),
        task_id=task_id,
        duration_ms=duration_ms,
    )


@task_failure.connect
def on_task_failure(task_id: str, exception: Exception, traceback: object, sender: object, **kwargs) -> None:
    start = _TASK_START_TIMES.pop(task_id, None)
    duration_ms = round((time.monotonic() - start) * 1000) if start is not None else None
    log.error(
        "celery_task_failure",
        task_name=getattr(sender, "name", str(sender)),
        task_id=task_id,
        duration_ms=duration_ms,
        exc_info=True,
    )


# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "fetch-weather-hourly": {
        "task": "workers.weather.fetch_weather",
        "schedule": 3600,  # every 3600 seconds (1 hour)
        "options": {"queue": "weather"},
    },
    "rebuild-features-daily": {
        "task": "workers.features.rebuild_features",
        "schedule": crontab(hour=3, minute=0),
        "options": {"queue": "features"},
    },
    "compute-risk-scores-daily": {
        "task": "workers.risk.compute_risk_scores",
        "schedule": crontab(hour=4, minute=0),
        "args": ["astana"],
        "options": {"queue": "risk"},
    },
    "daily-backup": {
        "task": "workers.backup.daily_backup",
        "schedule": crontab(hour=2, minute=0),  # 02:00 UTC daily
        "options": {"queue": "backup"},
    },
}
