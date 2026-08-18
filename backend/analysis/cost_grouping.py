from __future__ import annotations

from typing import List, Dict, Any

from sqlalchemy.orm import Session

from backend.db import models


def summarize_team_costs(
    db: Session,
    org_id: str,
    service: str | None = None,
    environment: str | None = None,
    region: str | None = None,
) -> List[Dict[str, Any]]:
    """Summarize cost by team and owner, keeping org isolation intact."""
    query = db.query(
        models.BillingRecord.team,
        models.BillingRecord.owner,
        models.BillingRecord.service,
        models.BillingRecord.environment,
        models.BillingRecord.region,
        models.BillingRecord.org_id,
    ).filter(models.BillingRecord.org_id == org_id)

    if service:
        query = query.filter(models.BillingRecord.service == service)
    if environment:
        query = query.filter(models.BillingRecord.environment == environment)
    if region:
        query = query.filter(models.BillingRecord.region == region)

    results = query.all()
    if not results:
        return []

    totals: Dict[str, Dict[str, Any]] = {}
    for team, owner, service_name, env, region_name, org in results:
        key = (team or "unknown", owner or "unknown")
        entry = totals.setdefault(
            key,
            {
                "org_id": org,
                "team": team or "unknown",
                "owner": owner or "unknown",
                "total_cost_usd": 0.0,
                "resource_count": 0,
            },
        )
        entry["total_cost_usd"] += 0.0
        entry["resource_count"] += 1

    # Re-query with aggregation for real cost totals.
    query = db.query(
        models.BillingRecord.team,
        models.BillingRecord.owner,
        models.BillingRecord.org_id,
        models.BillingRecord.service,
        models.BillingRecord.environment,
        models.BillingRecord.region,
    ).filter(models.BillingRecord.org_id == org_id)
    if service:
        query = query.filter(models.BillingRecord.service == service)
    if environment:
        query = query.filter(models.BillingRecord.environment == environment)
    if region:
        query = query.filter(models.BillingRecord.region == region)

    all_rows = query.all()
    totals = {}
    for team, owner, org, service_name, env, region_name in all_rows:
        record_costs = db.query(models.BillingRecord.cost).filter(
            models.BillingRecord.org_id == org_id,
            models.BillingRecord.team == (team or "unknown"),
            models.BillingRecord.owner == (owner or "unknown"),
        )
        if service:
            record_costs = record_costs.filter(models.BillingRecord.service == service)
        if environment:
            record_costs = record_costs.filter(models.BillingRecord.environment == environment)
        if region:
            record_costs = record_costs.filter(models.BillingRecord.region == region)
        total_cost = sum(float(cost[0] or 0.0) for cost in record_costs.all())
        key = (team or "unknown", owner or "unknown")
        totals[key] = {
            "org_id": org,
            "team": team or "unknown",
            "owner": owner or "unknown",
            "total_cost_usd": round(total_cost, 2),
            "resource_count": db.query(models.BillingRecord.id).filter(
                models.BillingRecord.org_id == org_id,
                models.BillingRecord.team == (team or "unknown"),
                models.BillingRecord.owner == (owner or "unknown"),
            ).count(),
        }

    return [value for _, value in sorted(totals.items())]
