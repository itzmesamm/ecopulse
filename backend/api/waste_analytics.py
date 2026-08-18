"""
Cost & Waste Analytics API endpoints — Layer 2.

Provides endpoints to:
  - Analyze billing records for waste
  - List identified waste items
  - Get waste analytics summary per organization
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.db.database import get_db
from backend.db import models
from backend.analysis.waste_analyzer import WasteAnalyzer, persist_waste_items

router = APIRouter(prefix="/waste-analytics", tags=["waste-analytics"])


# ============================================================================
# Pydantic Response Models
# ============================================================================

class WasteItemResponse(BaseModel):
    """Response model for a single waste item."""
    id: str
    resource_id: str
    service: str
    region: str
    environment: str
    waste_type: str
    severity_score: float
    estimated_monthly_waste_usd: float
    details: str

    class Config:
        from_attributes = True


class WasteAnalysisSummary(BaseModel):
    """Summary statistics for waste analysis."""
    org_id: str
    total_waste_items: int
    total_estimated_monthly_waste_usd: float
    avg_severity_score: float
    critical_waste_items: int  # Items with severity >= 0.8
    high_waste_items: int      # Items with severity >= 0.6 and < 0.8


class AnalysisResult(BaseModel):
    """Result of running an analysis."""
    org_id: str
    waste_items_identified: int
    total_estimated_monthly_waste_usd: float
    analysis_timestamp: str


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/analyze")
def analyze_waste(
    org_id: str = Query(..., description="Organization ID to analyze"),
    db: Session = Depends(get_db),
) -> AnalysisResult:
    """
    Analyze billing records for an organization to identify waste.
    
    This endpoint:
    1. Queries all billing records for the org
    2. Runs modular waste detection strategies
    3. Persists identified waste items to the database
    4. Returns a summary of findings
    
    Can be called periodically (e.g., daily) or on-demand.
    """
    # Verify org exists
    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Run waste analysis
    analyzer = WasteAnalyzer()
    waste_results = analyzer.analyze_records(db, org_id)
    
    # Persist results
    items_persisted = persist_waste_items(db, org_id, waste_results)
    
    total_waste = sum(r.estimated_monthly_waste_usd for r in waste_results)
    
    return AnalysisResult(
        org_id=org_id,
        waste_items_identified=items_persisted,
        total_estimated_monthly_waste_usd=round(total_waste, 2),
        analysis_timestamp=__import__("datetime").datetime.utcnow().isoformat(),
    )


@router.get("/summary")
def get_waste_summary(
    org_id: str = Query(..., description="Organization ID"),
    db: Session = Depends(get_db),
) -> WasteAnalysisSummary:
    """
    Get a summary of waste analysis results for an organization.
    
    Returns:
      - Total waste items identified
      - Total estimated monthly waste (USD)
      - Average severity score
      - Count of critical/high-severity items
    """
    # Verify org exists
    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Query waste items
    waste_items = db.query(models.WasteItem).filter(
        models.WasteItem.org_id == org_id
    ).all()
    
    if not waste_items:
        return WasteAnalysisSummary(
            org_id=org_id,
            total_waste_items=0,
            total_estimated_monthly_waste_usd=0.0,
            avg_severity_score=0.0,
            critical_waste_items=0,
            high_waste_items=0,
        )
    
    total_waste = sum(w.estimated_monthly_waste_usd for w in waste_items)
    avg_severity = sum(w.severity_score for w in waste_items) / len(waste_items)
    critical = sum(1 for w in waste_items if w.severity_score >= 0.8)
    high = sum(1 for w in waste_items if 0.6 <= w.severity_score < 0.8)
    
    return WasteAnalysisSummary(
        org_id=org_id,
        total_waste_items=len(waste_items),
        total_estimated_monthly_waste_usd=round(total_waste, 2),
        avg_severity_score=round(avg_severity, 3),
        critical_waste_items=critical,
        high_waste_items=high,
    )


@router.get("/items")
def list_waste_items(
    org_id: str = Query(..., description="Organization ID"),
    waste_type: str = Query(None, description="Filter by waste type (optional)"),
    min_severity: float = Query(0.0, description="Minimum severity score (0.0-1.0)"),
    limit: int = Query(100, description="Max results to return"),
    db: Session = Depends(get_db),
) -> list[WasteItemResponse]:
    """
    List all waste items identified for an organization.
    
    Supports filtering by:
      - waste_type: "low_utilization", "high_cost_low_usage", etc.
      - min_severity: Only return items with severity >= this value
      - limit: Maximum number of results
    
    Results are ordered by severity (highest first).
    """
    # Verify org exists
    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Build query
    query = db.query(models.WasteItem).filter(models.WasteItem.org_id == org_id)
    
    if waste_type:
        query = query.filter(models.WasteItem.waste_type == waste_type)
    
    query = query.filter(models.WasteItem.severity_score >= min_severity)
    
    # Sort by severity descending, then by cost descending
    waste_items = query.order_by(
        models.WasteItem.severity_score.desc(),
        models.WasteItem.estimated_monthly_waste_usd.desc(),
    ).limit(limit).all()
    
    return [WasteItemResponse.from_orm(item) for item in waste_items]


@router.get("/items/{item_id}")
def get_waste_item(
    item_id: str,
    db: Session = Depends(get_db),
) -> WasteItemResponse:
    """Get detailed information about a specific waste item."""
    waste_item = db.query(models.WasteItem).filter(models.WasteItem.id == item_id).first()
    
    if not waste_item:
        raise HTTPException(status_code=404, detail="Waste item not found")
    
    return WasteItemResponse.from_orm(waste_item)


@router.get("/insights/by-service")
def get_insights_by_service(
    org_id: str = Query(..., description="Organization ID"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get waste insights grouped by service type.
    
    Returns for each service:
      - count of waste items
      - total estimated waste
      - average severity
    """
    # Verify org exists
    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Query and aggregate by service
    waste_by_service = db.query(
        models.WasteItem.service,
        func.count(models.WasteItem.id).label("count"),
        func.sum(models.WasteItem.estimated_monthly_waste_usd).label("total_waste"),
        func.avg(models.WasteItem.severity_score).label("avg_severity"),
    ).filter(
        models.WasteItem.org_id == org_id
    ).group_by(
        models.WasteItem.service
    ).all()
    
    result = {}
    for service, count, total_waste, avg_severity in waste_by_service:
        result[service or "unknown"] = {
            "waste_item_count": count,
            "total_estimated_monthly_waste_usd": round(float(total_waste or 0), 2),
            "avg_severity_score": round(float(avg_severity or 0), 3),
        }
    
    return result


@router.get("/insights/by-environment")
def get_insights_by_environment(
    org_id: str = Query(..., description="Organization ID"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get waste insights grouped by environment (prod, staging, sandbox, etc).
    
    Returns for each environment:
      - count of waste items
      - total estimated waste
      - average severity
    """
    # Verify org exists
    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Query and aggregate by environment
    waste_by_env = db.query(
        models.WasteItem.environment,
        func.count(models.WasteItem.id).label("count"),
        func.sum(models.WasteItem.estimated_monthly_waste_usd).label("total_waste"),
        func.avg(models.WasteItem.severity_score).label("avg_severity"),
    ).filter(
        models.WasteItem.org_id == org_id
    ).group_by(
        models.WasteItem.environment
    ).all()
    
    result = {}
    for env, count, total_waste, avg_severity in waste_by_env:
        result[env or "unknown"] = {
            "waste_item_count": count,
            "total_estimated_monthly_waste_usd": round(float(total_waste or 0), 2),
            "avg_severity_score": round(float(avg_severity or 0), 3),
        }
    
    return result
