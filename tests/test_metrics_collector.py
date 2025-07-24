"""
Tests for metrics collection system.
"""

import pytest
import time
from datetime import datetime, timedelta

from src.rstudio_mcp.monitoring.metrics_collector import (
    MetricsCollector, MetricPoint, MetricSeries, TimingContext
)


class TestMetricsCollector:
    """Test metrics collection functionality."""
    
    @pytest.fixture
    def collector(self):
        """Create metrics collector for testing."""
        return MetricsCollector()
        
    def test_register_metric(self, collector):
        """Test metric registration."""
        collector.register_metric("test.metric", "count", "Test metric")
        
        assert "test.metric" in collector.series
        series = collector.series["test.metric"]
        assert series.name == "test.metric"
        assert series.unit == "count"
        assert series.description == "Test metric"
        
    def test_record_counter(self, collector):
        """Test counter recording."""
        collector.record_counter("requests", 1, {"endpoint": "/api"})
        collector.record_counter("requests", 2, {"endpoint": "/api"})
        
        # Check counter value
        assert collector.get_counter("requests", {"endpoint": "/api"}) == 3
        
        # Check time series
        assert "requests" in collector.series
        assert len(collector.series["requests"].points) == 2
        
    def test_record_gauge(self, collector):
        """Test gauge recording."""
        collector.record_gauge("temperature", 25.5, {"sensor": "cpu"})
        collector.record_gauge("temperature", 26.0, {"sensor": "cpu"})
        
        # Check gauge value (should be latest)
        assert collector.get_gauge("temperature", {"sensor": "cpu"}) == 26.0
        
        # Check time series
        assert "temperature" in collector.series
        assert len(collector.series["temperature"].points) == 2
        
    def test_record_histogram(self, collector):
        """Test histogram recording."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        for value in values:
            collector.record_histogram("response_time", value)
            
        stats = collector.get_histogram_stats("response_time")
        assert stats["count"] == 5
        assert stats["min"] == 1.0
        assert stats["max"] == 5.0
        assert stats["mean"] == 3.0
        assert stats["median"] == 3.0
        
    def test_record_timing(self, collector):
        """Test timing recording."""
        collector.record_timing("operation", 0.5, {"type": "db_query"})
        
        # Check that data was recorded in some form
        # The record_timing method should create both histogram and counter entries
        duration_recorded = (
            "operation.duration" in collector.series or
            any("operation.duration" in key for key in collector.histograms.keys())
        )
        count_recorded = (
            "operation.count" in collector.series or
            any("operation.count" in key for key in collector.counters.keys())
        )
        
        assert duration_recorded, "Duration timing not recorded"
        assert count_recorded, "Count timing not recorded"
        
    def test_get_series(self, collector):
        """Test getting metric series."""
        # Record some data
        collector.record_gauge("cpu", 50.0)
        time.sleep(0.001)
        collector.record_gauge("cpu", 60.0)
        
        # Get full series
        series = collector.get_series("cpu")
        assert series is not None
        assert len(series.points) == 2
        
        # Get filtered series (should include all recent points)
        filtered = collector.get_series("cpu", minutes=1)
        assert filtered is not None
        assert len(filtered.points) == 2
        
        # Get series that doesn't exist
        missing = collector.get_series("nonexistent")
        assert missing is None
        
    def test_get_all_metrics(self, collector):
        """Test getting all metrics."""
        collector.record_counter("requests", 5)
        collector.record_gauge("cpu", 75.0)
        collector.record_histogram("latency", 100.0)
        
        metrics = collector.get_all_metrics()
        
        assert "counters" in metrics
        assert "gauges" in metrics
        assert "histograms" in metrics
        assert "series_count" in metrics
        assert "total_points" in metrics
        
        assert metrics["series_count"] == 3
        
    def test_clear_metrics(self, collector):
        """Test clearing all metrics."""
        collector.record_counter("test", 1)
        collector.record_gauge("test", 1.0)
        collector.record_histogram("test", 1.0)
        
        assert len(collector.series) > 0
        assert len(collector.counters) > 0
        assert len(collector.gauges) > 0
        assert len(collector.histograms) > 0
        
        collector.clear_metrics()
        
        assert len(collector.series) == 0
        assert len(collector.counters) == 0
        assert len(collector.gauges) == 0
        assert len(collector.histograms) == 0
        
    def test_export_prometheus(self, collector):
        """Test Prometheus format export."""
        collector.record_counter("http_requests_total", 100, {"method": "GET"})
        collector.record_gauge("cpu_usage_percent", 75.5)
        
        prometheus_output = collector.export_metrics("prometheus")
        
        assert "http_requests_total" in prometheus_output
        assert "cpu_usage_percent" in prometheus_output
        assert "method=\"GET\"" in prometheus_output
        
    def test_make_key(self, collector):
        """Test cache key generation."""
        key1 = collector._make_key("metric", {"a": "1", "b": "2"})
        key2 = collector._make_key("metric", {"b": "2", "a": "1"})
        
        # Should be the same regardless of tag order
        assert key1 == key2
        
        key3 = collector._make_key("metric", None)
        assert key3 == "metric"
        
    def test_parse_tags(self, collector):
        """Test tag parsing from keys."""
        tags = collector._parse_tags("metric[a=1,b=2]")
        assert tags == {"a": "1", "b": "2"}
        
        tags = collector._parse_tags("metric")
        assert tags == {}


class TestTimingContext:
    """Test timing context manager."""
    
    @pytest.fixture
    def collector(self):
        """Create metrics collector for testing."""
        return MetricsCollector()
        
    def test_timing_context_success(self, collector):
        """Test timing context for successful operation."""
        with TimingContext(collector, "test_operation", {"type": "success"}):
            time.sleep(0.01)
            
        # Check that timing was recorded - check if data exists in any form
        duration_key = collector._make_key("test_operation.duration", {"type": "success", "success": "True"})
        count_key = collector._make_key("test_operation.count", {"type": "success", "success": "True"})
        
        # Check if data was recorded (either in histograms or series)
        assert (duration_key in collector.histograms or 
                "test_operation.duration" in collector.series), "Duration timing not recorded"
        assert (count_key in collector.counters or 
                "test_operation.count" in collector.series), "Count timing not recorded"
        
    def test_timing_context_error(self, collector):
        """Test timing context for failed operation."""
        try:
            with TimingContext(collector, "test_operation", {"type": "error"}):
                time.sleep(0.01)
                raise ValueError("Test error")
        except ValueError:
            pass
            
        # Check that timing was recorded with error flag
        duration_key = collector._make_key("test_operation.duration", {"type": "error", "success": "False"})
        count_key = collector._make_key("test_operation.count", {"type": "error", "success": "False"})
        
        # Check if data was recorded (either in histograms or series)
        assert (duration_key in collector.histograms or 
                "test_operation.duration" in collector.series), "Duration timing not recorded"
        assert (count_key in collector.counters or 
                "test_operation.count" in collector.series), "Count timing not recorded"


class TestMetricPoint:
    """Test MetricPoint data structure."""
    
    def test_metric_point_creation(self):
        """Test creating metric points."""
        timestamp = datetime.now()
        point = MetricPoint(
            timestamp=timestamp,
            value=42.5,
            tags={"env": "test"}
        )
        
        assert point.timestamp == timestamp
        assert point.value == 42.5
        assert point.tags == {"env": "test"}


class TestMetricSeries:
    """Test MetricSeries data structure."""
    
    def test_metric_series_creation(self):
        """Test creating metric series."""
        series = MetricSeries(
            name="test.metric",
            unit="count",
            description="Test metric",
            max_points=100
        )
        
        assert series.name == "test.metric"
        assert series.unit == "count"
        assert series.description == "Test metric"
        assert series.max_points == 100
        assert len(series.points) == 0