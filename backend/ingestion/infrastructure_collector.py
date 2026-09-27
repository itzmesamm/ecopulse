import datetime
import random

from backend.ingestion.prometheus_client import query_prometheus
from backend.ingestion.source_mode import is_synthetic_mode, synthetic_record_count


QUERIES = {
    "cpu_pct": '100 * (1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])))',
    "memory_pct": '100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)',
    "disk_pct": '100 * (1 - node_filesystem_avail_bytes{fstype!="tmpfs",mountpoint="/"} / node_filesystem_size_bytes{fstype!="tmpfs",mountpoint="/"})',
    "network_receive_bytes_per_second": 'sum by (instance) (rate(node_network_receive_bytes_total{device!="lo"}[5m]))',
    "network_transmit_bytes_per_second": 'sum by (instance) (rate(node_network_transmit_bytes_total{device!="lo"}[5m]))',
}


def get_infrastructure_metrics(n: int | None = None, org_id: str | None = None) -> list[dict]:
    """Collect node-exporter metrics from Prometheus or generate local demo data."""
    if is_synthetic_mode():
        n = n if n is not None else synthetic_record_count()
        return [
            {
                "org_id": org_id,
                "host_id": f"i-demo-{index:03d}",
                "cpu_pct": 2.0 if index == 0 else round(random.uniform(1, 95), 2),
                "memory_pct": round(random.Random(index + 100).uniform(10, 90), 2),
                "disk_pct": round(random.Random(index + 200).uniform(5, 85), 2),
                "network_receive_bytes_per_second": round(random.Random(index + 300).uniform(0, 100000), 2),
                "network_transmit_bytes_per_second": round(random.Random(index + 400).uniform(0, 100000), 2),
                "recorded_at": datetime.datetime.utcnow().isoformat(),
            }
            for index in range(n)
        ]

    hosts = {}
    for field, expression in QUERIES.items():
        for sample in query_prometheus(expression):
            labels = sample.get("metric", {})
            host_id = labels.get("aws_instance_id") or labels.get("instance_id") or labels.get("instance")
            if not host_id:
                continue
            entry = hosts.setdefault(host_id, {"org_id": org_id, "host_id": host_id})
            entry[field] = float(sample["value"][1])
            entry["recorded_at"] = datetime.datetime.fromtimestamp(
                float(sample["value"][0]), datetime.timezone.utc
            ).replace(tzinfo=None).isoformat()
    return list(hosts.values())