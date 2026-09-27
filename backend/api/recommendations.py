from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.db import models
from backend.db.database import get_db
from backend.genai.embeddings import embed_and_store_logs
from backend.services.recommendation_service import generate_recommendations_for_org, save_recommendations

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


class RecommendationResponse(BaseModel):
    id: str
    org_id: str
    resource_id: Optional[str]
    service: Optional[str]
    environment: Optional[str]
    source_type: str
    recommendation_type: str
    title: str
    summary: str
    action: str
    rationale: Optional[str]
    priority: str
    confidence_score: float
    estimated_savings_usd: float
    context_json: Optional[str]
    waste_finding_id: Optional[str]
    explanation: Optional[str]
    dollar_savings: float
    carbon_savings_kg: Optional[float]
    suggested_action: Optional[str]
    status: str

    model_config = ConfigDict(from_attributes=True)


class RecommendationRequest(BaseModel):
    org_id: str
    service: Optional[str] = None
    environment: Optional[str] = None
    limit: int = 5


class LogIndexResponse(BaseModel):
    org_id: str
    embedded_logs: int


@router.post("/generate")
def generate_recommendations(
    payload: RecommendationRequest,
    db: Session = Depends(get_db),
) -> dict:
    org = db.query(models.Organization).filter(models.Organization.id == payload.org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    recommendations = generate_recommendations_for_org(
        db,
        payload.org_id,
        service=payload.service,
        environment=payload.environment,
        limit=payload.limit,
    )

    if not recommendations:
        filters = []
        if payload.service:
            filters.append(f"service={payload.service}")
        if payload.environment:
            filters.append(f"environment={payload.environment}")
        filter_text = f" ({', '.join(filters)})" if filters else ""
        raise HTTPException(
            status_code=404,
            detail=f"No Layer 2 waste findings found for this organization{filter_text}. "
            "Run /waste-analytics/analyze or remove the filters.",
        )

    saved = save_recommendations(db, payload.org_id, recommendations)
    return {
        "org_id": payload.org_id,
        "count": len(saved),
        "recommendations": [
            RecommendationResponse(
                id=item.id,
                org_id=item.org_id,
                resource_id=item.resource_id,
                service=item.service,
                environment=item.environment,
                source_type=item.source_type,
                recommendation_type=item.recommendation_type,
                title=item.title,
                summary=item.summary,
                action=item.action,
                rationale=item.rationale,
                priority=item.priority,
                confidence_score=item.confidence_score,
                estimated_savings_usd=item.estimated_savings_usd or 0.0,
                context_json=item.context_json,
                waste_finding_id=item.waste_finding_id,
                explanation=item.explanation,
                dollar_savings=item.dollar_savings or 0.0,
                carbon_savings_kg=item.carbon_savings_kg,
                suggested_action=item.suggested_action,
                status=item.status,
            )
            for item in saved
        ],
    }


@router.post("/index-logs", response_model=LogIndexResponse)
def index_logs(
    org_id: str = Query(..., description="Organization ID"),
    db: Session = Depends(get_db),
) -> LogIndexResponse:
    """Create or refresh 384-dimensional embeddings for the org's logs."""
    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    try:
        embedded_logs = embed_and_store_logs(db, org_id)
    except (RuntimeError, ValueError, ImportError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return LogIndexResponse(org_id=org_id, embedded_logs=embedded_logs)


@router.get("")
def list_recommendations(
    org_id: str = Query(..., description="Organization ID"),
    service: Optional[str] = Query(None),
    environment: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> List[RecommendationResponse]:
    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    query = db.query(models.Recommendation).filter(models.Recommendation.org_id == org_id)
    if service:
        query = query.filter(models.Recommendation.service == service)
    if environment:
        query = query.filter(models.Recommendation.environment == environment)

    rows = query.order_by(models.Recommendation.created_at.desc()).limit(limit).all()
    return [
        RecommendationResponse(
            id=row.id,
            org_id=row.org_id,
            resource_id=row.resource_id,
            service=row.service,
            environment=row.environment,
            source_type=row.source_type,
            recommendation_type=row.recommendation_type,
            title=row.title,
            summary=row.summary,
            action=row.action,
            rationale=row.rationale,
            priority=row.priority,
            confidence_score=row.confidence_score,
            estimated_savings_usd=row.estimated_savings_usd or 0.0,
            context_json=row.context_json,
            waste_finding_id=row.waste_finding_id,
            explanation=row.explanation,
            dollar_savings=row.dollar_savings or 0.0,
            carbon_savings_kg=row.carbon_savings_kg,
            suggested_action=row.suggested_action,
            status=row.status,
        )
        for row in rows
    ]
