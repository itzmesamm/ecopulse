from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.analysis.gpu_optimizer import detect_gpu_optimizations, persist_gpu_optimizations
from backend.db import models
from backend.db.database import get_db

router = APIRouter(prefix="/gpu-optimizer", tags=["gpu-optimizer"])


class GPUOptimizationResponse(BaseModel):
    org_id: str
    gpu_id: str
    account: Optional[str]
    environment: Optional[str]
    utilization_pct: float
    power_watts: float
    severity_score: float
    estimated_monthly_waste_usd: float
    details: str

    model_config = ConfigDict(from_attributes=True)


@router.get("/detect")
def get_gpu_optimizations(
    org_id: str = Query(..., description="Organization ID"),
    environment: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> List[GPUOptimizationResponse]:
    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    findings = detect_gpu_optimizations(db, org_id, environment=environment)
    if not findings:
        return []

    persist_gpu_optimizations(db, org_id, findings)
    return [
        GPUOptimizationResponse(
            org_id=f.org_id,
            gpu_id=f.gpu_id,
            account=f.account,
            environment=f.environment,
            utilization_pct=f.utilization_pct,
            power_watts=f.power_watts,
            severity_score=f.severity_score,
            estimated_monthly_waste_usd=f.estimated_monthly_waste_usd,
            details=f.details,
        )
        for f in findings
    ]
