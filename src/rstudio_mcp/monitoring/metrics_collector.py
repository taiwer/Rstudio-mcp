"""
Metrics collection system for RStudio MCP operations.
"""

import time
import asyncio
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """A single metric data point."""
    timestamp: datetime
    value: Union[int, float]
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricSeries:
    """A series of metric points for a specific metric."""
    name: str
    unit: str
    description: str
    points: List[MetricPoint] = field(default_factory=list)
    max_points: int = 1000


class MetricsCollector:
    """
    Collects and aggregates metrics for RStudio MCP operations.
    """
    
    def __init__(self, max_series: int = 100):
        self.max_series = max_series
        self.series: Dict[str, MetricSeries] = {}
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        
    def register_metric(self, name: str, unit: str = "", description: str = "", max_points: int = 1000):
        """Register a new metric series."""
        if name not in self.series:
            self.series[name] = MetricSeries(
                name=name,
                unit=unit,
                description=description,
                max_points=max_points
            )
            logger.debug(f"Registered metric: {name}")
            
    def record_counter(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None):
        """Record a counter metric (cumulative)."""
        key = self._make_key(name, tags)
        self.counters[key] += value
        
        # Also record as time series
        self._record_point(name, value, tags)
        
    def record_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Record a gauge metric (current value)."""
        key = self._make_key(name, tags)
        self.gauges[key] = value
        
        # Also record as time series
        self._record_point(name, value, tags)
        
    def record_histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Record a histogram metric (distribution of values)."""
        key = self._make_key(name, tags)
        self.histograms[key].append(value)
        
        # Keep only recent values (last 1000)
        if len(self.histograms[key]) > 1000:
            self.histograms[key] = self.histograms[key][-1000:]
            
        # Also record as time series
        self._record_point(name, value, tags)
        
    def record_timing(self, name: str, duration: float, tags: Optional[Dict[str, str]] = None):
        """Record a timing metric."""
        timing_tags = (tags or {}).copy()
        timing_tags['type'] = 'timing'
        
        self.record_histogram(f"{name}.duration", duration, timing_tags)
        self.record_counter(f"{name}.count", 1, timing_tags)
        
    def _record_point(self, name: str, value: Union[int, float], tags: Optional[Dict[str, str]] = None):
        """Record a data point in the time series."""
        if name not in self.series:
            self.register_metric(name)
            
        series = self.series[name]
        point = MetricPoint(
            timestamp=datetime.now(),
            value=value,
            tags=tags or {}
        )
        
        series.points.append(point)
        
        # Keep only recent points
        if len(series.points) > series.max_points:
            series.points = series.points[-series.max_points:]
            
    def _make_key(self, name: str, tags: Optional[Dict[str, str]] = None) -> str:
        """Create a unique key for a metric with tags."""
        if not tags:
            return name
            
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}[{tag_str}]"
        
    def get_counter(self, name: str, tags: Optional[Dict[str, str]] = None) -> int:
        """Get current counter value."""
        key = self._make_key(name, tags)
        return self.counters.get(key, 0)
        
    def get_gauge(self, name: str, tags: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Get current gauge value."""
        key = self._make_key(name, tags)
        return self.gauges.get(key)
        
    def get_histogram_stats(self, name: str, tags: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """Get histogram statistics."""
        key = self._make_key(name, tags)
        values = self.histograms.get(key, [])
        
        if not values:
            return {}
            
        sorted_values = sorted(values)
        count = len(sorted_values)
        
        return {
            'count': count,
            'min': min(sorted_values),
            'max': max(sorted_values),
            'mean': sum(sorted_values) / count,
            'median': sorted_values[count // 2],
            'p95': sorted_values[int(count * 0.95)] if count > 0 else 0,
            'p99': sorted_values[int(count * 0.99)] if count > 0 else 0
        }
        
    def get_series(self, name: str, minutes: Optional[int] = None) -> Optional[MetricSeries]:
        """Get a metric series, optionally filtered by time."""
        series = self.series.get(name)
        if not series:
            return None
            
        if minutes is None:
            return series
            
        # Filter by time
        cutoff = datetime.now() - timedelta(minutes=minutes)
        filtered_points = [
            point for point in series.points
            if point.timestamp >= cutoff
        ]
        
        filtered_series = MetricSeries(
            name=series.name,
            unit=series.unit,
            description=series.description,
            points=filtered_points,
            max_points=series.max_points
        )
        
        return filtered_series
        
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all current metric values."""
        return {
            'counters': dict(self.counters),
            'gauges': dict(self.gauges),
            'histograms': {
                name: self.get_histogram_stats(name.split('[')[0], 
                    self._parse_tags(name) if '[' in name else None)
                for name in self.histograms.keys()
            },
            'series_count': len(self.series),
            'total_points': sum(len(series.points) for series in self.series.values())
        }
        
    def _parse_tags(self, key: str) -> Dict[str, str]:
        """Parse tags from a metric key."""
        if '[' not in key:
            return {}
            
        tag_str = key.split('[')[1].rstrip(']')
        tags = {}
        
        for pair in tag_str.split(','):
            if '=' in pair:
                k, v = pair.split('=', 1)
                tags[k] = v
                
        return tags
        
    def clear_metrics(self):
        """Clear all metrics."""
        self.series.clear()
        self.counters.clear()
        self.gauges.clear()
        self.histograms.clear()
        logger.info("All metrics cleared")
        
    def export_metrics(self, format: str = 'dict') -> Any:
        """Export metrics in specified format."""
        if format == 'dict':
            return self.get_all_metrics()
        elif format == 'prometheus':
            return self._export_prometheus()
        else:
            raise ValueError(f"Unsupported export format: {format}")
            
    def _export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        # Counters
        for key, value in self.counters.items():
            name = key.split('[')[0]
            tags = self._parse_tags(key)
            tag_str = ','.join(f'{k}="{v}"' for k, v in tags.items())
            metric_line = f'{name}{{{tag_str}}} {value}' if tag_str else f'{name} {value}'
            lines.append(metric_line)
            
        # Gauges
        for key, value in self.gauges.items():
            name = key.split('[')[0]
            tags = self._parse_tags(key)
            tag_str = ','.join(f'{k}="{v}"' for k, v in tags.items())
            metric_line = f'{name}{{{tag_str}}} {value}' if tag_str else f'{name} {value}'
            lines.append(metric_line)
            
        return '\n'.join(lines)


class TimingContext:
    """Context manager for timing operations."""
    
    def __init__(self, collector: MetricsCollector, metric_name: str, tags: Optional[Dict[str, str]] = None):
        self.collector = collector
        self.metric_name = metric_name
        self.tags = tags
        self.start_time = None
        
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.perf_counter() - self.start_time
            success_tags = (self.tags or {}).copy()
            success_tags['success'] = str(exc_type is None)
            self.collector.record_timing(self.metric_name, duration, success_tags)