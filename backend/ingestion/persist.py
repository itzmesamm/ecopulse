"""
Layer 1 — persistence.

Pulls from all 4 collectors and actually writes rows to the DB, scoped to
an org, so ingestion history exists beyond a single API call.
"""
from sqlalchemy.orm import Session

from backend.db import models
from backend.ingestion.billing_collector import get_billing_records
from backend.ingestion.gpu_telemetry_collector import get_gpu_metrics
from backend.ingestion.k8s_collector import get_k8s_metrics
from backend.ingestion.operational_logs_collector import get_operational_logs


def ingest_and_persist(db: Session, org_id: str) -> dict:
    """Pulls from all 4 Layer-1 sources and stores them, tagged with org_id."""
    billing = get_billing_records(org_id=org_id)
    gpu = get_gpu_metrics(org_id=org_id)
    k8s = get_k8s_metrics(org_id=org_id)
    logs = get_operational_logs(org_id=org_id)

    for r in billing:
        db.add(models.BillingRecord(
            org_id=r["org_id"], resource_id=r["resource_id"], service=r["resource_type"],
            region=r.get("region"), account=r.get("account"), environment=r.get("environment"),
            cost=r.get("estimated_monthly_cost_usd"), usage_hours=r.get("usage_hours"),
        ))
    for r in gpu:
        db.add(models.GPUMetric(
            org_id=r["org_id"], gpu_id=r["gpu_id"],
            utilization_pct=r.get("utilization_pct"), vram_used_mb=r.get("vram_used_mb"),
            power_watts=r.get("power_watts"), temp_c=r.get("temp_c"),
        ))
    for r in k8s:
        db.add(models.K8sMetric(
            org_id=r["org_id"], pod_name=r["pod_name"], namespace=r.get("namespace"),
            cpu_usage=r.get("cpu_usage"), memory_usage=r.get("memory_usage"),
        ))
    for r in logs:
        db.add(models.OperationalLog(
            org_id=r["org_id"], source=r["source"], message=r["message"], severity=r["severity"],
        ))

    db.commit()
    return {"billing": len(billing), "gpu": len(gpu), "k8s": len(k8s), "logs": len(logs)}
