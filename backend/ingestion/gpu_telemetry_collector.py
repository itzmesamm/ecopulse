"""
Layer 1 — GPU telemetry collector.

TODO: replace get_gpu_metrics() with a real NVIDIA DCGM Exporter / Prometheus
scrape once you have GPU hardware to monitor. For now, generates realistic
GPU utilization data with a mix of idle and active GPUs.
"""
import random
import uuid
import datetime


def get_gpu_metrics(n: int = 10, org_id: str | None = None) -> list[dict]:
    """Returns a list of synthetic GPU telemetry records."""
    records = []
    for i in range(n):
        is_idle = random.random() < 0.4
        utilization = random.uniform(0, 3) if is_idle else random.uniform(30, 95)
        vram_used_mb = random.uniform(200, 1500) if is_idle else random.uniform(4000, 16000)
        power_watts = random.uniform(30, 60) if is_idle else random.uniform(150, 300)
        temp_c = random.uniform(30, 40) if is_idle else random.uniform(55, 85)

        records.append({
            "org_id": org_id,
            "gpu_id": f"gpu-{uuid.uuid4().hex[:8]}",
            "utilization_pct": round(utilization, 2),
            "vram_used_mb": round(vram_used_mb, 2),
            "power_watts": round(power_watts, 2),
            "temp_c": round(temp_c, 2),
            "recorded_at": datetime.datetime.utcnow().isoformat(),
        })
    return records
