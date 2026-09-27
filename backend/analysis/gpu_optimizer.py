from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.db import models


@dataclass
class GPUOptimizationFinding:
    org_id: str
    gpu_id: str
    account: Optional[str]
    environment: Optional[str]
    utilization_pct: float
    power_watts: float
    severity_score: float
    estimated_monthly_waste_usd: float
    details: str


def _estimate_gpu_cost(power_watts: float, utilization_pct: float) -> float:
    """Simple cost estimate for GPU runtime using watts and load."""
    base_power = max(0.0, power_watts or 0.0)
    utilization = max(0.0, min(100.0, utilization_pct or 0.0)) / 100.0
    return round((base_power * 0.12 * (1.0 - utilization)) * 30.0, 2)


def detect_gpu_optimizations(
    db: Session,
    org_id: str,
    service: Optional[str] = None,
    environment: Optional[str] = None,
    region: Optional[str] = None,
    utilization_threshold: float = 20.0,
    power_threshold: float = 300.0,
    vram_threshold_mb: float = 1024.0,
    log_window_minutes: int = 30,
) -> List[GPUOptimizationFinding]:
    """Identify GPUs only when telemetry and a matching recent log agree.

    The confirmation requires low utilization, low VRAM use, positive power draw,
    and a GPU-specific idle/no-workload log inside the configured time window.
    """
    query = db.query(models.GPUMetric).filter(models.GPUMetric.org_id == org_id)
    if environment:
        query = query.filter(models.GPUMetric.environment == environment)

    metrics = query.all()
    if not metrics:
        return []

    logs = db.query(models.OperationalLog).filter(
        models.OperationalLog.org_id == org_id,
        models.OperationalLog.source == "gpu",
    ).all()

    findings: List[GPUOptimizationFinding] = []
    for metric in metrics:
        utilization = float(metric.utilization_pct or 0.0)
        power = float(metric.power_watts or 0.0)
        vram_used = float(metric.vram_used_mb or 0.0)
        is_idle = utilization <= min(utilization_threshold, 5.0) and vram_used <= vram_threshold_mb and power > 0
        metric_time = metric.recorded_at or datetime.utcnow()
        if metric_time.tzinfo is not None:
            metric_time = metric_time.replace(tzinfo=None)
        matching_logs = []
        for log in logs:
            message = (log.message or "").lower()
            if metric.gpu_id.lower() not in message:
                continue
            if not any(signal in message for signal in ("idle", "no workload", "no process")):
                continue
            log_time = log.recorded_at or metric_time
            if log_time.tzinfo is not None:
                log_time = log_time.replace(tzinfo=None)
            if abs(metric_time - log_time) <= timedelta(minutes=log_window_minutes):
                matching_logs.append(log)
        log_signal = bool(matching_logs)
        if not (is_idle and log_signal):
            continue

        severity = 0.0
        if utilization <= 2:
            severity = 0.9
        elif utilization <= 5:
            severity = 0.7
        if power >= power_threshold:
            severity = min(1.0, severity + 0.1)
        severity = min(1.0, severity + 0.15)

        waste = max(0.0, _estimate_gpu_cost(power, utilization))
        findings.append(
            GPUOptimizationFinding(
                org_id=org_id,
                gpu_id=metric.gpu_id,
                account=metric.account,
                environment=metric.environment,
                utilization_pct=utilization,
                power_watts=power,
                severity_score=round(severity, 4),
                estimated_monthly_waste_usd=round(waste, 2),
                details=(
                    f"GPU {metric.gpu_id} is operating at {utilization:.1f}% utilization with "
                    f"{vram_used:.0f}MB VRAM and {power:.0f}W power draw; recent GPU-specific idle log corroborates the low utilization."
                ),
            )
        )

    return sorted(findings, key=lambda item: item.severity_score, reverse=True)


def persist_gpu_optimizations(db: Session, org_id: str, findings: List[GPUOptimizationFinding]) -> int:
    count = 0
    for finding in findings:
        existing = db.query(models.GPUOptimizationFinding).filter(
            models.GPUOptimizationFinding.org_id == org_id,
            models.GPUOptimizationFinding.gpu_id == finding.gpu_id,
            models.GPUOptimizationFinding.utilization_pct == finding.utilization_pct,
            models.GPUOptimizationFinding.power_watts == finding.power_watts,
            models.GPUOptimizationFinding.details == finding.details,
        ).first()
        if existing:
            continue
        db.add(
            models.GPUOptimizationFinding(
                org_id=org_id,
                gpu_id=finding.gpu_id,
                account=finding.account,
                environment=finding.environment,
                utilization_pct=finding.utilization_pct,
                power_watts=finding.power_watts,
                severity_score=finding.severity_score,
                estimated_monthly_waste_usd=finding.estimated_monthly_waste_usd,
                details=finding.details,
            )
        )
        count += 1
    db.commit()
    return count
