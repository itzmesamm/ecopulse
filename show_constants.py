#!/usr/bin/env python3
"""Display waste analyzer configuration constants."""

from backend.analysis.waste_analyzer import LowUtilizationStrategy, HighCostLowUsageStrategy

print("=" * 60)
print("WASTE ANALYZER - CONFIGURABLE THRESHOLDS")
print("=" * 60)
print()
print("LowUtilizationStrategy:")
print(f"  • USAGE_THRESHOLD_HOURS = {LowUtilizationStrategy.USAGE_THRESHOLD_HOURS} hrs/month")
print(f"  • WASTE_PERCENTAGE = {LowUtilizationStrategy.WASTE_PERCENTAGE * 100:.0f}% of cost")
print(f"  • MINIMUM_WASTE_DOLLARS = ${LowUtilizationStrategy.MINIMUM_WASTE_DOLLARS}")
print()
print("HighCostLowUsageStrategy:")
print(f"  • COST_PER_HOUR_THRESHOLD = ${HighCostLowUsageStrategy.COST_PER_HOUR_THRESHOLD}/hour")
print(f"  • USAGE_THRESHOLD_HOURS = {HighCostLowUsageStrategy.USAGE_THRESHOLD_HOURS} hrs/month")
print(f"  • WASTE_PERCENTAGE = {HighCostLowUsageStrategy.WASTE_PERCENTAGE * 100:.0f}% of cost")
print(f"  • SEVERITY_MAX_MULTIPLIER = {HighCostLowUsageStrategy.SEVERITY_MAX_MULTIPLIER}x threshold")
print(f"  • MINIMUM_WASTE_DOLLARS = ${HighCostLowUsageStrategy.MINIMUM_WASTE_DOLLARS}")
print()
print("=" * 60)
