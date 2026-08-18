"""
Cost & Waste Analytics API endpoints — Layer 2.

Provides endpoints to:
  - Analyze billing records for waste
  - List identified waste items
  - Get waste analytics summary per organization
  - Parameter-based filtering, sorting, and analysis
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.db.database import get_db
from backend.db import models
from backend.analysis.waste_analyzer import WasteAnalyzer, persist_waste_items, filter_and_sort_waste_items

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

    model_config = ConfigDict(from_attributes=True)


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
# Pydantic Request Validation Models
# ============================================================================

class ParameterizedAnalysisRequest(BaseModel):
    """Validation model for parameter-based analysis queries."""
    scan_type: str = Field(
        default="waste",
        description="Type of analysis: 'waste' (all), 'high_cost', or 'low_usage'"
    )
    severity_min: float = Field(
        default=0.0,
        description="Minimum severity score (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    severity_max: float = Field(
        default=1.0,
        description="Maximum severity score (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    service: Optional[str] = Field(
        default=None,
        description="Filter by service name (e.g., 'EC2', 'RDS')"
    )
    environment: Optional[str] = Field(
        default=None,
        description="Filter by environment (e.g., 'production', 'staging')"
    )
    sort_by: str = Field(
        default="severity",
        description="Sort by: 'cost', 'severity', or 'estimated_savings'"
    )
    order: str = Field(
        default="desc",
        description="Sort order: 'asc' (ascending) or 'desc' (descending)"
    )
    limit: int = Field(
        default=100,
        description="Maximum number of results to return",
        ge=1,
        le=10000
    )

    @field_validator("scan_type")
    @classmethod
    def validate_scan_type(cls, v):
        """Ensure scan_type is one of the allowed values."""
        allowed = {"waste", "high_cost", "low_usage"}
        if v not in allowed:
            raise ValueError(f"scan_type must be one of {allowed}, got '{v}'")
        return v

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, v):
        """Ensure sort_by is one of the allowed values."""
        allowed = {"cost", "severity", "estimated_savings"}
        if v not in allowed:
            raise ValueError(f"sort_by must be one of {allowed}, got '{v}'")
        return v

    @field_validator("order")
    @classmethod
    def validate_order(cls, v):
        """Ensure order is asc or desc."""
        allowed = {"asc", "desc"}
        if v not in allowed:
            raise ValueError(f"order must be one of {allowed}, got '{v}'")
        return v

    @field_validator("severity_max")
    @classmethod
    def validate_severity_range(cls, v, info):
        """Ensure severity_max >= severity_min."""
        if "severity_min" in info.data and v < info.data["severity_min"]:
            raise ValueError("severity_max must be >= severity_min")
        return v


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


@router.get("/items/advanced")
def list_waste_items_advanced(
    org_id: str = Query(..., description="Organization ID (mandatory)"),
    scan_type: str = Query("waste", description="Analysis type: 'waste', 'high_cost', or 'low_usage'"),
    severity_min: float = Query(0.0, description="Minimum severity (0.0-1.0)", ge=0.0, le=1.0),
    severity_max: float = Query(1.0, description="Maximum severity (0.0-1.0)", ge=0.0, le=1.0),
    service: str = Query(None, description="Filter by service name (optional)"),
    environment: str = Query(None, description="Filter by environment (optional)"),
    sort_by: str = Query("severity", description="Sort by: 'cost', 'severity', or 'estimated_savings'"),
    order: str = Query("desc", description="Order: 'asc' or 'desc'"),
    limit: int = Query(100, description="Max results (1-10000)", ge=1, le=10000),
    db: Session = Depends(get_db),
) -> list[WasteItemResponse]:
    """
    Advanced parameter-based waste analysis endpoint.
    
    Supports filtering, sorting, and analysis by different scan types:
      - scan_type: "waste" (all), "high_cost", or "low_usage"
      - severity_min/max: Filter by severity range [0.0-1.0]
      - service: Filter by service (optional)
      - environment: Filter by environment (optional)
      - sort_by: "cost", "severity", or "estimated_savings"
      - order: "asc" or "desc"
      - limit: Maximum results to return
    
    Example:
      /waste-analytics/items/advanced?org_id=org123&scan_type=high_cost&sort_by=cost&order=desc&limit=50
    
    Organization ID (org_id) is mandatory to ensure results remain organization-scoped.
    """
    # Verify org exists
    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Validate parameters using Pydantic model
    try:
        params = ParameterizedAnalysisRequest(
            scan_type=scan_type,
            severity_min=severity_min,
            severity_max=severity_max,
            service=service,
            environment=environment,
            sort_by=sort_by,
            order=order,
            limit=limit,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameter: {str(e)}")
    
    # Get filtered and sorted waste items
    waste_items = filter_and_sort_waste_items(
        db,
        org_id,
        scan_type=params.scan_type,
        severity_min=params.severity_min,
        severity_max=params.severity_max,
        service=params.service,
        environment=params.environment,
        sort_by=params.sort_by,
        order=params.order,
        limit=params.limit,
    )
    
    return [WasteItemResponse.from_orm(item) for item in waste_items]


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
