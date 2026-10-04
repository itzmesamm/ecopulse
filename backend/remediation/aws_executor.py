from __future__ import annotations

import json
import re

from sqlalchemy.orm import Session

from backend.db import models
from backend.remediation.action_catalog import resolve_live_action_code
from backend.remediation.cloud_credentials import decrypt_cloud_credentials

_EC2_INSTANCE_ID = re.compile(r"^i-[0-9a-f]{8,17}$")
_AUTOMATION_TAG = "EcoPulseAutomation"


def _aws_client(db: Session, org_id: str, recommendation: models.Recommendation):
    provider = (
        db.query(models.CloudProvider)
        .filter_by(org_id=org_id, provider_type="aws", is_connected=True)
        .first()
    )
    if provider is None:
        raise RuntimeError("No verified AWS account is connected to this organization")
    credentials = decrypt_cloud_credentials(provider.credentials_encrypted)
    if not all(credentials.get(key) for key in ("access_key_id", "secret_access_key", "region")):
        raise RuntimeError("Stored AWS credentials are incomplete; reconnect the account")
    try:
        context = json.loads(recommendation.context_json or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError("Recommendation context is invalid; regenerate the recommendation") from exc
    target_region = context.get("region")
    if not isinstance(target_region, str) or not re.fullmatch(r"[a-z]{2}(?:-gov)?-[a-z]+-\d", target_region):
        raise RuntimeError("Recommendation has no valid AWS region; regenerate it from regional billing data")
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("AWS SDK is unavailable; install the backend requirements and retry") from exc

    session = boto3.Session(
        aws_access_key_id=credentials["access_key_id"],
        aws_secret_access_key=credentials["secret_access_key"],
        aws_session_token=credentials.get("session_token"),
        region_name=credentials["region"],
    )
    try:
        identity = session.client("sts").get_caller_identity()
    except Exception as exc:
        raise RuntimeError(f"AWS account identity could not be verified: {exc}") from exc
    expected_account = credentials.get("account_id")
    if expected_account and identity.get("Account") != expected_account:
        raise RuntimeError("AWS account identity does not match the account verified at connection time")
    return session.client("ec2", region_name=target_region), target_region


def stop_tagged_ec2_instance(*, db: Session, org_id: str, recommendation: models.Recommendation) -> str:
    service = (recommendation.service or "").lower()
    action = recommendation.suggested_action or recommendation.action
    resource_id = recommendation.resource_id or ""
    if service not in {"ec2", "aws_ec2"} or not _EC2_INSTANCE_ID.fullmatch(resource_id):
        raise RuntimeError("Live automation supports only valid AWS EC2 instance IDs")
    if resolve_live_action_code(action) != "aws.ec2.stop":
        raise RuntimeError("Live EC2 stop requires the exact supported action 'Stop idle EC2 instance'")

    client, region = _aws_client(db, org_id, recommendation)
    try:
        response = client.describe_instances(InstanceIds=[resource_id])
    except Exception as exc:
        raise RuntimeError(f"AWS could not verify the EC2 instance: {exc}") from exc
    instances = [instance for reservation in response.get("Reservations", []) for instance in reservation.get("Instances", [])]
    if len(instances) != 1:
        raise RuntimeError("AWS did not return exactly one matching EC2 instance")
    instance = instances[0]
    tags = {tag.get("Key"): tag.get("Value") for tag in instance.get("Tags", [])}
    if tags.get(_AUTOMATION_TAG) != "enabled":
        raise RuntimeError(f"Instance must have the {_AUTOMATION_TAG}=enabled tag before it can be stopped")
    state = instance.get("State", {}).get("Name")
    if state != "running":
        raise RuntimeError(f"EC2 instance is '{state}', expected 'running'")

    try:
        client.stop_instances(InstanceIds=[resource_id])
    except Exception as exc:
        raise RuntimeError(f"AWS rejected the EC2 stop request: {exc}") from exc
    return f"[EXECUTED] Stopped EC2 instance {resource_id} in {region}."