from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db import models
from backend.api.security import ensure_org_access, get_remediation_actor
from backend.remediation.executor import (
    approve_and_execute,
    prepare_automation_plans,
    process_recommendations,
)
from backend.remediation.aws_executor import stop_tagged_ec2_instance

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
    confirmations: dict[str, str] = Field(default_factory=dict)


class AutomationPlanRequest(BaseModel):
    org_id: str
    recommendation_ids: List[str] = Field(min_length=1, max_length=50)
    user_role: Optional[str] = None


@router.post("/plan")
def create_automation_plan(
    payload: AutomationPlanRequest,
    actor: models.UserProfile = Depends(get_remediation_actor),
    db: Session = Depends(get_db),
):
    ensure_org_access(actor, payload.org_id)
    org = db.query(models.Organization).filter(models.Organization.id == payload.org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    outcomes = prepare_automation_plans(
        db=db,
        org_id=payload.org_id,
        recommendation_ids=payload.recommendation_ids,
        actor=actor.id,
    )
    return {"processed": len(outcomes), "outcomes": outcomes}


@router.get("/history")
def automation_history(
    org_id: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
    actor: models.UserProfile = Depends(get_remediation_actor),
    db: Session = Depends(get_db),
):
    ensure_org_access(actor, org_id)
    rows = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.org_id == org_id, models.AuditLog.action_taken == "automation_plan_created")
        .order_by(models.AuditLog.executed_at.desc())
        .limit(limit)
        .all()
    )
    history = []
    for row in rows:
        try:
            plan = json.loads(row.result or "{}")
        except json.JSONDecodeError:
            continue
        history.append({
            "recommendation_id": row.recommendation_id,
            "plan": plan,
            "created_at": row.executed_at.isoformat() if row.executed_at else None,
        })
    return {"plans": history}


@router.post("/process")
def process(
    payload: RemediationProcessRequest,
    actor: models.UserProfile = Depends(get_remediation_actor),
    db: Session = Depends(get_db),
):
    ensure_org_access(actor, payload.org_id)
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

    try:
        if not payload.dry_run:
            raise HTTPException(status_code=403, detail="Live execution is only available through production approval")
        outcomes = process_recommendations(
            db=db,
            org_id=payload.org_id,
            recommendation_ids=ids,
            user_role=actor.role,
            dry_run=payload.dry_run,
            actor_id=actor.id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"processed": len(outcomes), "outcomes": outcomes}


@router.post("/approve")
def approve(
    payload: RemediationApproveRequest,
    actor: models.UserProfile = Depends(get_remediation_actor),
    db: Session = Depends(get_db),
):
    ensure_org_access(actor, payload.org_id)
    if not payload.dry_run and actor.role != "admin":
        raise HTTPException(status_code=403, detail="Live remediation requires an admin role.")
    org = db.query(models.Organization).filter(models.Organization.id == payload.org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if not payload.dry_run:
        rows = (
            db.query(models.Recommendation)
            .filter(
                models.Recommendation.org_id == payload.org_id,
                models.Recommendation.id.in_(payload.recommendation_ids),
            )
            .all()
        )
        by_id = {row.id: row for row in rows}
        for recommendation_id in payload.recommendation_ids:
            rec = by_id.get(recommendation_id)
            if rec is None:
                raise HTTPException(status_code=404, detail="Recommendation not found")
            if rec.status not in {"pending", "pending_approval"}:
                raise HTTPException(status_code=409, detail="Live execution requires a pending recommendation")
            if payload.confirmations.get(recommendation_id) != f"STOP {rec.resource_id}":
                raise HTTPException(status_code=422, detail=f"Typed confirmation is required: STOP {rec.resource_id}")

    try:
        outcomes = approve_and_execute(
            db=db,
            org_id=payload.org_id,
            recommendation_ids=payload.recommendation_ids,
            user_role=actor.role,
            dry_run=payload.dry_run,
            actor_id=actor.id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    return {"processed": len(outcomes), "outcomes": outcomes}

