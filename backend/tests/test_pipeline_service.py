from datetime import datetime

from fastapi.testclient import TestClient

from backend.db import models
from backend.main import app
from backend.ingestion.persist import ingest_and_persist
from backend.services import recommendation_service
from backend.services.pipeline_service import run_organization_pipeline


def test_pipeline_connects_findings_to_recommendations_without_duplicates(db_session, monkeypatch):
    org = models.Organization(name="Pipeline test")
    db_session.add(org)
    db_session.flush()
    billing = models.BillingRecord(
        org_id=org.id,
        resource_id="i-test-1",
        service="ec2",
        region="us-east-1",
        environment="sandbox",
        cost=100.0,
        usage_hours=1.0,
        recorded_at=datetime.utcnow(),
    )
    db_session.add(billing)
    db_session.add(models.GPUMetric(
        org_id=org.id,
        gpu_id="gpu-test-1",
        environment="sandbox",
        utilization_pct=2.0,
        vram_used_mb=512.0,
        power_watts=75.0,
        recorded_at=datetime.utcnow(),
    ))
    db_session.add(models.OperationalLog(
        org_id=org.id,
        source="gpu",
        message="gpu-test-1 idle with no workload",
        severity="WARNING",
        recorded_at=datetime.utcnow(),
    ))
    db_session.commit()
    monkeypatch.setattr(recommendation_service, "generate_recommendation", lambda *args, **kwargs: None)

    first = run_organization_pipeline(db_session, org.id)
    second = run_organization_pipeline(db_session, org.id)

    assert first["waste_findings"] == 1
    assert first["gpu_findings"] == 1
    assert first["recommendations"] == 2
    assert second["gpu_findings"] == 0
    assert second["recommendations"] == 2
    assert db_session.query(models.WasteItem).filter_by(org_id=org.id).count() == 1
    assert db_session.query(models.GPUOptimizationFinding).filter_by(org_id=org.id).count() == 1
    assert db_session.query(models.Recommendation).filter_by(org_id=org.id).count() == 2


def test_synthetic_collection_reaches_findings_and_recommendations(db_session, monkeypatch):
    org = models.Organization(name="Synthetic end-to-end test")
    db_session.add(org)
    db_session.commit()
    monkeypatch.setattr(recommendation_service, "generate_recommendation", lambda *args, **kwargs: None)

    collected = ingest_and_persist(db_session, org.id)
    repeated_collection = ingest_and_persist(db_session, org.id)
    result = run_organization_pipeline(db_session, org.id)

    assert collected["inserted"]["billing"] > 0
    assert collected["inserted"]["infrastructure"] > 0
    assert collected["inserted"]["gpu"] > 0
    assert repeated_collection["inserted"]["billing"] == 0
    assert repeated_collection["duplicates"]["billing"] == collected["inserted"]["billing"]
    assert result["waste_findings"] >= 1
    assert result["gpu_findings"] >= 1
    assert result["recommendations"] >= 2


def test_pipeline_api_requires_bearer_and_runs_for_authenticated_tenant(db_session, monkeypatch):
    org = models.Organization(id="pipeline-api-org", name="Pipeline API test")
    db_session.add(org)
    db_session.flush()
    profile = models.UserProfile(id="test-user", org_id=org.id, role="admin")
    db_session.add(profile)
    db_session.add(models.BillingRecord(
        org_id=org.id,
        resource_id="pipeline-api-resource",
        service="ec2",
        environment="sandbox",
        cost=100.0,
        usage_hours=1.0,
        recorded_at=datetime.utcnow(),
    ))
    db_session.commit()
    monkeypatch.setattr(recommendation_service, "generate_recommendation", lambda *args, **kwargs: None)
    client = TestClient(app)

    unauthenticated = client.post("/pipeline/run", json={"org_id": org.id})
    authenticated = client.post(
        "/pipeline/run",
        headers={"Authorization": "Bearer test-token"},
        json={"org_id": org.id, "collect": False},
    )

    assert unauthenticated.status_code == 401
    assert authenticated.status_code == 200
    assert authenticated.json()["org_id"] == org.id