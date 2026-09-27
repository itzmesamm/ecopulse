from __future__ import annotations

import os

from celery import shared_task
from sqlalchemy.orm import Session

from backend.celery_app import celery_app
from backend.db import models
from backend.db.database import SessionLocal
from backend.remediation.executor import process_recommendations


def _with_db() -> Session:
    return SessionLocal()


@celery_app.task(name="backend.tasks.remediation_tasks.process_pending_recommendations", bind=False)
def process_pending_recommendations(
    batch_limit: int = 50,
    dry_run: bool | None = None,
) -> int:
    """
    Processes the next batch of pending recommendations for all orgs (dry-run by default).
    """
    if dry_run is None:
        dry_run = os.getenv("REMEDIATION_DRY_RUN", "true").lower() == "true"

    user_role = os.getenv("SYSTEM_USER_ROLE", "system")

    db = _with_db()
    try:
        orgs = db.query(models.Organization).all()
        processed_total = 0

        for org in orgs:
            pending_ids_rows = (
                db.query(models.Recommendation.id)
                .filter(models.Recommendation.org_id == org.id, models.Recommendation.status == "pending")
                .order_by(models.Recommendation.created_at.asc())
                .limit(batch_limit)
                .all()
            )
            pending_ids = [row.id for row in pending_ids_rows]
            if not pending_ids:
                continue

            outcomes = process_recommendations(
                db=db,
                org_id=org.id,
                recommendation_ids=pending_ids,
                user_role=user_role,
                dry_run=dry_run,
            )
            processed_total += len(outcomes)

        return processed_total
    finally:
        db.close()

