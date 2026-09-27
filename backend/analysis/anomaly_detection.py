from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Optional, List

from sqlalchemy.orm import Session

from backend.db import models

try:
    from pyod.models import IsolationForest
except Exception:  # pragma: no cover
    IsolationForest = None


@dataclass
class AnomalyFindingResult:
    org_id: str
    resource_id: str
    service: Optional[str]
    region: Optional[str]
    environment: Optional[str]
    cost: float
    usage_hours: float
    anomaly_score: float
    severity_score: float
    details: str


def _safe_float(value):
    if value is None:
        return 0.0
    return float(value)


def detect_anomalies(
    db: Session,
    org_id: str,
    service: Optional[str] = None,
    environment: Optional[str] = None,
    region: Optional[str] = None,
    min_samples: int = 5,
) -> List[AnomalyFindingResult]:
    """Detect anomalous cost/usage patterns using Isolation Forest.

    Uses cost and usage_hours as the main signals; falls back safely to empty data.
    """
    query = db.query(models.BillingRecord).filter(models.BillingRecord.org_id == org_id)
    if service:
        query = query.filter(models.BillingRecord.service == service)
    if environment:
        query = query.filter(models.BillingRecord.environment == environment)
    if region:
        query = query.filter(models.BillingRecord.region == region)

    records = query.all()
    if not records or len(records) < max(2, min_samples):
        return []

    features = []
    for record in records:
        if record.cost is None or record.usage_hours is None:
            continue
        features.append([float(record.cost), float(record.usage_hours)])

    if len(features) < 2:
        return []

    findings: List[AnomalyFindingResult] = []

    if IsolationForest is not None:
        model = IsolationForest(contamination=0.1, random_state=42)
        model.fit(features)
        scores = model.decision_function(features)
        preds = model.predict(features)

        for idx, record in enumerate(records):
            if record.cost is None or record.usage_hours is None:
                continue
            if idx >= len(scores):
                continue
            if preds[idx] == -1:
                cost = _safe_float(record.cost)
                usage = _safe_float(record.usage_hours)
                anomaly_score = max(0.0, round(float(-scores[idx]), 4))
                severity = max(0.0, min(1.0, anomaly_score * 2.5))
                findings.append(
                    AnomalyFindingResult(
                        org_id=org_id,
                        resource_id=record.resource_id,
                        service=record.service,
                        region=record.region,
                        environment=record.environment,
                        cost=cost,
                        usage_hours=usage,
                        anomaly_score=anomaly_score,
                        severity_score=round(severity, 4),
                        details=(
                            f"Resource cost=${cost:.2f} and usage={usage:.2f}h deviate materially from "
                            f"the org baseline; anomaly score={anomaly_score:.4f}."
                        ),
                    )
                )

    if findings:
        return sorted(findings, key=lambda item: item.anomaly_score, reverse=True)

    # Fallback for small data sets where isolation forest may not produce a flagged outlier.
    costs = [float(r.cost) for r in records if r.cost is not None]
    usages = [float(r.usage_hours) for r in records if r.usage_hours is not None]
    if not costs or not usages:
        return []

    cost_median = median(costs)
    usage_median = median(usages)
    for record in records:
        if record.cost is None or record.usage_hours is None:
            continue
        cost = float(record.cost)
        usage = float(record.usage_hours)
        cost_ratio = abs(cost - cost_median) / max(abs(cost_median), 1.0)
        usage_ratio = abs(usage - usage_median) / max(abs(usage_median), 1.0)
        if max(cost_ratio, usage_ratio) > 0.35 and (cost > cost_median * 1.5 or usage > usage_median * 1.5):
            score = max(cost_ratio, usage_ratio)
            findings.append(
                AnomalyFindingResult(
                    org_id=org_id,
                    resource_id=record.resource_id,
                    service=record.service,
                    region=record.region,
                    environment=record.environment,
                    cost=cost,
                    usage_hours=usage,
                    anomaly_score=round(score, 4),
                    severity_score=round(min(1.0, score * 2.0), 4),
                    details=(
                        f"Resource cost=${cost:.2f} and usage={usage:.2f}h are materially above the org median; "
                        f"relative deviation={score:.4f}."
                    ),
                )
            )

    return sorted(findings, key=lambda item: item.anomaly_score, reverse=True)


def persist_anomaly_findings(db: Session, org_id: str, findings: List[AnomalyFindingResult]) -> int:
    """Persist anomaly findings to the database."""
    count = 0
    for finding in findings:
        db.add(
            models.AnomalyFinding(
                org_id=org_id,
                resource_id=finding.resource_id,
                service=finding.service,
                region=finding.region,
                environment=finding.environment,
                cost=finding.cost,
                usage_hours=finding.usage_hours,
                anomaly_score=finding.anomaly_score,
                severity_score=finding.severity_score,
                details=finding.details,
            )
        )
        count += 1
    db.commit()
    return count
