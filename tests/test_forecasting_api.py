"""
API tests for cost forecasting endpoints.

Covers:
  - Endpoint exists and responds correctly
  - Organization isolation and validation
  - Filter application (service, environment, region)
  - Error responses (insufficient data, org not found)
  - Response format and structure
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
from datetime import date, timedelta
from sqlalchemy.orm import Session

from backend.main import app
from backend.db import models
from backend.db.database import get_db
from backend.forecasting.aggregator import DailyCostAggregate
from backend.forecasting.forecaster import ForecastError


client = TestClient(app)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock SQLAlchemy session."""
    return Mock(spec=Session)


@pytest.fixture
def override_db(mock_db):
    """Override get_db dependency with mock."""
    def override_get_db():
        return mock_db
    
    app.dependency_overrides[get_db] = override_get_db
    yield mock_db
    app.dependency_overrides.clear()


@pytest.fixture
def sample_org():
    """Sample organization for testing."""
    return models.Organization(
        id="test-org-123",
        name="Test Company",
    )


def create_mock_aggregates_for_api(
    org_id: str,
    start_date: date,
    num_days: int,
    base_cost: float = 1000.0,
    trend: float = 5.0,
) -> list:
    """Generate mock DailyCostAggregate objects."""
    aggregates = []
    for i in range(num_days):
        current_date = start_date + timedelta(days=i)
        cost = base_cost + (trend * i)
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
# Tests: GET /forecasting/forecast
# ============================================================================

class TestGetForecastEndpoint:
    def test_forecast_endpoint_requires_org_id(self, override_db):
        """Endpoint requires org_id parameter."""
        response = client.get("/forecasting/forecast")
        assert response.status_code == 422  # Validation error (missing required param)
    
    def test_forecast_endpoint_org_not_found(self, override_db):
        """Endpoint returns 404 if organization doesn't exist."""
        override_db.query().filter_by().first.return_value = None
        
        response = client.get("/forecasting/forecast", params={"org_id": "nonexistent-org"})
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_forecast_endpoint_insufficient_data(self, override_db):
        """Endpoint returns 400 if insufficient historical data."""
        org = models.Organization(id="test-org", name="Test")
        override_db.query().filter_by().first.return_value = org
        
        with patch("backend.api.forecasting.forecast_costs_safe") as mock_forecast:
            error = ForecastError("insufficient_data", "Need at least 7 days of data")
            mock_forecast.return_value = (None, error)
            
            response = client.get(
                "/forecasting/forecast",
                params={"org_id": "test-org"}
            )
            assert response.status_code == 400
            assert "7 days" in response.json()["detail"].lower()
    
    def test_forecast_endpoint_no_data_for_filters(self, override_db):
        """Endpoint returns 400 if filters produce no results."""
        org = models.Organization(id="test-org", name="Test")
        override_db.query().filter_by().first.return_value = org
        
        with patch("backend.api.forecasting.forecast_costs_safe") as mock_forecast:
            error = ForecastError("no_data_for_filters", "No data found for filters")
            mock_forecast.return_value = (None, error)
            
            response = client.get(
                "/forecasting/forecast",
                params={"org_id": "test-org", "service": "nonexistent"}
            )
            assert response.status_code == 400
    
    def test_forecast_endpoint_success(self, override_db):
        """Endpoint returns forecast data on success."""
        from backend.forecasting.forecaster import ForecastResult, CostForecast
        
        org = models.Organization(id="test-org", name="Test")
        override_db.query().filter_by().first.return_value = org
        
        forecasts = [
            CostForecast(
                forecast_date=date(2024, 8, 20),
                forecasted_cost_usd=1050.0,
                confidence_lower_bound=892.5,
                confidence_upper_bound=1207.5,
            ),
            CostForecast(
                forecast_date=date(2024, 8, 21),
                forecasted_cost_usd=1055.0,
                confidence_lower_bound=897.75,
                confidence_upper_bound=1212.25,
            ),
        ]
        result = ForecastResult(
            org_id="test-org",
            forecast_start_date=date(2024, 8, 20),
            forecast_end_date=date(2024, 8, 21),
            forecasts=forecasts,
            historical_days_used=14,
            trend_direction="increasing",
            trend_value=5.0,
            average_historical_cost=1025.0,
            service=None,
            environment=None,
            region=None,
        )
        
        with patch("backend.api.forecasting.forecast_costs_safe") as mock_forecast:
            mock_forecast.return_value = (result, None)
            
            response = client.get(
                "/forecasting/forecast",
                params={"org_id": "test-org", "forecast_days": 2}
            )
            assert response.status_code == 200
            
            data = response.json()
            assert "metadata" in data
            assert "forecasts" in data
            
            # Verify metadata
            assert data["metadata"]["org_id"] == "test-org"
            assert data["metadata"]["forecast_period_days"] == 2
            assert data["metadata"]["historical_days_used"] == 14
            assert data["metadata"]["trend_direction"] == "increasing"
            assert data["metadata"]["trend_value"] == 5.0
            
            # Verify forecasts
            assert len(data["forecasts"]) == 2
            assert data["forecasts"][0]["forecast_date"] == "2024-08-20"
            assert data["forecasts"][0]["forecasted_cost_usd"] == 1050.0
            assert data["forecasts"][0]["confidence_lower_bound"] == 892.5
            assert data["forecasts"][0]["confidence_upper_bound"] == 1207.5
    
    def test_forecast_endpoint_with_filters(self, override_db):
        """Endpoint passes filters to forecasting function."""
        from backend.forecasting.forecaster import ForecastResult, CostForecast
        
        org = models.Organization(id="test-org", name="Test")
        override_db.query().filter_by().first.return_value = org
        
        result = ForecastResult(
            org_id="test-org",
            forecast_start_date=date(2024, 8, 20),
            forecast_end_date=date(2024, 8, 22),
            forecasts=[],
            historical_days_used=14,
            trend_direction="stable",
            trend_value=0.0,
            average_historical_cost=1000.0,
            service="ec2",
            environment="production",
            region="us-east-1",
        )
        
        with patch("backend.api.forecasting.forecast_costs_safe") as mock_forecast:
            mock_forecast.return_value = (result, None)
            
            response = client.get(
                "/forecasting/forecast",
                params={
                    "org_id": "test-org",
                    "forecast_days": 3,
                    "service": "ec2",
                    "environment": "production",
                    "region": "us-east-1",
                }
            )
            assert response.status_code == 200
            
            # Verify filters were passed
            mock_forecast.assert_called_once()
            call_kwargs = mock_forecast.call_args[1]
            assert call_kwargs["service"] == "ec2"
            assert call_kwargs["environment"] == "production"
            assert call_kwargs["region"] == "us-east-1"
            assert call_kwargs["forecast_days"] == 3
    
    def test_forecast_endpoint_default_forecast_days(self, override_db):
        """Endpoint uses default 30 days if not specified."""
        from backend.forecasting.forecaster import ForecastResult
        
        org = models.Organization(id="test-org", name="Test")
        override_db.query().filter_by().first.return_value = org
        
        result = ForecastResult(
            org_id="test-org",
            forecast_start_date=date(2024, 8, 20),
            forecast_end_date=date(2024, 9, 18),
            forecasts=[],
            historical_days_used=14,
            trend_direction="stable",
            trend_value=0.0,
            average_historical_cost=1000.0,
            service=None,
            environment=None,
            region=None,
        )
        
        with patch("backend.api.forecasting.forecast_costs_safe") as mock_forecast:
            mock_forecast.return_value = (result, None)
            
            response = client.get("/forecasting/forecast", params={"org_id": "test-org"})
            assert response.status_code == 200
            
            # Verify default forecast_days was used
            mock_forecast.assert_called_once()
            call_kwargs = mock_forecast.call_args[1]
            assert call_kwargs["forecast_days"] == 30
    
    def test_forecast_endpoint_validates_forecast_days(self, override_db):
        """Endpoint rejects invalid forecast_days values."""
        # Test 0 days (invalid)
        response = client.get(
            "/forecasting/forecast",
            params={"org_id": "test-org", "forecast_days": 0}
        )
        assert response.status_code == 422  # Validation error
        
        # Test 91 days (too many)
        response = client.get(
            "/forecasting/forecast",
            params={"org_id": "test-org", "forecast_days": 91}
        )
        assert response.status_code == 422  # Validation error


# ============================================================================
# Tests: GET /forecasting/forecast-summary
# ============================================================================

class TestGetForecastSummaryEndpoint:
    def test_forecast_summary_requires_org_id(self, override_db):
        """Endpoint requires org_id parameter."""
        response = client.get("/forecasting/forecast-summary")
        assert response.status_code == 422
    
    def test_forecast_summary_org_not_found(self, override_db):
        """Endpoint returns 404 if organization doesn't exist."""
        override_db.query().filter_by().first.return_value = None
        
        response = client.get("/forecasting/forecast-summary", params={"org_id": "nonexistent"})
        assert response.status_code == 404
    
    def test_forecast_summary_insufficient_data(self, override_db):
        """Endpoint returns 400 if insufficient historical data."""
        org = models.Organization(id="test-org", name="Test")
        override_db.query().filter_by().first.return_value = org
        
        with patch("backend.api.forecasting.forecast_costs_safe") as mock_forecast:
            error = ForecastError("insufficient_data", "Need at least 7 days of data")
            mock_forecast.return_value = (None, error)
            
            response = client.get(
                "/forecasting/forecast-summary",
                params={"org_id": "test-org"}
            )
            assert response.status_code == 400
    
    def test_forecast_summary_success(self, override_db):
        """Endpoint returns summary forecast on success."""
        from backend.forecasting.forecaster import ForecastResult, CostForecast
        
        org = models.Organization(id="test-org", name="Test")
        override_db.query().filter_by().first.return_value = org
        
        forecasts = [
            CostForecast(
                forecast_date=date(2024, 8, 20),
                forecasted_cost_usd=1000.0,
                confidence_lower_bound=850.0,
                confidence_upper_bound=1150.0,
            ),
            CostForecast(
                forecast_date=date(2024, 8, 21),
                forecasted_cost_usd=1050.0,
                confidence_lower_bound=892.5,
                confidence_upper_bound=1207.5,
            ),
            CostForecast(
                forecast_date=date(2024, 8, 22),
                forecasted_cost_usd=1100.0,
                confidence_lower_bound=935.0,
                confidence_upper_bound=1265.0,
            ),
        ]
        result = ForecastResult(
            org_id="test-org",
            forecast_start_date=date(2024, 8, 20),
            forecast_end_date=date(2024, 8, 22),
            forecasts=forecasts,
            historical_days_used=14,
            trend_direction="increasing",
            trend_value=50.0,
            average_historical_cost=1050.0,
            service=None,
            environment=None,
            region=None,
        )
        
        with patch("backend.api.forecasting.forecast_costs_safe") as mock_forecast:
            mock_forecast.return_value = (result, None)
            
            response = client.get(
                "/forecasting/forecast-summary",
                params={"org_id": "test-org", "forecast_days": 3}
            )
            assert response.status_code == 200
            
            data = response.json()
            assert data["org_id"] == "test-org"
            assert data["forecast_period_days"] == 3
            assert data["total_forecasted_cost_usd"] == 3150.0  # 1000 + 1050 + 1100
            assert data["average_daily_cost"] == 1050.0  # 3150 / 3
            assert data["min_daily_cost"] == 1000.0
            assert data["max_daily_cost"] == 1100.0
            assert data["trend_direction"] == "increasing"
            assert data["trend_value"] == 50.0
            
            # Verify confidence intervals around total
            assert data["confidence_lower_bound"] == round(3150.0 * 0.85, 2)
            assert data["confidence_upper_bound"] == round(3150.0 * 1.15, 2)
    
    def test_forecast_summary_with_filters(self, override_db):
        """Endpoint applies service/environment/region filters."""
        from backend.forecasting.forecaster import ForecastResult, CostForecast
        
        org = models.Organization(id="test-org", name="Test")
        override_db.query().filter_by().first.return_value = org
        
        result = ForecastResult(
            org_id="test-org",
            forecast_start_date=date(2024, 8, 20),
            forecast_end_date=date(2024, 8, 20),
            forecasts=[
                CostForecast(
                    forecast_date=date(2024, 8, 20),
                    forecasted_cost_usd=500.0,
                    confidence_lower_bound=425.0,
                    confidence_upper_bound=575.0,
                )
            ],
            historical_days_used=14,
            trend_direction="stable",
            trend_value=0.0,
            average_historical_cost=500.0,
            service="rds",
            environment="staging",
            region="eu-west-1",
        )
        
        with patch("backend.api.forecasting.forecast_costs_safe") as mock_forecast:
            mock_forecast.return_value = (result, None)
            
            response = client.get(
                "/forecasting/forecast-summary",
                params={
                    "org_id": "test-org",
                    "service": "rds",
                    "environment": "staging",
                    "region": "eu-west-1",
                }
            )
            assert response.status_code == 200
            
            # Verify filters were passed
            mock_forecast.assert_called_once()
            call_kwargs = mock_forecast.call_args[1]
            assert call_kwargs["service"] == "rds"
            assert call_kwargs["environment"] == "staging"
            assert call_kwargs["region"] == "eu-west-1"


# ============================================================================
# Tests: Response Format & Validation
# ============================================================================

class TestForecastResponseFormat:
    def test_forecast_response_structure(self, override_db):
        """Response has correct JSON structure."""
        from backend.forecasting.forecaster import ForecastResult, CostForecast
        
        org = models.Organization(id="test-org", name="Test")
        override_db.query().filter_by().first.return_value = org
        
        result = ForecastResult(
            org_id="test-org",
            forecast_start_date=date(2024, 8, 20),
            forecast_end_date=date(2024, 8, 20),
            forecasts=[
                CostForecast(
                    forecast_date=date(2024, 8, 20),
                    forecasted_cost_usd=1000.0,
                    confidence_lower_bound=850.0,
                    confidence_upper_bound=1150.0,
                )
            ],
            historical_days_used=14,
            trend_direction="stable",
            trend_value=0.0,
            average_historical_cost=1000.0,
            service=None,
            environment=None,
            region=None,
        )
        
        with patch("backend.api.forecasting.forecast_costs_safe") as mock_forecast:
            mock_forecast.return_value = (result, None)
            
            response = client.get("/forecasting/forecast", params={"org_id": "test-org", "forecast_days": 1})
            
            data = response.json()
            
            # Top-level keys
            assert set(data.keys()) == {"metadata", "forecasts"}
            
            # Metadata structure
            expected_metadata_keys = {
                "org_id", "forecast_period_days", "historical_days_used",
                "trend_direction", "trend_value", "average_historical_cost",
                "service", "environment", "region"
            }
            assert set(data["metadata"].keys()) == expected_metadata_keys
            
            # Forecast item structure
            expected_forecast_keys = {
                "forecast_date", "forecasted_cost_usd",
                "confidence_lower_bound", "confidence_upper_bound"
            }
            assert set(data["forecasts"][0].keys()) == expected_forecast_keys
            
            # Data types
            assert isinstance(data["forecasts"][0]["forecast_date"], str)
            assert isinstance(data["forecasts"][0]["forecasted_cost_usd"], (int, float))
