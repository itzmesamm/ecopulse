"""
Unit tests for Cost Aggregation Module.

Tests cover:
  - Daily cost aggregation (single date)
  - Date range aggregation
  - Filtering by service, environment, region
  - Organization isolation
  - Multiple records per dimension
  - Empty data handling
  - Summary calculations
  - Date range queries
"""
import pytest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from backend.forecasting.aggregator import (
    DailyCostAggregate,
    aggregate_daily_costs,
    aggregate_daily_costs_range,
    aggregate_daily_costs_summary,
    get_latest_cost_date,
    get_date_range_with_data,
)
from backend.db import models


# ============================================================================
# Test Helpers
# ============================================================================

def create_mock_billing_record(
    org_id: str = "org-123",
    resource_id: str = "res-1",
    service: str = "ec2",
    environment: str = "production",
    region: str = "us-east-1",
    cost: float = 100.0,
    usage_hours: float = 24.0,
    recorded_at: datetime = None,
) -> models.BillingRecord:
    """Create a mock BillingRecord for testing."""
    if recorded_at is None:
        recorded_at = datetime(2024, 8, 18, 12, 0, 0)
    
    record = MagicMock(spec=models.BillingRecord)
    record.org_id = org_id
    record.resource_id = resource_id
    record.service = service
    record.environment = environment
    record.region = region
    record.cost = cost
    record.usage_hours = usage_hours
    record.recorded_at = recorded_at
    record.id = resource_id  # For counting
    return record


# ============================================================================
# Test DailyCostAggregate Dataclass
# ============================================================================

class TestDailyCostAggregate:
    """Test the DailyCostAggregate dataclass."""
    
    def test_aggregate_creation(self):
        """Test creating a DailyCostAggregate."""
        agg = DailyCostAggregate(
            org_id="org-123",
            cost_date=date(2024, 8, 18),
            service="ec2",
            environment="production",
            region="us-east-1",
            total_cost_usd=1234.56,
            resource_count=5,
        )
        
        assert agg.org_id == "org-123"
        assert agg.cost_date == date(2024, 8, 18)
        assert agg.service == "ec2"
        assert agg.environment == "production"
        assert agg.region == "us-east-1"
        assert agg.total_cost_usd == 1234.56
        assert agg.resource_count == 5


# ============================================================================
# Test aggregate_daily_costs (Single Day)
# ============================================================================

class TestAggregateDailyCosts:
    """Test the aggregate_daily_costs function."""
    
    def test_multiple_records_same_date_summed(self):
        """Test that multiple records on the same date are summed."""
        mock_db = MagicMock(spec=Session)
        
        # Create mock query result: two EC2 production records that should be combined
        result_row = MagicMock()
        result_row.service = "ec2"
        result_row.environment = "production"
        result_row.region = "us-east-1"
        result_row.total_cost = 250.0  # Sum of 100 + 150
        result_row.resource_count = 2
        
        # Set up mock query chain
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [result_row]
        
        # Call aggregation
        aggs = aggregate_daily_costs(
            mock_db,
            "org-123",
            date(2024, 8, 18),
        )
        
        # Verify
        assert len(aggs) == 1
        assert aggs[0].total_cost_usd == 250.0
        assert aggs[0].resource_count == 2
        assert aggs[0].service == "ec2"
    
    def test_different_services_grouped_separately(self):
        """Test that different services are returned as separate groups."""
        mock_db = MagicMock(spec=Session)
        
        # Create mock results: one EC2 row and one RDS row
        ec2_row = MagicMock()
        ec2_row.service = "ec2"
        ec2_row.environment = "production"
        ec2_row.region = "us-east-1"
        ec2_row.total_cost = 500.0
        ec2_row.resource_count = 3
        
        rds_row = MagicMock()
        rds_row.service = "rds"
        rds_row.environment = "production"
        rds_row.region = "us-east-1"
        rds_row.total_cost = 300.0
        rds_row.resource_count = 2
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [ec2_row, rds_row]
        
        aggs = aggregate_daily_costs(mock_db, "org-123", date(2024, 8, 18))
        
        assert len(aggs) == 2
        assert aggs[0].service == "ec2"
        assert aggs[0].total_cost_usd == 500.0
        assert aggs[1].service == "rds"
        assert aggs[1].total_cost_usd == 300.0
    
    def test_different_environments_grouped_separately(self):
        """Test that different environments are grouped separately."""
        mock_db = MagicMock(spec=Session)
        
        prod_row = MagicMock()
        prod_row.service = "ec2"
        prod_row.environment = "production"
        prod_row.region = "us-east-1"
        prod_row.total_cost = 500.0
        prod_row.resource_count = 2
        
        staging_row = MagicMock()
        staging_row.service = "ec2"
        staging_row.environment = "staging"
        staging_row.region = "us-east-1"
        staging_row.total_cost = 100.0
        staging_row.resource_count = 1
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [prod_row, staging_row]
        
        aggs = aggregate_daily_costs(mock_db, "org-123", date(2024, 8, 18))
        
        assert len(aggs) == 2
        assert aggs[0].environment == "production"
        assert aggs[1].environment == "staging"
    
    def test_different_regions_grouped_separately(self):
        """Test that different regions are grouped separately."""
        mock_db = MagicMock(spec=Session)
        
        us_east_row = MagicMock()
        us_east_row.service = "ec2"
        us_east_row.environment = "production"
        us_east_row.region = "us-east-1"
        us_east_row.total_cost = 300.0
        us_east_row.resource_count = 2
        
        eu_west_row = MagicMock()
        eu_west_row.service = "ec2"
        eu_west_row.environment = "production"
        eu_west_row.region = "eu-west-1"
        eu_west_row.total_cost = 200.0
        eu_west_row.resource_count = 1
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [us_east_row, eu_west_row]
        
        aggs = aggregate_daily_costs(mock_db, "org-123", date(2024, 8, 18))
        
        assert len(aggs) == 2
        assert aggs[0].region == "us-east-1"
        assert aggs[1].region == "eu-west-1"
    
    def test_org_id_keeps_orgs_isolated(self):
        """Test that org_id is used in filtering (isolation)."""
        mock_db = MagicMock(spec=Session)
        
        result_row = MagicMock()
        result_row.service = "ec2"
        result_row.environment = "production"
        result_row.region = "us-east-1"
        result_row.total_cost = 100.0
        result_row.resource_count = 1
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [result_row]
        
        # Call with org-123
        aggs = aggregate_daily_costs(mock_db, "org-123", date(2024, 8, 18))
        
        # Verify filter was called with org_id
        assert mock_query.filter.called
        # The aggregates should have the correct org_id
        assert aggs[0].org_id == "org-123"
    
    def test_service_filter_applied(self):
        """Test that service filter is applied."""
        mock_db = MagicMock(spec=Session)
        
        result_row = MagicMock()
        result_row.service = "ec2"
        result_row.environment = "production"
        result_row.region = "us-east-1"
        result_row.total_cost = 100.0
        result_row.resource_count = 1
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [result_row]
        
        # Call with service filter
        aggs = aggregate_daily_costs(
            mock_db,
            "org-123",
            date(2024, 8, 18),
            service="ec2",
        )
        
        # Verify
        assert mock_query.filter.call_count >= 2  # org_id filter + service filter
        assert len(aggs) == 1
    
    def test_environment_filter_applied(self):
        """Test that environment filter is applied."""
        mock_db = MagicMock(spec=Session)
        
        result_row = MagicMock()
        result_row.service = "ec2"
        result_row.environment = "production"
        result_row.region = "us-east-1"
        result_row.total_cost = 100.0
        result_row.resource_count = 1
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [result_row]
        
        aggs = aggregate_daily_costs(
            mock_db,
            "org-123",
            date(2024, 8, 18),
            environment="production",
        )
        
        assert mock_query.filter.call_count >= 2
        assert len(aggs) == 1
    
    def test_region_filter_applied(self):
        """Test that region filter is applied."""
        mock_db = MagicMock(spec=Session)
        
        result_row = MagicMock()
        result_row.service = "ec2"
        result_row.environment = "production"
        result_row.region = "us-east-1"
        result_row.total_cost = 100.0
        result_row.resource_count = 1
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [result_row]
        
        aggs = aggregate_daily_costs(
            mock_db,
            "org-123",
            date(2024, 8, 18),
            region="us-east-1",
        )
        
        assert mock_query.filter.call_count >= 2
        assert len(aggs) == 1
    
    def test_combined_filters_applied(self):
        """Test that multiple filters work together."""
        mock_db = MagicMock(spec=Session)
        
        result_row = MagicMock()
        result_row.service = "ec2"
        result_row.environment = "production"
        result_row.region = "us-east-1"
        result_row.total_cost = 100.0
        result_row.resource_count = 1
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [result_row]
        
        aggs = aggregate_daily_costs(
            mock_db,
            "org-123",
            date(2024, 8, 18),
            service="ec2",
            environment="production",
            region="us-east-1",
        )
        
        # All filters should be applied (org_id + 3 optional filters)
        assert mock_query.filter.call_count >= 4
        assert len(aggs) == 1
    
    def test_empty_data_returns_empty_list(self):
        """Test that empty data returns an empty list."""
        mock_db = MagicMock(spec=Session)
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = []  # No results
        
        aggs = aggregate_daily_costs(mock_db, "org-123", date(2024, 8, 18))
        
        assert aggs == []
    
    def test_costs_rounded_to_two_decimals(self):
        """Test that costs are rounded to 2 decimal places."""
        mock_db = MagicMock(spec=Session)
        
        result_row = MagicMock()
        result_row.service = "ec2"
        result_row.environment = "production"
        result_row.region = "us-east-1"
        result_row.total_cost = 100.12345  # Unrounded
        result_row.resource_count = 1
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [result_row]
        
        aggs = aggregate_daily_costs(mock_db, "org-123", date(2024, 8, 18))
        
        assert aggs[0].total_cost_usd == 100.12  # Rounded


# ============================================================================
# Test aggregate_daily_costs_range (Date Range)
# ============================================================================

class TestAggregateDailyCostsRange:
    """Test the aggregate_daily_costs_range function."""
    
    def test_date_range_aggregation_works(self):
        """Test that date range aggregation calls single-day aggregation."""
        mock_db = MagicMock(spec=Session)
        
        # Create mock results for 3 days
        day1_result = MagicMock()
        day1_result.service = "ec2"
        day1_result.environment = "production"
        day1_result.region = "us-east-1"
        day1_result.total_cost = 100.0
        day1_result.resource_count = 1
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [day1_result]
        
        # Call with 3-day range
        aggs = aggregate_daily_costs_range(
            mock_db,
            "org-123",
            date(2024, 8, 18),
            date(2024, 8, 20),
        )
        
        # Should have results for 3 days (mock returns 1 result per day)
        assert len(aggs) == 3
    
    def test_single_day_range(self):
        """Test date range aggregation with same start and end date."""
        mock_db = MagicMock(spec=Session)
        
        result_row = MagicMock()
        result_row.service = "ec2"
        result_row.environment = "production"
        result_row.region = "us-east-1"
        result_row.total_cost = 100.0
        result_row.resource_count = 1
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [result_row]
        
        aggs = aggregate_daily_costs_range(
            mock_db,
            "org-123",
            date(2024, 8, 18),
            date(2024, 8, 18),
        )
        
        # Should have 1 result (single day)
        assert len(aggs) == 1
        assert aggs[0].cost_date == date(2024, 8, 18)
    
    def test_range_with_filters_applied(self):
        """Test that filters are applied across date range."""
        mock_db = MagicMock(spec=Session)
        
        result_row = MagicMock()
        result_row.service = "ec2"
        result_row.environment = "production"
        result_row.region = "us-east-1"
        result_row.total_cost = 100.0
        result_row.resource_count = 1
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [result_row]
        
        aggs = aggregate_daily_costs_range(
            mock_db,
            "org-123",
            date(2024, 8, 18),
            date(2024, 8, 20),
            service="ec2",
            environment="production",
            region="us-east-1",
        )
        
        # Should still return filtered results
        assert len(aggs) == 3
        for agg in aggs:
            assert agg.service == "ec2"
            assert agg.environment == "production"
            assert agg.region == "us-east-1"
    
    def test_empty_date_range_returns_empty_list(self):
        """Test that empty date range returns empty list."""
        mock_db = MagicMock(spec=Session)
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = []  # No results
        
        aggs = aggregate_daily_costs_range(
            mock_db,
            "org-123",
            date(2024, 8, 18),
            date(2024, 8, 20),
        )
        
        # Should have empty results for 3 days
        assert aggs == []
    
    def test_dates_increment_correctly(self):
        """Test that dates increment by 1 day each iteration."""
        mock_db = MagicMock(spec=Session)
        
        result_row = MagicMock()
        result_row.service = "ec2"
        result_row.environment = "production"
        result_row.region = "us-east-1"
        result_row.total_cost = 100.0
        result_row.resource_count = 1
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [result_row]
        
        start_date = date(2024, 8, 18)
        end_date = date(2024, 8, 20)
        
        aggs = aggregate_daily_costs_range(
            mock_db,
            "org-123",
            start_date,
            end_date,
        )
        
        # Verify cost_dates increment correctly
        assert aggs[0].cost_date == date(2024, 8, 18)
        assert aggs[1].cost_date == date(2024, 8, 19)
        assert aggs[2].cost_date == date(2024, 8, 20)


# ============================================================================
# Test aggregate_daily_costs_summary
# ============================================================================

class TestAggregateDailyCostsSummary:
    """Test the aggregate_daily_costs_summary function."""
    
    def test_summary_totals_calculated(self):
        """Test that summary correctly totals costs."""
        mock_db = MagicMock(spec=Session)
        
        # Create results for 2 services
        ec2_row = MagicMock()
        ec2_row.service = "ec2"
        ec2_row.environment = "production"
        ec2_row.region = "us-east-1"
        ec2_row.total_cost = 500.0
        ec2_row.resource_count = 2
        
        rds_row = MagicMock()
        rds_row.service = "rds"
        rds_row.environment = "production"
        rds_row.region = "us-east-1"
        rds_row.total_cost = 300.0
        rds_row.resource_count = 1
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [ec2_row, rds_row]
        
        summary = aggregate_daily_costs_summary(mock_db, "org-123", date(2024, 8, 18))
        
        assert summary['total_cost_usd'] == 800.0
        assert summary['resource_count'] == 3
        assert summary['dimension_count'] == 2
    
    def test_summary_by_service(self):
        """Test that summary correctly groups by service."""
        mock_db = MagicMock(spec=Session)
        
        ec2_row = MagicMock()
        ec2_row.service = "ec2"
        ec2_row.environment = "production"
        ec2_row.region = "us-east-1"
        ec2_row.total_cost = 500.0
        ec2_row.resource_count = 2
        
        rds_row = MagicMock()
        rds_row.service = "rds"
        rds_row.environment = "production"
        rds_row.region = "us-east-1"
        rds_row.total_cost = 300.0
        rds_row.resource_count = 1
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [ec2_row, rds_row]
        
        summary = aggregate_daily_costs_summary(mock_db, "org-123", date(2024, 8, 18))
        
        assert summary['by_service']['ec2'] == 500.0
        assert summary['by_service']['rds'] == 300.0
    
    def test_summary_by_environment(self):
        """Test that summary correctly groups by environment."""
        mock_db = MagicMock(spec=Session)
        
        prod_row = MagicMock()
        prod_row.service = "ec2"
        prod_row.environment = "production"
        prod_row.region = "us-east-1"
        prod_row.total_cost = 500.0
        prod_row.resource_count = 2
        
        staging_row = MagicMock()
        staging_row.service = "ec2"
        staging_row.environment = "staging"
        staging_row.region = "us-east-1"
        staging_row.total_cost = 100.0
        staging_row.resource_count = 1
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [prod_row, staging_row]
        
        summary = aggregate_daily_costs_summary(mock_db, "org-123", date(2024, 8, 18))
        
        assert summary['by_environment']['production'] == 500.0
        assert summary['by_environment']['staging'] == 100.0
    
    def test_summary_by_region(self):
        """Test that summary correctly groups by region."""
        mock_db = MagicMock(spec=Session)
        
        us_east_row = MagicMock()
        us_east_row.service = "ec2"
        us_east_row.environment = "production"
        us_east_row.region = "us-east-1"
        us_east_row.total_cost = 300.0
        us_east_row.resource_count = 2
        
        eu_west_row = MagicMock()
        eu_west_row.service = "ec2"
        eu_west_row.environment = "production"
        eu_west_row.region = "eu-west-1"
        eu_west_row.total_cost = 200.0
        eu_west_row.resource_count = 1
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [us_east_row, eu_west_row]
        
        summary = aggregate_daily_costs_summary(mock_db, "org-123", date(2024, 8, 18))
        
        assert summary['by_region']['us-east-1'] == 300.0
        assert summary['by_region']['eu-west-1'] == 200.0


# ============================================================================
# Test get_latest_cost_date
# ============================================================================

class TestGetLatestCostDate:
    """Test the get_latest_cost_date function."""
    
    def test_returns_latest_date(self):
        """Test that latest cost date is returned."""
        mock_db = MagicMock(spec=Session)
        
        result = MagicMock()
        result.latest_date = date(2024, 8, 18)
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = result
        
        latest = get_latest_cost_date(mock_db, "org-123")
        
        assert latest == date(2024, 8, 18)
    
    def test_returns_none_when_no_data(self):
        """Test that None is returned when no data exists."""
        mock_db = MagicMock(spec=Session)
        
        result = MagicMock()
        result.latest_date = None
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = result
        
        latest = get_latest_cost_date(mock_db, "org-123")
        
        assert latest is None


# ============================================================================
# Test get_date_range_with_data
# ============================================================================

class TestGetDateRangeWithData:
    """Test the get_date_range_with_data function."""
    
    def test_returns_date_range(self):
        """Test that date range is returned."""
        mock_db = MagicMock(spec=Session)
        
        result = MagicMock()
        result.earliest = date(2024, 8, 1)
        result.latest = date(2024, 8, 18)
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = result
        
        earliest, latest = get_date_range_with_data(mock_db, "org-123")
        
        assert earliest == date(2024, 8, 1)
        assert latest == date(2024, 8, 18)
    
    def test_returns_none_when_no_data(self):
        """Test that (None, None) is returned when no data exists."""
        mock_db = MagicMock(spec=Session)
        
        result = MagicMock()
        result.earliest = None
        result.latest = None
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = result
        
        earliest, latest = get_date_range_with_data(mock_db, "org-123")
        
        assert earliest is None
        assert latest is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
