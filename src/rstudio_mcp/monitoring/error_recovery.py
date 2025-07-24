"""
Error recovery and stability management for RStudio MCP.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import traceback
import threading

logger = logging.getLogger(__name__)


class RecoveryStrategy(Enum):
    """Error recovery strategies."""
    RETRY = "retry"
    FALLBACK = "fallback"
    CIRCUIT_BREAKER = "circuit_breaker"
    RESTART = "restart"
    IGNORE = "ignore"


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorInfo:
    """Information about an error occurrence."""
    error_type: str
    message: str
    timestamp: datetime
    severity: ErrorSeverity
    context: Dict[str, Any] = field(default_factory=dict)
    traceback: Optional[str] = None
    recovery_attempted: bool = False
    recovery_successful: bool = False


@dataclass
class RecoveryAction:
    """Recovery action configuration."""
    strategy: RecoveryStrategy
    max_attempts: int = 3
    delay_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    fallback_function: Optional[Callable] = None
    condition: Optional[Callable[[Exception], bool]] = None


class CircuitBreaker:
    """Circuit breaker pattern implementation."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed, open, half_open
        self._lock = threading.Lock()
        
    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        with self._lock:
            if self.state == "open":
                if self._should_attempt_reset():
                    self.state = "half_open"
                else:
                    raise RuntimeError("Circuit breaker is open")
            
            try:
                result = func(*args, **kwargs)
                if self.state == "half_open":
                    self._reset()
                return result
            except Exception as e:
                self._record_failure()
                raise
                
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset."""
        if self.last_failure_time is None:
            return True
        return (datetime.now() - self.last_failure_time).total_seconds() > self.recovery_timeout
        
    def _record_failure(self):
        """Record a failure."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
            
    def _reset(self):
        """Reset circuit breaker."""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"
        logger.info("Circuit breaker reset")


class ErrorRecoveryManager:
    """
    Manages error recovery and system stability.
    """
    
    def __init__(self):
        self.error_history: List[ErrorInfo] = []
        self.recovery_actions: Dict[str, RecoveryAction] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.health_checks: Dict[str, Callable] = {}
        self.auto_recovery_enabled = True
        self.max_error_history = 1000
        self._lock = threading.Lock()
        
        # Default recovery actions
        self._setup_default_recovery_actions()
        
    def _setup_default_recovery_actions(self):
        """Set up default recovery actions for common errors."""
        self.recovery_actions.update({
            "ConnectionError": RecoveryAction(
                strategy=RecoveryStrategy.RETRY,
                max_attempts=3,
                delay_seconds=2.0,
                backoff_multiplier=2.0
            ),
            "TimeoutError": RecoveryAction(
                strategy=RecoveryStrategy.RETRY,
                max_attempts=2,
                delay_seconds=5.0
            ),
            "MemoryError": RecoveryAction(
                strategy=RecoveryStrategy.RESTART,
                max_attempts=1
            ),
            "RRuntimeError": RecoveryAction(
                strategy=RecoveryStrategy.FALLBACK,
                max_attempts=2,
                delay_seconds=1.0
            ),
            "ProcessLookupError": RecoveryAction(
                strategy=RecoveryStrategy.RESTART,
                max_attempts=1
            )
        })
        
    def register_recovery_action(self, error_type: str, action: RecoveryAction):
        """Register a recovery action for a specific error type."""
        self.recovery_actions[error_type] = action
        logger.info(f"Registered recovery action for {error_type}: {action.strategy.value}")
        
    def register_health_check(self, name: str, check_function: Callable):
        """Register a health check function."""
        self.health_checks[name] = check_function
        logger.info(f"Registered health check: {name}")
        
    def get_circuit_breaker(self, name: str, failure_threshold: int = 5, 
                           recovery_timeout: float = 60.0) -> CircuitBreaker:
        """Get or create a circuit breaker."""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(failure_threshold, recovery_timeout)
        return self.circuit_breakers[name]
        
    async def handle_error(self, error: Exception, context: Dict[str, Any] = None) -> bool:
        """
        Handle an error with appropriate recovery strategy.
        
        Args:
            error: The exception that occurred
            context: Additional context information
            
        Returns:
            True if recovery was successful, False otherwise
        """
        error_type = type(error).__name__
        severity = self._determine_severity(error)
        
        # Record error
        error_info = ErrorInfo(
            error_type=error_type,
            message=str(error),
            timestamp=datetime.now(),
            severity=severity,
            context=context or {},
            traceback=traceback.format_exc()
        )
        
        with self._lock:
            self.error_history.append(error_info)
            if len(self.error_history) > self.max_error_history:
                self.error_history = self.error_history[-self.max_error_history:]
        
        logger.error(f"Error occurred: {error_type} - {str(error)}")
        
        # Attempt recovery if enabled
        if self.auto_recovery_enabled:
            recovery_successful = await self._attempt_recovery(error, error_info)
            error_info.recovery_attempted = True
            error_info.recovery_successful = recovery_successful
            return recovery_successful
            
        return False
        
    def _determine_severity(self, error: Exception) -> ErrorSeverity:
        """Determine error severity based on error type and message."""
        error_type = type(error).__name__
        message = str(error).lower()
        
        # Critical errors
        if error_type in ["MemoryError", "SystemExit", "KeyboardInterrupt"]:
            return ErrorSeverity.CRITICAL
        if "critical" in message or "fatal" in message:
            return ErrorSeverity.CRITICAL
            
        # High severity errors
        if error_type in ["ProcessLookupError", "ConnectionAbortedError", "BrokenPipeError"]:
            return ErrorSeverity.HIGH
        if "connection" in message and ("lost" in message or "broken" in message):
            return ErrorSeverity.HIGH
            
        # Medium severity errors
        if error_type in ["TimeoutError", "ConnectionError", "RRuntimeError"]:
            return ErrorSeverity.MEDIUM
        if "timeout" in message or "connection" in message:
            return ErrorSeverity.MEDIUM
            
        # Default to low severity
        return ErrorSeverity.LOW
        
    async def _attempt_recovery(self, error: Exception, error_info: ErrorInfo) -> bool:
        """Attempt to recover from an error."""
        error_type = type(error).__name__
        
        # Get recovery action
        recovery_action = self.recovery_actions.get(error_type)
        if not recovery_action:
            # Try to find a generic recovery action
            recovery_action = self._get_generic_recovery_action(error)
            
        if not recovery_action:
            logger.warning(f"No recovery action defined for {error_type}")
            return False
            
        # Check condition if specified
        if recovery_action.condition and not recovery_action.condition(error):
            logger.info(f"Recovery condition not met for {error_type}")
            return False
            
        logger.info(f"Attempting recovery for {error_type} using {recovery_action.strategy.value}")
        
        try:
            if recovery_action.strategy == RecoveryStrategy.RETRY:
                return await self._retry_recovery(error, recovery_action)
            elif recovery_action.strategy == RecoveryStrategy.FALLBACK:
                return await self._fallback_recovery(error, recovery_action)
            elif recovery_action.strategy == RecoveryStrategy.CIRCUIT_BREAKER:
                return await self._circuit_breaker_recovery(error, recovery_action)
            elif recovery_action.strategy == RecoveryStrategy.RESTART:
                return await self._restart_recovery(error, recovery_action)
            elif recovery_action.strategy == RecoveryStrategy.IGNORE:
                logger.info(f"Ignoring error {error_type} as per recovery strategy")
                return True
            else:
                logger.warning(f"Unknown recovery strategy: {recovery_action.strategy}")
                return False
                
        except Exception as recovery_error:
            logger.error(f"Recovery attempt failed: {recovery_error}")
            return False
            
    def _get_generic_recovery_action(self, error: Exception) -> Optional[RecoveryAction]:
        """Get a generic recovery action based on error characteristics."""
        error_type = type(error).__name__
        message = str(error).lower()
        
        # Connection-related errors
        if "connection" in error_type.lower() or "connection" in message:
            return RecoveryAction(
                strategy=RecoveryStrategy.RETRY,
                max_attempts=3,
                delay_seconds=2.0
            )
            
        # Timeout errors
        if "timeout" in error_type.lower() or "timeout" in message:
            return RecoveryAction(
                strategy=RecoveryStrategy.RETRY,
                max_attempts=2,
                delay_seconds=5.0
            )
            
        # Resource errors
        if "memory" in error_type.lower() or "resource" in message:
            return RecoveryAction(
                strategy=RecoveryStrategy.RESTART,
                max_attempts=1
            )
            
        return None
        
    async def _retry_recovery(self, error: Exception, action: RecoveryAction) -> bool:
        """Implement retry recovery strategy."""
        delay = action.delay_seconds
        
        for attempt in range(action.max_attempts):
            if attempt > 0:
                logger.info(f"Retry attempt {attempt + 1}/{action.max_attempts} after {delay}s delay")
                await asyncio.sleep(delay)
                delay *= action.backoff_multiplier
                
            try:
                # For retry, we assume the operation will be retried by the caller
                # This method just implements the delay and attempt counting
                return True
            except Exception as retry_error:
                logger.warning(f"Retry attempt {attempt + 1} failed: {retry_error}")
                if attempt == action.max_attempts - 1:
                    return False
                    
        return False
        
    async def _fallback_recovery(self, error: Exception, action: RecoveryAction) -> bool:
        """Implement fallback recovery strategy."""
        if action.fallback_function:
            try:
                if asyncio.iscoroutinefunction(action.fallback_function):
                    await action.fallback_function(error)
                else:
                    action.fallback_function(error)
                return True
            except Exception as fallback_error:
                logger.error(f"Fallback function failed: {fallback_error}")
                return False
        else:
            logger.warning("Fallback recovery requested but no fallback function provided")
            return False
            
    async def _circuit_breaker_recovery(self, error: Exception, action: RecoveryAction) -> bool:
        """Implement circuit breaker recovery strategy."""
        error_type = type(error).__name__
        breaker = self.get_circuit_breaker(error_type)
        
        try:
            # Circuit breaker will handle the retry logic
            return True
        except RuntimeError:
            logger.warning(f"Circuit breaker is open for {error_type}")
            return False
            
    async def _restart_recovery(self, error: Exception, action: RecoveryAction) -> bool:
        """Implement restart recovery strategy."""
        logger.warning("Restart recovery requested - this should be handled by the application")
        # In a real implementation, this would trigger a component restart
        # For now, we just log the request
        return False
        
    async def run_health_checks(self) -> Dict[str, bool]:
        """Run all registered health checks."""
        results = {}
        
        for name, check_function in self.health_checks.items():
            try:
                if asyncio.iscoroutinefunction(check_function):
                    result = await check_function()
                else:
                    result = check_function()
                results[name] = bool(result)
            except Exception as e:
                logger.error(f"Health check '{name}' failed: {e}")
                results[name] = False
                
        return results
        
    def get_error_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get error statistics for the specified time period."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self._lock:
            recent_errors = [
                error for error in self.error_history
                if error.timestamp >= cutoff_time
            ]
            
        if not recent_errors:
            return {
                "total_errors": 0,
                "error_rate": 0.0,
                "recovery_rate": 0.0,
                "error_types": {},
                "severity_distribution": {}
            }
            
        # Calculate statistics
        total_errors = len(recent_errors)
        recovery_attempts = sum(1 for e in recent_errors if e.recovery_attempted)
        successful_recoveries = sum(1 for e in recent_errors if e.recovery_successful)
        
        error_types = {}
        severity_distribution = {}
        
        for error in recent_errors:
            error_types[error.error_type] = error_types.get(error.error_type, 0) + 1
            severity_key = error.severity.value
            severity_distribution[severity_key] = severity_distribution.get(severity_key, 0) + 1
            
        return {
            "total_errors": total_errors,
            "error_rate": total_errors / hours,
            "recovery_rate": successful_recoveries / recovery_attempts if recovery_attempts > 0 else 0.0,
            "error_types": error_types,
            "severity_distribution": severity_distribution,
            "recovery_attempts": recovery_attempts,
            "successful_recoveries": successful_recoveries
        }
        
    def clear_error_history(self):
        """Clear error history."""
        with self._lock:
            self.error_history.clear()
        logger.info("Error history cleared")
        
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        stats = self.get_error_statistics(hours=1)  # Last hour
        
        # Determine health status
        error_rate = stats["error_rate"]
        recovery_rate = stats["recovery_rate"]
        critical_errors = stats["severity_distribution"].get("critical", 0)
        
        if critical_errors > 0:
            health_status = "critical"
        elif error_rate > 10:  # More than 10 errors per hour
            health_status = "unhealthy"
        elif error_rate > 5 or (stats["recovery_attempts"] > 0 and recovery_rate < 0.8):
            health_status = "degraded"
        else:
            health_status = "healthy"
            
        return {
            "status": health_status,
            "error_rate_per_hour": error_rate,
            "recovery_rate": recovery_rate,
            "critical_errors": critical_errors,
            "total_circuit_breakers": len(self.circuit_breakers),
            "open_circuit_breakers": sum(
                1 for cb in self.circuit_breakers.values() 
                if cb.state == "open"
            )
        }


def error_recovery(recovery_action: Optional[RecoveryAction] = None):
    """Decorator for automatic error recovery."""
    def decorator(func: Callable):
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                recovery_manager = getattr(args[0], '_error_recovery_manager', None) if args else None
                
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if recovery_manager:
                        context = {
                            "function": func.__name__,
                            "args": str(args)[:100],
                            "kwargs": str(kwargs)[:100]
                        }
                        recovered = await recovery_manager.handle_error(e, context)
                        if not recovered:
                            raise
                        # If recovered, retry the function once
                        return await func(*args, **kwargs)
                    else:
                        raise
                        
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                recovery_manager = getattr(args[0], '_error_recovery_manager', None) if args else None
                
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if recovery_manager:
                        context = {
                            "function": func.__name__,
                            "args": str(args)[:100],
                            "kwargs": str(kwargs)[:100]
                        }
                        # For sync functions, we can't use async recovery
                        # Just log the error and re-raise
                        logger.error(f"Error in {func.__name__}: {e}")
                        raise
                    else:
                        raise
                        
            return sync_wrapper
            
    return decorator