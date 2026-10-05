from backend.db import models
from backend.greenops.carbon_calc import estimate_carbon_savings_kg_for_waste_item


def test_carbon_estimate_normalizes_daily_usage_to_monthly(db_session):
    org = models.Organization(name="Carbon Period Test")
    db_session.add(org)
    db_session.flush()

    billing = models.BillingRecord(
        org_id=org.id,
        resource_id="i-demo-idle",
        service="ec2",
        region="us-east-1",
        environment="sandbox",
        cost=4.8,
        usage_hours=0.08,
        period_days=1,
    )
    db_session.add(billing)
    db_session.flush()

    finding = models.WasteItem(
        org_id=org.id,
        billing_record_id=billing.id,
        resource_id=billing.resource_id,
        service="ec2",
        region="us-east-1",
        environment="sandbox",
        waste_type="low_utilization",
        severity_score=0.2,
        estimated_monthly_waste_usd=115.2,
    )
    db_session.add(finding)
    db_session.commit()

    carbon = estimate_carbon_savings_kg_for_waste_item(db_session, org.id, finding.id)

    assert carbon == 0.0227