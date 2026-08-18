"""
Cost Forecasting API endpoints — Layer 3.

Provides endpoints to:
  - Generate cost forecasts based on historical data
  - Filter forecasts by service, environment, region
  - Get forecast metadata (trend, confidence intervals)
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db import models
from backend.forecasting.forecaster import (
    forecast_costs_safe,
    CostForecast,
    ForecastResult,
)

router = APIRouter(prefix="/forecasting", tags=["forecasting"])


# ============================================================================
# Pydantic Response Models
# ============================================================================

class CostForecastResponse(BaseModel):
    """Response model for a single day's forecast."""
    forecast_date: str
    forecasted_cost_usd: float
    confidence_lower_bound: float
    confidence_upper_bound: float
    
    model_config = ConfigDict(from_attributes=True)


class ForecastMetadata(BaseModel):
    """Metadata about the forecast."""
    org_id: str
    forecast_period_days: int
    historical_days_used: int
    trend_direction: str  # "increasing", "stable", "decreasing"
    trend_value: float  # $/day
    average_historical_cost: float  # $/day baseline
    service: Optional[str]
    environment: Optional[str]
    region: Optional[str]


class ForecastResponseBody(BaseModel):
    """Complete forecast response."""
    metadata: ForecastMetadata
    forecasts: List[CostForecastResponse]


class ForecastErrorResponse(BaseModel):
    """Error response for forecast requests."""
    error_code: str
    error_message: str
    hint: str


# ============================================================================
# Pydantic Request Validation
# ============================================================================

class ForecastRequest(BaseModel):
    """Validation model for forecast request parameters."""
    forecast_days: int = Field(
        default=30,
        ge=1,
        le=90,
        description="Number of days to forecast (1-90)"
    )
    service: Optional[str] = Field(
        default=None,
        description="Filter by service (e.g., 'ec2', 'rds')"
    )
    environment: Optional[str] = Field(
        default=None,
        description="Filter by environment (e.g., 'production', 'staging')"
    )
    region: Optional[str] = Field(
        default=None,
        description="Filter by region (e.g., 'us-east-1')"
    )


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/forecast")
def get_forecast(
    org_id: str = Query(..., description="Organization ID (mandatory)"),
    forecast_days: int = Query(30, ge=1, le=90, description="Days to forecast (1-90)"),
    service: Optional[str] = Query(None, description="Filter by service"),
    environment: Optional[str] = Query(None, description="Filter by environment"),
    region: Optional[str] = Query(None, description="Filter by region"),
    db: Session = Depends(get_db),
):
    """
    Generate cost forecast for an organization.
    
    Returns daily forecasted costs with confidence intervals for the next N days.
    
    Requires at least 7 days of historical billing data to generate forecasts.
    
    **Parameters:**
    - `org_id`: Organization ID (required for multi-tenancy isolation)
    - `forecast_days`: Number of future days to forecast (1-90, default 30)
    - `service`: Optional filter by service (e.g., "ec2", "rds")
    - `environment`: Optional filter by environment (e.g., "production", "staging")
    - `region`: Optional filter by region (e.g., "us-east-1")
    
    **Response:**
    - `metadata`: Forecast statistics including trend direction and historical baseline
    - `forecasts`: Array of daily cost forecasts with confidence intervals
    
    **Errors:**
    - 400: Insufficient historical data (need 7+ days)
    - 404: Organization not found
    - 400: No data for the requested filters
    
    **Example:**
    ```
    GET /forecasting/forecast?org_id=org-123&forecast_days=30&service=ec2
    
    {
      "metadata": {
        "org_id": "org-123",
        "forecast_period_days": 30,
        "historical_days_used": 30,
        "trend_direction": "increasing",
        "trend_value": 10.5,
        "average_historical_cost": 1000.0,
        "service": "ec2",
        "environment": null,
        "region": null
      },
      "forecasts": [
        {
          "forecast_date": "2024-08-19",
          "forecasted_cost_usd": 1010.5,
          "confidence_lower_bound": 858.93,
          "confidence_upper_bound": 1162.08
        },
        ...
      ]
    }
    ```
    """
    # Validate org exists
    org = db.query(models.Organization).filter_by(id=org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Attempt forecasting
    result, error = forecast_costs_safe(
        db,
        org_id,
        forecast_days=forecast_days,
        service=service,
        environment=environment,
        region=region,
    )
    
    # Handle errors
    if error:
        if error.code == "insufficient_data":
            raise HTTPException(status_code=400, detail=error.message)
        elif error.code == "no_data_for_filters":
            raise HTTPException(status_code=400, detail=error.message)
        elif error.code == "invalid_days":
            raise HTTPException(status_code=400, detail=error.message)
        else:
            raise HTTPException(status_code=500, detail=error.message)
    
    # Build response
    metadata = ForecastMetadata(
        org_id=result.org_id,
        forecast_period_days=(result.forecast_end_date - result.forecast_start_date).days + 1,
        historical_days_used=result.historical_days_used,
        trend_direction=result.trend_direction,
        trend_value=result.trend_value,
        average_historical_cost=result.average_historical_cost,
        service=result.service,
        environment=result.environment,
        region=result.region,
    )
    
    forecasts = [
        CostForecastResponse(
            forecast_date=f.forecast_date.isoformat(),
            forecasted_cost_usd=f.forecasted_cost_usd,
            confidence_lower_bound=f.confidence_lower_bound,
            confidence_upper_bound=f.confidence_upper_bound,
        )
        for f in result.forecasts
    ]
    
    return ForecastResponseBody(metadata=metadata, forecasts=forecasts)


@router.get("/forecast-summary")
def get_forecast_summary(
    org_id: str = Query(..., description="Organization ID (mandatory)"),
    forecast_days: int = Query(30, ge=1, le=90, description="Days to forecast (1-90)"),
    service: Optional[str] = Query(None, description="Filter by service"),
    environment: Optional[str] = Query(None, description="Filter by environment"),
    region: Optional[str] = Query(None, description="Filter by region"),
    db: Session = Depends(get_db),
):
    """
    Get a summary forecast (total costs only, no daily breakdown).
    
    Returns aggregated forecast statistics without daily details.
    Useful for dashboards and high-level planning.
    
    **Response:**
    - `total_forecasted_cost_usd`: Sum of all forecasted days
    - `average_daily_cost`: Average daily forecast
    - `min_daily_cost`: Lowest daily forecast
    - `max_daily_cost`: Highest daily forecast
    - `confidence_lower_bound`: ±15% confidence interval lower bound
    - `confidence_upper_bound`: ±15% confidence interval upper bound
    - `trend_direction`: "increasing", "stable", or "decreasing"
    - `trend_value`: $/day slope
    """
    # Validate org exists
    org = db.query(models.Organization).filter_by(id=org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Attempt forecasting
    result, error = forecast_costs_safe(
        db,
        org_id,
        forecast_days=forecast_days,
        service=service,
        environment=environment,
        region=region,
    )
    
    # Handle errors
    if error:
        if error.code == "insufficient_data":
            raise HTTPException(status_code=400, detail=error.message)
        elif error.code == "no_data_for_filters":
            raise HTTPException(status_code=400, detail=error.message)
        else:
            raise HTTPException(status_code=500, detail=error.message)
    
    # Calculate summary
    costs = [f.forecasted_cost_usd for f in result.forecasts]
    total_cost = sum(costs)
    avg_cost = total_cost / len(costs) if costs else 0.0
    
    lower_bound = round(total_cost * 0.85, 2)  # -15%
    upper_bound = round(total_cost * 1.15, 2)  # +15%
    
    return {
        "org_id": result.org_id,
        "forecast_period_days": len(result.forecasts),
        "total_forecasted_cost_usd": round(total_cost, 2),
        "average_daily_cost": round(avg_cost, 2),
        "min_daily_cost": round(min(costs), 2) if costs else 0.0,
        "max_daily_cost": round(max(costs), 2) if costs else 0.0,
        "confidence_lower_bound": lower_bound,
        "confidence_upper_bound": upper_bound,
        "trend_direction": result.trend_direction,
        "trend_value": result.trend_value,
        "historical_days_used": result.historical_days_used,
    }
