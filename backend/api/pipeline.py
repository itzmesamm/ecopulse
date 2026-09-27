from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.services.pipeline_service import run_organization_pipeline

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


class PipelineRequest(BaseModel):
    org_id: str
    collect: bool = False


@router.post("/run")
def run_pipeline(payload: PipelineRequest, db: Session = Depends(get_db)) -> dict:
    """Run one complete analysis pass; opt into provider collection explicitly."""
    try:
        return run_organization_pipeline(db, payload.org_id, collect=payload.collect)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
