"""
Celery app configuration for EcoPulse background jobs.

Roadmap goal: scheduled scans (alerts) + background remediation workflows.

This backend keeps API behavior the same; Celery only adds async + automation.
"""

from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "ecopulse",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    # Make failures visible during development.
    task_track_started=True,
)

# Scheduled automation (roadmap-style)
# Note: needs a running Redis broker and at least one celery worker + celery beat process.
celery_app.conf.beat_schedule = {
    "check-alerts-every-15-min": {
        "task": "backend.tasks.alerts_tasks.check_alerts_every_org",
        "schedule": crontab(minute="*/15"),
        "args": (),
    },
    "process-remediation-every-5-min": {
        "task": "backend.tasks.remediation_tasks.process_pending_recommendations",
        "schedule": crontab(minute="*/5"),
        "args": (),
    },
}

# Autodiscover tasks inside backend.tasks.* modules.
celery_app.autodiscover_tasks(["backend.tasks"])

