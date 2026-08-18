"""
Layer 2 — Waste Analysis.

Analyzes billing records to identify cost optimization opportunities and waste.
Uses modular analyzer strategies that can be extended/customized per organization.

Key heuristics:
  - Low usage hours + High cost = potential waste (idle resources)
  - Usage hours outliers = resources that deviate from normal patterns
  - High cost per hour = candidates for resource optimization

All thresholds and waste percentages are configurable via strategy constants.
"""
from dataclasses import dataclass
from typing import Optional, List
from sqlalchemy.orm import Session

from backend.db import models


@dataclass
class WasteAnalysisResult:
    """Result of analyzing a single billing record for waste."""
    resource_id: str
    waste_type: str
    severity_score: float  # 0.0 to 1.0, never negative
    estimated_monthly_waste_usd: float  # Never negative
    details: Optional[str] = None


def _clamp_score(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp a value to [min_val, max_val]. Always returns safe value."""
    return max(min_val, min(value, max_val))


def _ensure_positive(value: float) -> float:
    """Ensure a value is never negative. Returns 0.0 for any negative/None input."""
    if value is None or value < 0:
        return 0.0
    return value


class WasteAnalyzer:
    """
    Modular waste analyzer. Pluggable strategies for different waste detection methods.
    
    Strategies can be added/customized per organization's cloud infrastructure patterns.
    """
    
    def __init__(self):
        """Initialize with built-in waste detection strategies."""
        self.strategies = [
            LowUtilizationStrategy(),
            HighCostLowUsageStrategy(),
        ]
    
    def add_strategy(self, strategy: "WasteDetectionStrategy") -> None:
        """Register a new waste detection strategy."""
        self.strategies.append(strategy)
    
    def analyze_record(self, billing_record: models.BillingRecord) -> Optional[WasteAnalysisResult]:
        """
        Analyze a single billing record for waste using all registered strategies.
        
        Returns the highest-severity result, or None if no waste detected.
        Ensures returned values are never negative.
        """
        if not billing_record.cost or not billing_record.usage_hours:
            return None
        
        results = []
        for strategy in self.strategies:
            result = strategy.detect(billing_record)
            if result:
                results.append(result)
        
        # Return the most severe waste detected, if any
        if results:
            return max(results, key=lambda r: r.severity_score)
        return None
    
    def analyze_records(self, db: Session, org_id: str) -> list[WasteAnalysisResult]:
        """
        Analyze all recent billing records for an organization.
        
        Returns a list of detected waste items, highest-severity first.
        """
        # Get all billing records for this org (latest batch)
        # In production, you'd filter by date range or fetch only recent records
        records = db.query(models.BillingRecord).filter(
            models.BillingRecord.org_id == org_id
        ).all()
        
        results = []
        for record in records:
            result = self.analyze_record(record)
            if result:
                results.append(result)
        
        # Sort by severity descending
        results.sort(key=lambda r: r.severity_score, reverse=True)
        return results


class WasteDetectionStrategy:
    """Base class for waste detection strategies."""
    
    def detect(self, billing_record: models.BillingRecord) -> Optional[WasteAnalysisResult]:
        """
        Analyze a billing record for a specific type of waste.
        
        Returns a WasteAnalysisResult if waste is detected, None otherwise.
        Must ensure returned values are never negative.
        """
        raise NotImplementedError


class LowUtilizationStrategy(WasteDetectionStrategy):
    """
    Detects resources with suspiciously low usage hours despite having cost.
    
    Configurable thresholds:
      - USAGE_THRESHOLD_HOURS: Resources below this usage are flagged (default 3.0 hrs/month)
      - WASTE_PERCENTAGE: % of cost considered waste when usage is very low (default 80%)
    
    Logic:
      - Severity = 1.0 - (usage_hours / threshold), clamped to [0.0, 1.0]
      - Estimated waste = cost * waste_percentage
    """
    
    # Configurable constants
    USAGE_THRESHOLD_HOURS = 3.0   # Per month; resources below this are considered idle
    WASTE_PERCENTAGE = 0.80       # 80% of cost is waste for idle resources
    MINIMUM_WASTE_DOLLARS = 0.01  # Don't flag resources with trivial waste
    
    def detect(self, billing_record: models.BillingRecord) -> Optional[WasteAnalysisResult]:
        if billing_record.usage_hours is None or billing_record.cost is None:
            return None
        
        # Skip if resource is being used normally
        if billing_record.usage_hours >= self.USAGE_THRESHOLD_HOURS:
            return None
        
        # Calculate severity: how far below threshold
        # severity = 1.0 - (0.5 hours / 3.0 hours) = 0.833...
        if self.USAGE_THRESHOLD_HOURS > 0:
            severity = 1.0 - (billing_record.usage_hours / self.USAGE_THRESHOLD_HOURS)
        else:
            severity = 1.0
        
        severity = _clamp_score(severity)
        
        # Estimated waste: percentage of cost
        estimated_waste = billing_record.cost * self.WASTE_PERCENTAGE
        estimated_waste = _ensure_positive(estimated_waste)
        
        # Skip if waste is negligible
        if estimated_waste < self.MINIMUM_WASTE_DOLLARS:
            return None
        
        return WasteAnalysisResult(
            resource_id=billing_record.resource_id,
            waste_type="low_utilization",
            severity_score=round(severity, 3),
            estimated_monthly_waste_usd=round(estimated_waste, 2),
            details=f"Resource used only {billing_record.usage_hours:.1f} hours/month; likely idle. "
                    f"Estimated waste: ${estimated_waste:.2f}/month ({self.WASTE_PERCENTAGE*100:.0f}% of cost).",
        )


class HighCostLowUsageStrategy(WasteDetectionStrategy):
    """
    Detects resources with high cost-per-hour ratios and low total usage.
    
    Configurable thresholds:
      - COST_PER_HOUR_THRESHOLD: Resources exceeding this $/hour are candidates (default $100/hr)
      - USAGE_THRESHOLD_HOURS: Also must have low total usage (default 10 hrs/month)
      - WASTE_PERCENTAGE: % of cost considered waste for oversized resources (default 40%)
      - SEVERITY_MAX_MULTIPLIER: Cost/hour multiplier for max severity (default 2x threshold)
    
    Logic:
      - Severity = min(cost_per_hour / (2 * threshold), 1.0)
      - Estimated waste = cost * waste_percentage
    """
    
    # Configurable constants
    COST_PER_HOUR_THRESHOLD = 100.0     # USD per hour; high cost/hour indicates oversizing
    USAGE_THRESHOLD_HOURS = 10.0        # Per month; resources must also have low total usage
    WASTE_PERCENTAGE = 0.40             # 40% of cost is waste for oversized resources
    SEVERITY_MAX_MULTIPLIER = 2.0       # 2x threshold = max severity
    MINIMUM_WASTE_DOLLARS = 0.01        # Don't flag resources with trivial waste
    
    def detect(self, billing_record: models.BillingRecord) -> Optional[WasteAnalysisResult]:
        if billing_record.usage_hours is None or billing_record.cost is None:
            return None
        
        # Avoid division by zero
        if billing_record.usage_hours == 0:
            return None
        
        cost_per_hour = billing_record.cost / billing_record.usage_hours
        
        # Both conditions must be true: high cost/hour AND low total usage
        if not (cost_per_hour > self.COST_PER_HOUR_THRESHOLD and 
                billing_record.usage_hours < self.USAGE_THRESHOLD_HOURS):
            return None
        
        # Severity: normalized by max threshold
        # e.g., $150/hr with $100/hr threshold and 2x multiplier:
        # severity = min(150 / 200, 1.0) = 0.75
        severity_threshold = self.COST_PER_HOUR_THRESHOLD * self.SEVERITY_MAX_MULTIPLIER
        if severity_threshold > 0:
            severity = cost_per_hour / severity_threshold
        else:
            severity = 1.0
        
        severity = _clamp_score(severity)
        
        # Estimated waste
        estimated_waste = billing_record.cost * self.WASTE_PERCENTAGE
        estimated_waste = _ensure_positive(estimated_waste)
        
        # Skip if waste is negligible
        if estimated_waste < self.MINIMUM_WASTE_DOLLARS:
            return None
        
        return WasteAnalysisResult(
            resource_id=billing_record.resource_id,
            waste_type="high_cost_low_usage",
            severity_score=round(severity, 3),
            estimated_monthly_waste_usd=round(estimated_waste, 2),
            details=f"High cost (${cost_per_hour:.2f}/hr) despite low usage ({billing_record.usage_hours:.1f} hrs/month). "
                    f"Estimated waste: ${estimated_waste:.2f}/month ({self.WASTE_PERCENTAGE*100:.0f}% of cost). "
                    f"Consider right-sizing or using spot instances.",
        )


def persist_waste_items(db: Session, org_id: str, waste_results: list[WasteAnalysisResult]) -> int:
    """
    Persist detected waste items to the database.
    
    Returns the number of waste items persisted.
    """
    # Get the billing records for this org to link waste items
    billing_records = {
        r.resource_id: r 
        for r in db.query(models.BillingRecord).filter(
            models.BillingRecord.org_id == org_id
        ).all()
    }
    
    count = 0
    for result in waste_results:
        billing_record = billing_records.get(result.resource_id)
        if not billing_record:
            continue  # Skip if no matching billing record
        
        # Final safety check: ensure values are never negative
        severity = _clamp_score(result.severity_score)
        waste_usd = _ensure_positive(result.estimated_monthly_waste_usd)
        
        waste_item = models.WasteItem(
            org_id=org_id,
            billing_record_id=billing_record.id,
            resource_id=result.resource_id,
            service=billing_record.service,
            region=billing_record.region,
            environment=billing_record.environment,
            waste_type=result.waste_type,
            severity_score=severity,
            estimated_monthly_waste_usd=waste_usd,
            details=result.details,
        )
        db.add(waste_item)
        count += 1
    
    db.commit()
    return count


def filter_and_sort_waste_items(
    db: Session,
    org_id: str,
    scan_type: str = "waste",
    severity_min: float = 0.0,
    severity_max: float = 1.0,
    service: Optional[str] = None,
    environment: Optional[str] = None,
    sort_by: str = "severity",
    order: str = "desc",
    limit: int = 100,
) -> List[models.WasteItem]:
    """
    Filter and sort waste items based on parameters.
    
    Parameters:
      - scan_type: "waste" (all), "high_cost", or "low_usage"
      - severity_min/max: Filter by severity range [0.0-1.0]
      - service: Filter by service name (optional)
      - environment: Filter by environment (optional)
      - sort_by: "cost", "severity", or "estimated_savings"
      - order: "asc" or "desc"
      - limit: Maximum results to return
    
    Returns:
      List of WasteItem models matching the criteria, sorted as specified.
    """
    # Start with base query
    query = db.query(models.WasteItem).filter(
        models.WasteItem.org_id == org_id
    )
    
    # Apply scan_type filter
    if scan_type == "high_cost":
        # High cost: filter to items with high estimated waste
        # Top 25% by cost threshold
        query = query.filter(models.WasteItem.waste_type == "high_cost_low_usage")
    elif scan_type == "low_usage":
        # Low usage: filter to items detected by low utilization strategy
        query = query.filter(models.WasteItem.waste_type == "low_utilization")
    # else: scan_type == "waste" - include all waste types
    
    # Apply severity filter
    query = query.filter(
        models.WasteItem.severity_score >= severity_min,
        models.WasteItem.severity_score <= severity_max,
    )
    
    # Apply optional service filter
    if service:
        query = query.filter(models.WasteItem.service == service)
    
    # Apply optional environment filter
    if environment:
        query = query.filter(models.WasteItem.environment == environment)
    
    # Apply sorting
    sort_column = None
    if sort_by == "cost":
        sort_column = models.WasteItem.estimated_monthly_waste_usd
    elif sort_by == "severity":
        sort_column = models.WasteItem.severity_score
    elif sort_by == "estimated_savings":
        # estimated_savings = estimated_monthly_waste_usd (same as cost in our model)
        sort_column = models.WasteItem.estimated_monthly_waste_usd
    
    if sort_column is not None:
        if order == "asc":
            query = query.order_by(sort_column.asc())
        else:  # desc
            query = query.order_by(sort_column.desc())
    
    # Apply limit
    results = query.limit(limit).all()
    return results

