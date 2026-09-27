from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api import security
from backend.db import models
from backend.db.database import Base
from backend.ingestion import persist
from backend.ingestion import source_mode
from backend.remediation.executor import process_recommendations


def _database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)()


def test_auth_middleware_rejects_missing_and_cross_org_access(monkeypatch):
    engine, db = _database()
    org = models.Organization(name="Tenant A")
    db.add(org)
    db.flush()
    db.add(models.UserProfile(id="user-1", org_id=org.id, role="admin"))
    db.commit()
    monkeypatch.setattr(security, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        security,
        "get_supabase",
        lambda: SimpleNamespace(auth=SimpleNamespace(get_user=lambda token: SimpleNamespace(user=SimpleNamespace(id="user-1")))),
    )

    app = FastAPI()
    app.add_middleware(security.OrgAuthenticationMiddleware)

    @app.post("/echo")
    async def echo(request: Request):
        return {"profile": request.state.profile, "payload": await request.json()}

    client = TestClient(app)
    try:
        no_token = client.post("/echo", json={"org_id": org.id})
        denied = client.post(
            "/echo",
            headers={"Authorization": "Bearer valid"},
            json={"org_id": "other-org", "value": "body preserved"},
        )
        conflicting = client.post(
            "/echo",
            params={"org_id": org.id},
            headers={"Authorization": "Bearer valid"},
            json={"org_id": "other-org", "value": "body preserved"},
        )
        allowed = client.post(
            "/echo",
            headers={"Authorization": "Bearer valid"},
            json={"org_id": org.id, "value": "body preserved"},
        )
        assert no_token.status_code == 401
        assert denied.status_code == 403
        assert conflicting.status_code == 403
        assert allowed.status_code == 200
        assert allowed.json()["profile"]["role"] == "admin"
        assert allowed.json()["payload"]["value"] == "body preserved"
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_ingestion_is_idempotent_and_preserves_source_fields(monkeypatch):
    engine, db = _database()
    org = models.Organization(name="Ingestion tenant")
    db.add(org)
    db.commit()
    batch = {
        "billing": [{"resource_id": "i-123", "resource_type": "ec2", "region": "us-east-1", "estimated_monthly_cost_usd": 20, "usage_hours": 2, "recorded_at": "2026-09-01T00:00:00Z"}],
        "infrastructure": [{"host_id": "node-1", "cpu_pct": 10, "memory_pct": 20, "disk_pct": 30, "network_receive_bytes_per_second": 4, "network_transmit_bytes_per_second": 5, "recorded_at": "2026-09-01T00:00:00Z"}],
        "gpu": [{"gpu_id": "gpu-1", "account": "acct-1", "environment": "sandbox", "utilization_pct": 3, "vram_used_mb": 512, "power_watts": 50, "temp_c": 40, "recorded_at": "2026-09-01T00:00:00Z"}],
        "k8s": [{"pod_name": "pod-1", "namespace": "ml", "cpu_usage": 1, "memory_usage": 2, "recorded_at": "2026-09-01T00:00:00Z"}],
        "logs": [{"source": "gpu", "message": "idle", "severity": "WARNING", "recorded_at": "2026-09-01T00:00:00Z"}],
    }
    monkeypatch.setattr(persist, "get_billing_records", lambda **kwargs: batch["billing"])
    monkeypatch.setattr(persist, "get_infrastructure_metrics", lambda **kwargs: batch["infrastructure"])
    monkeypatch.setattr(persist, "get_gpu_metrics", lambda **kwargs: batch["gpu"])
    monkeypatch.setattr(persist, "get_k8s_metrics", lambda **kwargs: batch["k8s"])
    monkeypatch.setattr(persist, "get_operational_logs", lambda **kwargs: batch["logs"])

    try:
        first = persist.ingest_and_persist(db, org.id)
        second = persist.ingest_and_persist(db, org.id)
        expected_sources = {"billing": 1, "infrastructure": 1, "gpu": 1, "k8s": 1, "logs": 1}
        assert first["inserted"] == expected_sources
        assert second["inserted"] == {source: 0 for source in expected_sources}
        assert second["duplicates"] == expected_sources
        gpu = db.query(models.GPUMetric).one()
        assert gpu.vram_used_mb == 512
        assert gpu.environment == "sandbox"
        assert db.query(models.InfrastructureMetric).one().cpu_pct == 10
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_remediation_never_marks_mock_execution_as_success(monkeypatch):
    engine, db = _database()
    org = models.Organization(name="Remediation tenant")
    db.add(org)
    db.flush()
    recommendation = models.Recommendation(
        org_id=org.id,
        resource_id="not-an-aws-id",
        service="ec2",
        environment="sandbox",
        title="Stop instance",
        summary="Idle resource",
        action="Stop instance",
        suggested_action="Stop instance",
        status="pending",
    )
    db.add(recommendation)
    db.commit()

    try:
        dry_result = process_recommendations(
            db=db,
            org_id=org.id,
            recommendation_ids=[recommendation.id],
            user_role="admin",
            dry_run=True,
        )
        assert dry_result[0]["new_status"] == "dry_run"
        assert "DRY RUN" in dry_result[0]["result"]

        recommendation.status = "pending"
        db.commit()
        monkeypatch.setenv("REMEDIATION_ENABLED", "true")
        failed_result = process_recommendations(
            db=db,
            org_id=org.id,
            recommendation_ids=[recommendation.id],
            user_role="admin",
            dry_run=False,
        )
        assert failed_result[0]["new_status"] == "failed"
        assert "valid AWS EC2 instance ID" in failed_result[0]["result"]
        assert db.query(models.AuditLog).count() == 2
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_production_defaults_to_live_ingestion(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("INGESTION_MODE", raising=False)
    assert source_mode.is_synthetic_mode() is False