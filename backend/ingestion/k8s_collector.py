"""
Layer 1 — Kubernetes metrics collector.

TODO: replace get_k8s_metrics() with a real kube-state-metrics /
Prometheus scrape against your cluster once one exists. For now, generates
realistic pod-level CPU/memory data with a mix of idle and active pods.
"""
import random
import uuid
import datetime

from backend.ingestion.prometheus_client import query_prometheus
from backend.ingestion.source_mode import is_synthetic_mode, synthetic_record_count

NAMESPACES = ["default", "backend", "ml-jobs", "monitoring"]


def get_k8s_metrics(n: int | None = None, org_id: str | None = None) -> list[dict]:
    """Collect pod CPU/memory from Prometheus or generate demo records."""
    if not is_synthetic_mode():
        query_by_pod = {
            "cpu_usage": 'sum by (pod, namespace) (rate(container_cpu_usage_seconds_total{container!="",pod!=""}[5m]))',
            "memory_usage": 'sum by (pod, namespace) (container_memory_working_set_bytes{container!="",pod!=""}) / 1048576',
        }
        pods = {}
        for field, expression in query_by_pod.items():
            for sample in query_prometheus(expression):
                labels = sample.get("metric", {})
                pod_name = labels.get("pod")
                if not pod_name:
                    continue
                entry = pods.setdefault(
                    pod_name,
                    {"org_id": org_id, "pod_name": pod_name, "namespace": labels.get("namespace")},
                )
                entry[field] = float(sample["value"][1])
                entry["recorded_at"] = datetime.datetime.fromtimestamp(
                    float(sample["value"][0]), datetime.timezone.utc
                ).replace(tzinfo=None).isoformat()
        return list(pods.values())

    n = n if n is not None else synthetic_record_count()
    records = []
    for i in range(n):
        generator = random.Random(i + 500)
        is_idle = generator.random() < 0.3
        cpu_usage = generator.uniform(0, 5) if is_idle else generator.uniform(15, 85)
        memory_usage = generator.uniform(50, 200) if is_idle else generator.uniform(500, 4000)

        records.append({
            "org_id": org_id,
            "pod_name": f"pod-demo-{i:04d}",
            "namespace": generator.choice(NAMESPACES),
            "cpu_usage": round(cpu_usage, 2),
            "memory_usage": round(memory_usage, 2),
            "recorded_at": datetime.datetime.utcnow().isoformat(),
        })
    return records
