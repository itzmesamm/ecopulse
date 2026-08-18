from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.analysis.anomaly_detection import detect_anomalies, persist_anomaly_findings
from backend.db import models
from backend.db.database import get_db

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


class AnomalyResponse(BaseModel):
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

    model_config = ConfigDict(from_attributes=True)


@router.get("/detect")
def get_anomalies(
    org_id: str = Query(..., description="Organization ID"),
    service: Optional[str] = Query(None),
    environment: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> List[AnomalyResponse]:
    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    findings = detect_anomalies(db, org_id, service=service, environment=environment, region=region)
    if not findings:
        return []

    persist_anomaly_findings(db, org_id, findings)
    return [
        AnomalyResponse(
            org_id=f.org_id,
            resource_id=f.resource_id,
            service=f.service,
            region=f.region,
            environment=f.environment,
            cost=f.cost,
            usage_hours=f.usage_hours,
            anomaly_score=f.anomaly_score,
            severity_score=f.severity_score,
            details=f.details,
        )
        for f in findings
    ]
