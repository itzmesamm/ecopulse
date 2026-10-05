from datetime import date

from backend.analysis.waste_analyzer import WasteAnalyzer
from backend.db import models
from backend.forecasting.aggregator import aggregate_daily_costs
from backend.ingestion.demo_dataset import build_demo_dataset
from backend.ingestion.persist import ingest_and_persist


def test_demo_dataset_is_stable_and_has_daily_history():
    first = build_demo_dataset("org-demo", as_of=date(2026, 10, 5))
    second = build_demo_dataset("org-demo", as_of=date(2026, 10, 5))

    assert first == second
    assert len(first["billing"]) == 30 * 6
    assert len(first["gpu"]) == 30 * 2
    assert len(first["k8s"]) == 30 * 4
    assert len(first["logs"]) == 14
    assert {item["period_days"] for item in first["billing"]} == {1}
    assert {item["resource_id"] for item in first["billing"]} == {
        "i-demo-ec2-idle",
        "i-demo-ec2-prod",
        "db-demo-rds-prod",
        "vol-demo-ebs-idle",
        "bucket-demo-s3-logs",
        "fn-demo-api",
    }


def test_demo_ingestion_is_idempotent_and_analytics_use_correct_periods(db_session):
    org = models.Organization(name="Demo Dataset Test")
    db_session.add(org)
    db_session.commit()

    first = ingest_and_persist(db_session, org.id)
    second = ingest_and_persist(db_session, org.id)

    assert first["data_mode"] == "synthetic_demo"
    assert first["dataset_version"] == "ecopulse-demo-v1"
    assert first["billing"] == 180
    assert second["billing"] == second["gpu"] == second["k8s"] == second["logs"] == 0
    assert db_session.query(models.BillingRecord).count() == 180

    today_costs = aggregate_daily_costs(db_session, org.id, date.today())
    assert today_costs
    assert all(item.total_cost_usd > 0 for item in today_costs)

    findings = WasteAnalyzer().analyze_records(db_session, org.id)
    idle_instance = next(item for item in findings if item.resource_id == "i-demo-ec2-idle")
    assert idle_instance.estimated_monthly_waste_usd > 100
    assert any(item.resource_id == "vol-demo-ebs-idle" for item in findings)