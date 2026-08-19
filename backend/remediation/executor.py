"""
Dry-run remediation executor.

Roadmap expects an Actions layer that executes corrective actions safely.
For now, we only do dry-run execution and write:
  - recommendations.status updates
  - audit_logs rows for traceability
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from backend.db import models
from backend.remediation.policy_engine import can_approve_in_production, decision_for_recommendation


def _dry_run_result(action: str, resource_id: str | None) -> str:
    rid = resource_id or "resource"
    return f"[DRY RUN] Would execute action='{action}' on resource_id='{rid}'"


def _real_execution_result(action: str, resource_id: str | None) -> str:
    rid = resource_id or "resource"
    return f"[EXECUTED] Action='{action}' executed on resource_id='{rid}' (webhook/mock)"


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
      - else => executed
    Writes audit logs and returns per-recommendation outcomes.
    """
    if not recommendation_ids:
        return []

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
            result_text = "REQUIRES_APPROVAL: dry-run policy gate"
        else:
            new_status = "executed"
            if dry_run:
                result_text = _dry_run_result(action=audit_action, resource_id=rec.resource_id)
            else:
                result_text = _real_execution_result(action=audit_action, resource_id=rec.resource_id)

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
            rec.status = "executed"
            audit_action = rec.suggested_action or rec.action
            if dry_run:
                result_text = _dry_run_result(action=audit_action, resource_id=rec.resource_id)
            else:
                result_text = _real_execution_result(action=audit_action, resource_id=rec.resource_id)

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

