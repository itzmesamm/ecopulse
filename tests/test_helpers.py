"""
Test-only helper for generating deterministic historical BillingRecord data.

This module is used ONLY in tests to create reproducible cost data with
known trends for forecasting integration testing. Never used in production.
"""
import random
from datetime import date, timedelta
from typing import List
from backend.db import models


def generate_deterministic_billing_records(
    org_id: str,
    start_date: date,
    end_date: date,
    daily_base_cost: float = 1000.0,
    trend: float = 0.0,
    service: str = "ec2",
    environment: str = "production",
    region: str = "us-east-1",
    records_per_day: int = 5,
    seed: int = 42,
) -> List[models.BillingRecord]:
    """
    Generate deterministic BillingRecord objects with known trend.
    
    TEST-ONLY function. Never called in production code.
    
    Parameters:
        org_id: Organization ID
        start_date: First date to generate records for
        end_date: Last date to generate records for (inclusive)
        daily_base_cost: Starting cost per day in USD
        trend: Cost change per day in USD (e.g., +10.0 = increasing, -5.0 = decreasing)
        service: Resource type (e.g., "ec2", "rds")
        environment: Environment (e.g., "production", "staging")
        region: Region (e.g., "us-east-1")
        records_per_day: Number of records to create per day
        seed: Random seed for reproducibility (same seed = same values)
    
    Returns:
        List of BillingRecord objects (not persisted to DB)
    
    Example:
        >>> records = generate_deterministic_billing_records(
        ...     org_id="org-test",
        ...     start_date=date(2024, 8, 5),
        ...     end_date=date(2024, 8, 18),
        ...     daily_base_cost=1000.0,
        ...     trend=10.0,  # +$10/day increasing
        ...     seed=42
        ... )
        >>> len(records)  # 14 days * 5 records/day
        70
    """
    if seed is not None:
        random.seed(seed)
    
    records = []
    current_date = start_date
    day_offset = 0
    
    while current_date <= end_date:
        # Calculate cost for this day (base + trend)
        daily_cost = daily_base_cost + (trend * day_offset)
        # Distribute across records with slight variation
        cost_per_record = daily_cost / records_per_day
        
        for i in range(records_per_day):
            # Add small random variance (±5% per record)
            cost_variance = cost_per_record * random.uniform(-0.05, 0.05)
            record_cost = max(0.0, round(cost_per_record + cost_variance, 2))
            
            # Realistic usage hours based on cost
            usage_hours = round(random.uniform(5, 24), 2)
            
            record = models.BillingRecord(
                org_id=org_id,
                resource_id=f"{service}-{current_date.isoformat()}-{i}",
                service=service,
                region=region,
                account=f"acct-{random.randint(100, 999)}",
                environment=environment,
                cost=record_cost,
                usage_hours=usage_hours,
                recorded_at=current_date,  # Use date, not datetime
            )
            records.append(record)
        
        current_date += timedelta(days=1)
        day_offset += 1
    
    return records
