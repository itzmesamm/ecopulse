"""
Layer 1 — GPU telemetry collector.

TODO: replace get_gpu_metrics() with a real NVIDIA DCGM Exporter / Prometheus
scrape once you have GPU hardware to monitor. For now, generates realistic
GPU utilization data with a mix of idle and active GPUs.
"""
import random
import datetime

from backend.ingestion.prometheus_client import query_prometheus
from backend.ingestion.source_mode import is_synthetic_mode, synthetic_record_count


def get_gpu_metrics(n: int | None = None, org_id: str | None = None) -> list[dict]:
    """Collect NVIDIA DCGM metrics from Prometheus or generate demo records."""
    if not is_synthetic_mode():
        expressions = {
            "utilization_pct": "DCGM_FI_DEV_GPU_UTIL",
            "vram_used_mb": "DCGM_FI_DEV_FB_USED",
            "power_watts": "DCGM_FI_DEV_POWER_USAGE",
            "temp_c": "DCGM_FI_DEV_GPU_TEMP",
        }
        metrics = {}
        timestamps = {}
        for field, expression in expressions.items():
            for sample in query_prometheus(expression):
                labels = sample.get("metric", {})
                gpu_id = labels.get("UUID") or labels.get("gpu") or labels.get("device") or labels.get("instance")
                if not gpu_id:
                    continue
                value = float(sample["value"][1])
                metrics.setdefault(gpu_id, {"gpu_id": gpu_id, "org_id": org_id})[field] = value
                timestamps[gpu_id] = datetime.datetime.fromtimestamp(
                    float(sample["value"][0]), datetime.timezone.utc
                ).replace(tzinfo=None).isoformat()
        return [dict(metric, recorded_at=timestamps[gpu_id]) for gpu_id, metric in metrics.items()]

    n = n if n is not None else synthetic_record_count()
    records = []
    for i in range(n):
        generator = random.Random(i)
        is_idle = i == 0 or generator.random() < 0.4
        utilization = generator.uniform(0, 3) if is_idle else generator.uniform(30, 95)
        vram_used_mb = 400.0 if i == 0 else (generator.uniform(200, 1500) if is_idle else generator.uniform(4000, 16000))
        power_watts = generator.uniform(30, 60) if is_idle else generator.uniform(150, 300)
        temp_c = generator.uniform(30, 40) if is_idle else generator.uniform(55, 85)

        records.append({
            "org_id": org_id,
            "gpu_id": f"gpu-{i}",
            "utilization_pct": round(utilization, 2),
            "vram_used_mb": round(vram_used_mb, 2),
            "power_watts": round(power_watts, 2),
            "temp_c": round(temp_c, 2),
            "recorded_at": datetime.datetime.utcnow().isoformat(),
        })
    return records
