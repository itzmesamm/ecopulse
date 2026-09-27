import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.db import models
from backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_generate_recommendations_returns_fallback_payload(client, db_session):
    org = models.Organization(name="Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    db_session.add(
        models.BillingRecord(
            org_id=org.id,
            resource_id="res-1",
            service="ec2",
            region="us-east-1",
            environment="production",
            cost=250.0,
            usage_hours=1.2,
        )
    )
    db_session.add(
        models.WasteItem(
            org_id=org.id,
            billing_record_id="dummy-id",
            resource_id="res-1",
            service="ec2",
            region="us-east-1",
            environment="production",
            waste_type="low_utilization",
            severity_score=0.85,
            estimated_monthly_waste_usd=200.0,
            details="Low usage",
        )
    )
    db_session.commit()

    response = client.post(
        "/recommendations/generate",
        json={"org_id": org.id, "service": "ec2", "environment": "production", "limit": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["org_id"] == org.id
    assert payload["count"] >= 1
    assert len(payload["recommendations"]) >= 1
    assert payload["recommendations"][0]["title"]
    assert payload["recommendations"][0]["summary"]
