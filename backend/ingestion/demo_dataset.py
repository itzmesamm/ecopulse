"""Deterministic, time-coherent demo data for local and evaluation use."""
from datetime import date, datetime, time, timedelta


_BILLING_RESOURCES = (
    {
        "resource_id": "i-demo-ec2-idle",
        "service": "ec2",
        "region": "us-east-1",
        "environment": "sandbox",
        "team": "platform",
        "owner": "demo-platform",
        "daily_cost": 4.80,
        "daily_usage_hours": 0.08,
        "daily_growth": 0.001,
    },
    {
        "resource_id": "i-demo-ec2-prod",
        "service": "ec2",
        "region": "us-east-1",
        "environment": "production",
        "team": "payments",
        "owner": "demo-payments",
        "daily_cost": 26.40,
        "daily_usage_hours": 20.0,
        "daily_growth": 0.002,
    },
    {
        "resource_id": "db-demo-rds-prod",
        "service": "rds",
        "region": "us-east-1",
        "environment": "production",
        "team": "payments",
        "owner": "demo-payments",
        "daily_cost": 38.00,
        "daily_usage_hours": 22.0,
        "daily_growth": 0.0015,
    },
    {
        "resource_id": "vol-demo-ebs-idle",
        "service": "ebs",
        "region": "us-west-2",
        "environment": "development",
        "team": "ml-platform",
        "owner": "demo-ml",
        "daily_cost": 1.80,
        "daily_usage_hours": 0.0,
        "daily_growth": 0.0,
    },
    {
        "resource_id": "bucket-demo-s3-logs",
        "service": "s3",
        "region": "us-east-1",
        "environment": "production",
        "team": "platform",
        "owner": "demo-platform",
        "daily_cost": 6.00,
        "daily_usage_hours": 24.0,
        "daily_growth": 0.003,
    },
    {
        "resource_id": "fn-demo-api",
        "service": "lambda",
        "region": "us-east-1",
        "environment": "production",
        "team": "payments",
        "owner": "demo-payments",
        "daily_cost": 12.00,
        "daily_usage_hours": 7.5,
        "daily_growth": 0.0025,
    },
)

_GPU_PROFILES = (
    {"gpu_id": "gpu-demo-training", "environment": "production", "base_utilization": 72.0},
    {"gpu_id": "gpu-demo-idle", "environment": "sandbox", "base_utilization": 2.0},
)

_PODS = (
    ("api-7d8f", "payments", 48.0, 1536.0),
    ("worker-3b2a", "payments", 31.0, 1024.0),
    ("trainer-a91c", "ml-jobs", 4.0, 320.0),
    ("metrics-5e10", "monitoring", 12.0, 512.0),
)


def build_demo_dataset(org_id: str, as_of: date | None = None) -> dict[str, list[dict]]:
    """Return 30 days of stable resources and correlated operational signals."""
    end_date = as_of or date.today()
    billing = []
    gpu_metrics = []
    k8s_metrics = []
    operational_logs = []

    for days_ago in range(29, -1, -1):
        sample_date = end_date - timedelta(days=days_ago)
        timestamp = datetime.combine(sample_date, time(hour=12))
        weekend_factor = 0.88 if sample_date.weekday() >= 5 else 1.0

        for resource in _BILLING_RESOURCES:
            trend = 1.0 + resource["daily_growth"] * (29 - days_ago)
            billing.append({
                **resource,
                "org_id": org_id,
                "account": "demo-account-001",
                "cost": round(resource["daily_cost"] * trend * weekend_factor, 2),
                "usage_hours": round(resource["daily_usage_hours"] * weekend_factor, 2),
                "period_days": 1,
                "recorded_at": timestamp.isoformat(),
            })

        for index, profile in enumerate(_GPU_PROFILES):
            utilization = profile["base_utilization"] + ((days_ago + index * 3) % 7 - 3) * 0.7
            if profile["base_utilization"] < 10:
                utilization = max(0.0, utilization)
            else:
                utilization = min(95.0, max(35.0, utilization))
            gpu_metrics.append({
                **profile,
                "org_id": org_id,
                "account": "demo-account-001",
                "utilization_pct": round(utilization, 2),
                "vram_used_mb": round(800.0 + utilization * 145.0, 2),
                "power_watts": round(35.0 + utilization * 2.4, 2),
                "temp_c": round(31.0 + utilization * 0.48, 2),
                "recorded_at": timestamp.isoformat(),
            })

        for pod_name, namespace, base_cpu, base_memory in _PODS:
            variation = ((days_ago + len(pod_name)) % 5 - 2) * 0.04
            k8s_metrics.append({
                "org_id": org_id,
                "pod_name": pod_name,
                "namespace": namespace,
                "cpu_usage": round(max(0.0, base_cpu * (1.0 + variation)), 2),
                "memory_usage": round(max(0.0, base_memory * (1.0 + variation / 2)), 2),
                "recorded_at": timestamp.isoformat(),
            })

        if days_ago in {0, 2, 5, 9, 14, 20, 26}:
            operational_logs.extend([
                {
                    "org_id": org_id,
                    "source": "cloudwatch-demo",
                    "severity": "WARNING",
                    "message": "Instance i-demo-ec2-idle CPU utilization remained below 2% during the observation window.",
                    "recorded_at": timestamp.isoformat(),
                },
                {
                    "org_id": org_id,
                    "source": "storage-demo",
                    "severity": "INFO",
                    "message": "Volume vol-demo-ebs-idle reported no read or write operations during the observation window.",
                    "recorded_at": timestamp.isoformat(),
                },
            ])

    return {
        "billing": billing,
        "gpu": gpu_metrics,
        "k8s": k8s_metrics,
        "logs": operational_logs,
    }