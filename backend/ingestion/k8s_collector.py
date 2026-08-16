"""
Layer 1 — Kubernetes metrics collector.

TODO: replace get_k8s_metrics() with a real kube-state-metrics /
Prometheus scrape against your cluster once one exists. For now, generates
realistic pod-level CPU/memory data with a mix of idle and active pods.
"""
import random
import uuid
import datetime

NAMESPACES = ["default", "backend", "ml-jobs", "monitoring"]


def get_k8s_metrics(n: int = 10, org_id: str | None = None) -> list[dict]:
    """Returns a list of synthetic Kubernetes pod metrics."""
    records = []
    for i in range(n):
        is_idle = random.random() < 0.3
        cpu_usage = random.uniform(0, 5) if is_idle else random.uniform(15, 85)
        memory_usage = random.uniform(50, 200) if is_idle else random.uniform(500, 4000)

        records.append({
            "org_id": org_id,
            "pod_name": f"pod-{uuid.uuid4().hex[:8]}",
            "namespace": random.choice(NAMESPACES),
            "cpu_usage": round(cpu_usage, 2),
            "memory_usage": round(memory_usage, 2),
            "recorded_at": datetime.datetime.utcnow().isoformat(),
        })
    return records
