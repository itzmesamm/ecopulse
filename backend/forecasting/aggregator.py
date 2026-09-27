"""
Cost Aggregation Module — Layer 3.

Aggregates BillingRecord data into daily cost snapshots grouped by
service, environment, and region. Provides reusable functions for
historical cost analysis and forecasting preparation.

No database writes; all aggregations are query-based.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.db import models


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class DailyCostAggregate:
    """Aggregated daily cost data for a specific dimension combination."""
    org_id: str
    cost_date: date
    service: Optional[str]
    environment: Optional[str]
    region: Optional[str]
    total_cost_usd: float
    resource_count: int


# ============================================================================
# Aggregation Functions
# ============================================================================

def aggregate_daily_costs(
    db: Session,
    org_id: str,
    cost_date: date,
    service: Optional[str] = None,
    environment: Optional[str] = None,
    region: Optional[str] = None,
) -> List[DailyCostAggregate]:
    """
    Aggregate billing records for a specific date and organization.
    
    Groups by (service, environment, region) and returns daily cost totals
    and resource counts for that date.
    
    Parameters:
        db: SQLAlchemy database session
        org_id: Organization ID (mandatory)
        cost_date: Date to aggregate (uses date(recorded_at))
        service: Optional filter by service (e.g., 'ec2', 'rds')
        environment: Optional filter by environment (e.g., 'production')
        region: Optional filter by region (e.g., 'us-east-1')
    
    Returns:
        List of DailyCostAggregate objects, one per (service, env, region) combination
    
    Example:
        >>> aggs = aggregate_daily_costs(db, 'org-123', date(2024, 8, 18))
        >>> for agg in aggs:
        ...     print(f"{agg.service}/{agg.environment}: ${agg.total_cost_usd}")
        ec2/production: $1234.56
        rds/production: $567.89
    """
    # Build base query
    query = db.query(models.BillingRecord).filter(
        models.BillingRecord.org_id == org_id,
        func.date(models.BillingRecord.recorded_at) == cost_date,
    )
    
    # Apply optional filters
    if service:
        query = query.filter(models.BillingRecord.service == service)
    if environment:
        query = query.filter(models.BillingRecord.environment == environment)
    if region:
        query = query.filter(models.BillingRecord.region == region)
    
    # Group and aggregate
    results = query.with_entities(
        models.BillingRecord.service,
        models.BillingRecord.environment,
        models.BillingRecord.region,
        func.sum(models.BillingRecord.cost).label('total_cost'),
        func.count(models.BillingRecord.id).label('resource_count'),
    ).group_by(
        models.BillingRecord.service,
        models.BillingRecord.environment,
        models.BillingRecord.region,
    ).all()
    
    # Convert to DailyCostAggregate objects
    aggregates = [
        DailyCostAggregate(
            org_id=org_id,
            cost_date=cost_date,
            service=r.service,
            environment=r.environment,
            region=r.region,
            total_cost_usd=round(float(r.total_cost or 0.0), 2),
            resource_count=int(r.resource_count or 0),
        )
        for r in results
    ]
    
    return aggregates


def aggregate_daily_costs_range(
    db: Session,
    org_id: str,
    start_date: date,
    end_date: date,
    service: Optional[str] = None,
    environment: Optional[str] = None,
    region: Optional[str] = None,
) -> List[DailyCostAggregate]:
    """
    Aggregate billing records for a date range and organization.
    
    Calls aggregate_daily_costs for each day in the range and returns
    combined results.
    
    Parameters:
        db: SQLAlchemy database session
        org_id: Organization ID (mandatory)
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        service: Optional filter by service
        environment: Optional filter by environment
        region: Optional filter by region
    
    Returns:
        List of DailyCostAggregate objects for all days in range
    
    Example:
        >>> aggs = aggregate_daily_costs_range(
        ...     db, 'org-123', date(2024, 8, 1), date(2024, 8, 31)
        ... )
        >>> len(aggs)  # Could be hundreds (31 days × multiple dimensions)
        342
    """
    aggregates = []
    current_date = start_date
    
    while current_date <= end_date:
        daily_aggs = aggregate_daily_costs(
            db,
            org_id,
            current_date,
            service=service,
            environment=environment,
            region=region,
        )
        aggregates.extend(daily_aggs)
        current_date += timedelta(days=1)
    
    return aggregates


def aggregate_daily_costs_summary(
    db: Session,
    org_id: str,
    cost_date: date,
) -> Dict[str, Any]:
    """
    Get a summary of daily costs for an organization on a specific date.
    
    Returns totals across all services/environments/regions.
    
    Parameters:
        db: SQLAlchemy database session
        org_id: Organization ID
        cost_date: Date to summarize
    
    Returns:
        Dict with keys:
            - total_cost_usd: Total cost for the day
            - resource_count: Total resources for the day
            - dimension_count: Number of (service, env, region) combinations
            - by_service: Dict of cost totals by service
            - by_environment: Dict of cost totals by environment
            - by_region: Dict of cost totals by region
    
    Example:
        >>> summary = aggregate_daily_costs_summary(db, 'org-123', date(2024, 8, 18))
        >>> summary['total_cost_usd']
        2500.0
        >>> summary['by_service']['ec2']
        1500.0
    """
    # Get all aggregates for the day
    aggregates = aggregate_daily_costs(db, org_id, cost_date)
    
    # Calculate totals
    total_cost = sum(agg.total_cost_usd for agg in aggregates)
    total_resources = sum(agg.resource_count for agg in aggregates)
    
    # Group by dimension
    by_service = {}
    by_environment = {}
    by_region = {}
    
    for agg in aggregates:
        if agg.service:
            by_service[agg.service] = by_service.get(agg.service, 0.0) + agg.total_cost_usd
        if agg.environment:
            by_environment[agg.environment] = by_environment.get(agg.environment, 0.0) + agg.total_cost_usd
        if agg.region:
            by_region[agg.region] = by_region.get(agg.region, 0.0) + agg.total_cost_usd
    
    return {
        'cost_date': cost_date.isoformat(),
        'org_id': org_id,
        'total_cost_usd': round(total_cost, 2),
        'resource_count': total_resources,
        'dimension_count': len(aggregates),
        'by_service': {k: round(v, 2) for k, v in by_service.items()},
        'by_environment': {k: round(v, 2) for k, v in by_environment.items()},
        'by_region': {k: round(v, 2) for k, v in by_region.items()},
    }


def get_latest_cost_date(db: Session, org_id: str) -> Optional[date]:
    """
    Get the most recent date with billing data for an organization.
    
    Parameters:
        db: SQLAlchemy database session
        org_id: Organization ID
    
    Returns:
        Latest cost date, or None if no billing records exist
    
    Example:
        >>> latest = get_latest_cost_date(db, 'org-123')
        >>> latest
        datetime.date(2024, 8, 18)
    """
    result = db.query(
        func.max(func.date(models.BillingRecord.recorded_at)).label('latest_date')
    ).filter(
        models.BillingRecord.org_id == org_id
    ).first()
    
    return result.latest_date if result and result.latest_date else None


def get_date_range_with_data(db: Session, org_id: str) -> tuple[Optional[date], Optional[date]]:
    """
    Get the earliest and latest dates with billing data for an organization.
    
    Parameters:
        db: SQLAlchemy database session
        org_id: Organization ID
    
    Returns:
        Tuple of (earliest_date, latest_date), or (None, None) if no data
    
    Example:
        >>> earliest, latest = get_date_range_with_data(db, 'org-123')
        >>> earliest
        datetime.date(2024, 7, 20)
        >>> latest
        datetime.date(2024, 8, 18)
    """
    result = db.query(
        func.min(func.date(models.BillingRecord.recorded_at)).label('earliest'),
        func.max(func.date(models.BillingRecord.recorded_at)).label('latest'),
    ).filter(
        models.BillingRecord.org_id == org_id
    ).first()
    
    if result and result.earliest and result.latest:
        return result.earliest, result.latest
    return None, None
