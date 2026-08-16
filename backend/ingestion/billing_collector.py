"""
Layer 1 — Billing records collector.

TODO: replace get_billing_records() with a real cloud billing API call
(AWS Cost Explorer, Azure Cost Management, GCP Billing) once you're ready
to move off synthetic data. For now, generates realistic-looking billing
data with a deliberate mix of wasteful and healthy resources.
"""
import random
import uuid
import datetime

RESOURCE_TYPES = ["ec2", "rds", "ebs", "s3", "lambda"]
REGIONS = ["us-east-1", "us-west-2", "eu-west-1", "ap-south-1"]
ENVIRONMENTS = ["production", "staging", "sandbox"]


def get_billing_records(n: int = 20, org_id: str | None = None) -> list[dict]:
    """Returns a list of synthetic billing records, one per resource."""
    records = []
    for i in range(n):
        resource_type = random.choice(RESOURCE_TYPES)
        is_wasteful = random.random() < 0.35
        usage_hours = random.uniform(0, 5) if is_wasteful else random.uniform(15, 24)
        cost = random.uniform(50, 900)

        records.append({
            "org_id": org_id,
            "resource_id": f"{resource_type}-{uuid.uuid4().hex[:8]}",
            "resource_type": resource_type,
            "region": random.choice(REGIONS),
            "account": f"acct-{random.randint(100, 999)}",
            "environment": random.choice(ENVIRONMENTS),
            "estimated_monthly_cost_usd": round(cost, 2),
            "usage_hours": round(usage_hours, 2),
            "recorded_at": datetime.datetime.utcnow().isoformat(),
        })
    return records
