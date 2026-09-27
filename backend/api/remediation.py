from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db import models
from backend.remediation.executor import process_recommendations, approve_and_execute

router = APIRouter(prefix="/remediation", tags=["remediation"])


class RemediationProcessRequest(BaseModel):
    org_id: str
    recommendation_ids: Optional[List[str]] = Field(default=None, description="If omitted, processes up to 50 pending recommendations")
    user_role: Optional[str] = Field(default=None, description="Role used for approval logic (admin/approver/viewer)")
    dry_run: bool = True


class RemediationApproveRequest(BaseModel):
    org_id: str
    recommendation_ids: List[str]
    user_role: Optional[str] = Field(default=None, description="Role used for approval logic (admin/approver/viewer)")
    dry_run: bool = True


@router.post("/process")
def process(
    payload: RemediationProcessRequest,
    db: Session = Depends(get_db),
):
    # Ensure org exists
    org = db.query(models.Organization).filter(models.Organization.id == payload.org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if payload.recommendation_ids:
        ids = payload.recommendation_ids
    else:
        # Minimal “process next” behavior
        ids = (
            db.query(models.Recommendation.id)
            .filter(models.Recommendation.org_id == payload.org_id, models.Recommendation.status == "pending")
            .order_by(models.Recommendation.created_at.asc())
            .limit(50)
            .all()
        )
        ids = [row.id for row in ids]

    if not ids:
        return {"processed": 0, "outcomes": [], "message": "No pending recommendations found"}

    outcomes = process_recommendations(
        db=db,
        org_id=payload.org_id,
        recommendation_ids=ids,
        user_role=payload.user_role,
        dry_run=payload.dry_run,
    )
    return {"processed": len(outcomes), "outcomes": outcomes}


@router.post("/approve")
def approve(
    payload: RemediationApproveRequest,
    db: Session = Depends(get_db),
):
    org = db.query(models.Organization).filter(models.Organization.id == payload.org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    outcomes = approve_and_execute(
        db=db,
        org_id=payload.org_id,
        recommendation_ids=payload.recommendation_ids,
        user_role=payload.user_role,
        dry_run=payload.dry_run,
    )
    return {"processed": len(outcomes), "outcomes": outcomes}

