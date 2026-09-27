import pytest
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.remediation.executor import process_recommendations
from backend.db import models
from backend.remediation.policy_engine import decision_for_recommendation, requires_approval


@pytest.mark.parametrize("environment", [None, "", "production", "prod", "staging", "unknown"])
def test_non_explicit_nonproduction_requires_approval(environment):
    assert requires_approval(environment) is True
    assert decision_for_recommendation(environment=environment, user_role="admin") == "pending_approval"


@pytest.mark.parametrize("environment", ["sandbox", "development", "dev", "test"])
def test_explicit_nonproduction_requires_an_authorized_role(environment):
    assert requires_approval(environment) is False
    assert decision_for_recommendation(environment=environment, user_role="admin") == "executed"
    assert decision_for_recommendation(environment=environment, user_role="viewer") == "denied"


def test_allowlisted_sandbox_ec2_stop_waits_for_confirmation(db_session, monkeypatch):
    org = models.Organization(name="AWS remediation test")
    db_session.add(org)
    db_session.flush()
    recommendation = models.Recommendation(
        org_id=org.id,
        resource_id="i-0123456789abcdef0",
        service="ec2",
        environment="sandbox",
        title="Stop sandbox instance",
        summary="Idle",
        action="Stop instance",
        suggested_action="Stop instance",
        status="pending",
        context_json='{"region":"us-east-1"}',
    )
    db_session.add(recommendation)
    db_session.commit()

    ec2 = MagicMock()
    ec2.describe_instances.return_value = {
        "Reservations": [{"Instances": [{"State": {"Name": "running"}}]}]
    }
    ec2.stop_instances.return_value = {
        "StoppingInstances": [{"CurrentState": {"Name": "stopping"}}]
    }
    client = MagicMock(return_value=ec2)
    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=client))
    monkeypatch.setenv("REMEDIATION_ENABLED", "true")
    monkeypatch.setenv("REMEDIATION_ALLOWED_INSTANCE_IDS", recommendation.resource_id)

    outcomes = process_recommendations(
        db=db_session,
        org_id=org.id,
        recommendation_ids=[recommendation.id],
        user_role="admin",
        dry_run=False,
    )

    assert outcomes[0]["new_status"] == "executed"
    ec2.stop_instances.assert_called_once_with(InstanceIds=[recommendation.resource_id])
    ec2.get_waiter.assert_called_once_with("instance_stopped")