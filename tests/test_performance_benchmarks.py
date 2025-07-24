"""
Performance benchmarks and tests for RStudio MCP operations.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch

from src.rstudio_mcp.monitoring.performance_monitor import PerformanceMonitor
from src.rstudio_mcp.monitoring.metrics_collector import MetricsCollector
from src.rstudio_mcp.monitoring.cache_manager import CacheManager
from src.rstudio_mcp.monitoring.resource_monitor import ResourceMonitor
from src.rstudio_mcp.api_wrapper import RStudioAPIWrapper


class TestPerformanceBenchmarks:
    """Performance benchmarks for RStudio MCP operations."""
    
    @pytest.fixture
    def performance_monitor(self):
        """Create performance monitor for benchmarking."""
        return PerformanceMonitor(max_metrics=1000)
        
    @pytest.fixture
    def metrics_collector(self):
        """Create metrics collector for benchmarking."""
        return MetricsCollector(max_series=50)
        
    @pytest.fixture
    def cache_manager(self):
        """Create cache manager for benchmarking."""
        return CacheManager()
        
    @pytest.fixture
    def resource_monitor(self):
        """Create resource monitor for benchmarking."""
        return ResourceMonitor()
        
    def test_performance_monitor_overhead(self, performance_monitor):
        """Test performance monitoring overhead."""
        # Measure baseline operation time
        start_time = time.perf_counter()
        for i in range(1000):
            pass  # Empty operation
        baseline_time = time.perf_counter() - start_time
        
        # Measure operation time with monitoring
        start_time = time.perf_counter()
        for i in range(1000):
            op_id = performance_monitor.start_operation("test_op")
            performance_monitor.end_operation(op_id, "test_op", success=True)
        monitored_time = time.perf_counter() - start_time
        
        # Calculate overhead
        overhead = monitored_time - baseline_time
        overhead_per_op = overhead / 1000
        
        # Overhead should be minimal (less than 1ms per operation)
        assert overhead_per_op < 0.001, f"Performance monitoring overhead too high: {overhead_per_op:.6f}s per operation"
        
        print(f"Performance monitoring overhead: {overhead_per_op * 1000:.3f}ms per operation")
        
    def test_metrics_collection_performance(self, metrics_collector):
        """Test metrics collection performance."""
        # Test counter performance
        start_time = time.perf_counter()
        for i in range(10000):
            metrics_collector.record_counter("test_counter", 1)
        counter_time = time.perf_counter() - start_time
        
        # Test gauge performance
        start_time = time.perf_counter()
        for i in range(10000):
            metrics_collector.record_gauge("test_gauge", float(i))
        gauge_time = time.perf_counter() - start_time
        
        # Test histogram performance
        start_time = time.perf_counter()
        for i in range(10000):
            metrics_collector.record_histogram("test_histogram", float(i))
        histogram_time = time.perf_counter() - start_time
        
        print(f"Counter recording: {counter_time / 10000 * 1000:.3f}ms per operation")
        print(f"Gauge recording: {gauge_time / 10000 * 1000:.3f}ms per operation")
        print(f"Histogram recording: {histogram_time / 10000 * 1000:.3f}ms per operation")
        
        # All operations should be fast
        assert counter_time / 10000 < 0.001
        assert gauge_time / 10000 < 0.001
        assert histogram_time / 10000 < 0.001
        
    def test_cache_performance(self, cache_manager):
        """Test cache performance."""
        cache = cache_manager.create_cache("test_cache", max_size=1000)
        
        # Test cache write performance
        test_data = {"key": "value", "number": 42, "list": [1, 2, 3, 4, 5]}
        
        start_time = time.perf_counter()
        for i in range(1000):
            cache.put(f"key_{i}", test_data)
        write_time = time.perf_counter() - start_time
        
        # Test cache read performance
        start_time = time.perf_counter()
        for i in range(1000):
            cache.get(f"key_{i}")
        read_time = time.perf_counter() - start_time
        
        print(f"Cache write: {write_time / 1000 * 1000:.3f}ms per operation")
        print(f"Cache read: {read_time / 1000 * 1000:.3f}ms per operation")
        
        # Cache operations should be fast
        assert write_time / 1000 < 0.01  # Less than 10ms per write
        assert read_time / 1000 < 0.001  # Less than 1ms per read
        
    @pytest.mark.asyncio
    async def test_resource_monitoring_performance(self, resource_monitor):
        """Test resource monitoring performance."""
        # Start monitoring
        resource_monitor.start_monitoring(interval=0.1)
        
        # Let it collect some data
        await asyncio.sleep(0.5)
        
        # Test getting current usage
        start_time = time.perf_counter()
        for i in range(100):
            resource_monitor.get_current_usage()
        usage_time = time.perf_counter() - start_time
        
        # Test getting usage history
        start_time = time.perf_counter()
        for i in range(100):
            resource_monitor.get_usage_history(minutes=1)
        history_time = time.perf_counter() - start_time
        
        # Stop monitoring
        await resource_monitor.stop_monitoring()
        
        print(f"Get current usage: {usage_time / 100 * 1000:.3f}ms per operation")
        print(f"Get usage history: {history_time / 100 * 1000:.3f}ms per operation")
        
        # Operations should be fast
        assert usage_time / 100 < 0.01
        assert history_time / 100 < 0.01
        
    @pytest.mark.asyncio
    async def test_api_wrapper_performance(self):
        """Test API wrapper performance with monitoring."""
        with patch('rpy2.robjects.r') as mock_r, \
             patch('rpy2.robjects.packages.importr') as mock_importr:
            
            # Mock R interface
            mock_r.return_value = "test output"
            mock_importr.return_value = Mock()
            
            # Create API wrapper
            api_wrapper = RStudioAPIWrapper()
            
            # Test code execution performance
            simple_code = "print('Hello, World!')"
            
            start_time = time.perf_counter()
            for i in range(10):
                result = await api_wrapper.execute_r_code(simple_code)
                assert result.success
            execution_time = time.perf_counter() - start_time
            
            print(f"R code execution: {execution_time / 10 * 1000:.3f}ms per operation")
            
            # Check that performance monitoring was used
            assert hasattr(api_wrapper, '_performance_monitor')
            assert len(api_wrapper._performance_monitor.operation_stats) > 0
            
            # Get performance stats
            stats = api_wrapper._performance_monitor.get_operation_stats("r_code_execution")
            assert "r_code_execution" in stats
            assert stats["r_code_execution"].total_calls == 10
            
    def test_memory_usage_monitoring(self, performance_monitor):
        """Test memory usage during monitoring operations."""
        import psutil
        import gc
        
        # Get initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        # Perform many monitoring operations
        for i in range(10000):
            performance_monitor.record_metric(f"test_metric_{i % 100}", float(i))
            
            if i % 1000 == 0:
                op_id = performance_monitor.start_operation("memory_test")
                performance_monitor.end_operation(op_id, "memory_test", success=True)
        
        # Force garbage collection
        gc.collect()
        
        # Get final memory usage
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        print(f"Memory increase after 10k operations: {memory_increase / 1024 / 1024:.2f}MB")
        
        # Memory increase should be reasonable (less than 50MB for 10k operations)
        assert memory_increase < 50 * 1024 * 1024, f"Memory usage too high: {memory_increase / 1024 / 1024:.2f}MB"
        
    @pytest.mark.asyncio
    async def test_concurrent_monitoring_performance(self, performance_monitor):
        """Test performance under concurrent load."""
        async def monitoring_task(task_id: int):
            """Simulate monitoring operations."""
            for i in range(100):
                op_id = performance_monitor.start_operation(f"concurrent_task_{task_id}")
                await asyncio.sleep(0.001)  # Simulate work
                performance_monitor.end_operation(op_id, f"concurrent_task_{task_id}", success=True)
                performance_monitor.record_metric(f"task_{task_id}_metric", float(i))
        
        # Run multiple concurrent monitoring tasks
        start_time = time.perf_counter()
        tasks = [monitoring_task(i) for i in range(10)]
        await asyncio.gather(*tasks)
        total_time = time.perf_counter() - start_time
        
        print(f"Concurrent monitoring (10 tasks, 100 ops each): {total_time:.3f}s total")
        
        # Check that all operations were recorded
        total_operations = sum(
            stats.total_calls 
            for stats in performance_monitor.operation_stats.values()
        )
        assert total_operations == 1000  # 10 tasks * 100 operations
        
        # Total time should be reasonable (less than 5 seconds)
        assert total_time < 5.0
        
    def test_performance_data_export(self, performance_monitor, metrics_collector):
        """Test performance of data export operations."""
        # Add test data
        for i in range(1000):
            performance_monitor.record_metric(f"export_test_{i % 10}", float(i))
            metrics_collector.record_counter("export_counter", 1)
            metrics_collector.record_gauge("export_gauge", float(i))
        
        # Test performance summary export
        start_time = time.perf_counter()
        summary = performance_monitor.get_performance_summary()
        summary_time = time.perf_counter() - start_time
        
        # Test metrics export
        start_time = time.perf_counter()
        metrics = metrics_collector.get_all_metrics()
        metrics_time = time.perf_counter() - start_time
        
        # Test Prometheus export
        start_time = time.perf_counter()
        prometheus_data = metrics_collector.export_metrics("prometheus")
        prometheus_time = time.perf_counter() - start_time
        
        print(f"Performance summary export: {summary_time * 1000:.3f}ms")
        print(f"Metrics export: {metrics_time * 1000:.3f}ms")
        print(f"Prometheus export: {prometheus_time * 1000:.3f}ms")
        
        # Export operations should be fast
        assert summary_time < 0.1
        assert metrics_time < 0.1
        assert prometheus_time < 0.1
        
        # Verify data integrity
        assert isinstance(summary, dict)
        assert isinstance(metrics, dict)
        assert isinstance(prometheus_data, str)


class TestPerformanceOptimizations:
    """Test performance optimizations and caching."""
    
    @pytest.fixture
    def cache_manager(self):
        """Create cache manager for testing."""
        return CacheManager()
        
    def test_lru_cache_efficiency(self, cache_manager):
        """Test LRU cache efficiency."""
        cache = cache_manager.create_cache("lru_test", max_size=100)
        
        # Fill cache to capacity
        for i in range(100):
            cache.put(f"key_{i}", f"value_{i}")
        
        # Test hit rate for recently accessed items
        hits = 0
        for i in range(90, 100):  # Access recent items
            if cache.get(f"key_{i}") is not None:
                hits += 1
        
        hit_rate = hits / 10
        assert hit_rate >= 0.9, f"LRU cache hit rate too low: {hit_rate}"
        
        # Add more items to trigger eviction
        for i in range(100, 150):
            cache.put(f"key_{i}", f"value_{i}")
        
        # Old items should be evicted
        old_items_found = 0
        for i in range(0, 50):
            if cache.get(f"key_{i}") is not None:
                old_items_found += 1
        
        # Most old items should be evicted
        assert old_items_found < 10, f"Too many old items retained: {old_items_found}"
        
    def test_cache_memory_management(self, cache_manager):
        """Test cache memory management."""
        cache = cache_manager.create_cache("memory_test", max_size=1000, max_memory_mb=1)
        
        # Create large objects
        large_object = "x" * 100000  # 100KB string
        
        # Add objects until memory limit is reached
        added_count = 0
        for i in range(20):  # Try to add 20 * 100KB = 2MB (should hit 1MB limit)
            if cache.put(f"large_key_{i}", large_object):
                added_count += 1
            else:
                break
        
        # Should not be able to add all objects due to memory limit
        assert added_count < 15, f"Memory limit not enforced: added {added_count} objects"
        
        stats = cache.get_stats()
        memory_usage_mb = stats['memory_usage_bytes'] / (1024 * 1024)
        assert memory_usage_mb <= 1.1, f"Memory usage exceeded limit: {memory_usage_mb:.2f}MB"
        
    @pytest.mark.asyncio
    async def test_cached_decorator_performance(self, cache_manager):
        """Test performance improvement from caching decorator."""
        from src.rstudio_mcp.monitoring.cache_manager import cached
        
        class TestService:
            def __init__(self):
                self._cache_manager = cache_manager
                self.call_count = 0
            
            @cached("expensive_operation", ttl=60.0)
            def expensive_operation(self, value: int) -> int:
                """Simulate expensive operation."""
                self.call_count += 1
                time.sleep(0.01)  # Simulate work
                return value * 2
        
        service = TestService()
        
        # First call should be slow (cache miss)
        start_time = time.perf_counter()
        result1 = service.expensive_operation(42)
        first_call_time = time.perf_counter() - start_time
        
        # Second call should be fast (cache hit)
        start_time = time.perf_counter()
        result2 = service.expensive_operation(42)
        second_call_time = time.perf_counter() - start_time
        
        assert result1 == result2 == 84
        assert service.call_count == 1  # Should only be called once
        assert second_call_time < first_call_time / 2  # Should be much faster
        
        print(f"First call (cache miss): {first_call_time * 1000:.3f}ms")
        print(f"Second call (cache hit): {second_call_time * 1000:.3f}ms")
        print(f"Speedup: {first_call_time / second_call_time:.1f}x")


if __name__ == "__main__":
    # Run benchmarks
    pytest.main([__file__, "-v", "-s"])