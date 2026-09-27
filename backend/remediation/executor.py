"""
Dry-run remediation executor.

Roadmap expects an Actions layer that executes corrective actions safely.
For now, we only do dry-run execution and write:
  - recommendations.status updates
  - audit_logs rows for traceability
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime

from sqlalchemy.orm import Session

from backend.db import models
from backend.remediation.policy_engine import can_approve_in_production, decision_for_recommendation


def _dry_run_result(action: str, resource_id: str | None) -> str:
    rid = resource_id or "resource"
    return f"[DRY RUN] Would execute action='{action}' on resource_id='{rid}'"


class RemediationExecutionError(RuntimeError):
    """Raised when a remediation cannot be safely executed by a real adapter."""


def _execute_action(*, action: str, resource_id: str | None, context_json: str | None) -> str:
    if os.getenv("REMEDIATION_ENABLED", "false").lower() != "true":
        raise RemediationExecutionError("Real remediation is disabled; set REMEDIATION_ENABLED=true after configuring cloud access")

    normalized_action = re.sub(r"[^a-z0-9]+", " ", (action or "").lower()).strip()
    is_stop = normalized_action in {"stop", "stop instance", "stop resource", "stop ec2 instance"} or any(
        phrase in normalized_action for phrase in ("shut down", "shutdown", "stop instance")
    )
    if not is_stop:
        raise RemediationExecutionError("Unsupported action; only stopping an AWS EC2 instance is currently supported")
    if not resource_id or not re.fullmatch(r"i-[0-9a-fA-F]{8,17}", resource_id):
        raise RemediationExecutionError("Resource is not a valid AWS EC2 instance ID")
    allowed_ids = {
        value.strip()
        for value in os.getenv("REMEDIATION_ALLOWED_INSTANCE_IDS", "").split(",")
        if value.strip()
    }
    if resource_id not in allowed_ids:
        raise RemediationExecutionError("Instance ID is not present in REMEDIATION_ALLOWED_INSTANCE_IDS")

    try:
        import boto3
    except ImportError as exc:
        raise RemediationExecutionError("boto3 is required for AWS EC2 remediation") from exc

    context = {}
    if context_json:
        try:
            context = json.loads(context_json)
        except json.JSONDecodeError:
            context = {}
    region = context.get("region") or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    if not region:
        raise RemediationExecutionError("AWS_REGION or AWS_DEFAULT_REGION must be configured")

    try:
        client = boto3.client("ec2", region_name=region)
        current = client.describe_instances(InstanceIds=[resource_id])
        instances = [instance for reservation in current.get("Reservations", []) for instance in reservation.get("Instances", [])]
        if not instances:
            raise RemediationExecutionError("AWS could not find the configured EC2 instance")
        state = instances[0].get("State", {}).get("Name")
        if state == "stopped":
            return f"AWS EC2 instance {resource_id} is already stopped in {region}"
        response = client.stop_instances(InstanceIds=[resource_id])
    except Exception as exc:
        if isinstance(exc, RemediationExecutionError):
            raise
        raise RemediationExecutionError(f"AWS EC2 stop request failed: {exc}") from exc

    states = response.get("StoppingInstances", [])
    if not states:
        raise RemediationExecutionError("AWS returned no stopping-instance confirmation")
    try:
        client.get_waiter("instance_stopped").wait(
            InstanceIds=[resource_id],
            WaiterConfig={"Delay": 5, "MaxAttempts": 60},
        )
    except Exception as exc:
        raise RemediationExecutionError(f"AWS did not confirm the instance stopped: {exc}") from exc
    return f"AWS EC2 instance {resource_id} stopped and confirmed in {region}"


def process_recommendations(
    *,
    db: Session,
    org_id: str,
    recommendation_ids: list[str],
    user_role: str | None,
    dry_run: bool = True,
) -> list[dict]:
    """
    For each recommendation:
      - if production => pending_approval
    - else => dry_run, denied, failed, or executed after adapter confirmation
    Writes audit logs and returns per-recommendation outcomes.
    """
    if not recommendation_ids:
        return []

    rows = (
        db.query(models.Recommendation)
        .filter(
            models.Recommendation.org_id == org_id,
            models.Recommendation.id.in_(recommendation_ids),
            models.Recommendation.status == "pending",
        )
        .all()
    )

    outcomes: list[dict] = []
    for rec in rows:
        decision = decision_for_recommendation(environment=rec.environment, user_role=user_role)

        previous_status = rec.status
        new_status = rec.status
        audit_action = rec.suggested_action or rec.action
        result_text: str

        if decision == "pending_approval":
            new_status = "pending_approval"
            result_text = "REQUIRES_APPROVAL: dry-run policy gate"
        elif decision == "denied":
            new_status = "denied"
            result_text = "DENIED: caller role is not permitted to execute remediation"
        elif dry_run:
            new_status = "dry_run"
            result_text = _dry_run_result(action=audit_action, resource_id=rec.resource_id)
        else:
            try:
                result_text = _execute_action(
                    action=audit_action,
                    resource_id=rec.resource_id,
                    context_json=rec.context_json,
                )
                new_status = "executed"
            except RemediationExecutionError as exc:
                new_status = "failed"
                result_text = f"FAILED: {exc}"

        rec.status = new_status

        db.add(
            models.AuditLog(
                org_id=org_id,
                recommendation_id=rec.id,
                action_taken=audit_action,
                result=result_text,
                executed_by=user_role or "system",
                executed_at=datetime.utcnow(),
            )
        )

        outcomes.append(
            {
                "recommendation_id": rec.id,
                "previous_status": previous_status,
                "new_status": new_status,
                "result": result_text,
            }
        )

    db.commit()
    return outcomes


def approve_and_execute(
    *,
    db: Session,
    org_id: str,
    recommendation_ids: list[str],
    user_role: str | None,
    dry_run: bool = True,
) -> list[dict]:
    """Approve pending production recommendations and mark them executed (dry-run)."""
    if not recommendation_ids:
        return []

    can_approve = can_approve_in_production(user_role=user_role)
    rows = (
        db.query(models.Recommendation)
        .filter(models.Recommendation.org_id == org_id, models.Recommendation.id.in_(recommendation_ids))
        .all()
    )

    outcomes: list[dict] = []
    for rec in rows:
        if rec.status != "pending_approval":
            outcomes.append(
                {
                    "recommendation_id": rec.id,
                    "new_status": rec.status,
                    "result": "SKIPPED: not in pending_approval",
                }
            )
            continue

        if not can_approve:
            rec.status = "denied"
            result_text = "DENIED: user_role not allowed to approve production"
        else:
            audit_action = rec.suggested_action or rec.action
            if dry_run:
                rec.status = "dry_run"
                result_text = _dry_run_result(action=audit_action, resource_id=rec.resource_id)
            else:
                try:
                    result_text = _execute_action(
                        action=audit_action,
                        resource_id=rec.resource_id,
                        context_json=rec.context_json,
                    )
                    rec.status = "executed"
                except RemediationExecutionError as exc:
                    rec.status = "failed"
                    result_text = f"FAILED: {exc}"

        db.add(
            models.AuditLog(
                org_id=org_id,
                recommendation_id=rec.id,
                action_taken=rec.suggested_action or rec.action,
                result=result_text,
                executed_by=user_role or "system",
                executed_at=datetime.utcnow(),
            )
        )

        outcomes.append(
            {
                "recommendation_id": rec.id,
                "new_status": rec.status,
                "result": result_text,
            }
        )

    db.commit()
    return outcomes

