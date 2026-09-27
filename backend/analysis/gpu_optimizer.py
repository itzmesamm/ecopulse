from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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
) -> List[GPUOptimizationFinding]:
    """Identify idle or underutilized GPUs and estimate waste.

    Combines GPU utilization and operational log signal to reduce false positives.
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
    log_messages = [log.message.lower() for log in logs]

    findings: List[GPUOptimizationFinding] = []
    for metric in metrics:
        utilization = float(metric.utilization_pct or 0.0)
        power = float(metric.power_watts or 0.0)
        is_idle = utilization <= utilization_threshold
        log_signal = any(metric.gpu_id.lower() in msg or "idle" in msg for msg in log_messages)
        if not (is_idle or log_signal):
            continue

        severity = 0.0
        if utilization <= 10:
            severity = 0.9
        elif utilization <= 20:
            severity = 0.7
        elif utilization <= 35:
            severity = 0.5
        if power >= power_threshold:
            severity = min(1.0, severity + 0.1)
        if log_signal:
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
                    f"{power:.0f}W power draw; likely underused and a candidate for shutdown or right-sizing."
                ),
            )
        )

    return sorted(findings, key=lambda item: item.severity_score, reverse=True)


def persist_gpu_optimizations(db: Session, org_id: str, findings: List[GPUOptimizationFinding]) -> int:
    count = 0
    for finding in findings:
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
