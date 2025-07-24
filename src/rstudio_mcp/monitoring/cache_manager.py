"""
Cache management system for RStudio MCP to improve performance.
"""

import time
import asyncio
import hashlib
import pickle
from typing import Any, Optional, Dict, List, Callable, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from collections import OrderedDict
import threading

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    key: str
    value: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    ttl: Optional[float] = None
    size_bytes: int = 0


class LRUCache:
    """Thread-safe LRU cache implementation."""
    
    def __init__(self, max_size: int = 1000, max_memory_mb: int = 100):
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.total_size_bytes = 0
        self._lock = threading.RLock()
        
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self._lock:
            entry = self.cache.get(key)
            if entry is None:
                return None
                
            # Check TTL
            if entry.ttl and time.time() - entry.created_at.timestamp() > entry.ttl:
                self._remove_entry(key)
                return None
                
            # Update access info
            entry.last_accessed = datetime.now()
            entry.access_count += 1
            
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            
            return entry.value
            
    def put(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """Put value in cache."""
        with self._lock:
            # Calculate size
            try:
                size_bytes = len(pickle.dumps(value))
            except Exception:
                size_bytes = 1024  # Default size if can't serialize
                
            # Check if value is too large
            if size_bytes > self.max_memory_bytes:
                logger.warning(f"Value too large for cache: {size_bytes} bytes")
                return False
                
            # Remove existing entry if present
            if key in self.cache:
                self._remove_entry(key)
                
            # Make space if needed
            while (len(self.cache) >= self.max_size or 
                   self.total_size_bytes + size_bytes > self.max_memory_bytes):
                if not self.cache:
                    break
                oldest_key = next(iter(self.cache))
                self._remove_entry(oldest_key)
                
            # Add new entry
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                ttl=ttl,
                size_bytes=size_bytes
            )
            
            self.cache[key] = entry
            self.total_size_bytes += size_bytes
            
            return True
            
    def remove(self, key: str) -> bool:
        """Remove entry from cache."""
        with self._lock:
            return self._remove_entry(key)
            
    def _remove_entry(self, key: str) -> bool:
        """Internal method to remove entry."""
        entry = self.cache.pop(key, None)
        if entry:
            self.total_size_bytes -= entry.size_bytes
            return True
        return False
        
    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            self.cache.clear()
            self.total_size_bytes = 0
            
    def cleanup_expired(self):
        """Remove expired entries."""
        with self._lock:
            current_time = time.time()
            expired_keys = []
            
            for key, entry in self.cache.items():
                if entry.ttl and current_time - entry.created_at.timestamp() > entry.ttl:
                    expired_keys.append(key)
                    
            for key in expired_keys:
                self._remove_entry(key)
                
            return len(expired_keys)
            
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'memory_usage_bytes': self.total_size_bytes,
                'max_memory_bytes': self.max_memory_bytes,
                'memory_usage_percent': (self.total_size_bytes / self.max_memory_bytes) * 100,
                'entries': [
                    {
                        'key': entry.key,
                        'size_bytes': entry.size_bytes,
                        'created_at': entry.created_at.isoformat(),
                        'last_accessed': entry.last_accessed.isoformat(),
                        'access_count': entry.access_count,
                        'ttl': entry.ttl
                    }
                    for entry in list(self.cache.values())
                ]
            }


class CacheManager:
    """
    Manages multiple caches for different types of data.
    """
    
    def __init__(self):
        self.caches: Dict[str, LRUCache] = {}
        self.hit_counts: Dict[str, int] = {}
        self.miss_counts: Dict[str, int] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_interval = 300  # 5 minutes
        
    def create_cache(self, name: str, max_size: int = 1000, max_memory_mb: int = 100) -> LRUCache:
        """Create a new cache."""
        cache = LRUCache(max_size=max_size, max_memory_mb=max_memory_mb)
        self.caches[name] = cache
        self.hit_counts[name] = 0
        self.miss_counts[name] = 0
        logger.info(f"Created cache '{name}' with max_size={max_size}, max_memory={max_memory_mb}MB")
        return cache
        
    def get_cache(self, name: str) -> Optional[LRUCache]:
        """Get existing cache."""
        return self.caches.get(name)
        
    def get_or_create_cache(self, name: str, max_size: int = 1000, max_memory_mb: int = 100) -> LRUCache:
        """Get existing cache or create new one."""
        cache = self.get_cache(name)
        if cache is None:
            cache = self.create_cache(name, max_size, max_memory_mb)
        return cache
        
    def get(self, cache_name: str, key: str) -> Optional[Any]:
        """Get value from named cache."""
        cache = self.get_cache(cache_name)
        if cache is None:
            return None
            
        value = cache.get(key)
        if value is not None:
            self.hit_counts[cache_name] += 1
        else:
            self.miss_counts[cache_name] += 1
            
        return value
        
    def put(self, cache_name: str, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """Put value in named cache."""
        cache = self.get_cache(cache_name)
        if cache is None:
            cache = self.create_cache(cache_name)
            
        return cache.put(key, value, ttl)
        
    def remove(self, cache_name: str, key: str) -> bool:
        """Remove value from named cache."""
        cache = self.get_cache(cache_name)
        if cache is None:
            return False
            
        return cache.remove(key)
        
    def clear_cache(self, cache_name: str):
        """Clear specific cache."""
        cache = self.get_cache(cache_name)
        if cache:
            cache.clear()
            self.hit_counts[cache_name] = 0
            self.miss_counts[cache_name] = 0
            
    def clear_all_caches(self):
        """Clear all caches."""
        for cache in self.caches.values():
            cache.clear()
        self.hit_counts.clear()
        self.miss_counts.clear()
        
    def start_cleanup_task(self):
        """Start automatic cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            
    async def stop_cleanup_task(self):
        """Stop automatic cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
                
    async def _cleanup_loop(self):
        """Automatic cleanup loop."""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                self.cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cache cleanup: {e}")
                
    def cleanup_expired(self):
        """Clean up expired entries in all caches."""
        total_removed = 0
        for name, cache in self.caches.items():
            removed = cache.cleanup_expired()
            total_removed += removed
            if removed > 0:
                logger.debug(f"Removed {removed} expired entries from cache '{name}'")
                
        return total_removed
        
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all caches."""
        stats = {
            'total_caches': len(self.caches),
            'caches': {}
        }
        
        for name, cache in self.caches.items():
            cache_stats = cache.get_stats()
            hits = self.hit_counts.get(name, 0)
            misses = self.miss_counts.get(name, 0)
            total_requests = hits + misses
            
            cache_stats.update({
                'hits': hits,
                'misses': misses,
                'hit_rate': hits / total_requests if total_requests > 0 else 0,
                'total_requests': total_requests
            })
            
            stats['caches'][name] = cache_stats
            
        return stats
        
    def make_key(self, *args, **kwargs) -> str:
        """Create a cache key from arguments."""
        key_data = {
            'args': args,
            'kwargs': kwargs
        }
        key_str = pickle.dumps(key_data, protocol=pickle.HIGHEST_PROTOCOL)
        return hashlib.md5(key_str).hexdigest()


def cached(cache_name: str, ttl: Optional[float] = None, key_func: Optional[Callable] = None):
    """Decorator for caching function results."""
    def decorator(func: Callable):
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                # Get cache manager from first argument (self) if available
                cache_manager = getattr(args[0], '_cache_manager', None) if args else None
                if not cache_manager:
                    return await func(*args, **kwargs)
                    
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = cache_manager.make_key(func.__name__, *args, **kwargs)
                    
                # Try to get from cache
                cached_result = cache_manager.get(cache_name, cache_key)
                if cached_result is not None:
                    return cached_result
                    
                # Execute function and cache result
                result = await func(*args, **kwargs)
                cache_manager.put(cache_name, cache_key, result, ttl)
                return result
                
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                # Get cache manager from first argument (self) if available
                cache_manager = getattr(args[0], '_cache_manager', None) if args else None
                if not cache_manager:
                    return func(*args, **kwargs)
                    
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = cache_manager.make_key(func.__name__, *args, **kwargs)
                    
                # Try to get from cache
                cached_result = cache_manager.get(cache_name, cache_key)
                if cached_result is not None:
                    return cached_result
                    
                # Execute function and cache result
                result = func(*args, **kwargs)
                cache_manager.put(cache_name, cache_key, result, ttl)
                return result
                
            return sync_wrapper
            
    return decorator