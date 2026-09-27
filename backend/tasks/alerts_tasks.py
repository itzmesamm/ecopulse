from __future__ import annotations

import os

from celery import shared_task
from sqlalchemy.orm import Session

from backend.celery_app import celery_app
from backend.alerts.notifier import check_and_create_alerts
from backend.db import models
from backend.db.database import SessionLocal


def _with_db() -> Session:
    return SessionLocal()


@celery_app.task(name="backend.tasks.alerts_tasks.check_alerts_every_org", bind=False)
def check_alerts_every_org(
    budget_limit_usd: float = 5000.0,
    anomaly_threshold: float = 0.8,
    forecast_days: int = 30,
) -> int:
    """
    Runs alert checks for all orgs.
    Returns total number of alerts created (best-effort).
    """
    db = _with_db()
    try:
        orgs = db.query(models.Organization).all()
        created_total = 0
        for org in orgs:
            created = check_and_create_alerts(
                db=db,
                org_id=org.id,
                budget_limit_usd=budget_limit_usd,
                anomaly_threshold=anomaly_threshold,
                forecast_days=forecast_days,
            )
            created_total += len(created)
        return created_total
    finally:
        db.close()

