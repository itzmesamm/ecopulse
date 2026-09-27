"""
Policy engine (minimal implementation).

Roadmap goal: keep production safe by requiring approval for production
resources, while allowing auto-execution in sandbox/dev.

This backend already stores `Recommendation.environment`, so we use that
as the primary approval gate.
"""

from __future__ import annotations


def requires_approval(environment: str | None) -> bool:
    """Only explicitly non-production environments can be auto-approved."""
    normalized = (environment or "").strip().lower()
    return normalized not in {"sandbox", "development", "dev", "test"}


def decision_for_recommendation(*, environment: str | None, user_role: str | None) -> str:
    """
    Returns:
      - 'executed' (auto-approved)
      - 'pending_approval'
      - 'denied'
    """
    if requires_approval(environment):
        return "pending_approval"

    role = (user_role or "").lower()
    if role in {"admin", "approver", "system"}:
        return "executed"
    return "denied"


def can_approve_in_production(*, user_role: str | None) -> bool:
    """Allowed roles to approve production actions."""
    role = (user_role or "").lower()
    return role in {"admin", "approver"}

