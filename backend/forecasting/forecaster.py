"""
Cost Forecasting Module — Layer 3.

Implements simple, explainable cost forecasting using:
- Exponential smoothing (7-day moving average)
- Linear trend detection (slope of last 14 days)
- Confidence intervals (±15% of forecast)

No database writes; all forecasts are computed on-demand from aggregated costs.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from statistics import mean, stdev

from backend.forecasting.aggregator import (
    aggregate_daily_costs,
    aggregate_daily_costs_range,
    get_date_range_with_data,
)


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class CostForecast:
    """A single day's cost forecast."""
    forecast_date: date
    forecasted_cost_usd: float
    confidence_lower_bound: float  # -15%
    confidence_upper_bound: float  # +15%


@dataclass
class ForecastResult:
    """Complete forecast result for a time period."""
    org_id: str
    forecast_start_date: date
    forecast_end_date: date
    forecasts: List[CostForecast]
    
    # Metadata
    historical_days_used: int
    trend_direction: str  # "increasing", "stable", "decreasing"
    trend_value: float  # $/day slope
    average_historical_cost: float  # $/day baseline
    
    # Filters applied
    service: Optional[str]
    environment: Optional[str]
    region: Optional[str]


class ForecastError(Exception):
    """Raised when forecasting cannot proceed."""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


# ============================================================================
# Helper Functions
# ============================================================================

def _exponential_smoothing(values: List[float], alpha: float = 0.2) -> float:
    """
    Calculate exponential smoothing of values.
    
    alpha=0.2 is conservative smoothing; lower alpha = more smoothing.
    """
    if not values:
        return 0.0
    
    smoothed = values[0]
    for value in values[1:]:
        smoothed = alpha * value + (1 - alpha) * smoothed
    
    return smoothed


def _moving_average(values: List[float], window: int = 7) -> float:
    """Calculate simple moving average over a window."""
    if len(values) < window:
        return mean(values) if values else 0.0
    
    return mean(values[-window:])


def _linear_regression_slope(values: List[float]) -> float:
    """
    Calculate slope of linear regression line through values.
    
    Returns: slope ($/day) showing trend direction and magnitude
    """
    if len(values) < 2:
        return 0.0
    
    n = len(values)
    x = list(range(n))
    
    # Least squares regression
    mean_x = mean(x)
    mean_y = mean(values)
    
    numerator = sum((x[i] - mean_x) * (values[i] - mean_y) for i in range(n))
    denominator = sum((x[i] - mean_x) ** 2 for i in range(n))
    
    if denominator == 0:
        return 0.0
    
    slope = numerator / denominator
    return slope


def _trend_direction(slope: float, threshold: float = 5.0) -> str:
    """Classify trend direction based on slope."""
    if abs(slope) <= threshold:
        return "stable"
    elif slope > 0:
        return "increasing"
    else:
        return "decreasing"


def _confidence_interval(value: float, confidence_pct: float = 0.15) -> Tuple[float, float]:
    """Calculate confidence bounds around a value."""
    margin = value * confidence_pct
    return (
        round(value - margin, 2),
        round(value + margin, 2),
    )


# ============================================================================
# Forecasting Engine
# ============================================================================

def forecast_costs(
    db: Session,
    org_id: str,
    forecast_days: int = 30,
    service: Optional[str] = None,
    environment: Optional[str] = None,
    region: Optional[str] = None,
    historical_window_days: int = 30,
    minimum_historical_days: int = 7,
) -> ForecastResult:
    """
    Forecast costs for an organization over a future period.
    
    Uses exponential smoothing + linear trend detection on recent historical costs.
    
    Parameters:
        db: SQLAlchemy session
        org_id: Organization ID (mandatory)
        forecast_days: Number of days to forecast (1-90)
        service: Optional filter by service
        environment: Optional filter by environment
        region: Optional filter by region
        historical_window_days: How many historical days to use (default 30)
        minimum_historical_days: Minimum required for forecasting (default 7)
    
    Returns:
        ForecastResult with daily forecasts and metadata
    
    Raises:
        ForecastError: If insufficient data, invalid org, etc.
    
    Example:
        >>> result = forecast_costs(db, "org-123", forecast_days=30, service="ec2")
        >>> for forecast in result.forecasts:
        ...     print(f"{forecast.forecast_date}: ${forecast.forecasted_cost_usd} ±${forecast.confidence_upper_bound - forecast.forecasted_cost_usd}")
    """
    # Validate parameters
    if forecast_days < 1 or forecast_days > 90:
        raise ForecastError("invalid_days", "forecast_days must be between 1 and 90")
    
    # Get date range with data for this org
    earliest_date, latest_date = get_date_range_with_data(db, org_id)
    
    if earliest_date is None or latest_date is None:
        raise ForecastError(
            "no_data",
            "No billing data found for this organization. Run /ingest first."
        )
    
    # Calculate how many days of history we have
    historical_days_available = (latest_date - earliest_date).days + 1
    
    if historical_days_available < minimum_historical_days:
        raise ForecastError(
            "insufficient_data",
            f"Need at least {minimum_historical_days} days of historical data for forecasting; "
            f"only {historical_days_available} days available. Collect more data and try again."
        )
    
    # Get historical costs (use available data or requested window, whichever is smaller)
    history_start = latest_date - timedelta(days=min(historical_window_days, historical_days_available - 1))
    
    # Aggregate daily costs for history
    daily_aggregates = aggregate_daily_costs_range(
        db,
        org_id,
        history_start,
        latest_date,
        service=service,
        environment=environment,
        region=region,
    )
    
    if not daily_aggregates:
        raise ForecastError(
            "no_data_for_filters",
            f"No billing data found for the requested filters (service={service}, "
            f"environment={environment}, region={region}). Try with fewer filters."
        )
    
    # Organize costs by date
    daily_costs = {}
    for agg in daily_aggregates:
        if agg.cost_date not in daily_costs:
            daily_costs[agg.cost_date] = 0.0
        daily_costs[agg.cost_date] += agg.total_cost_usd
    
    # Get sorted list of costs (fill gaps with 0 if any)
    date_range = [history_start + timedelta(days=i) for i in range((latest_date - history_start).days + 1)]
    cost_values = [daily_costs.get(d, 0.0) for d in date_range]
    
    # Calculate statistics
    avg_cost = mean(cost_values) if cost_values else 0.0
    trend_slope = _linear_regression_slope(cost_values)
    trend_dir = _trend_direction(trend_slope)
    
    # Generate forecasts
    forecasts = []
    last_date = latest_date
    
    for day_offset in range(1, forecast_days + 1):
        forecast_date = last_date + timedelta(days=day_offset)
        
        # Forecast = baseline + trend
        forecasted_cost = max(0.0, avg_cost + (trend_slope * day_offset))
        lower_bound, upper_bound = _confidence_interval(forecasted_cost, confidence_pct=0.15)
        
        forecasts.append(
            CostForecast(
                forecast_date=forecast_date,
                forecasted_cost_usd=round(forecasted_cost, 2),
                confidence_lower_bound=lower_bound,
                confidence_upper_bound=upper_bound,
            )
        )
    
    return ForecastResult(
        org_id=org_id,
        forecast_start_date=last_date + timedelta(days=1),
        forecast_end_date=last_date + timedelta(days=forecast_days),
        forecasts=forecasts,
        historical_days_used=len(date_range),
        trend_direction=trend_dir,
        trend_value=round(trend_slope, 2),
        average_historical_cost=round(avg_cost, 2),
        service=service,
        environment=environment,
        region=region,
    )


def forecast_costs_safe(
    db: Session,
    org_id: str,
    forecast_days: int = 30,
    service: Optional[str] = None,
    environment: Optional[str] = None,
    region: Optional[str] = None,
) -> Tuple[Optional[ForecastResult], Optional[ForecastError]]:
    """
    Wrapper around forecast_costs that returns (result, error) tuple.
    
    Useful for API endpoints that need to differentiate error types.
    
    Returns:
        (ForecastResult, None) on success
        (None, ForecastError) on failure
    """
    try:
        result = forecast_costs(
            db,
            org_id,
            forecast_days=forecast_days,
            service=service,
            environment=environment,
            region=region,
        )
        return result, None
    except ForecastError as e:
        return None, e
    except Exception as e:
        return None, ForecastError("internal_error", f"Forecasting failed: {str(e)}")
