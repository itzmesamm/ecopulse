from __future__ import annotations

import logging
import os

from backend.celery_app import celery_app
from backend.db import models
from backend.db.database import SessionLocal
from backend.services.pipeline_service import run_organization_pipeline

logger = logging.getLogger(__name__)


@celery_app.task(name="backend.tasks.pipeline_tasks.run_pipeline_for_all_organizations")
def run_pipeline_for_all_organizations() -> dict:
    """Run the full pipeline on schedule only when explicitly enabled."""
    if os.getenv("PIPELINE_ENABLED", "false").lower() != "true":
        return {"completed": 0, "failed": 0, "disabled": True}

    db = SessionLocal()
    completed = 0
    failed = 0
    try:
        org_ids = [row[0] for row in db.query(models.Organization.id).all()]
        for org_id in org_ids:
            try:
                run_organization_pipeline(
                    db,
                    org_id,
                    collect=os.getenv("INGESTION_ENABLED", "false").lower() == "true",
                )
                completed += 1
            except Exception:
                db.rollback()
                failed += 1
                logger.exception("Scheduled EcoPulse pipeline failed for organization %s", org_id)
        return {"completed": completed, "failed": failed, "disabled": False}
    finally:
        db.close()
