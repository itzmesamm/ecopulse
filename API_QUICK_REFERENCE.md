# Quick Reference: Parameter-Based Waste Analysis API

## Endpoint
```
GET /waste-analytics/items/advanced
```

## Required Parameters
- `org_id` (string): Your organization ID

## Optional Parameters

### Analysis Type
- `scan_type` (string): `"waste"` | `"high_cost"` | `"low_usage"` (default: `"waste"`)

### Filtering
- `severity_min` (float): 0.0 to 1.0 (default: 0.0)
- `severity_max` (float): 0.0 to 1.0 (default: 1.0)
- `service` (string): Service name like "EC2", "RDS" (optional)
- `environment` (string): Environment like "production", "staging" (optional)

### Sorting & Pagination
- `sort_by` (string): `"severity"` | `"cost"` | `"estimated_savings"` (default: `"severity"`)
- `order` (string): `"asc"` | `"desc"` (default: `"desc"`)
- `limit` (integer): 1 to 10000 (default: 100)

## Common Use Cases

### 1. Get Top 10 Highest-Cost Waste Items
```
GET /waste-analytics/items/advanced?org_id=YOUR_ORG_ID&scan_type=high_cost&sort_by=cost&order=desc&limit=10
```

### 2. Find Critical Waste (Severity >= 0.8)
```
GET /waste-analytics/items/advanced?org_id=YOUR_ORG_ID&severity_min=0.8&sort_by=severity&order=desc
```

### 3. Analyze Production EC2 Instances
```
GET /waste-analytics/items/advanced?org_id=YOUR_ORG_ID&service=EC2&environment=production&sort_by=cost&order=desc
```

### 4. Find Low-Utilization Resources
```
GET /waste-analytics/items/advanced?org_id=YOUR_ORG_ID&scan_type=low_usage&sort_by=severity&order=desc&limit=50
```

### 5. Medium-Severity Waste in Staging
```
GET /waste-analytics/items/advanced?org_id=YOUR_ORG_ID&severity_min=0.4&severity_max=0.7&environment=staging
```

### 6. Potential $$ Savings (Sorted by Estimated Savings)
```
GET /waste-analytics/items/advanced?org_id=YOUR_ORG_ID&sort_by=estimated_savings&order=desc&limit=20
```

## Response Format

```json
[
  {
    "id": "waste-item-123",
    "resource_id": "i-0abc123def456",
    "service": "EC2",
    "region": "us-east-1",
    "environment": "production",
    "waste_type": "high_cost_low_usage",
    "severity_score": 0.85,
    "estimated_monthly_waste_usd": 2500.00,
    "details": "High cost ($240/hr) despite low usage (5 hrs/month)..."
  },
  ...
]
```

## Error Responses

### Invalid Parameter
```
HTTP 400 Bad Request
{
  "detail": "Invalid parameter: severity_max must be >= severity_min"
}
```

### Organization Not Found
```
HTTP 404 Not Found
{
  "detail": "Organization not found"
}
```

### Empty Results
```
HTTP 200 OK
[]
```

## Parameter Validation Rules

| Parameter | Valid Range | Default | Required |
|-----------|------------|---------|----------|
| org_id | any string | - | ✓ Yes |
| scan_type | waste, high_cost, low_usage | waste | No |
| severity_min | 0.0 - 1.0 | 0.0 | No |
| severity_max | 0.0 - 1.0 | 1.0 | No |
| service | any string | None | No |
| environment | any string | None | No |
| sort_by | severity, cost, estimated_savings | severity | No |
| order | asc, desc | desc | No |
| limit | 1 - 10000 | 100 | No |

**Rules:**
- severity_max must be >= severity_min
- severity values must be in range [0.0, 1.0]
- limit must be in range [1, 10000]

## Backward Compatibility

### Existing Endpoints Still Work
- `POST /waste-analytics/analyze` - Run analysis
- `GET /waste-analytics/summary` - Get summary stats
- `GET /waste-analytics/items` - List items (basic filtering)
- `GET /waste-analytics/items/{item_id}` - Get item details
- `GET /waste-analytics/insights/by-service` - Service aggregation
- `GET /waste-analytics/insights/by-environment` - Environment aggregation

## Tips & Best Practices

1. **Start with defaults**: Use minimal parameters first, add filters as needed
2. **Use severity filtering**: Prioritize high-severity items (>= 0.7)
3. **Combine filters**: Service + environment + severity for precise results
4. **Sort by savings**: Use `sort_by=estimated_savings` to prioritize cost impact
5. **Pagination**: Use limit parameter for large result sets (default: 100)
6. **Scan types**: Use scan_type for quick analysis of specific waste patterns

## Example: Dashboard Query
Get summary of top waste opportunities by cost:
```
GET /waste-analytics/items/advanced?org_id=YOUR_ORG_ID&sort_by=cost&order=desc&limit=5
```

This returns the 5 most expensive waste items, helping you quickly identify the biggest opportunities for cost savings.
