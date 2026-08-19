"""
Policy engine (minimal implementation).

Roadmap goal: keep production safe by requiring approval for production
resources, while allowing auto-execution in sandbox/dev.

This backend already stores `Recommendation.environment`, so we use that
as the primary approval gate.
"""

from __future__ import annotations


def requires_approval(environment: str | None) -> bool:
    """Production resources require human approval."""
    return (environment or "").lower() == "production"


def decision_for_recommendation(*, environment: str | None, user_role: str | None) -> str:
    """
    Returns:
      - 'executed' (auto-approved)
      - 'pending_approval'
      - 'denied'
    """
    # For minimal dry-run integration:
    # - Production always requires approval gate (pending_approval).
    # - Non-production can be executed (dry-run).
    if requires_approval(environment):
        return "pending_approval"

    # Non-prod execution is allowed regardless of role in this minimal model.
    # Later you can gate based on resource tags / IAM.
    _ = user_role
    return "executed"


def can_approve_in_production(*, user_role: str | None) -> bool:
    """Allowed roles to approve production actions."""
    role = (user_role or "").lower()
    return role in {"admin", "approver"}

