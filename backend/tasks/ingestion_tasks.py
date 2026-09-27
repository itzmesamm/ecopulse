from __future__ import annotations

import os

from backend.celery_app import celery_app
from backend.db import models
from backend.db.database import SessionLocal
from backend.ingestion.persist import ingest_and_persist


@celery_app.task(name="backend.tasks.ingestion_tasks.ingest_all_organizations")
def ingest_all_organizations() -> int:
    """Run scheduled ingestion only when explicitly enabled by deployment config."""
    if os.getenv("INGESTION_ENABLED", "false").lower() != "true":
        return 0

    db = SessionLocal()
    try:
        completed = 0
        for org in db.query(models.Organization.id).all():
            ingest_and_persist(db, org.id)
            completed += 1
        return completed
    finally:
        db.close()