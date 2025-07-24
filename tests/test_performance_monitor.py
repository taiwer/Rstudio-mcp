"""
Tests for performance monitoring system.
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.rstudio_mcp.monitoring.performance_monitor import (
    PerformanceMonitor, PerformanceMetric, OperationStats, performance_monitor
)


class TestPerformanceMonitor:
    """Test performance monitoring functionality."""
    
    @pytest.fixture
    def monitor(self):
        """Create performance monitor for testing."""
        return PerformanceMonitor(max_metrics=100)
        
    def test_record_metric(self, monitor):
        """Test recording metrics."""
        monitor.record_metric("test.metric", 42.0, {"tag": "value"}, "units")
        
        assert len(monitor.metrics) == 1
        metric = monitor.metrics[0]
        assert metric.name == "test.metric"
        assert metric.value == 42.0
        assert metric.tags == {"tag": "value"}
        assert metric.unit == "units"
        assert isinstance(metric.timestamp, datetime)
        
    def test_start_end_operation(self, monitor):
        """Test operation timing."""
        op_id = monitor.start_operation("test_operation")
        assert op_id in monitor.active_operations
        
        time.sleep(0.01)  # Small delay
        monitor.end_operation(op_id, "test_operation", success=True)
        
        assert op_id not in monitor.active_operations
        assert "test_operation" in monitor.operation_stats
        
        stats = monitor.operation_stats["test_operation"]
        assert stats.total_calls == 1
        assert stats.total_time > 0
        assert stats.error_count == 0
        
    def test_operation_error_tracking(self, monitor):
        """Test error tracking in operations."""
        op_id = monitor.start_operation("error_operation")
        monitor.end_operation(op_id, "error_operation", success=False)
        
        stats = monitor.operation_stats["error_operation"]
        assert stats.error_count == 1
        
    def test_get_operation_stats(self, monitor):
        """Test getting operation statistics."""
        # Record some operations
        for i in range(3):
            op_id = monitor.start_operation("test_op")
            time.sleep(0.001)
            monitor.end_operation(op_id, "test_op", success=True)
            
        stats = monitor.get_operation_stats("test_op")
        assert "test_op" in stats
        assert stats["test_op"].total_calls == 3
        
        all_stats = monitor.get_operation_stats()
        assert "test_op" in all_stats
        
    def test_get_recent_metrics(self, monitor):
        """Test getting recent metrics."""
        # Record metrics with different timestamps
        monitor.record_metric("old.metric", 1.0)
        time.sleep(0.001)
        monitor.record_metric("new.metric", 2.0)
        
        recent = monitor.get_recent_metrics(minutes=1)
        assert len(recent) == 2
        
        # Test filtering by name pattern
        filtered = monitor.get_recent_metrics("new", minutes=1)
        assert len(filtered) == 1
        assert filtered[0].name == "new.metric"
        
    def test_performance_summary(self, monitor):
        """Test performance summary generation."""
        # Add some test data
        op_id = monitor.start_operation("summary_test")
        monitor.end_operation(op_id, "summary_test", success=True)
        monitor.record_metric("test.metric", 100.0)
        
        summary = monitor.get_performance_summary()
        
        assert "total_metrics" in summary
        assert "active_operations" in summary
        assert "operation_count" in summary
        assert "operations" in summary
        assert "summary_test" in summary["operations"]
        
    def test_clear_metrics(self, monitor):
        """Test clearing metrics."""
        monitor.record_metric("test", 1.0)
        op_id = monitor.start_operation("test")
        monitor.end_operation(op_id, "test", success=True)
        
        assert len(monitor.metrics) > 0
        assert len(monitor.operation_stats) > 0
        
        monitor.clear_metrics()
        
        assert len(monitor.metrics) == 0
        assert len(monitor.operation_stats) == 0
        assert len(monitor.active_operations) == 0
        
    @pytest.mark.asyncio
    async def test_monitoring_loop(self, monitor):
        """Test continuous monitoring."""
        with patch('psutil.cpu_percent', return_value=50.0), \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.Process') as mock_process:
            
            # Mock memory info
            mock_memory.return_value.percent = 60.0
            mock_memory.return_value.available = 1000000
            mock_memory.return_value.used = 500000
            
            # Mock process info
            mock_proc = Mock()
            mock_proc.memory_info.return_value.rss = 100000
            mock_proc.memory_info.return_value.vms = 200000
            mock_proc.cpu_percent.return_value = 10.0
            mock_proc.num_threads.return_value = 5
            mock_process.return_value = mock_proc
            
            monitor.start_monitoring(interval=0.1)
            await asyncio.sleep(0.2)  # Let it run for a bit
            await monitor.stop_monitoring()
            
            # Check that system metrics were recorded
            cpu_metrics = [m for m in monitor.metrics if m.name == "system.cpu.usage"]
            assert len(cpu_metrics) > 0
            
    def test_max_metrics_limit(self):
        """Test that metrics are limited to max_metrics."""
        monitor = PerformanceMonitor(max_metrics=5)
        
        # Add more metrics than the limit
        for i in range(10):
            monitor.record_metric(f"metric_{i}", float(i))
            
        assert len(monitor.metrics) == 5
        # Should keep the most recent ones
        assert monitor.metrics[-1].name == "metric_9"


class TestPerformanceDecorator:
    """Test performance monitoring decorator."""
    
    @pytest.fixture
    def monitor(self):
        """Create monitor for testing."""
        return PerformanceMonitor()
        
    def test_sync_function_decorator(self, monitor):
        """Test decorator on synchronous function."""
        class TestClass:
            def __init__(self):
                self._performance_monitor = monitor
                
            @performance_monitor("test_sync_op")
            def test_method(self, value):
                time.sleep(0.001)
                return value * 2
                
        obj = TestClass()
        result = obj.test_method(5)
        
        assert result == 10
        assert "test_sync_op" in monitor.operation_stats
        assert monitor.operation_stats["test_sync_op"].total_calls == 1
        
    @pytest.mark.asyncio
    async def test_async_function_decorator(self, monitor):
        """Test decorator on asynchronous function."""
        class TestClass:
            def __init__(self):
                self._performance_monitor = monitor
                
            @performance_monitor("test_async_op")
            async def test_method(self, value):
                await asyncio.sleep(0.001)
                return value * 3
                
        obj = TestClass()
        result = await obj.test_method(4)
        
        assert result == 12
        assert "test_async_op" in monitor.operation_stats
        assert monitor.operation_stats["test_async_op"].total_calls == 1
        
    def test_decorator_error_handling(self, monitor):
        """Test decorator handles errors correctly."""
        class TestClass:
            def __init__(self):
                self._performance_monitor = monitor
                
            @performance_monitor("error_op")
            def error_method(self):
                raise ValueError("Test error")
                
        obj = TestClass()
        
        with pytest.raises(ValueError):
            obj.error_method()
            
        assert "error_op" in monitor.operation_stats
        stats = monitor.operation_stats["error_op"]
        assert stats.total_calls == 1
        assert stats.error_count == 1
        
    def test_decorator_without_monitor(self):
        """Test decorator works when no monitor is available."""
        class TestClass:
            @performance_monitor("no_monitor_op")
            def test_method(self):
                return "success"
                
        obj = TestClass()
        result = obj.test_method()
        assert result == "success"


class TestPerformanceMetric:
    """Test PerformanceMetric data structure."""
    
    def test_metric_creation(self):
        """Test creating performance metrics."""
        timestamp = datetime.now()
        metric = PerformanceMetric(
            name="test.metric",
            value=42.5,
            timestamp=timestamp,
            tags={"env": "test"},
            unit="ms"
        )
        
        assert metric.name == "test.metric"
        assert metric.value == 42.5
        assert metric.timestamp == timestamp
        assert metric.tags == {"env": "test"}
        assert metric.unit == "ms"


class TestOperationStats:
    """Test OperationStats data structure."""
    
    def test_stats_creation(self):
        """Test creating operation statistics."""
        stats = OperationStats("test_operation")
        
        assert stats.operation_name == "test_operation"
        assert stats.total_calls == 0
        assert stats.total_time == 0.0
        assert stats.min_time == float('inf')
        assert stats.max_time == 0.0
        assert stats.error_count == 0
        assert stats.last_called is None
        assert len(stats.recent_times) == 0