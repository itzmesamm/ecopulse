from datetime import datetime, timedelta

from backend.analysis.gpu_optimizer import detect_gpu_optimizations, persist_gpu_optimizations
from backend.db import models


def _add_gpu(db_session, org_id, utilization=3, vram=512, power=100):
    metric = models.GPUMetric(
        org_id=org_id,
        gpu_id="gpu-test-1",
        environment="sandbox",
        utilization_pct=utilization,
        vram_used_mb=vram,
        power_watts=power,
        recorded_at=datetime.utcnow(),
    )
    db_session.add(metric)
    db_session.commit()
    return metric


def _add_log(db_session, org_id, message, minutes_ago=0):
    db_session.add(models.OperationalLog(
        org_id=org_id,
        source="gpu",
        message=message,
        severity="WARNING",
        recorded_at=datetime.utcnow() - timedelta(minutes=minutes_ago),
    ))
    db_session.commit()


def test_gpu_requires_recent_gpu_specific_log(db_session):
    org = models.Organization(name="GPU test")
    db_session.add(org)
    db_session.commit()
    _add_gpu(db_session, org.id)

    assert detect_gpu_optimizations(db_session, org.id) == []

    _add_log(db_session, org.id, "gpu-test-1 workload idle")
    findings = detect_gpu_optimizations(db_session, org.id)
    assert len(findings) == 1
    assert findings[0].severity_score > 0
    assert "VRAM" in findings[0].details


def test_gpu_rejects_high_vram_stale_or_unrelated_log(db_session):
    org = models.Organization(name="GPU test")
    db_session.add(org)
    db_session.commit()
    _add_gpu(db_session, org.id, vram=4096)
    _add_log(db_session, org.id, "gpu-test-1 idle", minutes_ago=90)
    _add_log(db_session, org.id, "gpu-other idle")

    assert detect_gpu_optimizations(db_session, org.id) == []


def test_gpu_findings_are_not_duplicated(db_session):
    org = models.Organization(name="GPU test")
    db_session.add(org)
    db_session.commit()
    _add_gpu(db_session, org.id)
    _add_log(db_session, org.id, "gpu-test-1 no workload")
    findings = detect_gpu_optimizations(db_session, org.id)

    assert persist_gpu_optimizations(db_session, org.id, findings) == 1
    assert persist_gpu_optimizations(db_session, org.id, findings) == 0