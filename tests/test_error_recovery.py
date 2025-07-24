"""
Tests for error recovery and stability management.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timedelta

from src.rstudio_mcp.monitoring.error_recovery import (
    ErrorRecoveryManager, CircuitBreaker, RecoveryStrategy, ErrorSeverity,
    RecoveryAction, ErrorInfo, error_recovery
)


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker for testing."""
        return CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)
        
    def test_circuit_breaker_closed_state(self, circuit_breaker):
        """Test circuit breaker in closed state."""
        def success_function():
            return "success"
            
        result = circuit_breaker.call(success_function)
        assert result == "success"
        assert circuit_breaker.state == "closed"
        assert circuit_breaker.failure_count == 0
        
    def test_circuit_breaker_failure_tracking(self, circuit_breaker):
        """Test circuit breaker failure tracking."""
        def failing_function():
            raise ValueError("Test error")
            
        # First two failures should keep circuit closed
        for i in range(2):
            with pytest.raises(ValueError):
                circuit_breaker.call(failing_function)
            assert circuit_breaker.state == "closed"
            assert circuit_breaker.failure_count == i + 1
            
        # Third failure should open circuit
        with pytest.raises(ValueError):
            circuit_breaker.call(failing_function)
        assert circuit_breaker.state == "open"
        assert circuit_breaker.failure_count == 3
        
    def test_circuit_breaker_open_state(self, circuit_breaker):
        """Test circuit breaker in open state."""
        def failing_function():
            raise ValueError("Test error")
            
        # Trigger circuit breaker to open
        for i in range(3):
            with pytest.raises(ValueError):
                circuit_breaker.call(failing_function)
                
        assert circuit_breaker.state == "open"
        
        # Now calls should be rejected immediately
        with pytest.raises(RuntimeError, match="Circuit breaker is open"):
            circuit_breaker.call(lambda: "should not execute")
            
    def test_circuit_breaker_recovery(self, circuit_breaker):
        """Test circuit breaker recovery."""
        def failing_function():
            raise ValueError("Test error")
            
        def success_function():
            return "recovered"
            
        # Open the circuit
        for i in range(3):
            with pytest.raises(ValueError):
                circuit_breaker.call(failing_function)
                
        assert circuit_breaker.state == "open"
        
        # Wait for recovery timeout
        time.sleep(1.1)
        
        # Next call should transition to half-open and succeed
        result = circuit_breaker.call(success_function)
        assert result == "recovered"
        assert circuit_breaker.state == "closed"
        assert circuit_breaker.failure_count == 0


class TestErrorRecoveryManager:
    """Test error recovery manager functionality."""
    
    @pytest.fixture
    def recovery_manager(self):
        """Create error recovery manager for testing."""
        return ErrorRecoveryManager()
        
    def test_default_recovery_actions(self, recovery_manager):
        """Test default recovery actions are set up."""
        assert "ConnectionError" in recovery_manager.recovery_actions
        assert "TimeoutError" in recovery_manager.recovery_actions
        assert "MemoryError" in recovery_manager.recovery_actions
        
        connection_action = recovery_manager.recovery_actions["ConnectionError"]
        assert connection_action.strategy == RecoveryStrategy.RETRY
        assert connection_action.max_attempts == 3
        
    def test_register_recovery_action(self, recovery_manager):
        """Test registering custom recovery actions."""
        custom_action = RecoveryAction(
            strategy=RecoveryStrategy.FALLBACK,
            max_attempts=2,
            fallback_function=lambda e: "fallback"
        )
        
        recovery_manager.register_recovery_action("CustomError", custom_action)
        assert "CustomError" in recovery_manager.recovery_actions
        assert recovery_manager.recovery_actions["CustomError"] == custom_action
        
    def test_register_health_check(self, recovery_manager):
        """Test registering health checks."""
        def health_check():
            return True
            
        recovery_manager.register_health_check("test_check", health_check)
        assert "test_check" in recovery_manager.health_checks
        assert recovery_manager.health_checks["test_check"] == health_check
        
    def test_circuit_breaker_creation(self, recovery_manager):
        """Test circuit breaker creation and retrieval."""
        breaker1 = recovery_manager.get_circuit_breaker("test_service")
        breaker2 = recovery_manager.get_circuit_breaker("test_service")
        
        # Should return the same instance
        assert breaker1 is breaker2
        assert "test_service" in recovery_manager.circuit_breakers
        
    def test_error_severity_determination(self, recovery_manager):
        """Test error severity determination."""
        # Critical errors
        memory_error = MemoryError("Out of memory")
        assert recovery_manager._determine_severity(memory_error) == ErrorSeverity.CRITICAL
        
        # High severity errors
        process_error = ProcessLookupError("Process not found")
        assert recovery_manager._determine_severity(process_error) == ErrorSeverity.HIGH
        
        # Medium severity errors
        timeout_error = TimeoutError("Operation timed out")
        assert recovery_manager._determine_severity(timeout_error) == ErrorSeverity.MEDIUM
        
        # Low severity errors
        value_error = ValueError("Invalid value")
        assert recovery_manager._determine_severity(value_error) == ErrorSeverity.LOW
        
    @pytest.mark.asyncio
    async def test_handle_error_recording(self, recovery_manager):
        """Test error recording functionality."""
        test_error = ValueError("Test error")
        context = {"operation": "test_operation"}
        
        # Disable auto recovery for this test
        recovery_manager.auto_recovery_enabled = False
        
        result = await recovery_manager.handle_error(test_error, context)
        assert result is False  # No recovery attempted
        
        # Check error was recorded
        assert len(recovery_manager.error_history) == 1
        error_info = recovery_manager.error_history[0]
        assert error_info.error_type == "ValueError"
        assert error_info.message == "Test error"
        assert error_info.context == context
        assert error_info.severity == ErrorSeverity.LOW
        
    @pytest.mark.asyncio
    async def test_retry_recovery(self, recovery_manager):
        """Test retry recovery strategy."""
        # Create a custom retry action
        retry_action = RecoveryAction(
            strategy=RecoveryStrategy.RETRY,
            max_attempts=2,
            delay_seconds=0.1
        )
        recovery_manager.register_recovery_action("TestError", retry_action)
        
        class TestError(Exception):
            pass
            
        test_error = TestError("Retry test")
        
        start_time = time.time()
        result = await recovery_manager.handle_error(test_error)
        end_time = time.time()
        
        # Should have succeeded (retry strategy returns True)
        assert result is True
        
        # Check that error was recorded
        assert len(recovery_manager.error_history) == 1
        error_info = recovery_manager.error_history[0]
        assert error_info.recovery_attempted is True
        assert error_info.recovery_successful is True
        
    @pytest.mark.asyncio
    async def test_fallback_recovery(self, recovery_manager):
        """Test fallback recovery strategy."""
        fallback_called = False
        
        def fallback_function(error):
            nonlocal fallback_called
            fallback_called = True
            return "fallback_result"
            
        fallback_action = RecoveryAction(
            strategy=RecoveryStrategy.FALLBACK,
            fallback_function=fallback_function
        )
        recovery_manager.register_recovery_action("TestError", fallback_action)
        
        class TestError(Exception):
            pass
            
        test_error = TestError("Fallback test")
        result = await recovery_manager.handle_error(test_error)
        
        assert result is True
        assert fallback_called is True
        
    @pytest.mark.asyncio
    async def test_async_fallback_recovery(self, recovery_manager):
        """Test async fallback recovery strategy."""
        fallback_called = False
        
        async def async_fallback_function(error):
            nonlocal fallback_called
            await asyncio.sleep(0.01)
            fallback_called = True
            return "async_fallback_result"
            
        fallback_action = RecoveryAction(
            strategy=RecoveryStrategy.FALLBACK,
            fallback_function=async_fallback_function
        )
        recovery_manager.register_recovery_action("TestError", fallback_action)
        
        class TestError(Exception):
            pass
            
        test_error = TestError("Async fallback test")
        result = await recovery_manager.handle_error(test_error)
        
        assert result is True
        assert fallback_called is True
        
    @pytest.mark.asyncio
    async def test_run_health_checks(self, recovery_manager):
        """Test running health checks."""
        def healthy_check():
            return True
            
        def unhealthy_check():
            return False
            
        async def async_healthy_check():
            await asyncio.sleep(0.01)
            return True
            
        def failing_check():
            raise Exception("Health check failed")
            
        recovery_manager.register_health_check("healthy", healthy_check)
        recovery_manager.register_health_check("unhealthy", unhealthy_check)
        recovery_manager.register_health_check("async_healthy", async_healthy_check)
        recovery_manager.register_health_check("failing", failing_check)
        
        results = await recovery_manager.run_health_checks()
        
        assert results["healthy"] is True
        assert results["unhealthy"] is False
        assert results["async_healthy"] is True
        assert results["failing"] is False
        
    def test_error_statistics(self, recovery_manager):
        """Test error statistics calculation."""
        # Add some test errors
        now = datetime.now()
        
        errors = [
            ErrorInfo("ValueError", "Error 1", now - timedelta(minutes=30), ErrorSeverity.LOW),
            ErrorInfo("ConnectionError", "Error 2", now - timedelta(minutes=20), ErrorSeverity.MEDIUM, recovery_attempted=True, recovery_successful=True),
            ErrorInfo("MemoryError", "Error 3", now - timedelta(minutes=10), ErrorSeverity.CRITICAL, recovery_attempted=True, recovery_successful=False),
            ErrorInfo("ValueError", "Error 4", now - timedelta(hours=25), ErrorSeverity.LOW),  # Outside 24h window
        ]
        
        recovery_manager.error_history.extend(errors)
        
        stats = recovery_manager.get_error_statistics(hours=24)
        
        assert stats["total_errors"] == 3  # Only errors within 24h
        assert stats["error_rate"] == 3 / 24
        assert stats["recovery_attempts"] == 2
        assert stats["successful_recoveries"] == 1
        assert stats["recovery_rate"] == 0.5
        assert stats["error_types"]["ValueError"] == 1
        assert stats["error_types"]["ConnectionError"] == 1
        assert stats["error_types"]["MemoryError"] == 1
        assert stats["severity_distribution"]["low"] == 1
        assert stats["severity_distribution"]["medium"] == 1
        assert stats["severity_distribution"]["critical"] == 1
        
    def test_system_health_assessment(self):
        """Test system health assessment."""
        # Create a fresh recovery manager for this test
        recovery_manager = ErrorRecoveryManager()
        
        # Test healthy system
        health = recovery_manager.get_system_health()
        
        # Debug: print health details if not healthy
        if health["status"] != "healthy":
            print(f"Health status: {health}")
            stats = recovery_manager.get_error_statistics(hours=1)
            print(f"Error stats: {stats}")
        
        # A fresh recovery manager should be healthy
        assert health["status"] == "healthy", f"Expected healthy but got {health['status']}: {health}"
        
        # Add some errors to make system unhealthy
        now = datetime.now()
        errors = [
            ErrorInfo("ValueError", f"Error {i}", now - timedelta(minutes=i*5), ErrorSeverity.LOW)
            for i in range(15)  # 15 errors in last hour
        ]
        recovery_manager.error_history.extend(errors)
        
        health = recovery_manager.get_system_health()
        assert health["status"] == "unhealthy"
        assert health["error_rate_per_hour"] == 15
        
        # Add critical error
        critical_error = ErrorInfo("MemoryError", "Critical", now, ErrorSeverity.CRITICAL)
        recovery_manager.error_history.append(critical_error)
        
        health = recovery_manager.get_system_health()
        assert health["status"] == "critical"
        assert health["critical_errors"] == 1
        
    def test_clear_error_history(self, recovery_manager):
        """Test clearing error history."""
        # Add some errors
        errors = [
            ErrorInfo("ValueError", "Error 1", datetime.now(), ErrorSeverity.LOW),
            ErrorInfo("ConnectionError", "Error 2", datetime.now(), ErrorSeverity.MEDIUM),
        ]
        recovery_manager.error_history.extend(errors)
        
        assert len(recovery_manager.error_history) == 2
        
        recovery_manager.clear_error_history()
        assert len(recovery_manager.error_history) == 0


class TestErrorRecoveryDecorator:
    """Test error recovery decorator."""
    
    @pytest.fixture
    def recovery_manager(self):
        """Create error recovery manager for testing."""
        return ErrorRecoveryManager()
        
    @pytest.mark.asyncio
    async def test_async_decorator_success(self, recovery_manager):
        """Test decorator with successful async function."""
        class TestService:
            def __init__(self):
                self._error_recovery_manager = recovery_manager
                
            @error_recovery()
            async def test_method(self, value):
                return value * 2
                
        service = TestService()
        result = await service.test_method(5)
        assert result == 10
        
    @pytest.mark.asyncio
    async def test_async_decorator_with_recovery(self, recovery_manager):
        """Test decorator with error and recovery."""
        call_count = 0
        
        class TestService:
            def __init__(self):
                self._error_recovery_manager = recovery_manager
                
            @error_recovery()
            async def test_method(self):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise ConnectionError("First call fails")
                return "success"
                
        # Set up recovery action
        recovery_action = RecoveryAction(
            strategy=RecoveryStrategy.RETRY,
            max_attempts=1
        )
        recovery_manager.register_recovery_action("ConnectionError", recovery_action)
        
        service = TestService()
        result = await service.test_method()
        
        assert result == "success"
        assert call_count == 2  # Original call + retry
        assert len(recovery_manager.error_history) == 1
        
    def test_sync_decorator_success(self, recovery_manager):
        """Test decorator with successful sync function."""
        class TestService:
            def __init__(self):
                self._error_recovery_manager = recovery_manager
                
            @error_recovery()
            def test_method(self, value):
                return value * 3
                
        service = TestService()
        result = service.test_method(4)
        assert result == 12
        
    def test_sync_decorator_with_error(self, recovery_manager):
        """Test decorator with sync function error."""
        class TestService:
            def __init__(self):
                self._error_recovery_manager = recovery_manager
                
            @error_recovery()
            def test_method(self):
                raise ValueError("Sync error")
                
        service = TestService()
        
        with pytest.raises(ValueError):
            service.test_method()
            
        # Error should be logged but not recovered (sync limitation)
        # The error history won't be updated because sync recovery is limited
        
    def test_decorator_without_recovery_manager(self):
        """Test decorator without recovery manager."""
        class TestService:
            @error_recovery()
            def test_method(self):
                raise ValueError("No recovery manager")
                
        service = TestService()
        
        with pytest.raises(ValueError):
            service.test_method()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])