from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.analysis.anomaly_detection import detect_anomalies
from backend.analysis.cost_grouping import summarize_team_costs
from backend.analysis.gpu_optimizer import detect_gpu_optimizations
from backend.db import models
from backend.db.database import Base


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def seed_org(session):
    org = models.Organization(id="org-anom", name="Acme")
    session.add(org)
    session.commit()
    return org


def seed_billing_records(session, org_id):
    base = datetime(2024, 8, 1, 12, 0, 0)
    for idx in range(11):
        session.add(
            models.BillingRecord(
                id=f"bill-{idx}",
                org_id=org_id,
                resource_id=f"res-{idx}",
                service="ec2" if idx % 2 == 0 else "rds",
                region="us-east-1" if idx % 3 else "us-west-2",
                environment="production" if idx % 2 == 0 else "staging",
                owner="alice" if idx % 2 == 0 else "bob",
                team="platform" if idx % 2 == 0 else "data",
                cost=1200 + idx * 12,
                usage_hours=30.0 + idx,
                recorded_at=base + timedelta(days=idx),
            )
        )

    # Make the final record an obvious outlier for the anomaly detector.
    session.add(
        models.BillingRecord(
            id="bill-11",
            org_id=org_id,
            resource_id="res-outlier",
            service="ec2",
            region="us-east-1",
            environment="production",
            owner="alice",
            team="platform",
            cost=5000.0,
            usage_hours=120.0,
            recorded_at=base + timedelta(days=11),
        )
    )
    session.commit()


def test_detect_anomalies_finds_outliers():
    session = make_session()
    org = seed_org(session)
    seed_billing_records(session, org.id)

    findings = detect_anomalies(session, org.id, min_samples=5)
    assert findings
    assert all(f.resource_id for f in findings)
    assert all(f.anomaly_score >= 0 for f in findings)


def test_detect_anomalies_handles_empty_data():
    session = make_session()
    org = seed_org(session)

    findings = detect_anomalies(session, org.id)
    assert findings == []


def test_team_cost_summary_groups_by_team_and_owner():
    session = make_session()
    org = seed_org(session)
    seed_billing_records(session, org.id)

    summary = summarize_team_costs(session, org.id)
    assert summary
    assert summary[0]["org_id"] == org.id
    assert "team" in summary[0]
    assert "owner" in summary[0]
    assert summary[0]["total_cost_usd"] >= 0


def test_gpu_optimizer_detects_idle_gpus():
    session = make_session()
    org = seed_org(session)
    session.add(
        models.GPUMetric(
            id="gpu-1",
            org_id=org.id,
            gpu_id="gpu-a",
            account="acct-1",
            environment="production",
            utilization_pct=5.0,
            vram_used_mb=512,
            power_watts=250,
            temp_c=42,
            recorded_at=datetime(2024, 8, 2, 9, 0),
        )
    )
    session.add(
        models.GPUMetric(
            id="gpu-2",
            org_id=org.id,
            gpu_id="gpu-b",
            account="acct-1",
            environment="production",
            utilization_pct=85.0,
            vram_used_mb=20000,
            power_watts=340,
            temp_c=67,
            recorded_at=datetime(2024, 8, 2, 9, 5),
        )
    )
    session.add(
        models.OperationalLog(
            id="log-1",
            org_id=org.id,
            source="gpu",
            message="GPU gpu-a idle for 6h, utilization near zero",
            severity="WARNING",
            recorded_at=datetime(2024, 8, 2, 10, 0),
        )
    )
    session.commit()

    findings = detect_gpu_optimizations(session, org.id)
    assert findings
    assert any(f.gpu_id == "gpu-a" for f in findings)
    assert all(f.estimated_monthly_waste_usd >= 0 for f in findings)
