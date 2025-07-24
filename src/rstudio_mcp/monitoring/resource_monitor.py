"""
Resource monitoring for RStudio MCP operations.
"""

import asyncio
import psutil
import threading
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import deque
import logging

logger = logging.getLogger(__name__)


@dataclass
class ResourceSnapshot:
    """Snapshot of system resources at a point in time."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage_percent: float
    process_memory_mb: float
    process_cpu_percent: float
    thread_count: int
    open_files: int


@dataclass
class ResourceThreshold:
    """Resource usage threshold configuration."""
    cpu_percent: float = 80.0
    memory_percent: float = 85.0
    disk_percent: float = 90.0
    process_memory_mb: float = 1024.0


class ResourceMonitor:
    """
    Monitors system and process resource usage.
    """
    
    def __init__(self, threshold: Optional[ResourceThreshold] = None):
        self.threshold = threshold or ResourceThreshold()
        self.snapshots: deque = deque(maxlen=1000)
        self.alerts: List[Dict[str, Any]] = []
        self.max_alerts = 100
        
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._lock = threading.Lock()
        
        # Callbacks for threshold violations
        self.threshold_callbacks: List[Callable[[str, ResourceSnapshot], None]] = []
        
    def add_threshold_callback(self, callback: Callable[[str, ResourceSnapshot], None]):
        """Add callback for threshold violations."""
        self.threshold_callbacks.append(callback)
        
    def start_monitoring(self, interval: float = 5.0):
        """Start resource monitoring."""
        if self._monitoring:
            return
            
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop(interval))
        logger.info(f"Resource monitoring started with {interval}s interval")
        
    async def stop_monitoring(self):
        """Stop resource monitoring."""
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Resource monitoring stopped")
        
    async def _monitoring_loop(self, interval: float):
        """Main monitoring loop."""
        while self._monitoring:
            try:
                snapshot = await self._take_snapshot()
                self._check_thresholds(snapshot)
                
                with self._lock:
                    self.snapshots.append(snapshot)
                    
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in resource monitoring: {e}")
                await asyncio.sleep(interval)
                
    async def _take_snapshot(self) -> ResourceSnapshot:
        """Take a snapshot of current resource usage."""
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Process metrics
            process = psutil.Process()
            process_memory = process.memory_info()
            process_cpu = process.cpu_percent()
            
            # Additional process info
            try:
                thread_count = process.num_threads()
                open_files = len(process.open_files())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                thread_count = 0
                open_files = 0
                
            return ResourceSnapshot(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory.used / (1024 * 1024),
                memory_available_mb=memory.available / (1024 * 1024),
                disk_usage_percent=disk.percent,
                process_memory_mb=process_memory.rss / (1024 * 1024),
                process_cpu_percent=process_cpu,
                thread_count=thread_count,
                open_files=open_files
            )
            
        except Exception as e:
            logger.error(f"Error taking resource snapshot: {e}")
            # Return empty snapshot
            return ResourceSnapshot(
                timestamp=datetime.now(),
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_used_mb=0.0,
                memory_available_mb=0.0,
                disk_usage_percent=0.0,
                process_memory_mb=0.0,
                process_cpu_percent=0.0,
                thread_count=0,
                open_files=0
            )
            
    def _check_thresholds(self, snapshot: ResourceSnapshot):
        """Check if any thresholds are violated."""
        violations = []
        
        if snapshot.cpu_percent > self.threshold.cpu_percent:
            violations.append(f"CPU usage: {snapshot.cpu_percent:.1f}% > {self.threshold.cpu_percent}%")
            
        if snapshot.memory_percent > self.threshold.memory_percent:
            violations.append(f"Memory usage: {snapshot.memory_percent:.1f}% > {self.threshold.memory_percent}%")
            
        if snapshot.disk_usage_percent > self.threshold.disk_percent:
            violations.append(f"Disk usage: {snapshot.disk_usage_percent:.1f}% > {self.threshold.disk_percent}%")
            
        if snapshot.process_memory_mb > self.threshold.process_memory_mb:
            violations.append(f"Process memory: {snapshot.process_memory_mb:.1f}MB > {self.threshold.process_memory_mb}MB")
            
        if violations:
            alert = {
                'timestamp': snapshot.timestamp,
                'violations': violations,
                'snapshot': snapshot
            }
            
            with self._lock:
                self.alerts.append(alert)
                if len(self.alerts) > self.max_alerts:
                    self.alerts = self.alerts[-self.max_alerts:]
                    
            # Call threshold callbacks
            for callback in self.threshold_callbacks:
                try:
                    for violation in violations:
                        callback(violation, snapshot)
                except Exception as e:
                    logger.error(f"Error in threshold callback: {e}")
                    
            logger.warning(f"Resource threshold violations: {', '.join(violations)}")
            
    def get_current_usage(self) -> Optional[ResourceSnapshot]:
        """Get the most recent resource snapshot."""
        with self._lock:
            return self.snapshots[-1] if self.snapshots else None
            
    def get_usage_history(self, minutes: int = 60) -> List[ResourceSnapshot]:
        """Get resource usage history for the specified time period."""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        
        with self._lock:
            return [
                snapshot for snapshot in self.snapshots
                if snapshot.timestamp >= cutoff
            ]
            
    def get_usage_stats(self, minutes: int = 60) -> Dict[str, Any]:
        """Get usage statistics for the specified time period."""
        history = self.get_usage_history(minutes)
        
        if not history:
            return {}
            
        cpu_values = [s.cpu_percent for s in history]
        memory_values = [s.memory_percent for s in history]
        process_memory_values = [s.process_memory_mb for s in history]
        
        return {
            'period_minutes': minutes,
            'sample_count': len(history),
            'cpu': {
                'current': cpu_values[-1] if cpu_values else 0,
                'min': min(cpu_values) if cpu_values else 0,
                'max': max(cpu_values) if cpu_values else 0,
                'avg': sum(cpu_values) / len(cpu_values) if cpu_values else 0
            },
            'memory': {
                'current': memory_values[-1] if memory_values else 0,
                'min': min(memory_values) if memory_values else 0,
                'max': max(memory_values) if memory_values else 0,
                'avg': sum(memory_values) / len(memory_values) if memory_values else 0
            },
            'process_memory': {
                'current': process_memory_values[-1] if process_memory_values else 0,
                'min': min(process_memory_values) if process_memory_values else 0,
                'max': max(process_memory_values) if process_memory_values else 0,
                'avg': sum(process_memory_values) / len(process_memory_values) if process_memory_values else 0
            }
        }
        
    def get_alerts(self, minutes: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get recent alerts."""
        with self._lock:
            alerts = list(self.alerts)
            
        if minutes is not None:
            cutoff = datetime.now() - timedelta(minutes=minutes)
            alerts = [
                alert for alert in alerts
                if alert['timestamp'] >= cutoff
            ]
            
        return alerts
        
    def clear_alerts(self):
        """Clear all alerts."""
        with self._lock:
            self.alerts.clear()
            
    def is_healthy(self) -> bool:
        """Check if system is currently healthy (no threshold violations)."""
        current = self.get_current_usage()
        if not current:
            return True
            
        return (
            current.cpu_percent <= self.threshold.cpu_percent and
            current.memory_percent <= self.threshold.memory_percent and
            current.disk_usage_percent <= self.threshold.disk_percent and
            current.process_memory_mb <= self.threshold.process_memory_mb
        )
        
    def get_health_status(self) -> Dict[str, Any]:
        """Get detailed health status."""
        current = self.get_current_usage()
        recent_alerts = self.get_alerts(minutes=10)
        
        if not current:
            return {
                'healthy': False,
                'reason': 'No resource data available'
            }
            
        status = {
            'healthy': self.is_healthy(),
            'current_usage': {
                'cpu_percent': current.cpu_percent,
                'memory_percent': current.memory_percent,
                'disk_percent': current.disk_usage_percent,
                'process_memory_mb': current.process_memory_mb
            },
            'thresholds': {
                'cpu_percent': self.threshold.cpu_percent,
                'memory_percent': self.threshold.memory_percent,
                'disk_percent': self.threshold.disk_percent,
                'process_memory_mb': self.threshold.process_memory_mb
            },
            'recent_alerts': len(recent_alerts),
            'monitoring_active': self._monitoring
        }
        
        if not status['healthy']:
            violations = []
            if current.cpu_percent > self.threshold.cpu_percent:
                violations.append('cpu')
            if current.memory_percent > self.threshold.memory_percent:
                violations.append('memory')
            if current.disk_usage_percent > self.threshold.disk_percent:
                violations.append('disk')
            if current.process_memory_mb > self.threshold.process_memory_mb:
                violations.append('process_memory')
                
            status['violations'] = violations
            
        return status


class ResourceLimiter:
    """
    Limits resource usage by controlling operation execution.
    """
    
    def __init__(self, monitor: ResourceMonitor, max_concurrent_ops: int = 10):
        self.monitor = monitor
        self.max_concurrent_ops = max_concurrent_ops
        self.active_operations = 0
        self._semaphore = asyncio.Semaphore(max_concurrent_ops)
        self._lock = asyncio.Lock()
        
    async def can_execute_operation(self) -> bool:
        """Check if an operation can be executed based on current resource usage."""
        if not self.monitor.is_healthy():
            return False
            
        async with self._lock:
            return self.active_operations < self.max_concurrent_ops
            
    async def execute_with_limits(self, operation: Callable, *args, **kwargs):
        """Execute operation with resource limits."""
        if not await self.can_execute_operation():
            raise RuntimeError("Cannot execute operation: resource limits exceeded")
            
        async with self._semaphore:
            async with self._lock:
                self.active_operations += 1
                
            try:
                if asyncio.iscoroutinefunction(operation):
                    return await operation(*args, **kwargs)
                else:
                    return operation(*args, **kwargs)
            finally:
                async with self._lock:
                    self.active_operations -= 1