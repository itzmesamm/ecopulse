from datetime import datetime
from datetime import timedelta

from backend.analysis.waste_analyzer import WasteAnalyzer
from backend.db import models


def test_infra_waste_needs_billing_utilization_and_matching_log(db_session):
    org = models.Organization(name="Infra signal test")
    db_session.add(org)
    db_session.flush()
    db_session.add(models.BillingRecord(
        org_id=org.id,
        resource_id="i-test-host",
        service="ec2",
        cost=120.0,
        usage_hours=None,
        recorded_at=datetime.utcnow(),
    ))
    db_session.add(models.InfrastructureMetric(
        org_id=org.id,
        host_id="i-test-host",
        cpu_pct=2.0,
        recorded_at=datetime.utcnow(),
    ))
    db_session.commit()

    assert WasteAnalyzer().analyze_records(db_session, org.id) == []

    db_session.add(models.OperationalLog(
        org_id=org.id,
        source="node-exporter",
        message="i-test-host idle: CPU utilization below 5%",
        severity="INFO",
        recorded_at=datetime.utcnow(),
    ))
    db_session.commit()
    findings = WasteAnalyzer().analyze_records(db_session, org.id)

    assert len(findings) == 1
    assert findings[0].waste_type == "infrastructure_idle"
    assert findings[0].estimated_monthly_waste_usd == 60.0


def test_billing_analysis_uses_only_latest_record_per_resource(db_session):
    org = models.Organization(name="Latest billing test")
    db_session.add(org)
    db_session.flush()
    now = datetime.utcnow()
    db_session.add_all([
        models.BillingRecord(
            org_id=org.id, resource_id="resource-latest", service="ec2",
            cost=100, usage_hours=1, recorded_at=now - timedelta(days=1),
        ),
        models.BillingRecord(
            org_id=org.id, resource_id="resource-latest", service="ec2",
            cost=100, usage_hours=20, recorded_at=now,
        ),
    ])
    db_session.commit()

    assert WasteAnalyzer().analyze_records(db_session, org.id) == []