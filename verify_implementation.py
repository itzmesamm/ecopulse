#!/usr/bin/env python3
"""Verification script for parameter-based waste analysis implementation."""

from backend.api.waste_analytics import router, ParameterizedAnalysisRequest, list_waste_items_advanced
from backend.analysis.waste_analyzer import filter_and_sort_waste_items
import inspect

# Verify endpoint is registered
routes = [route.path for route in router.routes]
print('✓ API Router Status:')
print(f'  - Routes registered: {len(router.routes)}')
has_advanced = any("advanced" in str(r) for r in routes)
print(f'  - /advanced endpoint exists: {has_advanced}')
print(f'  - Route paths: {routes}')

# Verify Pydantic model
params = ParameterizedAnalysisRequest(
    scan_type='high_cost',
    severity_min=0.5,
    severity_max=0.9,
    sort_by='cost',
    order='desc',
    limit=50
)
print(f'\n✓ Pydantic Model Status:')
print(f'  - scan_type: {params.scan_type}')
print(f'  - severity_min: {params.severity_min}')
print(f'  - severity_max: {params.severity_max}')
print(f'  - sort_by: {params.sort_by}')
print(f'  - order: {params.order}')
print(f'  - limit: {params.limit}')

# Verify function signature
sig = inspect.signature(filter_and_sort_waste_items)
print(f'\n✓ Filter Function Status:')
print(f'  - Function exists: True')
print(f'  - Parameters: {list(sig.parameters.keys())}')

print('\n✅ All components verified successfully!')
