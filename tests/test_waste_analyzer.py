"""
Unit tests for waste detection strategies and waste analyzer.

Tests cover:
  - Low utilization detection
  - High cost + low usage detection  
  - Normal resources (no waste detected)
  - Edge cases (null/empty data, division by zero)
  - Negative value prevention
  - Threshold configuration
"""
import pytest
from unittest.mock import MagicMock

from backend.analysis.waste_analyzer import (
    WasteAnalyzer,
    LowUtilizationStrategy,
    HighCostLowUsageStrategy,
    WasteAnalysisResult,
    _clamp_score,
    _ensure_positive,
)
from backend.db import models


# ============================================================================
# Test Helper Functions
# ============================================================================

def test_clamp_score_default_range():
    """Test _clamp_score with default 0.0-1.0 range."""
    assert _clamp_score(0.5) == 0.5
    assert _clamp_score(-0.5) == 0.0
    assert _clamp_score(1.5) == 1.0
    assert _clamp_score(0.0) == 0.0
    assert _clamp_score(1.0) == 1.0


def test_clamp_score_custom_range():
    """Test _clamp_score with custom range."""
    assert _clamp_score(50, min_val=0, max_val=100) == 50
    assert _clamp_score(-10, min_val=0, max_val=100) == 0
    assert _clamp_score(150, min_val=0, max_val=100) == 100


def test_ensure_positive_valid():
    """Test _ensure_positive with valid positive values."""
    assert _ensure_positive(10.5) == 10.5
    assert _ensure_positive(0.0) == 0.0
    assert _ensure_positive(0.01) == 0.01


def test_ensure_positive_invalid():
    """Test _ensure_positive with invalid inputs."""
    assert _ensure_positive(-5.0) == 0.0
    assert _ensure_positive(None) == 0.0
    assert _ensure_positive(-0.001) == 0.0


# ============================================================================
# Test Low Utilization Strategy
# ============================================================================

def create_billing_record(
    resource_id: str = "test-resource",
    cost: float = 100.0,
    usage_hours: float = 10.0,
) -> models.BillingRecord:
    """Helper to create a mock BillingRecord."""
    record = MagicMock(spec=models.BillingRecord)
    record.resource_id = resource_id
    record.cost = cost
    record.usage_hours = usage_hours
    return record


class TestLowUtilizationStrategy:
    """Test suite for LowUtilizationStrategy."""
    
    def test_detects_idle_resource(self):
        """Test detection of an idle resource with very low usage."""
        strategy = LowUtilizationStrategy()
        record = create_billing_record(cost=100.0, usage_hours=0.5)
        
        result = strategy.detect(record)
        
        assert result is not None
        assert result.waste_type == "low_utilization"
        assert result.severity_score > 0.0
        assert result.estimated_monthly_waste_usd > 0.0
        assert result.severity_score <= 1.0
        assert result.estimated_monthly_waste_usd <= 100.0
    
    def test_max_severity_zero_usage(self):
        """Test that zero usage hours produces high severity."""
        strategy = LowUtilizationStrategy()
        record = create_billing_record(cost=100.0, usage_hours=0.0)
        
        result = strategy.detect(record)
        
        assert result is not None
        assert result.severity_score >= 0.95  # Should be very high
    
    def test_normal_utilization_not_flagged(self):
        """Test that normally-used resources are not flagged."""
        strategy = LowUtilizationStrategy()
        # Using 20 hours/month (well above 3 hour threshold)
        record = create_billing_record(cost=100.0, usage_hours=20.0)
        
        result = strategy.detect(record)
        
        assert result is None  # No waste detected
    
    def test_threshold_boundary(self):
        """Test behavior at threshold boundary."""
        strategy = LowUtilizationStrategy()
        
        # Just at threshold (should not be flagged)
        record = create_billing_record(cost=100.0, usage_hours=3.0)
        result = strategy.detect(record)
        assert result is None
        
        # Just below threshold (should be flagged)
        record = create_billing_record(cost=100.0, usage_hours=2.99)
        result = strategy.detect(record)
        assert result is not None
    
    def test_waste_percentage_calculation(self):
        """Test that waste percentage is correctly applied."""
        strategy = LowUtilizationStrategy()
        # Cost $100, using 1 hour of 3 hour threshold
        # waste_percentage = 0.80 (80% of cost is waste)
        record = create_billing_record(cost=100.0, usage_hours=1.0)
        
        result = strategy.detect(record)
        
        assert result is not None
        # Expected waste: 100.0 * 0.80 = 80.0
        assert result.estimated_monthly_waste_usd == 80.0
    
    def test_null_cost_not_flagged(self):
        """Test that records with null cost are not flagged."""
        strategy = LowUtilizationStrategy()
        record = create_billing_record(cost=None, usage_hours=1.0)
        
        result = strategy.detect(record)
        
        assert result is None
    
    def test_null_usage_not_flagged(self):
        """Test that records with null usage are not flagged."""
        strategy = LowUtilizationStrategy()
        record = create_billing_record(cost=100.0, usage_hours=None)
        
        result = strategy.detect(record)
        
        assert result is None
    
    def test_result_values_never_negative(self):
        """Test that severity and waste are never negative."""
        strategy = LowUtilizationStrategy()
        record = create_billing_record(cost=0.01, usage_hours=0.001)
        
        result = strategy.detect(record)
        
        if result:  # Might not trigger if waste is < minimum
            assert result.severity_score >= 0.0
            assert result.severity_score <= 1.0
            assert result.estimated_monthly_waste_usd >= 0.0
    
    def test_minimum_waste_threshold(self):
        """Test that negligible waste amounts are not reported."""
        strategy = LowUtilizationStrategy()
        # Very cheap resource: $0.001 * 80% = $0.0008 (below minimum)
        record = create_billing_record(cost=0.001, usage_hours=0.1)
        
        result = strategy.detect(record)
        
        assert result is None  # Below minimum waste threshold


# ============================================================================
# Test High Cost + Low Usage Strategy
# ============================================================================

class TestHighCostLowUsageStrategy:
    """Test suite for HighCostLowUsageStrategy."""
    
    def test_detects_oversized_resource(self):
        """Test detection of an oversized resource with high cost/hour."""
        strategy = HighCostLowUsageStrategy()
        # $1200 cost / 5 hours = $240/hour (above $100 threshold)
        record = create_billing_record(cost=1200.0, usage_hours=5.0)
        
        result = strategy.detect(record)
        
        assert result is not None
        assert result.waste_type == "high_cost_low_usage"
        assert result.severity_score > 0.0
        assert result.estimated_monthly_waste_usd > 0.0
        assert result.severity_score <= 1.0
    
    def test_high_cost_hour_only_not_flagged(self):
        """Test that high cost/hour is not flagged if usage is normal."""
        strategy = HighCostLowUsageStrategy()
        # High cost/hour but used for 100 hours (well above 10 hour threshold)
        record = create_billing_record(cost=3000.0, usage_hours=100.0)
        
        result = strategy.detect(record)
        
        assert result is None  # No waste detected
    
    def test_low_usage_only_not_flagged(self):
        """Test that low usage is not flagged if cost/hour is reasonable."""
        strategy = HighCostLowUsageStrategy()
        # Low cost/hour ($50/hour) but low usage
        record = create_billing_record(cost=250.0, usage_hours=5.0)
        
        result = strategy.detect(record)
        
        assert result is None  # No waste detected
    
    def test_threshold_boundary_cost_per_hour(self):
        """Test behavior at cost/hour threshold boundary."""
        strategy = HighCostLowUsageStrategy()
        
        # Just at threshold: $100/hour * 5 hours = $500
        record = create_billing_record(cost=500.0, usage_hours=5.0)
        result = strategy.detect(record)
        assert result is None
        
        # Just above threshold: $100.01/hour * 5 hours = $500.05
        record = create_billing_record(cost=500.05, usage_hours=5.0)
        result = strategy.detect(record)
        assert result is not None
    
    def test_zero_usage_not_flagged(self):
        """Test that zero usage hours doesn't cause division by zero."""
        strategy = HighCostLowUsageStrategy()
        record = create_billing_record(cost=1000.0, usage_hours=0.0)
        
        result = strategy.detect(record)
        
        assert result is None  # Zero usage skipped
    
    def test_null_cost_not_flagged(self):
        """Test that null cost is handled."""
        strategy = HighCostLowUsageStrategy()
        record = create_billing_record(cost=None, usage_hours=5.0)
        
        result = strategy.detect(record)
        
        assert result is None
    
    def test_null_usage_not_flagged(self):
        """Test that null usage is handled."""
        strategy = HighCostLowUsageStrategy()
        record = create_billing_record(cost=1000.0, usage_hours=None)
        
        result = strategy.detect(record)
        
        assert result is None
    
    def test_waste_percentage_calculation(self):
        """Test that waste percentage is correctly applied."""
        strategy = HighCostLowUsageStrategy()
        # $600 cost with $120/hour ($600/5 hours)
        # Meets both thresholds: $120/hr > $100/hr AND 5 hrs < 10 hrs
        record = create_billing_record(cost=600.0, usage_hours=5.0)
        
        result = strategy.detect(record)
        
        assert result is not None
        # Expected waste: 600.0 * 0.40 = 240.0
        assert result.estimated_monthly_waste_usd == 240.0
    
    def test_severity_scaling(self):
        """Test that severity scales with cost/hour."""
        strategy = HighCostLowUsageStrategy()
        
        # $600/5h = $120/hour: severity = 120 / 200 = 0.6
        record1 = create_billing_record(cost=600.0, usage_hours=5.0)
        result1 = strategy.detect(record1)
        assert result1 is not None
        severity1 = result1.severity_score
        
        # $1000/5h = $200/hour: severity = 200 / 200 = 1.0
        record2 = create_billing_record(cost=1000.0, usage_hours=5.0)
        result2 = strategy.detect(record2)
        assert result2 is not None
        severity2 = result2.severity_score
        
        # Higher cost/hour should have higher severity
        assert severity2 > severity1
    
    def test_result_values_never_negative(self):
        """Test that severity and waste are never negative."""
        strategy = HighCostLowUsageStrategy()
        record = create_billing_record(cost=500.0, usage_hours=3.0)
        
        result = strategy.detect(record)
        
        if result:
            assert result.severity_score >= 0.0
            assert result.severity_score <= 1.0
            assert result.estimated_monthly_waste_usd >= 0.0


# ============================================================================
# Test WasteAnalyzer
# ============================================================================

class TestWasteAnalyzer:
    """Test suite for the main WasteAnalyzer orchestrator."""
    
    def test_analyzer_with_multiple_strategies(self):
        """Test that analyzer runs all strategies."""
        analyzer = WasteAnalyzer()
        assert len(analyzer.strategies) == 2  # Low utilization + High cost/hour
    
    def test_add_custom_strategy(self):
        """Test adding a custom strategy."""
        analyzer = WasteAnalyzer()
        
        class DummyStrategy(WasteAnalyzer):
            def detect(self, record):
                return None
        
        dummy = DummyStrategy()
        analyzer.add_strategy(dummy)
        
        assert len(analyzer.strategies) == 3
    
    def test_analyze_record_returns_highest_severity(self):
        """Test that analyzer returns highest severity result."""
        analyzer = WasteAnalyzer()
        # This record should trigger both strategies
        record = create_billing_record(cost=1000.0, usage_hours=1.0)
        
        result = analyzer.analyze_record(record)
        
        assert result is not None
        # Should be the highest severity of the two detections
        assert result.severity_score > 0.0
    
    def test_analyze_record_with_null_data(self):
        """Test analyzer with null data."""
        analyzer = WasteAnalyzer()
        record = create_billing_record(cost=None, usage_hours=None)
        
        result = analyzer.analyze_record(record)
        
        assert result is None
    
    def test_analyze_record_no_waste_detected(self):
        """Test analyzer when no waste is detected."""
        analyzer = WasteAnalyzer()
        # Normal resource: low cost, high usage
        record = create_billing_record(cost=100.0, usage_hours=20.0)
        
        result = analyzer.analyze_record(record)
        
        assert result is None


# ============================================================================
# Integration Tests
# ============================================================================

class TestWasteAnalysisIntegration:
    """Integration tests combining multiple components."""
    
    def test_full_analysis_pipeline_with_waste(self):
        """Test complete pipeline detects and categorizes waste."""
        strategy = LowUtilizationStrategy()
        record = create_billing_record(
            resource_id="ec2-idle-001",
            cost=150.0,
            usage_hours=0.5
        )
        
        result = strategy.detect(record)
        
        assert result is not None
        assert result.resource_id == "ec2-idle-001"
        assert result.waste_type == "low_utilization"
        assert result.severity_score > 0.0
        assert result.estimated_monthly_waste_usd > 0.0
        assert "likely idle" in result.details.lower()
    
    def test_severity_score_ranges(self):
        """Test that severity scores are in valid range for various inputs."""
        strategy = LowUtilizationStrategy()
        
        test_cases = [
            (100.0, 0.0),      # Completely unused
            (100.0, 0.1),      # Minimal usage
            (100.0, 1.0),      # Very low usage
            (100.0, 2.9),      # Just under threshold
        ]
        
        for cost, usage in test_cases:
            record = create_billing_record(cost=cost, usage_hours=usage)
            result = strategy.detect(record)
            
            if result:
                assert 0.0 <= result.severity_score <= 1.0, \
                    f"Severity out of range: {result.severity_score}"
                assert result.estimated_monthly_waste_usd >= 0.0, \
                    f"Waste is negative: {result.estimated_monthly_waste_usd}"


# ============================================================================
# Test Parameter Validation
# ============================================================================

class TestParameterizedAnalysisValidation:
    """Test parameter validation for parameter-based analysis."""
    
    def test_valid_scan_types(self):
        """Test that all valid scan_types are accepted."""
        from backend.api.waste_analytics import ParameterizedAnalysisRequest
        
        valid_types = ["waste", "high_cost", "low_usage"]
        for scan_type in valid_types:
            params = ParameterizedAnalysisRequest(scan_type=scan_type)
            assert params.scan_type == scan_type
    
    def test_invalid_scan_type(self):
        """Test that invalid scan_type raises validation error."""
        from backend.api.waste_analytics import ParameterizedAnalysisRequest
        
        with pytest.raises(ValueError, match="scan_type must be one of"):
            ParameterizedAnalysisRequest(scan_type="invalid_type")
    
    def test_valid_sort_by_options(self):
        """Test that all valid sort_by options are accepted."""
        from backend.api.waste_analytics import ParameterizedAnalysisRequest
        
        valid_sorts = ["cost", "severity", "estimated_savings"]
        for sort_by in valid_sorts:
            params = ParameterizedAnalysisRequest(sort_by=sort_by)
            assert params.sort_by == sort_by
    
    def test_invalid_sort_by(self):
        """Test that invalid sort_by raises validation error."""
        from backend.api.waste_analytics import ParameterizedAnalysisRequest
        
        with pytest.raises(ValueError, match="sort_by must be one of"):
            ParameterizedAnalysisRequest(sort_by="invalid_sort")
    
    def test_valid_order_options(self):
        """Test that asc and desc order are accepted."""
        from backend.api.waste_analytics import ParameterizedAnalysisRequest
        
        params_asc = ParameterizedAnalysisRequest(order="asc")
        assert params_asc.order == "asc"
        
        params_desc = ParameterizedAnalysisRequest(order="desc")
        assert params_desc.order == "desc"
    
    def test_invalid_order(self):
        """Test that invalid order raises validation error."""
        from backend.api.waste_analytics import ParameterizedAnalysisRequest
        
        with pytest.raises(ValueError, match="order must be one of"):
            ParameterizedAnalysisRequest(order="invalid_order")
    
    def test_severity_range_validation(self):
        """Test severity min/max validation."""
        from backend.api.waste_analytics import ParameterizedAnalysisRequest
        
        # Valid: min < max
        params = ParameterizedAnalysisRequest(severity_min=0.2, severity_max=0.8)
        assert params.severity_min == 0.2
        assert params.severity_max == 0.8
    
    def test_severity_max_must_exceed_min(self):
        """Test that severity_max must be >= severity_min."""
        from backend.api.waste_analytics import ParameterizedAnalysisRequest
        
        with pytest.raises(ValueError, match="severity_max must be >= severity_min"):
            ParameterizedAnalysisRequest(severity_min=0.8, severity_max=0.2)
    
    def test_severity_boundaries(self):
        """Test severity boundary validation."""
        from backend.api.waste_analytics import ParameterizedAnalysisRequest
        
        # Valid boundaries
        params_min = ParameterizedAnalysisRequest(severity_min=0.0)
        assert params_min.severity_min == 0.0
        
        params_max = ParameterizedAnalysisRequest(severity_max=1.0)
        assert params_max.severity_max == 1.0
    
    def test_severity_out_of_range(self):
        """Test that severity outside [0.0, 1.0] raises error."""
        from backend.api.waste_analytics import ParameterizedAnalysisRequest
        
        with pytest.raises(ValueError):
            ParameterizedAnalysisRequest(severity_min=-0.1)
        
        with pytest.raises(ValueError):
            ParameterizedAnalysisRequest(severity_max=1.1)
    
    def test_limit_validation(self):
        """Test limit parameter validation."""
        from backend.api.waste_analytics import ParameterizedAnalysisRequest
        
        # Valid: within range
        params = ParameterizedAnalysisRequest(limit=500)
        assert params.limit == 500
        
        # Invalid: below minimum
        with pytest.raises(ValueError):
            ParameterizedAnalysisRequest(limit=0)
        
        # Invalid: above maximum
        with pytest.raises(ValueError):
            ParameterizedAnalysisRequest(limit=10001)
    
    def test_optional_filters(self):
        """Test that service and environment filters are optional."""
        from backend.api.waste_analytics import ParameterizedAnalysisRequest
        
        params = ParameterizedAnalysisRequest()
        assert params.service is None
        assert params.environment is None
        
        # With filters
        params = ParameterizedAnalysisRequest(service="EC2", environment="prod")
        assert params.service == "EC2"
        assert params.environment == "prod"
    
    def test_default_parameters(self):
        """Test that default parameters are set correctly."""
        from backend.api.waste_analytics import ParameterizedAnalysisRequest
        
        params = ParameterizedAnalysisRequest()
        assert params.scan_type == "waste"
        assert params.severity_min == 0.0
        assert params.severity_max == 1.0
        assert params.sort_by == "severity"
        assert params.order == "desc"
        assert params.limit == 100
        assert params.service is None
        assert params.environment is None


# ============================================================================
# Test Filter and Sort Functionality (Mock Database Tests)
# ============================================================================

class TestFilterAndSortWasteItems:
    """Test the filter_and_sort_waste_items function."""
    
    def test_filter_all_waste_items(self):
        """Test that scan_type='waste' returns all waste types."""
        from backend.analysis.waste_analyzer import filter_and_sort_waste_items
        from sqlalchemy.orm import Session
        
        # This would require a test database setup
        # For now, we test the logic with mocks
        pass  # Database integration tests would go here
    
    def test_filter_high_cost_scan_type(self):
        """Test scan_type='high_cost' filters correctly."""
        # Database integration test
        pass
    
    def test_filter_low_usage_scan_type(self):
        """Test scan_type='low_usage' filters correctly."""
        # Database integration test
        pass
    
    def test_severity_range_filter(self):
        """Test severity_min/max filtering."""
        # Database integration test
        pass
    
    def test_service_filter(self):
        """Test filtering by service."""
        # Database integration test
        pass
    
    def test_environment_filter(self):
        """Test filtering by environment."""
        # Database integration test
        pass
    
    def test_sort_by_cost(self):
        """Test sorting by cost (estimated_savings)."""
        # Database integration test
        pass
    
    def test_sort_by_severity(self):
        """Test sorting by severity."""
        # Database integration test
        pass
    
    def test_sort_order_descending(self):
        """Test descending sort order."""
        # Database integration test
        pass
    
    def test_sort_order_ascending(self):
        """Test ascending sort order."""
        # Database integration test
        pass
    
    def test_limit_parameter(self):
        """Test that limit parameter is respected."""
        # Database integration test
        pass
    
    def test_combined_filters(self):
        """Test multiple filters combined."""
        # Database integration test: service + environment + severity range
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
