from backend.api.greenops import get_report
from backend.db import models


def test_report_totals_cover_all_executed_recommendations(db_session):
    org = models.Organization(name="GreenOps test")
    db_session.add(org)
    db_session.flush()
    db_session.add_all([
        models.Recommendation(
            org_id=org.id,
            resource_id="resource-1",
            title="one",
            summary="one",
            action="review",
            environment="staging",
            status="executed",
            dollar_savings=10,
            carbon_savings_kg=2,
        ),
        models.Recommendation(
            org_id=org.id,
            resource_id="resource-2",
            title="two",
            summary="two",
            action="review",
            environment="staging",
            status="executed",
            dollar_savings=20,
            carbon_savings_kg=None,
        ),
    ])
    db_session.commit()

    report = get_report(org_id=org.id, limit=1, db=db_session)

    assert report.executed_recommendations_count == 2
    assert report.total_dollar_savings_usd == 30
    assert report.total_carbon_savings_kg == 2
    assert report.carbon_estimate_coverage_pct == 50
    assert len(report.top_recommendations) == 1
    assert report.estimated_energy_kwh_saved is None
    assert "not verified" in report.savings_basis