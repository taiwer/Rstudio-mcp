"""
Performance monitoring system for RStudio MCP operations.
"""

import time
import asyncio
import psutil
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Performance metric data structure."""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    unit: str = ""


@dataclass
class OperationStats:
    """Statistics for a specific operation."""
    operation_name: str
    total_calls: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    avg_time: float = 0.0
    error_count: int = 0
    last_called: Optional[datetime] = None
    recent_times: deque = field(default_factory=lambda: deque(maxlen=100))


class PerformanceMonitor:
    """
    Monitors and tracks performance metrics for RStudio MCP operations.
    """
    
    def __init__(self, max_metrics: int = 10000):
        self.max_metrics = max_metrics
        self.metrics: deque = deque(maxlen=max_metrics)
        self.operation_stats: Dict[str, OperationStats] = {}
        self.active_operations: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._monitoring_active = False
        self._monitor_task: Optional[asyncio.Task] = None
        
    def start_monitoring(self, interval: float = 5.0):
        """Start continuous performance monitoring."""
        if self._monitoring_active:
            return
            
        self._monitoring_active = True
        self._monitor_task = asyncio.create_task(
            self._monitoring_loop(interval)
        )
        logger.info("Performance monitoring started")
        
    async def stop_monitoring(self):
        """Stop continuous performance monitoring."""
        self._monitoring_active = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Performance monitoring stopped")
        
    async def _monitoring_loop(self, interval: float):
        """Main monitoring loop."""
        while self._monitoring_active:
            try:
                await self._collect_system_metrics()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(interval)
                
    async def _collect_system_metrics(self):
        """Collect system-level performance metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=None)
            self.record_metric("system.cpu.usage", cpu_percent, unit="%")
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.record_metric("system.memory.usage", memory.percent, unit="%")
            self.record_metric("system.memory.available", memory.available, unit="bytes")
            self.record_metric("system.memory.used", memory.used, unit="bytes")
            
            # Process-specific metrics
            process = psutil.Process()
            process_memory = process.memory_info()
            self.record_metric("process.memory.rss", process_memory.rss, unit="bytes")
            self.record_metric("process.memory.vms", process_memory.vms, unit="bytes")
            self.record_metric("process.cpu.percent", process.cpu_percent(), unit="%")
            
            # Thread count
            self.record_metric("process.threads", process.num_threads(), unit="count")
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            
    def record_metric(self, name: str, value: float, tags: Optional[Dict[str, str]] = None, unit: str = ""):
        """Record a performance metric."""
        metric = PerformanceMetric(
            name=name,
            value=value,
            timestamp=datetime.now(),
            tags=tags or {},
            unit=unit
        )
        
        with self._lock:
            self.metrics.append(metric)
            
    def start_operation(self, operation_name: str, operation_id: Optional[str] = None) -> str:
        """Start timing an operation."""
        op_id = operation_id or f"{operation_name}_{int(time.time() * 1000000)}"
        start_time = time.perf_counter()
        
        with self._lock:
            self.active_operations[op_id] = start_time
            
        return op_id
        
    def end_operation(self, operation_id: str, operation_name: str, success: bool = True):
        """End timing an operation and record statistics."""
        end_time = time.perf_counter()
        
        with self._lock:
            start_time = self.active_operations.pop(operation_id, None)
            if start_time is None:
                logger.warning(f"Operation {operation_id} not found in active operations")
                return
                
            duration = end_time - start_time
            
            # Update operation statistics
            if operation_name not in self.operation_stats:
                self.operation_stats[operation_name] = OperationStats(operation_name)
                
            stats = self.operation_stats[operation_name]
            stats.total_calls += 1
            stats.total_time += duration
            stats.min_time = min(stats.min_time, duration)
            stats.max_time = max(stats.max_time, duration)
            stats.avg_time = stats.total_time / stats.total_calls
            stats.last_called = datetime.now()
            stats.recent_times.append(duration)
            
            if not success:
                stats.error_count += 1
                
        # Record metric
        self.record_metric(
            f"operation.{operation_name}.duration",
            duration,
            tags={"success": str(success)},
            unit="seconds"
        )
        
        if not success:
            self.record_metric(
                f"operation.{operation_name}.error",
                1,
                unit="count"
            )
            
    def get_operation_stats(self, operation_name: Optional[str] = None) -> Dict[str, OperationStats]:
        """Get operation statistics."""
        with self._lock:
            if operation_name:
                return {operation_name: self.operation_stats.get(operation_name)}
            return dict(self.operation_stats)
            
    def get_recent_metrics(self, name_pattern: Optional[str] = None, 
                          minutes: int = 5) -> List[PerformanceMetric]:
        """Get recent metrics matching the pattern."""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        with self._lock:
            recent_metrics = [
                metric for metric in self.metrics
                if metric.timestamp >= cutoff_time
            ]
            
        if name_pattern:
            recent_metrics = [
                metric for metric in recent_metrics
                if name_pattern in metric.name
            ]
            
        return recent_metrics
        
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get a summary of performance metrics."""
        with self._lock:
            summary = {
                "total_metrics": len(self.metrics),
                "active_operations": len(self.active_operations),
                "operation_count": len(self.operation_stats),
                "operations": {}
            }
            
            for name, stats in self.operation_stats.items():
                summary["operations"][name] = {
                    "total_calls": stats.total_calls,
                    "avg_time": round(stats.avg_time, 4),
                    "min_time": round(stats.min_time, 4),
                    "max_time": round(stats.max_time, 4),
                    "error_rate": stats.error_count / stats.total_calls if stats.total_calls > 0 else 0,
                    "last_called": stats.last_called.isoformat() if stats.last_called else None
                }
                
        return summary
        
    def clear_metrics(self):
        """Clear all stored metrics and statistics."""
        with self._lock:
            self.metrics.clear()
            self.operation_stats.clear()
            self.active_operations.clear()
            
        logger.info("Performance metrics cleared")


def performance_monitor(operation_name: str):
    """Decorator for monitoring function performance."""
    def decorator(func: Callable):
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                monitor = getattr(args[0], '_performance_monitor', None) if args else None
                if not monitor:
                    return await func(*args, **kwargs)
                    
                op_id = monitor.start_operation(operation_name)
                try:
                    result = await func(*args, **kwargs)
                    monitor.end_operation(op_id, operation_name, success=True)
                    return result
                except Exception as e:
                    monitor.end_operation(op_id, operation_name, success=False)
                    raise
                    
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                monitor = getattr(args[0], '_performance_monitor', None) if args else None
                if not monitor:
                    return func(*args, **kwargs)
                    
                op_id = monitor.start_operation(operation_name)
                try:
                    result = func(*args, **kwargs)
                    monitor.end_operation(op_id, operation_name, success=True)
                    return result
                except Exception as e:
                    monitor.end_operation(op_id, operation_name, success=False)
                    raise
                    
            return sync_wrapper
            
    return decorator