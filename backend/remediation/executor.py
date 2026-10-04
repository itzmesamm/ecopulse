"""
Dry-run remediation executor.

Roadmap expects an Actions layer that executes corrective actions safely.
For now, we only do dry-run execution and write:
  - recommendations.status updates
  - audit_logs rows for traceability
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from backend.db import models
from backend.remediation.action_catalog import resolve_live_action_code
from backend.remediation.aws_executor import stop_tagged_ec2_instance
from backend.remediation.policy_engine import can_approve_in_production, decision_for_recommendation


def _dry_run_result(action: str, resource_id: str | None) -> str:
    rid = resource_id or "resource"
    return f"[DRY RUN] Would execute action='{action}' on resource_id='{rid}'"


def build_automation_plan(recommendation: models.Recommendation) -> dict:
    """Create a provider-neutral, non-executable automation plan."""
    service = (recommendation.service or recommendation.source_type or "").lower()
    action = recommendation.suggested_action or recommendation.action or "Review resource"

    if any(term in service for term in ("gpu", "accelerator")):
        strategy = "GPU utilization scheduling"
        steps = [
            "Verify GPU utilization, power draw, and queued jobs over the observation window.",
            f"Prepare a queue-aware schedule or right-sizing proposal for {recommendation.resource_id or 'the GPU resource'}.",
            "Run a dry-run and validate workload availability before an authorized change.",
        ]
        safety_checks = ["Never interrupt a running or queued workload.", "Require an approver before changing a production GPU."]
    elif any(term in service for term in ("kubernetes", "k8s", "container")):
        strategy = "Kubernetes resource right-sizing"
        steps = [
            "Review historical CPU and memory use, restarts, and availability targets.",
            f"Stage the proposed resource change: {action}.",
            "Apply as a staged rollout only after dry-run validation and health checks.",
        ]
        safety_checks = ["Respect minimum replica and availability budgets.", "Rollback if readiness or error-rate checks regress."]
    elif any(term in service for term in ("storage", "volume", "ebs", "s3")):
        strategy = "Storage lifecycle optimization"
        steps = [
            "Confirm attachment state, recent reads/writes, retention rules, and ownership.",
            f"Prepare the proposed storage change: {action}.",
            "Require a recoverability check and explicit approval before any deletion.",
        ]
        safety_checks = ["Never delete an attached or recently accessed resource.", "Require a recoverable snapshot before destructive changes."]
    else:
        strategy = "Compute utilization right-sizing"
        steps = [
            "Compare sustained CPU, memory, and network use against the resource's current capacity.",
            f"Stage a sizing or schedule proposal: {action}.",
            "Run a dry-run and verify service health before an authorized rollout.",
        ]
        safety_checks = ["Do not change production without an authorized approver.", "Retain the current configuration for rollback."]

    return {
        "strategy": strategy,
        "resource_id": recommendation.resource_id,
        "service": recommendation.service,
        "environment": recommendation.environment or "unknown",
        "requested_action": action,
        "steps": steps,
        "safety_checks": safety_checks,
        "rollback": (
            "An operator can restart the same EC2 instance with StartInstances after confirming workload ownership, "
            "then verify service health. No automatic rollback is performed."
            if resolve_live_action_code(action) == "aws.ec2.stop"
            else "Restore the previous resource configuration and re-run health checks."
        ),
        "estimated_monthly_savings_usd": float(recommendation.dollar_savings or recommendation.estimated_savings_usd or 0.0),
        "execution_mode": "dry_run_only",
        "live_execution_available": False,
    }


def prepare_automation_plans(
    *, db: Session, org_id: str, recommendation_ids: list[str], actor: str | None,
) -> list[dict]:
    rows = (
        db.query(models.Recommendation)
        .filter(models.Recommendation.org_id == org_id, models.Recommendation.id.in_(recommendation_ids))
        .all()
    )
    by_id = {row.id: row for row in rows}
    outcomes = []
    for recommendation_id in recommendation_ids:
        rec = by_id.get(recommendation_id)
        if rec is None:
            outcomes.append({"recommendation_id": recommendation_id, "error": "Recommendation not found"})
            continue
        plan = build_automation_plan(rec)
        db.add(models.AuditLog(
            org_id=org_id,
            recommendation_id=rec.id,
            action_taken="automation_plan_created",
            result=json.dumps(plan),
            executed_by=actor or "system",
            executed_at=datetime.utcnow(),
        ))
        outcomes.append({"recommendation_id": rec.id, "status": rec.status, "plan": plan})
    db.commit()
    return outcomes


def process_recommendations(
    *,
    db: Session,
    org_id: str,
    recommendation_ids: list[str],
    user_role: str | None,
    dry_run: bool = True,
    actor_id: str | None = None,
) -> list[dict]:
    """
        For each recommendation:
            - if production => pending_approval
            - else => simulated, unless an authorized live run was explicitly requested
    Writes audit logs and returns per-recommendation outcomes.
    """
    if not recommendation_ids:
        return []
    if not dry_run:
        raise RuntimeError("Live execution is only available through production approval.")

    rows = (
        db.query(models.Recommendation)
        .filter(models.Recommendation.org_id == org_id, models.Recommendation.id.in_(recommendation_ids))
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
            result_text = "REQUIRES_APPROVAL: production change was not run."
        elif dry_run:
            new_status = "simulated"
            result_text = _dry_run_result(action=audit_action, resource_id=rec.resource_id)
        rec.status = new_status

        db.add(
            models.AuditLog(
                org_id=org_id,
                recommendation_id=rec.id,
                action_taken=audit_action,
                result=result_text,
                executed_by=actor_id or user_role or "system",
                executed_at=datetime.utcnow(),
            )
        )

        outcomes.append(
            {
                "recommendation_id": rec.id,
                "previous_status": previous_status,
                "new_status": new_status,
                "result": result_text,
                "automation_plan": build_automation_plan(rec),
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
    actor_id: str | None = None,
) -> list[dict]:
    """Approve pending production recommendations; execute only via a configured provider adapter."""
    if not recommendation_ids:
        return []
    if not dry_run and str(user_role or "").lower() != "admin":
        raise RuntimeError("Live remediation requires an admin role.")

    can_approve = can_approve_in_production(user_role=user_role)
    rows = (
        db.query(models.Recommendation)
        .filter(models.Recommendation.org_id == org_id, models.Recommendation.id.in_(recommendation_ids))
        .all()
    )

    outcomes: list[dict] = []
    for rec in rows:
        if rec.status != "pending_approval" and not (not dry_run and rec.status == "pending"):
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
                rec.status = "simulated"
                result_text = _dry_run_result(action=audit_action, resource_id=rec.resource_id)
            else:
                try:
                    result_text = stop_tagged_ec2_instance(db=db, org_id=org_id, recommendation=rec)
                    rec.status = "executed"
                except RuntimeError as exc:
                    rec.status = "failed"
                    result_text = f"[FAILED] {exc}"

        db.add(
            models.AuditLog(
                org_id=org_id,
                recommendation_id=rec.id,
                action_taken=rec.suggested_action or rec.action,
                result=result_text,
                executed_by=actor_id or user_role or "system",
                executed_at=datetime.utcnow(),
            )
        )

        outcomes.append(
            {
                "recommendation_id": rec.id,
                "new_status": rec.status,
                "result": result_text,
                "automation_plan": build_automation_plan(rec),
            }
        )

    db.commit()
    return outcomes

