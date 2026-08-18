from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.analysis.cost_grouping import summarize_team_costs
from backend.db import models
from backend.db.database import get_db

router = APIRouter(prefix="/cost-grouping", tags=["cost-grouping"])


class CostGroupingResponse(BaseModel):
    org_id: str
    team: str
    owner: str
    total_cost_usd: float
    resource_count: int

    model_config = ConfigDict(from_attributes=True)


@router.get("/team-costs")
def get_team_costs(
    org_id: str = Query(..., description="Organization ID"),
    service: str | None = Query(None),
    environment: str | None = Query(None),
    region: str | None = Query(None),
    db: Session = Depends(get_db),
) -> List[CostGroupingResponse]:
    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    rows = summarize_team_costs(db, org_id, service=service, environment=environment, region=region)
    return [
        CostGroupingResponse(
            org_id=row["org_id"],
            team=row["team"],
            owner=row["owner"],
            total_cost_usd=row["total_cost_usd"],
            resource_count=row["resource_count"],
        )
        for row in rows
    ]
