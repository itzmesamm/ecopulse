import os

from sqlalchemy.orm import Session

from backend.alerts.notifier import check_and_create_alerts
from backend.analysis.anomaly_detection import detect_anomalies, persist_anomaly_findings
from backend.analysis.gpu_optimizer import detect_gpu_optimizations, persist_gpu_optimizations
from backend.analysis.waste_analyzer import WasteAnalyzer, persist_waste_items
from backend.db import models
from backend.ingestion.persist import ingest_and_persist
from backend.services.recommendation_service import generate_recommendations_for_org, save_recommendations


def run_organization_pipeline(db: Session, org_id: str, *, collect: bool = False) -> dict:
    """Run the connected ingestion-to-alert workflow for one organization."""
    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if org is None:
        raise ValueError("Organization not found")

    result = {"org_id": org_id, "ingestion": None}
    if collect:
        result["ingestion"] = ingest_and_persist(db, org_id)

    waste_results = WasteAnalyzer().analyze_records(db, org_id)
    result["waste_findings"] = persist_waste_items(db, org_id, waste_results)

    gpu_findings = detect_gpu_optimizations(db, org_id)
    result["gpu_findings"] = persist_gpu_optimizations(db, org_id, gpu_findings)

    anomaly_findings = detect_anomalies(db, org_id)
    result["anomaly_findings"] = persist_anomaly_findings(db, org_id, anomaly_findings)

    recommendation_limit = int(os.getenv("PIPELINE_RECOMMENDATION_LIMIT", "5"))
    if not 1 <= recommendation_limit <= 100:
        raise ValueError("PIPELINE_RECOMMENDATION_LIMIT must be between 1 and 100")
    recommendations = generate_recommendations_for_org(db, org_id, limit=recommendation_limit)
    saved = save_recommendations(db, org_id, recommendations)
    result["recommendations"] = len(saved)

    alerts = check_and_create_alerts(db=db, org_id=org_id)
    result["alerts"] = len(alerts)
    return result
