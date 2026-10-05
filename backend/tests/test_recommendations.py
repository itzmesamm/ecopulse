import json
import sys
from types import SimpleNamespace

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from backend.db import models
from backend.api.remediation import get_remediation_actor
from backend.main import app


@pytest.fixture
def client():
    async def test_actor(request: Request):
        if request.method == "GET":
            org_id = request.query_params.get("org_id")
        else:
            body = await request.json()
            org_id = body.get("org_id") or request.query_params.get("org_id")
        return SimpleNamespace(id="test-user", org_id=org_id, role="admin")

    app.dependency_overrides[get_remediation_actor] = test_actor
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_remediation_actor_override():
    yield
    app.dependency_overrides.pop(get_remediation_actor, None)


def test_generate_recommendations_returns_fallback_payload(client, db_session, monkeypatch):
    from backend.services import recommendation_service

    monkeypatch.setattr(recommendation_service, "generate_recommendation", lambda *args: None)
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


def _create_recommendation(db_session, org, *, environment="development"):
    recommendation = models.Recommendation(
        org_id=org.id,
        environment=environment,
        title="Right-size test resource",
        summary="Resource usage is low.",
        action="Reduce instance size",
        suggested_action="Reduce instance size",
        status="pending",
    )
    db_session.add(recommendation)
    db_session.commit()
    db_session.refresh(recommendation)
    return recommendation


def test_dry_run_remediation_is_saved_as_simulated(client, db_session):
    org = models.Organization(name="Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    recommendation = _create_recommendation(db_session, org)

    response = client.post(
        "/remediation/process",
        json={
            "org_id": org.id,
            "recommendation_ids": [recommendation.id],
            "user_role": "viewer",
            "dry_run": True,
        },
    )

    assert response.status_code == 200
    outcome = response.json()["outcomes"][0]
    assert outcome["new_status"] == "simulated"
    assert "[DRY RUN]" in outcome["result"]
    db_session.refresh(recommendation)
    assert recommendation.status == "simulated"


def test_live_remediation_is_rejected_without_cloud_adapter(client, db_session):
    org = models.Organization(name="Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    recommendation = _create_recommendation(db_session, org)

    response = client.post(
        "/remediation/process",
        json={
            "org_id": org.id,
            "recommendation_ids": [recommendation.id],
            "user_role": "admin",
            "dry_run": False,
        },
    )

    assert response.status_code == 403
    assert "only available through production approval" in response.json()["detail"]
    db_session.refresh(recommendation)
    assert recommendation.status == "pending"


def test_only_admin_can_request_live_approval(client, db_session):
    org = models.Organization(name="Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    recommendation = _create_recommendation(db_session, org, environment="production")
    recommendation.status = "pending_approval"
    db_session.commit()
    app.dependency_overrides[get_remediation_actor] = lambda: SimpleNamespace(
        id="approver-user", org_id=org.id, role="approver"
    )

    response = client.post(
        "/remediation/approve",
        json={"org_id": org.id, "recommendation_ids": [recommendation.id], "user_role": "admin", "dry_run": False},
    )

    assert response.status_code == 403
    db_session.refresh(recommendation)
    assert recommendation.status == "pending_approval"


def test_live_approval_requires_server_confirmation(client, db_session):
    org = models.Organization(name="Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    recommendation = _create_recommendation(db_session, org, environment="production")
    recommendation.resource_id = "i-12345678"
    recommendation.status = "pending_approval"
    db_session.commit()

    response = client.post(
        "/remediation/approve",
        json={"org_id": org.id, "recommendation_ids": [recommendation.id], "dry_run": False},
    )

    assert response.status_code == 422
    assert "Typed confirmation is required" in response.json()["detail"]
    assert db_session.query(models.AuditLog).filter_by(recommendation_id=recommendation.id).count() == 0


def test_admin_live_approval_calls_adapter_and_audits_actor(client, db_session, monkeypatch):
    from backend.remediation import executor

    org = models.Organization(name="Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    recommendation = _create_recommendation(db_session, org, environment="production")
    recommendation.resource_id = "i-12345678"
    recommendation.service = "ec2"
    recommendation.action = "Stop idle instance"
    recommendation.suggested_action = "Stop idle instance"
    recommendation.status = "pending_approval"
    db_session.commit()
    monkeypatch.setattr(
        executor,
        "stop_tagged_ec2_instance",
        lambda **kwargs: "[EXECUTED] Stopped EC2 instance i-12345678 in us-east-1.",
    )

    response = client.post(
        "/remediation/approve",
        json={
            "org_id": org.id,
            "recommendation_ids": [recommendation.id],
            "dry_run": False,
            "confirmations": {recommendation.id: "STOP i-12345678"},
        },
    )

    assert response.status_code == 200
    outcome = response.json()["outcomes"][0]
    assert outcome["new_status"] == "executed"
    assert "[EXECUTED]" in outcome["result"]
    audit = db_session.query(models.AuditLog).filter_by(recommendation_id=recommendation.id).one()
    assert audit.executed_by == "test-user"


def test_admin_can_confirm_live_stop_for_pending_sandbox_recommendation(client, db_session, monkeypatch):
    from backend.remediation import executor

    org = models.Organization(name="Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    recommendation = _create_recommendation(db_session, org, environment="development")
    recommendation.resource_id = "i-12345678"
    recommendation.service = "ec2"
    recommendation.action = "Stop idle EC2 instance"
    recommendation.suggested_action = "Stop idle EC2 instance"
    db_session.commit()
    monkeypatch.setattr(
        executor,
        "stop_tagged_ec2_instance",
        lambda **kwargs: "[EXECUTED] Stopped EC2 instance i-12345678 in us-east-1.",
    )

    response = client.post(
        "/remediation/approve",
        json={
            "org_id": org.id,
            "recommendation_ids": [recommendation.id],
            "dry_run": False,
            "confirmations": {recommendation.id: "STOP i-12345678"},
        },
    )

    assert response.status_code == 200
    assert response.json()["outcomes"][0]["new_status"] == "executed"


def test_aws_onboarding_verifies_and_encrypts_credentials(client, db_session, monkeypatch):
    from cryptography.fernet import Fernet

    from backend.remediation.cloud_credentials import decrypt_cloud_credentials

    class MockSts:
        def get_caller_identity(self):
            return {"Account": "123456789012"}

    class MockSession:
        def __init__(self, **kwargs):
            self.credentials = kwargs

        def client(self, service, **kwargs):
            assert service == "sts"
            return MockSts()

    monkeypatch.setenv("CLOUD_CREDENTIALS_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(Session=MockSession))
    org = models.Organization(name="Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    response = client.post(
        f"/auth/onboarding/connect?provider=aws&org_id={org.id}",
        json={"provider": "aws", "credentials": {
            "access_key_id": "AKIA" + "A" * 16,
            "secret_access_key": "s" * 40,
            "region": "us-east-1",
        }},
    )

    assert response.status_code == 200
    assert response.json()["account_id"] == "123456789012"
    provider = db_session.query(models.CloudProvider).filter_by(org_id=org.id).one()
    assert provider.credentials_encrypted != json.dumps({"secret_access_key": "s" * 40})
    assert decrypt_cloud_credentials(provider.credentials_encrypted)["secret_access_key"] == "s" * 40


def test_aws_adapter_stops_only_tagged_running_instance(db_session, monkeypatch):
    from cryptography.fernet import Fernet

    from backend.remediation.aws_executor import stop_tagged_ec2_instance
    from backend.remediation.cloud_credentials import encrypt_cloud_credentials

    stopped = []

    class MockEc2:
        def describe_instances(self, InstanceIds):
            return {"Reservations": [{"Instances": [{
                "InstanceId": InstanceIds[0],
                "State": {"Name": "running"},
                "Tags": [{"Key": "EcoPulseAutomation", "Value": "enabled"}],
            }]}]}

        def stop_instances(self, InstanceIds):
            stopped.extend(InstanceIds)

    class MockSession:
        def __init__(self, **kwargs):
            pass

        def client(self, service, **kwargs):
            if service == "sts":
                return SimpleNamespace(get_caller_identity=lambda: {"Account": "123456789012"})
            assert service == "ec2"
            return MockEc2()

    monkeypatch.setenv("CLOUD_CREDENTIALS_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(Session=MockSession))
    org = models.Organization(name="Test Org")
    db_session.add(org)
    db_session.flush()
    db_session.add(models.CloudProvider(
        org_id=org.id,
        provider_type="aws",
        is_connected=True,
        credentials_encrypted=encrypt_cloud_credentials({
            "access_key_id": "AKIA" + "A" * 16,
            "secret_access_key": "s" * 40,
            "region": "us-east-1",
            "account_id": "123456789012",
        }),
    ))
    recommendation = models.Recommendation(
        org_id=org.id,
        resource_id="i-12345678",
        service="ec2",
        environment="production",
        title="Stop idle instance",
        summary="Low utilization",
        action="Stop idle EC2 instance",
        suggested_action="Stop idle EC2 instance",
        context_json=json.dumps({"region": "us-east-1"}),
    )
    db_session.add(recommendation)
    db_session.commit()

    result = stop_tagged_ec2_instance(db=db_session, org_id=org.id, recommendation=recommendation)

    assert result == "[EXECUTED] Stopped EC2 instance i-12345678 in us-east-1."
    assert stopped == ["i-12345678"]


def test_aws_adapter_rejects_noncanonical_action(db_session):
    from backend.remediation.aws_executor import stop_tagged_ec2_instance

    recommendation = models.Recommendation(
        org_id="org-1",
        resource_id="i-12345678",
        service="ec2",
        environment="production",
        title="Keep instance online",
        summary="The recommendation text contains a negated stop instruction.",
        action="Do not stop this idle EC2 instance",
        suggested_action="Do not stop this idle EC2 instance",
    )

    with pytest.raises(RuntimeError, match="exact supported action"):
        stop_tagged_ec2_instance(db=db_session, org_id="org-1", recommendation=recommendation)


def test_remediation_rejects_caller_supplied_role(client, db_session):
    org = models.Organization(name="Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    recommendation = _create_recommendation(db_session, org, environment="production")
    recommendation.status = "pending_approval"
    db_session.commit()
    app.dependency_overrides[get_remediation_actor] = lambda: SimpleNamespace(
        id="viewer-user", org_id=org.id, role="viewer"
    )

    response = client.post(
        "/remediation/approve",
        json={
            "org_id": org.id,
            "recommendation_ids": [recommendation.id],
            "user_role": "admin",
            "dry_run": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["outcomes"][0]["new_status"] == "denied"


def test_remediation_cannot_access_another_organization(client, db_session):
    org = models.Organization(name="Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    app.dependency_overrides[get_remediation_actor] = lambda: SimpleNamespace(
        id="other-user", org_id="another-org", role="admin"
    )

    response = client.post(
        "/remediation/plan",
        json={"org_id": org.id, "recommendation_ids": ["missing"]},
    )

    assert response.status_code == 403


def test_automation_plan_is_persisted_and_resource_specific(client, db_session):
    org = models.Organization(name="Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    recommendation = _create_recommendation(db_session, org)
    recommendation.service = "kubernetes"
    recommendation.resource_id = "staging-api"
    recommendation.dollar_savings = 84.5
    db_session.commit()

    response = client.post(
        "/remediation/plan",
        json={"org_id": org.id, "recommendation_ids": [recommendation.id], "user_role": "admin"},
    )

    assert response.status_code == 200
    plan = response.json()["outcomes"][0]["plan"]
    assert plan["strategy"] == "Kubernetes resource right-sizing"
    assert plan["resource_id"] == "staging-api"
    assert plan["estimated_monthly_savings_usd"] == 84.5
    assert plan["live_execution_available"] is False
    assert "previous resource configuration" in plan["rollback"]
    audit = db_session.query(models.AuditLog).filter_by(recommendation_id=recommendation.id).one()
    assert audit.action_taken == "automation_plan_created"
    assert json.loads(audit.result)["strategy"] == plan["strategy"]
    history_response = client.get(f"/remediation/history?org_id={org.id}")
    assert history_response.status_code == 200
    assert history_response.json()["plans"][0]["plan"]["strategy"] == plan["strategy"]
    db_session.refresh(recommendation)
    assert recommendation.status == "pending"


def test_production_remediation_requires_approval_then_simulates(client, db_session):
    org = models.Organization(name="Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    recommendation = _create_recommendation(db_session, org, environment="production")

    process_response = client.post(
        "/remediation/process",
        json={"org_id": org.id, "recommendation_ids": [recommendation.id], "dry_run": True},
    )
    assert process_response.status_code == 200
    assert process_response.json()["outcomes"][0]["new_status"] == "pending_approval"

    approve_response = client.post(
        "/remediation/approve",
        json={
            "org_id": org.id,
            "recommendation_ids": [recommendation.id],
            "user_role": "admin",
            "dry_run": True,
        },
    )
    assert approve_response.status_code == 200
    outcome = approve_response.json()["outcomes"][0]
    assert outcome["new_status"] == "simulated"
    assert "[DRY RUN]" in outcome["result"]


def test_dismiss_recommendation_updates_its_status(client, db_session):
    org = models.Organization(name="Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    recommendation = _create_recommendation(db_session, org)

    response = client.post(
        f"/recommendations/{recommendation.id}/dismiss",
        json={"org_id": org.id},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_generation_keeps_ai_results_when_one_finding_falls_back(monkeypatch):
    from backend.services import recommendation_service

    findings = [
        {
            "resource_id": "resource-ai",
            "service": "compute",
            "environment": "development",
            "severity_score": 0.8,
            "estimated_monthly_waste_usd": 100.0,
        },
        {
            "resource_id": "resource-fallback",
            "service": "compute",
            "environment": "development",
            "severity_score": 0.7,
            "estimated_monthly_waste_usd": 50.0,
            "waste_type": "low_utilization",
        },
    ]
    results = iter([
        {
            "explanation": "Model-grounded explanation.",
            "dollar_savings": 800.0,
            "confidence": 0.9,
            "suggested_action": "Right-size this resource.",
        },
        None,
    ])
    monkeypatch.setattr(recommendation_service, "generate_recommendation", lambda *args: next(results))

    generated = recommendation_service._generate_ai_recommendations(None, "org-1", findings)

    assert generated[0]["summary"] == "Model-grounded explanation."
    assert generated[0]["dollar_savings"] == 100.0
    assert generated[0]["estimated_savings_usd"] == 100.0
    assert generated[1]["resource_id"] == "resource-fallback"
    assert "low utilization" in generated[1]["summary"]


def test_generation_passes_user_focus_to_ai(monkeypatch):
    from backend.services import recommendation_service

    received = {}

    def generate(*args, user_question=None):
        received["question"] = user_question
        return None

    monkeypatch.setattr(recommendation_service, "generate_recommendation", generate)
    recommendation_service._generate_ai_recommendations(
        None,
        "org-1",
        [{"resource_id": "gpu-1", "service": "gpu"}],
        user_question="Recommend queue-aware GPU scheduling.",
    )

    assert received["question"] == "Recommend queue-aware GPU scheduling."


def test_context_skips_findings_with_existing_recommendations(db_session):
    from backend.services.recommendation_service import _build_recommendation_context

    org = models.Organization(name="Test Org")
    db_session.add(org)
    db_session.flush()
    first = models.WasteItem(
        org_id=org.id,
        billing_record_id="billing-1",
        resource_id="already-covered",
        service="compute",
        waste_type="low_utilization",
        severity_score=0.9,
        estimated_monthly_waste_usd=100.0,
    )
    second = models.WasteItem(
        org_id=org.id,
        billing_record_id="billing-2",
        resource_id="new-finding",
        service="compute",
        waste_type="low_utilization",
        severity_score=0.8,
        estimated_monthly_waste_usd=80.0,
    )
    db_session.add_all([first, second])
    db_session.flush()
    db_session.add(
        models.Recommendation(
            org_id=org.id,
            waste_finding_id=first.id,
            title="Existing recommendation",
            summary="Already covered.",
            action="Review",
        )
    )
    db_session.commit()

    context = _build_recommendation_context(db_session, org.id, limit=5)

    assert [finding["resource_id"] for finding in context] == ["new-finding"]
