from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.db import models
from backend.db.database import get_db
from backend.alerts.notifier import check_and_create_alerts

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertOut(BaseModel):
    id: str
    org_id: str
    alert_type: str
    message: str
    severity: str
    channel: Optional[str] = None

    class Config:
        from_attributes = True


class AlertsCheckRequest(BaseModel):
    org_id: str
    budget_limit_usd: float = Field(default=5000.0, ge=0.0)
    anomaly_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    forecast_days: int = Field(default=30, ge=1, le=90)


@router.post("/check")
def check_alerts(payload: AlertsCheckRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    created = check_and_create_alerts(
        db=db,
        org_id=payload.org_id,
        budget_limit_usd=payload.budget_limit_usd,
        anomaly_threshold=payload.anomaly_threshold,
        forecast_days=payload.forecast_days,
    )
    return {"created": created}


@router.get("")
def list_alerts(
    org_id: str = Query(..., description="Organization ID"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(models.Alert)
        .filter(models.Alert.org_id == org_id)
        .order_by(models.Alert.sent_at.desc())
        .limit(limit)
        .all()
    )
    return [
        AlertOut(
            id=row.id,
            org_id=row.org_id,
            alert_type=row.alert_type,
            message=row.message,
            severity=row.severity,
            channel=row.channel,
        )
        for row in rows
    ]

