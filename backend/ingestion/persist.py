"""Normalize and persist source events once per organization and fingerprint."""
import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.db import models
from backend.ingestion.billing_collector import get_billing_records
from backend.ingestion.infrastructure_collector import get_infrastructure_metrics
from backend.ingestion.gpu_telemetry_collector import get_gpu_metrics
from backend.ingestion.k8s_collector import get_k8s_metrics
from backend.ingestion.operational_logs_collector import get_operational_logs


def _recorded_at(record: dict) -> datetime:
    value = record.get("recorded_at")
    if not value:
        return datetime.utcnow()
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _source_key(record: dict) -> str:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def ingest_and_persist(db: Session, org_id: str) -> dict:
    """Pull all configured sources and atomically persist unseen source events."""
    billing = get_billing_records(org_id=org_id)
    infrastructure = get_infrastructure_metrics(org_id=org_id)
    gpu = get_gpu_metrics(org_id=org_id)
    k8s = get_k8s_metrics(org_id=org_id)
    logs = get_operational_logs(org_id=org_id)

    batches = {"billing": billing, "infrastructure": infrastructure, "gpu": gpu, "k8s": k8s, "logs": logs}
    sources = {
        "billing": "billing",
        "infrastructure": "infrastructure",
        "gpu": "gpu",
        "k8s": "k8s",
        "logs": "operational_logs",
    }
    existing = {
        source: {
            row[0]
            for row in db.query(models.IngestionRecord.source_key).filter(
                models.IngestionRecord.org_id == org_id,
                models.IngestionRecord.source == sources[source],
            ).all()
        }
        for source in batches
    }
    inserted = {source: 0 for source in batches}
    duplicates = {source: 0 for source in batches}

    for kind, records in batches.items():
        for record in records:
            key = _source_key(record)
            if key in existing[kind]:
                duplicates[kind] += 1
                continue
            existing[kind].add(key)
            recorded_at = _recorded_at(record)
            db.add(models.IngestionRecord(org_id=org_id, source=sources[kind], source_key=key))
            if kind == "billing":
                db.add(models.BillingRecord(
                    org_id=org_id, resource_id=record["resource_id"],
                    service=record.get("service") or record.get("resource_type"),
                    region=record.get("region"), account=record.get("account"),
                    environment=record.get("environment"), team=record.get("team"),
                    owner=record.get("owner"),
                    cost=record.get("cost", record.get("estimated_monthly_cost_usd")),
                    usage_hours=record.get("usage_hours"), recorded_at=recorded_at,
                ))
            elif kind == "gpu":
                db.add(models.GPUMetric(
                    org_id=org_id, gpu_id=record["gpu_id"], account=record.get("account"),
                    environment=record.get("environment"), utilization_pct=record.get("utilization_pct"),
                    vram_used_mb=record.get("vram_used_mb"), power_watts=record.get("power_watts"),
                    temp_c=record.get("temp_c"), recorded_at=recorded_at,
                ))
            elif kind == "infrastructure":
                db.add(models.InfrastructureMetric(
                    org_id=org_id, host_id=record["host_id"], cpu_pct=record.get("cpu_pct"),
                    memory_pct=record.get("memory_pct"), disk_pct=record.get("disk_pct"),
                    network_receive_bytes_per_second=record.get("network_receive_bytes_per_second"),
                    network_transmit_bytes_per_second=record.get("network_transmit_bytes_per_second"),
                    recorded_at=recorded_at,
                ))
            elif kind == "k8s":
                db.add(models.K8sMetric(
                    org_id=org_id, pod_name=record["pod_name"], namespace=record.get("namespace"),
                    cpu_usage=record.get("cpu_usage"), memory_usage=record.get("memory_usage"),
                    recorded_at=recorded_at,
                ))
            else:
                db.add(models.OperationalLog(
                    org_id=org_id, source=record["source"], message=record["message"],
                    severity=record.get("severity", "INFO"), recorded_at=recorded_at,
                ))
            inserted[kind] += 1

    db.commit()
    return {"inserted": inserted, "duplicates": duplicates}
