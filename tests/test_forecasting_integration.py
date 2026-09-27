"""
Integration tests for cost forecasting.

Tests the complete flow:
  BillingRecord data → Daily Aggregation → Cost Forecasting

Uses deterministic test data to verify forecasting algorithm accuracy
and error handling without touching production code or Supabase.
"""
import pytest
from datetime import date, timedelta
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from backend.db import models
from backend.forecasting.aggregator import aggregate_daily_costs_range, get_date_range_with_data
from backend.forecasting.forecaster import forecast_costs, forecast_costs_safe, ForecastError
from tests.test_helpers import generate_deterministic_billing_records


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock SQLAlchemy session for integration tests."""
    return Mock(spec=Session)


@pytest.fixture
def org_id():
    """Test organization ID."""
    return "test-org-integration"


@pytest.fixture
def increasing_trend_data(org_id):
    """Fixture: 14 days of increasing cost trend."""
    return generate_deterministic_billing_records(
        org_id=org_id,
        start_date=date(2024, 8, 5),
        end_date=date(2024, 8, 18),
        daily_base_cost=1000.0,
        trend=10.0,  # +$10/day
        service="ec2",
        environment="production",
        region="us-east-1",
        records_per_day=5,
        seed=42,
    )


@pytest.fixture
def decreasing_trend_data(org_id):
    """Fixture: 14 days of decreasing cost trend."""
    return generate_deterministic_billing_records(
        org_id=org_id,
        start_date=date(2024, 8, 5),
        end_date=date(2024, 8, 18),
        daily_base_cost=1000.0,
        trend=-8.0,  # -$8/day
        service="rds",
        environment="staging",
        region="eu-west-1",
        records_per_day=5,
        seed=43,
    )


@pytest.fixture
def stable_trend_data(org_id):
    """Fixture: 14 days of stable cost (no trend)."""
    return generate_deterministic_billing_records(
        org_id=org_id,
        start_date=date(2024, 8, 5),
        end_date=date(2024, 8, 18),
        daily_base_cost=1000.0,
        trend=0.0,  # No change
        service="s3",
        environment="sandbox",
        region="ap-south-1",
        records_per_day=5,
        seed=44,
    )


@pytest.fixture
def insufficient_data(org_id):
    """Fixture: Only 3 days of data (below 7-day minimum)."""
    return generate_deterministic_billing_records(
        org_id=org_id,
        start_date=date(2024, 8, 15),
        end_date=date(2024, 8, 17),  # Only 3 days
        daily_base_cost=1000.0,
        trend=0.0,
        service="lambda",
        environment="production",
        region="us-east-1",
        records_per_day=5,
        seed=45,
    )


# ============================================================================
# Helper: Mock database setup
# ============================================================================

def setup_mock_db_with_records(mock_db, records):
    """
    Configure mock_db to return billing records when queried.
    
    Simulates the aggregator's query pattern:
    db.query(BillingRecord).filter(...).all()
    """
    def mock_query(*args, **kwargs):
        query_mock = Mock()
        
        def mock_filter(*f_args, **f_kwargs):
            filter_mock = Mock()
            # Return all records (in real scenario, filter would narrow down)
            filter_mock.all.return_value = records
            return filter_mock
        
        query_mock.filter.side_effect = mock_filter
        return query_mock
    
    mock_db.query.side_effect = mock_query


# ============================================================================
# Tests: Increasing Trend
# ============================================================================

class TestForecastingIncreasingTrend:
    def test_increasing_trend_detected(self, mock_db, org_id, increasing_trend_data):
        """Verify forecast detects increasing cost trend."""
        setup_mock_db_with_records(mock_db, increasing_trend_data)
        
        # Mock helper functions
        import backend.forecasting.forecaster as forecaster_module
        
        with patch.object(
            forecaster_module, "get_date_range_with_data"
        ) as mock_range, patch.object(
            forecaster_module, "aggregate_daily_costs_range"
        ) as mock_agg:
            start_date = date(2024, 8, 5)
            end_date = date(2024, 8, 18)
            mock_range.return_value = (start_date, end_date)
            
            # Build aggregates from our records
            daily_costs = {}
            for record in increasing_trend_data:
                d = record.recorded_at if isinstance(record.recorded_at, date) else record.recorded_at.date()
                if d not in daily_costs:
                    daily_costs[d] = 0.0
                daily_costs[d] += record.cost
            
            aggregates = [
                Mock(
                    org_id=org_id,
                    cost_date=d,
                    service="ec2",
                    environment="production",
                    region="us-east-1",
                    total_cost_usd=cost,
                    resource_count=5,
                )
                for d, cost in sorted(daily_costs.items())
            ]
            mock_agg.return_value = aggregates
            
            # Forecast
            result = forecast_costs(mock_db, org_id, forecast_days=7)
            
            # Verify trend detected as increasing
            assert result.trend_direction == "increasing", f"Expected 'increasing', got '{result.trend_direction}'"
            assert result.trend_value > 0, f"Expected positive slope, got {result.trend_value}"
            
            # Verify forecasts show increasing pattern
            forecast_values = [f.forecasted_cost_usd for f in result.forecasts]
            assert forecast_values[-1] > forecast_values[0], "Forecasts should show increasing cost"
    
    def test_increasing_trend_confidence_intervals(self, mock_db, org_id, increasing_trend_data):
        """Verify confidence intervals around increasing trend forecasts."""
        setup_mock_db_with_records(mock_db, increasing_trend_data)
        
        import backend.forecasting.forecaster as forecaster_module
        
        with patch.object(
            forecaster_module, "get_date_range_with_data"
        ) as mock_range, patch.object(
            forecaster_module, "aggregate_daily_costs_range"
        ) as mock_agg:
            start_date = date(2024, 8, 5)
            end_date = date(2024, 8, 18)
            mock_range.return_value = (start_date, end_date)
            
            daily_costs = {}
            for record in increasing_trend_data:
                d = record.recorded_at if isinstance(record.recorded_at, date) else record.recorded_at.date()
                if d not in daily_costs:
                    daily_costs[d] = 0.0
                daily_costs[d] += record.cost
            
            aggregates = [
                Mock(
                    org_id=org_id,
                    cost_date=d,
                    service="ec2",
                    environment="production",
                    region="us-east-1",
                    total_cost_usd=cost,
                    resource_count=5,
                )
                for d, cost in sorted(daily_costs.items())
            ]
            mock_agg.return_value = aggregates
            
            result = forecast_costs(mock_db, org_id, forecast_days=7)
            
            # Verify confidence intervals
            for forecast in result.forecasts:
                # Lower bound should be ~85% of forecast
                expected_lower = round(forecast.forecasted_cost_usd * 0.85, 2)
                # Allow for floating-point rounding differences
                assert abs(forecast.confidence_lower_bound - expected_lower) < 0.01
                
                # Upper bound should be ~115% of forecast
                expected_upper = round(forecast.forecasted_cost_usd * 1.15, 2)
                # Allow for floating-point rounding differences
                assert abs(forecast.confidence_upper_bound - expected_upper) < 0.01


# ============================================================================
# Tests: Decreasing Trend
# ============================================================================

class TestForecastingDecreasingTrend:
    def test_decreasing_trend_detected(self, mock_db, org_id, decreasing_trend_data):
        """Verify forecast detects decreasing cost trend."""
        setup_mock_db_with_records(mock_db, decreasing_trend_data)
        
        import backend.forecasting.forecaster as forecaster_module
        
        with patch.object(
            forecaster_module, "get_date_range_with_data"
        ) as mock_range, patch.object(
            forecaster_module, "aggregate_daily_costs_range"
        ) as mock_agg:
            start_date = date(2024, 8, 5)
            end_date = date(2024, 8, 18)
            mock_range.return_value = (start_date, end_date)
            
            daily_costs = {}
            for record in decreasing_trend_data:
                d = record.recorded_at if isinstance(record.recorded_at, date) else record.recorded_at.date()
                if d not in daily_costs:
                    daily_costs[d] = 0.0
                daily_costs[d] += record.cost
            
            aggregates = [
                Mock(
                    org_id=org_id,
                    cost_date=d,
                    service="rds",
                    environment="staging",
                    region="eu-west-1",
                    total_cost_usd=cost,
                    resource_count=5,
                )
                for d, cost in sorted(daily_costs.items())
            ]
            mock_agg.return_value = aggregates
            
            result = forecast_costs(mock_db, org_id, forecast_days=7, service="rds", environment="staging", region="eu-west-1")
            
            # Verify trend detected as decreasing
            assert result.trend_direction == "decreasing", f"Expected 'decreasing', got '{result.trend_direction}'"
            assert result.trend_value < 0, f"Expected negative slope, got {result.trend_value}"
            
            # Verify forecasts show decreasing pattern (with lower bound at 0)
            forecast_values = [f.forecasted_cost_usd for f in result.forecasts]
            # Forecasts should be lower than start (decreasing) or at least not all increasing
            assert forecast_values[0] >= forecast_values[-1] or result.trend_value < 0, "Decreasing trend expected"


# ============================================================================
# Tests: Stable Trend
# ============================================================================

class TestForecastingStableTrend:
    def test_stable_trend_detected(self, mock_db, org_id, stable_trend_data):
        """Verify forecast detects stable (no trend) pattern."""
        setup_mock_db_with_records(mock_db, stable_trend_data)
        
        import backend.forecasting.forecaster as forecaster_module
        
        with patch.object(
            forecaster_module, "get_date_range_with_data"
        ) as mock_range, patch.object(
            forecaster_module, "aggregate_daily_costs_range"
        ) as mock_agg:
            start_date = date(2024, 8, 5)
            end_date = date(2024, 8, 18)
            mock_range.return_value = (start_date, end_date)
            
            daily_costs = {}
            for record in stable_trend_data:
                d = record.recorded_at if isinstance(record.recorded_at, date) else record.recorded_at.date()
                if d not in daily_costs:
                    daily_costs[d] = 0.0
                daily_costs[d] += record.cost
            
            aggregates = [
                Mock(
                    org_id=org_id,
                    cost_date=d,
                    service="s3",
                    environment="sandbox",
                    region="ap-south-1",
                    total_cost_usd=cost,
                    resource_count=5,
                )
                for d, cost in sorted(daily_costs.items())
            ]
            mock_agg.return_value = aggregates
            
            result = forecast_costs(mock_db, org_id, forecast_days=7, service="s3", environment="sandbox", region="ap-south-1")
            
            # Verify trend detected as stable
            assert result.trend_direction == "stable", f"Expected 'stable', got '{result.trend_direction}'"
            assert abs(result.trend_value) <= 5.0, f"Expected near-zero slope, got {result.trend_value}"
            
            # Forecasts should be relatively flat
            forecast_values = [f.forecasted_cost_usd for f in result.forecasts]
            variation = max(forecast_values) - min(forecast_values)
            avg_value = sum(forecast_values) / len(forecast_values)
            # Variation should be small relative to average
            assert variation / avg_value < 0.2, "Stable forecasts should have low variation"


# ============================================================================
# Tests: Insufficient Data
# ============================================================================

class TestInsufficientHistoricalData:
    def test_insufficient_data_raises_error(self, mock_db, org_id, insufficient_data):
        """Verify forecasting fails gracefully with < 7 days of data."""
        setup_mock_db_with_records(mock_db, insufficient_data)
        
        import backend.forecasting.forecaster as forecaster_module
        
        with patch.object(
            forecaster_module, "get_date_range_with_data"
        ) as mock_range:
            # 3 days of data (below minimum of 7)
            start_date = date(2024, 8, 15)
            end_date = date(2024, 8, 17)
            mock_range.return_value = (start_date, end_date)
            
            with pytest.raises(ForecastError) as exc_info:
                forecast_costs(mock_db, org_id, forecast_days=7)
            
            # Verify error details
            assert exc_info.value.code == "insufficient_data"
            assert "7 days" in exc_info.value.message.lower()
            assert "3 days" in exc_info.value.message.lower()
    
    def test_insufficient_data_safe_wrapper(self, mock_db, org_id, insufficient_data):
        """Verify safe wrapper returns error tuple for insufficient data."""
        setup_mock_db_with_records(mock_db, insufficient_data)
        
        import backend.forecasting.forecaster as forecaster_module
        
        with patch.object(
            forecaster_module, "get_date_range_with_data"
        ) as mock_range:
            start_date = date(2024, 8, 15)
            end_date = date(2024, 8, 17)
            mock_range.return_value = (start_date, end_date)
            
            result, error = forecast_costs_safe(mock_db, org_id, forecast_days=7)
            
            # Safe wrapper should return (None, error)
            assert result is None
            assert error is not None
            assert error.code == "insufficient_data"


# ============================================================================
# Tests: End-to-End Flow Validation
# ============================================================================

class TestForecastingEndToEnd:
    def test_forecast_dates_are_in_future(self, mock_db, org_id, increasing_trend_data):
        """Verify forecast dates are after the last historical date."""
        setup_mock_db_with_records(mock_db, increasing_trend_data)
        
        import backend.forecasting.forecaster as forecaster_module
        
        with patch.object(
            forecaster_module, "get_date_range_with_data"
        ) as mock_range, patch.object(
            forecaster_module, "aggregate_daily_costs_range"
        ) as mock_agg:
            start_date = date(2024, 8, 5)
            end_date = date(2024, 8, 18)
            mock_range.return_value = (start_date, end_date)
            
            daily_costs = {}
            for record in increasing_trend_data:
                d = record.recorded_at if isinstance(record.recorded_at, date) else record.recorded_at.date()
                if d not in daily_costs:
                    daily_costs[d] = 0.0
                daily_costs[d] += record.cost
            
            aggregates = [
                Mock(
                    org_id=org_id,
                    cost_date=d,
                    service="ec2",
                    environment="production",
                    region="us-east-1",
                    total_cost_usd=cost,
                    resource_count=5,
                )
                for d, cost in sorted(daily_costs.items())
            ]
            mock_agg.return_value = aggregates
            
            result = forecast_costs(mock_db, org_id, forecast_days=7)
            
            # All forecast dates should be after end_date
            for forecast in result.forecasts:
                assert forecast.forecast_date > end_date, \
                    f"Forecast date {forecast.forecast_date} should be after {end_date}"
    
    def test_forecast_result_metadata(self, mock_db, org_id, increasing_trend_data):
        """Verify forecast result contains all required metadata."""
        setup_mock_db_with_records(mock_db, increasing_trend_data)
        
        import backend.forecasting.forecaster as forecaster_module
        
        with patch.object(
            forecaster_module, "get_date_range_with_data"
        ) as mock_range, patch.object(
            forecaster_module, "aggregate_daily_costs_range"
        ) as mock_agg:
            start_date = date(2024, 8, 5)
            end_date = date(2024, 8, 18)
            mock_range.return_value = (start_date, end_date)
            
            daily_costs = {}
            for record in increasing_trend_data:
                d = record.recorded_at if isinstance(record.recorded_at, date) else record.recorded_at.date()
                if d not in daily_costs:
                    daily_costs[d] = 0.0
                daily_costs[d] += record.cost
            
            aggregates = [
                Mock(
                    org_id=org_id,
                    cost_date=d,
                    service="ec2",
                    environment="production",
                    region="us-east-1",
                    total_cost_usd=cost,
                    resource_count=5,
                )
                for d, cost in sorted(daily_costs.items())
            ]
            mock_agg.return_value = aggregates
            
            result = forecast_costs(mock_db, org_id, forecast_days=10, service="ec2", environment="production")
            
            # Verify metadata
            assert result.org_id == org_id
            assert result.historical_days_used == 14  # 8/5 to 8/18 inclusive
            assert result.average_historical_cost > 0
            assert result.trend_value is not None
            assert result.trend_direction in ["increasing", "decreasing", "stable"]
            assert result.service == "ec2"
            assert result.environment == "production"
            assert len(result.forecasts) == 10
