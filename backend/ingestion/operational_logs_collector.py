"""
Layer 1 — Operational logs collector.

TODO: replace get_operational_logs() with a real log source (CloudWatch
Logs, Azure Monitor, application logs shipped to a log aggregator). For now,
synthetic log lines shaped like real waste-signal messages, so Layer 3's
RAG retrieval (when we build it) has something realistic to embed and search.
"""
import random
import datetime
import uuid

SEVERITIES = ["INFO", "WARNING", "ERROR"]
SOURCES = ["billing", "gpu", "k8s"]
TEMPLATES = [
    "GPU {gid} idle for {h}h - utilization 0%",
    "Instance {rid} CPU usage below 5% for {h}h",
    "Storage volume {rid} has zero I/O for {h}h",
    "Pod {rid} in namespace {ns} restarted {n} times",
]


def get_operational_logs(n: int = 20, org_id: str | None = None) -> list[dict]:
    """Returns a list of synthetic operational log records."""
    logs = []
    for _ in range(n):
        template = random.choice(TEMPLATES)
        message = template.format(
            gid=f"gpu-{random.randint(0, 7)}",
            rid=str(uuid.uuid4())[:8],
            h=random.randint(1, 48),
            ns="default",
            n=random.randint(1, 5),
        )
        logs.append({
            "org_id": org_id,
            "source": random.choice(SOURCES),
            "message": message,
            "severity": random.choice(SEVERITIES),
            "recorded_at": datetime.datetime.utcnow().isoformat(),
        })
    return logs
