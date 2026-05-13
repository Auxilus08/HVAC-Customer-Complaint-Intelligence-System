"""Celery application factory wired to Redis broker with Beat schedule."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import Settings


def create_celery_app(settings: Settings | None = None) -> Celery:
    """Create and configure the Celery application."""
    if settings is None:
        from app.config import get_settings

        settings = get_settings()

    app = Celery("hvac_workers")

    beat_schedule: dict = {
        "nightly-batch-pipeline": {
            "task": "app.workers.cluster_job.run_nightly_batch",
            "schedule": crontab(hour=2, minute=0),
            "options": {"queue": "batch"},
        }
    }

    if settings.TELEGRAM_ENABLED:
        # Schedule getUpdates long-poll on a tight interval. The task itself
        # blocks for up to TELEGRAM_LONG_POLL_TIMEOUT_SECONDS, so a 2s schedule
        # effectively gives a constant connection without spamming Telegram.
        beat_schedule["telegram-poll-updates"] = {
            "task": "app.workers.telegram_poll_worker.poll_updates",
            "schedule": float(settings.TELEGRAM_POLL_INTERVAL_SECONDS),
            "options": {"queue": "telegram"},
        }

    app.conf.update(
        broker_url=settings.CELERY_BROKER_URL,
        result_backend=settings.CELERY_RESULT_BACKEND,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        task_routes={
            "app.workers.embedding_worker.*": {"queue": "embeddings"},
            "app.workers.sentiment_worker.*": {"queue": "sentiment"},
            "app.workers.cluster_job.*": {"queue": "batch"},
            "app.workers.label_job.*": {"queue": "batch"},
            "app.workers.trend_job.*": {"queue": "batch"},
            "app.workers.telegram_poll_worker.*": {"queue": "telegram"},
        },
        # Dead-letter: failed tasks go to a dedicated DLQ queue via Redis
        task_reject_on_worker_lost=True,
        beat_schedule=beat_schedule,
    )

    app.autodiscover_tasks(
        [
            "app.workers.embedding_worker",
            "app.workers.sentiment_worker",
            "app.workers.cluster_job",
            "app.workers.label_job",
            "app.workers.trend_job",
            "app.workers.telegram_poll_worker",
        ]
    )

    return app


# Module-level singleton used by workers when imported directly
celery_app = create_celery_app()
