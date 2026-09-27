import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def query_prometheus(query: str) -> list[dict]:
    base_url = os.getenv("PROMETHEUS_URL")
    if not base_url:
        raise RuntimeError("PROMETHEUS_URL is required for live metric ingestion")
    url = f"{base_url.rstrip('/')}/api/v1/query?{urlencode({'query': query})}"
    try:
        headers = {}
        token = os.getenv("PROMETHEUS_BEARER_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        with urlopen(Request(url, headers=headers), timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Prometheus query failed: {exc}") from exc
    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus returned an unsuccessful query: {payload}")
    return payload.get("data", {}).get("result", [])