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
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from backend.ingestion.source_mode import is_synthetic_mode, synthetic_record_count

SEVERITIES = ["INFO", "WARNING", "ERROR"]
SOURCES = ["billing", "gpu", "k8s"]
TEMPLATES = [
    "GPU {gid} idle for {h}h - utilization 0%",
    "Instance {rid} CPU usage below 5% for {h}h",
    "Storage volume {rid} has zero I/O for {h}h",
    "Pod {rid} in namespace {ns} restarted {n} times",
]


def get_operational_logs(n: int | None = None, org_id: str | None = None) -> list[dict]:
    """Collect recent operational logs from Loki or generate demo records."""
    if not is_synthetic_mode():
        base_url = os.getenv("LOKI_URL")
        if not base_url:
            raise RuntimeError("LOKI_URL is required for live operational log ingestion")
        end_ns = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1_000_000_000)
        start_ns = end_ns - int(os.getenv("LOKI_LOOKBACK_MINUTES", "15")) * 60 * 1_000_000_000
        query = os.getenv("LOKI_QUERY", '{job=~".+"}')
        params = {"query": query, "start": start_ns, "end": end_ns, "limit": n, "direction": "BACKWARD"}
        url = f"{base_url.rstrip('/')}/loki/api/v1/query_range?{urlencode(params)}"
        try:
            headers = {}
            token = os.getenv("LOKI_BEARER_TOKEN")
            if token:
                headers["Authorization"] = f"Bearer {token}"
            with urlopen(Request(url, headers=headers), timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"Loki query failed: {exc}") from exc
        logs = []
        for stream in payload.get("data", {}).get("result", []):
            labels = stream.get("stream", {})
            for timestamp, message in stream.get("values", []):
                lowered = message.lower()
                severity = "ERROR" if "error" in lowered else "WARNING" if "warn" in lowered else "INFO"
                logs.append({
                    "org_id": org_id,
                    "source": labels.get("job") or labels.get("app") or "loki",
                    "message": message,
                    "severity": severity,
                    "recorded_at": datetime.datetime.fromtimestamp(
                        int(timestamp) / 1_000_000_000, datetime.timezone.utc
                    ).replace(tzinfo=None).isoformat(),
                })
        return logs

    n = n if n is not None else synthetic_record_count()
    logs = []
    for index in range(n):
        if index == 0:
            logs.append({
                "org_id": org_id,
                "source": "node-exporter",
                "message": "i-demo-000 idle with CPU utilization below 5%",
                "severity": "WARNING",
                "recorded_at": datetime.datetime.utcnow().isoformat(),
            })
            continue
        if index == 1:
            logs.append({
                "org_id": org_id,
                "source": "gpu",
                "message": "gpu-0 idle with no workload",
                "severity": "WARNING",
                "recorded_at": datetime.datetime.utcnow().isoformat(),
            })
            continue
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
