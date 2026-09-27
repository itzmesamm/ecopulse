from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from backend.db import models
from backend.db.database import get_db

router = APIRouter(prefix="/greenops", tags=["greenops"])


class GreenOpsReport(BaseModel):
    org_id: str
    executed_recommendations_count: int
    total_dollar_savings_usd: float
    total_carbon_savings_kg: float
    estimated_energy_kwh_saved: Optional[float]
    sustainability_score: float
    esg_summary: str
    savings_basis: str
    carbon_methodology: str
    carbon_estimate_coverage_pct: float

    top_recommendations: list[dict[str, Any]]


@router.get("/report")
def get_report(
    org_id: str = Query(..., description="Organization ID"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> GreenOpsReport:
    executed_query = (
        db.query(models.Recommendation)
        .filter(models.Recommendation.org_id == org_id, models.Recommendation.status == "executed")
    )
    executed = executed_query.order_by(models.Recommendation.created_at.desc()).limit(limit).all()
    totals = executed_query.with_entities(
        func.count(models.Recommendation.id),
        func.coalesce(func.sum(models.Recommendation.dollar_savings), 0.0),
        func.coalesce(func.sum(models.Recommendation.carbon_savings_kg), 0.0),
        func.sum(case((models.Recommendation.carbon_savings_kg.is_not(None), 1), else_=0)),
    ).one()
    executed_count = int(totals[0] or 0)
    total_dollar = float(totals[1] or 0.0)
    total_carbon = float(totals[2] or 0.0)
    carbon_estimate_count = int(totals[3] or 0)

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

    # The current regional-factor estimator does not persist energy per action;
    # avoid dividing by an invented average factor and present no fake precision.
    estimated_energy_kwh_saved = None

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
        executed_recommendations_count=executed_count,
        total_dollar_savings_usd=round(total_dollar, 2),
        total_carbon_savings_kg=round(total_carbon, 4),
        estimated_energy_kwh_saved=estimated_energy_kwh_saved,
        sustainability_score=round(float(sustainability_score), 2),
        esg_summary=esg_summary,
        savings_basis="model-estimated opportunity amounts for recommendations marked executed; not verified post-action savings",
        carbon_methodology="regional grid-intensity estimate using configured static factors; CCF-inspired, not a direct Cloud Carbon Footprint calculation",
        carbon_estimate_coverage_pct=round((carbon_estimate_count / executed_count) * 100, 2) if executed_count else 0.0,
        top_recommendations=top,
    )

