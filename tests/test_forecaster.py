"""
Unit tests for cost forecasting logic.

Covers:
  - Exponential smoothing calculation
  - Trend detection (linear regression)
  - Confidence interval calculation
  - Data validation and error handling
  - Forecast generation with various data scenarios
"""
import pytest
from datetime import date, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from backend.forecasting.forecaster import (
    forecast_costs,
    forecast_costs_safe,
    _exponential_smoothing,
    _moving_average,
    _linear_regression_slope,
    _trend_direction,
    _confidence_interval,
    ForecastResult,
    CostForecast,
    ForecastError,
)
from backend.forecasting.aggregator import DailyCostAggregate


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock SQLAlchemy session."""
    return Mock(spec=Session)


def create_mock_aggregates(
    org_id: str,
    start_date: date,
    num_days: int,
    base_cost: float = 1000.0,
    trend: float = 5.0,  # $/day increase
) -> list:
    """Generate mock DailyCostAggregate objects with optional trend."""
    aggregates = []
    for i in range(num_days):
        current_date = start_date + timedelta(days=i)
        cost = base_cost + (trend * i)  # Add linear trend
        aggregates.append(
            DailyCostAggregate(
                org_id=org_id,
                cost_date=current_date,
                service="ec2",
                environment="production",
                region="us-east-1",
                total_cost_usd=cost,
                resource_count=5,
            )
        )
    return aggregates


# ============================================================================
# Tests: Mathematical Functions
# ============================================================================

class TestExponentialSmoothing:
    def test_single_value(self):
        """Exponential smoothing of single value returns that value."""
        result = _exponential_smoothing([100.0])
        assert result == 100.0
    
    def test_stable_values(self):
        """Smoothing stable values returns close to the value."""
        values = [100.0] * 10
        result = _exponential_smoothing(values)
        assert 99 < result < 101  # Close to 100
    
    def test_increasing_values(self):
        """Smoothing increasing values lags behind trend."""
        values = [100.0, 110.0, 120.0, 130.0]
        result = _exponential_smoothing(values)
        assert 100 < result < 130  # Between first and last
    
    def test_empty_list(self):
        """Smoothing empty list returns 0."""
        result = _exponential_smoothing([])
        assert result == 0.0
    
    def test_alpha_parameter(self):
        """Higher alpha gives more weight to recent values."""
        values = [100.0, 200.0]
        result_low = _exponential_smoothing(values, alpha=0.1)
        result_high = _exponential_smoothing(values, alpha=0.9)
        assert result_high > result_low  # High alpha closer to 200


class TestMovingAverage:
    def test_window_within_size(self):
        """Moving average uses all values if window exceeds size."""
        values = [10.0, 20.0, 30.0]
        result = _moving_average(values, window=10)
        assert result == 20.0  # (10+20+30)/3
    
    def test_window_exact_size(self):
        """Moving average with exact window size."""
        values = [10.0, 20.0, 30.0]
        result = _moving_average(values, window=3)
        assert result == 20.0  # (10+20+30)/3
    
    def test_window_smaller_than_size(self):
        """Moving average uses only recent values in window."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = _moving_average(values, window=2)
        assert result == 45.0  # (40+50)/2
    
    def test_empty_list(self):
        """Moving average of empty list returns 0."""
        result = _moving_average([], window=7)
        assert result == 0.0


class TestLinearRegressionSlope:
    def test_stable_values(self):
        """Slope of stable values is zero."""
        values = [100.0] * 10
        slope = _linear_regression_slope(values)
        assert abs(slope) < 0.01  # Very close to 0
    
    def test_increasing_values(self):
        """Slope of linearly increasing values is positive."""
        values = [100.0, 110.0, 120.0, 130.0, 140.0]
        slope = _linear_regression_slope(values)
        assert slope > 0
        assert 8 < slope < 12  # Slope should be ~10
    
    def test_decreasing_values(self):
        """Slope of decreasing values is negative."""
        values = [100.0, 90.0, 80.0, 70.0, 60.0]
        slope = _linear_regression_slope(values)
        assert slope < 0
        assert -12 < slope < -8  # Slope should be ~-10
    
    def test_single_value(self):
        """Slope with single value returns 0."""
        slope = _linear_regression_slope([100.0])
        assert slope == 0.0
    
    def test_empty_list(self):
        """Slope with empty list returns 0."""
        slope = _linear_regression_slope([])
        assert slope == 0.0


class TestTrendDirection:
    def test_stable_trend(self):
        """Trend near zero is stable."""
        direction = _trend_direction(2.0, threshold=5.0)
        assert direction == "stable"
    
    def test_increasing_trend(self):
        """Positive slope indicates increasing."""
        direction = _trend_direction(10.0)
        assert direction == "increasing"
    
    def test_decreasing_trend(self):
        """Negative slope indicates decreasing."""
        direction = _trend_direction(-10.0)
        assert direction == "decreasing"
    
    def test_threshold_boundary(self):
        """Slope exactly at threshold is stable."""
        direction = _trend_direction(5.0, threshold=5.0)
        assert direction == "stable"


class TestConfidenceInterval:
    def test_default_confidence(self):
        """Default 15% confidence interval."""
        lower, upper = _confidence_interval(100.0)
        assert lower == 85.0
        assert upper == 115.0
    
    def test_custom_confidence(self):
        """Custom confidence interval percentage."""
        lower, upper = _confidence_interval(100.0, confidence_pct=0.20)
        assert lower == 80.0
        assert upper == 120.0
    
    def test_zero_value(self):
        """Confidence interval of zero is (0, 0)."""
        lower, upper = _confidence_interval(0.0)
        assert lower == 0.0
        assert upper == 0.0
    
    def test_rounding(self):
        """Confidence intervals are rounded to 2 decimals."""
        lower, upper = _confidence_interval(123.456)
        assert isinstance(lower, float)
        assert isinstance(upper, float)
        assert len(str(lower).split('.')[-1]) <= 2


# ============================================================================
# Tests: Forecasting Logic
# ============================================================================

class TestForecastCostsValidation:
    def test_invalid_forecast_days_zero(self, mock_db):
        """Forecast days must be >= 1."""
        with pytest.raises(ForecastError) as exc_info:
            forecast_costs(mock_db, "org-1", forecast_days=0)
        assert exc_info.value.code == "invalid_days"
    
    def test_invalid_forecast_days_too_many(self, mock_db):
        """Forecast days must be <= 90."""
        with pytest.raises(ForecastError) as exc_info:
            forecast_costs(mock_db, "org-1", forecast_days=91)
        assert exc_info.value.code == "invalid_days"
    
    def test_no_data_for_org(self, mock_db):
        """Forecast fails if org has no billing data."""
        with patch("backend.forecasting.forecaster.get_date_range_with_data") as mock_get:
            mock_get.return_value = (None, None)
            
            with pytest.raises(ForecastError) as exc_info:
                forecast_costs(mock_db, "org-1")
            assert exc_info.value.code == "no_data"
    
    def test_insufficient_historical_data(self, mock_db):
        """Forecast fails if less than 7 days of data."""
        with patch("backend.forecasting.forecaster.get_date_range_with_data") as mock_get:
            start = date(2024, 8, 10)
            end = date(2024, 8, 12)  # Only 3 days
            mock_get.return_value = (start, end)
            
            with pytest.raises(ForecastError) as exc_info:
                forecast_costs(mock_db, "org-1", minimum_historical_days=7)
            assert exc_info.value.code == "insufficient_data"
            assert "7 days" in exc_info.value.message


class TestForecastCostsExecution:
    def test_forecast_stable_costs(self, mock_db):
        """Forecast with stable historical costs."""
        start_date = date(2024, 8, 10)
        aggregates = create_mock_aggregates("org-1", start_date, 14, base_cost=1000.0, trend=0.0)
        
        with patch("backend.forecasting.forecaster.get_date_range_with_data") as mock_range, \
             patch("backend.forecasting.forecaster.aggregate_daily_costs_range") as mock_agg:
            mock_range.return_value = (start_date, start_date + timedelta(days=13))
            mock_agg.return_value = aggregates
            
            result = forecast_costs(mock_db, "org-1", forecast_days=7)
            
            assert isinstance(result, ForecastResult)
            assert result.org_id == "org-1"
            assert len(result.forecasts) == 7
            assert result.trend_direction == "stable"
            assert all(900 < f.forecasted_cost_usd < 1100 for f in result.forecasts)
    
    def test_forecast_with_increasing_trend(self, mock_db):
        """Forecast with increasing cost trend."""
        start_date = date(2024, 8, 10)
        aggregates = create_mock_aggregates("org-1", start_date, 14, base_cost=1000.0, trend=10.0)
        
        with patch("backend.forecasting.forecaster.get_date_range_with_data") as mock_range, \
             patch("backend.forecasting.forecaster.aggregate_daily_costs_range") as mock_agg:
            mock_range.return_value = (start_date, start_date + timedelta(days=13))
            mock_agg.return_value = aggregates
            
            result = forecast_costs(mock_db, "org-1", forecast_days=5)
            
            assert result.trend_direction == "increasing"
            # Forecasts should show increasing pattern
            forecast_costs_values = [f.forecasted_cost_usd for f in result.forecasts]
            assert forecast_costs_values[-1] > forecast_costs_values[0]
    
    def test_forecast_with_decreasing_trend(self, mock_db):
        """Forecast with decreasing cost trend."""
        start_date = date(2024, 8, 10)
        aggregates = create_mock_aggregates("org-1", start_date, 14, base_cost=1000.0, trend=-10.0)
        
        with patch("backend.forecasting.forecaster.get_date_range_with_data") as mock_range, \
             patch("backend.forecasting.forecaster.aggregate_daily_costs_range") as mock_agg:
            mock_range.return_value = (start_date, start_date + timedelta(days=13))
            mock_agg.return_value = aggregates
            
            result = forecast_costs(mock_db, "org-1", forecast_days=5)
            
            assert result.trend_direction == "decreasing"
    
    def test_forecast_respects_filters(self, mock_db):
        """Forecast applies service/environment/region filters."""
        start_date = date(2024, 8, 10)
        aggregates = create_mock_aggregates("org-1", start_date, 14, base_cost=500.0, trend=5.0)
        
        with patch("backend.forecasting.forecaster.get_date_range_with_data") as mock_range, \
             patch("backend.forecasting.forecaster.aggregate_daily_costs_range") as mock_agg:
            mock_range.return_value = (start_date, start_date + timedelta(days=13))
            mock_agg.return_value = aggregates
            
            result = forecast_costs(
                mock_db,
                "org-1",
                forecast_days=7,
                service="ec2",
                environment="production",
                region="us-east-1"
            )
            
            # Verify filters were stored in result
            assert result.service == "ec2"
            assert result.environment == "production"
            assert result.region == "us-east-1"
            
            # Verify filters were passed to aggregation call
            mock_agg.assert_called_once()
            call_kwargs = mock_agg.call_args[1]
            assert call_kwargs["service"] == "ec2"
            assert call_kwargs["environment"] == "production"
            assert call_kwargs["region"] == "us-east-1"
    
    def test_forecast_no_data_for_filters(self, mock_db):
        """Forecast fails if filters return no data."""
        start_date = date(2024, 8, 10)
        
        with patch("backend.forecasting.forecaster.get_date_range_with_data") as mock_range, \
             patch("backend.forecasting.forecaster.aggregate_daily_costs_range") as mock_agg:
            mock_range.return_value = (start_date, start_date + timedelta(days=13))
            mock_agg.return_value = []  # No data for this filter
            
            with pytest.raises(ForecastError) as exc_info:
                forecast_costs(mock_db, "org-1", service="nonexistent")
            assert exc_info.value.code == "no_data_for_filters"
    
    def test_forecast_fill_gaps_in_data(self, mock_db):
        """Forecast handles gaps in historical data (treats as 0 cost)."""
        start_date = date(2024, 8, 10)
        # Create aggregates with gaps (only even days)
        aggregates = []
        for i in range(0, 14, 2):
            current_date = start_date + timedelta(days=i)
            aggregates.append(
                DailyCostAggregate(
                    org_id="org-1",
                    cost_date=current_date,
                    service="ec2",
                    environment="production",
                    region="us-east-1",
                    total_cost_usd=1000.0,
                    resource_count=5,
                )
            )
        
        with patch("backend.forecasting.forecaster.get_date_range_with_data") as mock_range, \
             patch("backend.forecasting.forecaster.aggregate_daily_costs_range") as mock_agg:
            mock_range.return_value = (start_date, start_date + timedelta(days=13))
            mock_agg.return_value = aggregates
            
            # Should not raise an error
            result = forecast_costs(mock_db, "org-1", forecast_days=7)
            assert len(result.forecasts) == 7


class TestForecastCostsSafe:
    def test_success_case(self, mock_db):
        """forecast_costs_safe returns (result, None) on success."""
        start_date = date(2024, 8, 10)
        aggregates = create_mock_aggregates("org-1", start_date, 14)
        
        with patch("backend.forecasting.forecaster.get_date_range_with_data") as mock_range, \
             patch("backend.forecasting.forecaster.aggregate_daily_costs_range") as mock_agg:
            mock_range.return_value = (start_date, start_date + timedelta(days=13))
            mock_agg.return_value = aggregates
            
            result, error = forecast_costs_safe(mock_db, "org-1")
            
            assert result is not None
            assert error is None
            assert isinstance(result, ForecastResult)
    
    def test_error_case(self, mock_db):
        """forecast_costs_safe returns (None, error) on failure."""
        with patch("backend.forecasting.forecaster.get_date_range_with_data") as mock_range:
            mock_range.return_value = (None, None)
            
            result, error = forecast_costs_safe(mock_db, "org-1")
            
            assert result is None
            assert error is not None
            assert isinstance(error, ForecastError)
            assert error.code == "no_data"


# ============================================================================
# Tests: Forecast Output
# ============================================================================

class TestForecastOutput:
    def test_forecast_dates_correct(self, mock_db):
        """Forecast dates are sequential and in the future."""
        start_date = date(2024, 8, 10)
        aggregates = create_mock_aggregates("org-1", start_date, 14)
        
        with patch("backend.forecasting.forecaster.get_date_range_with_data") as mock_range, \
             patch("backend.forecasting.forecaster.aggregate_daily_costs_range") as mock_agg:
            mock_range.return_value = (start_date, start_date + timedelta(days=13))
            mock_agg.return_value = aggregates
            
            result = forecast_costs(mock_db, "org-1", forecast_days=5)
            
            forecast_dates = [f.forecast_date for f in result.forecasts]
            
            # All dates should be after latest historical date
            assert all(d > start_date + timedelta(days=13) for d in forecast_dates)
            
            # Dates should be sequential
            for i in range(1, len(forecast_dates)):
                assert forecast_dates[i] == forecast_dates[i-1] + timedelta(days=1)
    
    def test_forecast_confidence_intervals(self, mock_db):
        """Confidence intervals are ±15% around forecast."""
        start_date = date(2024, 8, 10)
        aggregates = create_mock_aggregates("org-1", start_date, 14, base_cost=1000.0)
        
        with patch("backend.forecasting.forecaster.get_date_range_with_data") as mock_range, \
             patch("backend.forecasting.forecaster.aggregate_daily_costs_range") as mock_agg:
            mock_range.return_value = (start_date, start_date + timedelta(days=13))
            mock_agg.return_value = aggregates
            
            result = forecast_costs(mock_db, "org-1", forecast_days=3)
            
            for forecast in result.forecasts:
                # Lower bound should be ~85% of forecast
                expected_lower = round(forecast.forecasted_cost_usd * 0.85, 2)
                # Upper bound should be ~115% of forecast
                expected_upper = round(forecast.forecasted_cost_usd * 1.15, 2)
                
                assert forecast.confidence_lower_bound == expected_lower
                assert forecast.confidence_upper_bound == expected_upper
    
    def test_forecast_metadata(self, mock_db):
        """Forecast result contains proper metadata."""
        start_date = date(2024, 8, 10)
        aggregates = create_mock_aggregates("org-1", start_date, 15, base_cost=1000.0, trend=10.0)  # Trend > threshold
        
        with patch("backend.forecasting.forecaster.get_date_range_with_data") as mock_range, \
             patch("backend.forecasting.forecaster.aggregate_daily_costs_range") as mock_agg:
            mock_range.return_value = (start_date, start_date + timedelta(days=14))
            mock_agg.return_value = aggregates
            
            result = forecast_costs(mock_db, "org-1", forecast_days=10)
            
            assert result.org_id == "org-1"
            assert result.forecast_start_date == start_date + timedelta(days=15)
            assert result.forecast_end_date == start_date + timedelta(days=24)
            assert result.historical_days_used == 15
            assert result.average_historical_cost > 0
            assert result.trend_value > 0  # Increasing trend
            assert result.trend_direction == "increasing"
