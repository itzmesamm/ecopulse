from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db import models
from backend.db.database import get_db

router = APIRouter(prefix="/greenops", tags=["greenops"])


class GreenOpsReport(BaseModel):
    org_id: str
    executed_recommendations_count: int
    total_dollar_savings_usd: float
    total_carbon_savings_kg: float
    estimated_energy_kwh_saved: float
    sustainability_score: float
    esg_summary: str

    top_recommendations: list[dict[str, Any]]


@router.get("/report")
def get_report(
    org_id: str = Query(..., description="Organization ID"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> GreenOpsReport:
    executed = (
        db.query(models.Recommendation)
        .filter(models.Recommendation.org_id == org_id, models.Recommendation.status == "executed")
        .order_by(models.Recommendation.created_at.desc())
        .limit(limit)
        .all()
    )

    top = [
        {
            "id": r.id,
            "resource_id": r.resource_id,
            "environment": r.environment,
            "title": r.title,
            "dollar_savings_usd": float(r.dollar_savings or 0.0),
            "carbon_savings_kg": float(r.carbon_savings_kg or 0.0),
            "suggested_action": r.suggested_action,
            "confidence_score": float(r.confidence_score or 0.0),
        }
        for r in executed
    ]

    total_dollar = sum(float(r.dollar_savings or 0.0) for r in executed)
    total_carbon = sum(float(r.carbon_savings_kg or 0.0) for r in executed)

    # Derived / heuristic report extras (kept minimal since carbon is already estimated).
    default_intensity = 0.4  # kg CO2 / kWh fallback
    estimated_energy_kwh_saved = 0.0
    if total_carbon > 0:
        estimated_energy_kwh_saved = total_carbon / default_intensity

    # Simple sustainability score: scaled and clamped into [0,100]
    sustainability_score = min(100.0, (total_carbon / 1000.0) * 25.0) if total_carbon > 0 else 0.0

    if total_carbon > 0 and total_dollar > 0:
        esg_summary = "Good alignment: cost savings and carbon savings are both being generated."
    elif total_carbon > 0:
        esg_summary = "Carbon savings are being generated; cost impact may require review."
    elif total_dollar > 0:
        esg_summary = "Cost savings are being generated; carbon savings are not detected yet."
    else:
        esg_summary = "No meaningful savings detected yet. Generate recommendations and run remediation."

    return GreenOpsReport(
        org_id=org_id,
        executed_recommendations_count=len(executed),
        total_dollar_savings_usd=round(total_dollar, 2),
        total_carbon_savings_kg=round(total_carbon, 4),
        estimated_energy_kwh_saved=round(estimated_energy_kwh_saved, 2),
        sustainability_score=round(float(sustainability_score), 2),
        esg_summary=esg_summary,
        top_recommendations=top,
    )

