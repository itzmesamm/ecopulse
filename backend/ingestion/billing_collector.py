"""
Layer 1 — Billing records collector.

TODO: replace get_billing_records() with a real cloud billing API call
(AWS Cost Explorer, Azure Cost Management, GCP Billing) once you're ready
to move off synthetic data. For now, generates realistic-looking billing
data with a deliberate mix of wasteful and healthy resources.
"""
import random
import datetime
import os

from backend.ingestion.source_mode import is_synthetic_mode, synthetic_record_count

RESOURCE_TYPES = ["ec2", "rds", "ebs", "s3", "lambda"]
REGIONS = ["us-east-1", "us-west-2", "eu-west-1", "ap-south-1"]
ENVIRONMENTS = ["production", "staging", "sandbox"]


def get_billing_records(n: int | None = None, org_id: str | None = None) -> list[dict]:
    """Fetch AWS resource-level costs in live mode or generate demo records."""
    if not is_synthetic_mode():
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("Install boto3 to use live AWS billing ingestion") from exc

        month_start = datetime.date.today().replace(day=1)
        end_date = month_start
        start_date = (month_start - datetime.timedelta(days=1)).replace(day=1)
        client = boto3.client("ce", region_name=os.getenv("AWS_REGION", "us-east-1"))
        request = {
            "TimePeriod": {"Start": start_date.isoformat(), "End": end_date.isoformat()},
            "Granularity": "DAILY",
            "Metrics": ["UnblendedCost"],
            "GroupBy": [
                {"Type": "DIMENSION", "Key": "SERVICE"},
                {"Type": "DIMENSION", "Key": "REGION"},
                {"Type": "DIMENSION", "Key": "RESOURCE_ID"},
            ],
        }
        records = []
        next_token = None
        while True:
            if next_token:
                request["NextPageToken"] = next_token
            response = client.get_cost_and_usage_with_resources(**request)
            for result in response.get("ResultsByTime", []):
                for group in result.get("Groups", []):
                    keys = group.get("Keys", [])
                    service, region, resource_id = (keys + ["unknown"] * 3)[:3]
                    cost = float(group.get("Metrics", {}).get("UnblendedCost", {}).get("Amount", 0.0))
                    if cost <= 0:
                        continue
                    records.append({
                        "org_id": org_id,
                        "resource_id": resource_id if resource_id not in {"", "NoResourceId"} else f"{service}:{region}",
                        "resource_type": service,
                        "region": region,
                        "account": os.getenv("AWS_ACCOUNT_ID"),
                        "environment": "production",
                        "estimated_monthly_cost_usd": cost,
                        "usage_hours": None,
                        "recorded_at": f"{result['TimePeriod']['Start']}T00:00:00",
                    })
            next_token = response.get("NextPageToken")
            if not next_token:
                return records

    n = n if n is not None else synthetic_record_count()
    records = []
    today = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    for i in range(n):
        generator = random.Random(i)
        resource_type = generator.choice(RESOURCE_TYPES)
        is_wasteful = generator.random() < 0.35
        usage_hours = None if i == 0 else (generator.uniform(0, 5) if is_wasteful else generator.uniform(15, 24))
        cost = 600.0 if i == 0 else generator.uniform(50, 900)

        records.append({
            "org_id": org_id,
            "resource_id": f"i-demo-{i:03d}",
            "resource_type": resource_type,
            "region": generator.choice(REGIONS),
            "account": f"acct-{generator.randint(100, 999)}",
            "environment": generator.choice(ENVIRONMENTS),
            "estimated_monthly_cost_usd": round(cost, 2),
            "usage_hours": round(usage_hours, 2) if usage_hours is not None else None,
            "recorded_at": (today - datetime.timedelta(days=i % 30)).isoformat(),
        })
    return records
