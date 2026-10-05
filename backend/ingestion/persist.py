"""
Layer 1 — persistence.

Pulls from all 4 collectors and actually writes rows to the DB, scoped to
an org, so ingestion history exists beyond a single API call.
"""
import datetime
from sqlalchemy.orm import Session

from backend.db import models
from backend.ingestion.demo_dataset import build_demo_dataset


def _parse_ts(value):
    if not value:
        return datetime.datetime.utcnow()
    if isinstance(value, datetime.datetime):
        return value
    try:
        return datetime.datetime.fromisoformat(str(value).replace("Z", ""))
    except ValueError:
        return datetime.datetime.utcnow()


def ingest_and_persist(db: Session, org_id: str) -> dict:
    """Persist the versioned demo dataset without duplicating prior samples."""
    dataset = build_demo_dataset(org_id)
    billing = dataset["billing"]
    gpu = dataset["gpu"]
    k8s = dataset["k8s"]
    logs = dataset["logs"]

    existing_billing = {
        (row.resource_id, row.recorded_at)
        for row in db.query(models.BillingRecord).filter_by(org_id=org_id).all()
    }
    existing_gpu = {
        (row.gpu_id, row.recorded_at)
        for row in db.query(models.GPUMetric).filter_by(org_id=org_id).all()
    }
    existing_k8s = {
        (row.pod_name, row.recorded_at)
        for row in db.query(models.K8sMetric).filter_by(org_id=org_id).all()
    }
    existing_logs = {
        (row.source, row.message, row.recorded_at)
        for row in db.query(models.OperationalLog).filter_by(org_id=org_id).all()
    }

    inserted = {"billing": 0, "gpu": 0, "k8s": 0, "logs": 0}

    for r in billing:
        recorded_at = _parse_ts(r.get("recorded_at"))
        key = (r["resource_id"], recorded_at)
        if key in existing_billing:
            continue
        db.add(models.BillingRecord(
            org_id=r["org_id"], resource_id=r["resource_id"], service=r["service"],
            region=r.get("region"), account=r.get("account"), environment=r.get("environment"),
            team=r.get("team"), owner=r.get("owner"), cost=r.get("cost"),
            usage_hours=r.get("usage_hours"), period_days=r.get("period_days", 30),
            recorded_at=recorded_at,
        ))
        existing_billing.add(key)
        inserted["billing"] += 1
    for r in gpu:
        recorded_at = _parse_ts(r.get("recorded_at"))
        key = (r["gpu_id"], recorded_at)
        if key in existing_gpu:
            continue
        db.add(models.GPUMetric(
            org_id=r["org_id"], gpu_id=r["gpu_id"],
            utilization_pct=r.get("utilization_pct"), vram_used_mb=r.get("vram_used_mb"),
            power_watts=r.get("power_watts"), temp_c=r.get("temp_c"),
            environment=r.get("environment"), account=r.get("account"), recorded_at=recorded_at,
        ))
        existing_gpu.add(key)
        inserted["gpu"] += 1
    for r in k8s:
        recorded_at = _parse_ts(r.get("recorded_at"))
        key = (r["pod_name"], recorded_at)
        if key in existing_k8s:
            continue
        db.add(models.K8sMetric(
            org_id=r["org_id"], pod_name=r["pod_name"], namespace=r.get("namespace"),
            cpu_usage=r.get("cpu_usage"), memory_usage=r.get("memory_usage"), recorded_at=recorded_at,
        ))
        existing_k8s.add(key)
        inserted["k8s"] += 1
    for r in logs:
        recorded_at = _parse_ts(r.get("recorded_at"))
        key = (r["source"], r["message"], recorded_at)
        if key in existing_logs:
            continue
        db.add(models.OperationalLog(
            org_id=r["org_id"], source=r["source"], message=r["message"], severity=r["severity"],
            recorded_at=recorded_at,
        ))
        existing_logs.add(key)
        inserted["logs"] += 1

    db.commit()
    return {**inserted, "dataset_version": "ecopulse-demo-v1", "data_mode": "synthetic_demo"}
