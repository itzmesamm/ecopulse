"""
GreenOps carbon estimation (minimal + practical).

Roadmap expects CO2 impact via carbon intensity factors. This backend currently
estimates "carbon_savings_kg" using:
  - waste signal type + usage hours (from BillingRecord via WasteItem)
  - assumed idle power draw (configurable constants)
  - region-specific carbon intensity (kg CO2 / kWh)

This is intentionally lightweight so it works immediately with the current
database schema (without requiring GPU telemetry for every waste finding).
"""

from __future__ import annotations

import os
from typing import Optional

from sqlalchemy.orm import Session

from backend.analysis.waste_analyzer import HighCostLowUsageStrategy, LowUtilizationStrategy
from backend.db import models


CARBON_INTENSITY_KG_PER_KWH: dict[str, float] = {
    # From your roadmap synopsis (Cloud Carbon Footprint inspired mapping)
    "us-east-1": 0.379,
    "us-west-2": 0.135,
    "eu-west-1": 0.316,
    "ap-south-1": 0.708,
}

# Heuristic constants: assumed average power draw while "idle enough to save".
# Tune later based on real infra/power telemetry.
ASSUMED_IDLE_POWER_WATTS: dict[str, float] = {
    "low_utilization": 100.0,
    "high_cost_low_usage": 150.0,
}

DEFAULT_REGION = os.getenv("DEFAULT_CARBON_REGION", "us-east-1")


def estimate_carbon_savings_kg_for_waste_item(
    db: Session,
    org_id: str,
    waste_item_id: str,
) -> Optional[float]:
    """
    Estimate carbon savings for a single WasteItem (and return kg CO2).

    Returns None if required data is missing.
    """
    waste_item = (
        db.query(models.WasteItem)
        .filter(models.WasteItem.org_id == org_id, models.WasteItem.id == waste_item_id)
        .first()
    )
    if not waste_item:
        return None

    billing = (
        db.query(models.BillingRecord)
        .filter(models.BillingRecord.org_id == org_id, models.BillingRecord.id == waste_item.billing_record_id)
        .first()
    )
    if not billing:
        return None

    waste_type = waste_item.waste_type
    usage_hours = float(billing.usage_hours or 0.0)
    region = billing.region or waste_item.region or "us-east-1"
    intensity = CARBON_INTENSITY_KG_PER_KWH.get(region, 0.4)

    if waste_type == "low_utilization":
        threshold_hours = float(LowUtilizationStrategy.USAGE_THRESHOLD_HOURS)
    elif waste_type == "high_cost_low_usage":
        threshold_hours = float(HighCostLowUsageStrategy.USAGE_THRESHOLD_HOURS)
    else:
        # Unknown waste type → cannot safely infer "hours saved"
        return None

    # How many monthly hours we assume can be avoided.
    hours_saved = max(0.0, threshold_hours - usage_hours)
    if hours_saved <= 0:
        return 0.0

    assumed_power_watts = ASSUMED_IDLE_POWER_WATTS.get(waste_type, 120.0)
    kwh_saved = (assumed_power_watts * hours_saved) / 1000.0
    carbon_kg = kwh_saved * intensity
    return round(float(carbon_kg), 4)


def estimate_carbon_savings_kg_for_gpu_finding(
    db: Session,
    org_id: str,
    gpu_id: str,
) -> Optional[float]:
    """
    Estimate carbon savings for a GPU-based recommendation using:
      - stored GPU `power_watts`
      - a snapshot-based idle-hours heuristic

    Note: GPUOptimizationFinding doesn’t store region in the current schema,
    so we use DEFAULT_CARBON_REGION.
    """
    gpu = (
        db.query(models.GPUOptimizationFinding)
        .filter(models.GPUOptimizationFinding.org_id == org_id, models.GPUOptimizationFinding.gpu_id == gpu_id)
        .first()
    )
    if not gpu:
        return None

    intensity = CARBON_INTENSITY_KG_PER_KWH.get(DEFAULT_REGION, 0.4)
    power_watts = float(gpu.power_watts or 0.0)
    utilization_pct = float(gpu.utilization_pct or 0.0)

    # Heuristic idle-hours estimate:
    # If utilization is near 0, assume most of the month could be saved.
    # If utilization is >= 20%, savings approach 0.
    assumed_month_hours = 720.0
    utilization_threshold = 20.0
    idle_fraction = max(0.0, (utilization_threshold - utilization_pct) / utilization_threshold)
    idle_hours_saved = assumed_month_hours * idle_fraction

    if idle_hours_saved <= 0 or power_watts <= 0:
        return 0.0

    kwh_saved = (power_watts * idle_hours_saved) / 1000.0
    carbon_kg = kwh_saved * intensity
    return round(float(carbon_kg), 4)

