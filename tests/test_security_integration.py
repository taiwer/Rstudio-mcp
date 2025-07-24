"""Integration tests for security module."""

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from rstudio_mcp.security import (
    AccessController, Permission, ResourceType, AccessRule,
    AuditLogger, AuditEvent, AuditLevel, AuditEventType,
    CodeSecurityValidator, SecurityLevel, SecurityViolation,
    ConfigEncryption, EncryptedConfig
)


class TestCodeSecurityValidator:
    """Test code security validation."""
    
    @pytest.fixture
    def validator(self):
        """Create security validator fixture."""
        return CodeSecurityValidator()
    
    def test_safe_code_validation(self, validator):
        """Test validation of safe R code."""
        safe_code = """
        x <- c(1, 2, 3, 4, 5)
        mean_x <- mean(x)
        plot(x, main="Test Plot")
        """
        
        violations = validator.validate_code(safe_code)
        assert len(violations) == 0
        assert validator.is_code_safe(safe_code)
    
    def test_blocked_function_detection(self, validator):
        """Test detection of blocked functions."""
        dangerous_code = """
        system("rm -rf /")
        shell("malicious command")
        """
        
        violations = validator.validate_code(dangerous_code)
        assert len(violations) >= 2
        
        # Check for system and shell violations
        violation_messages = [v.message for v in violations]
        assert any("system" in msg.lower() for msg in violation_messages)
        assert any("shell" in msg.lower() for msg in violation_messages)
        
        assert not validator.is_code_safe(dangerous_code)
    
    def test_package_usage_validation(self, validator):
        """Test validation of package usage."""
        code_with_disallowed_package = """
        library(malicious_package)
        malicious_package::dangerous_function()
        """
        
        violations = validator.validate_code(code_with_disallowed_package)
        assert len(violations) >= 1
        
        # Should detect non-allowed package
        violation_messages = [v.message for v in violations]
        assert any("malicious_package" in msg for msg in violation_messages)
    
    def test_security_report_generation(self, validator):
        """Test security report generation."""
        mixed_code = """
        x <- c(1, 2, 3)
        system("echo hello")  # Dangerous
        library(unknown_pkg)  # Not allowed
        mean(x)  # Safe
        """
        
        report = validator.get_security_report(mixed_code)
        
        assert "total_violations" in report
        assert "risk_score" in report
        assert "is_safe" in report
        assert "violations" in report
        assert "recommendations" in report
        
        assert report["total_violations"] > 0
        assert report["risk_score"] > 0
        assert not report["is_safe"]
        assert len(report["recommendations"]) > 0


class TestAccessController:
    """Test access control system."""
    
    @pytest.fixture
    def access_controller(self):
        """Create access controller fixture."""
        return AccessController()
    
    def test_session_management(self, access_controller):
        """Test session creation and management."""
        session_id = "test-session-123"
        user_id = "test-user"
        
        # Create session
        access_controller.create_session(session_id, user_id)
        
        # Verify session exists
        session_info = access_controller.get_session_info(session_id)
        assert session_info is not None
        assert session_info["user_id"] == user_id
        
        # List sessions
        sessions = access_controller.list_active_sessions()
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == session_id
        
        # Destroy session
        assert access_controller.destroy_session(session_id)
        assert access_controller.get_session_info(session_id) is None
    
    def test_access_permission_checking(self, access_controller):
        """Test access permission checking."""
        session_id = "test-session"
        user_id = "test-user"
        
        access_controller.create_session(session_id, user_id)
        
        # Test file access
        assert access_controller.check_access(
            session_id, ResourceType.FILE, "/tmp/test.txt", Permission.READ
        )
        
        # Test blocked access
        assert not access_controller.check_access(
            session_id, ResourceType.FILE, "/etc/passwd", Permission.WRITE
        )
        
        # Test environment access
        assert access_controller.check_access(
            session_id, ResourceType.ENVIRONMENT, "test-env", Permission.CREATE
        )
    
    def test_custom_access_rules(self, access_controller):
        """Test custom access rule management."""
        # Add custom rule
        custom_rule = AccessRule(
            resource_type=ResourceType.FILE,
            resource_pattern="/custom/*",
            permissions={Permission.READ, Permission.WRITE},
            description="Custom file access rule"
        )
        
        access_controller.add_access_rule(custom_rule)
        
        # Test access with custom rule
        session_id = "test-session"
        access_controller.create_session(session_id)
        
        assert access_controller.check_access(
            session_id, ResourceType.FILE, "/custom/file.txt", Permission.READ
        )
        assert access_controller.check_access(
            session_id, ResourceType.FILE, "/custom/file.txt", Permission.WRITE
        )
        assert not access_controller.check_access(
            session_id, ResourceType.FILE, "/custom/file.txt", Permission.DELETE
        )
    
    def test_session_cleanup(self, access_controller):
        """Test expired session cleanup."""
        session_id = "test-session"
        access_controller.create_session(session_id)
        
        # Manually set old timestamp
        access_controller.active_sessions[session_id]["last_activity"] = time.time() - 7200  # 2 hours ago
        
        # Cleanup with 1 hour max age
        cleaned_count = access_controller.cleanup_expired_sessions(max_age_seconds=3600)
        
        assert cleaned_count == 1
        assert access_controller.get_session_info(session_id) is None


class TestAuditLogger:
    """Test audit logging system."""
    
    @pytest.fixture
    def temp_log_file(self):
        """Create temporary log file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            temp_path = f.name
        yield temp_path
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)
    
    @pytest.fixture
    def audit_logger(self, temp_log_file):
        """Create audit logger fixture."""
        config = {
            'enabled': True,
            'log_file': temp_log_file,
            'flush_interval': 0.1  # Quick flush for testing
        }
        logger = AuditLogger(config)
        yield logger
        logger.shutdown()
    
    def test_audit_event_logging(self, audit_logger):
        """Test basic audit event logging."""
        event = AuditEvent(
            event_type=AuditEventType.ACCESS_GRANTED,
            level=AuditLevel.INFO,
            message="Test access granted",
            timestamp=time.time(),
            session_id="test-session",
            user_id="test-user"
        )
        
        # Log event
        success = audit_logger.log_event(event)
        assert success
        
        # Wait for flush
        time.sleep(0.2)
        
        # Verify event was written
        stats = audit_logger.get_statistics()
        assert stats['events_logged'] > 0
    
    def test_convenience_logging_methods(self, audit_logger):
        """Test convenience logging methods."""
        session_id = "test-session"
        user_id = "test-user"
        
        # Test different log methods
        audit_logger.log_access_granted(
            session_id, user_id, "file", "/test/file.txt", "read"
        )
        
        audit_logger.log_access_denied(
            session_id, user_id, "file", "/etc/passwd", "write", "Permission denied"
        )
        
        audit_logger.log_code_execution(
            session_id, user_id, "print('hello')", "success", 0.1
        )
        
        audit_logger.log_security_violation(
            session_id, user_id, "blocked_function", "high", "system() call detected"
        )
        
        # Wait for flush
        time.sleep(0.2)
        
        # Verify events were logged
        stats = audit_logger.get_statistics()
        assert stats['events_logged'] >= 4
    
    def test_event_querying(self, audit_logger, temp_log_file):
        """Test querying audit events."""
        # Log some events
        current_time = time.time()
        
        for i in range(5):
            event = AuditEvent(
                event_type=AuditEventType.TOOL_EXECUTED,
                level=AuditLevel.INFO,
                message=f"Tool execution {i}",
                timestamp=current_time + i,
                session_id=f"session-{i}",
                user_id="test-user"
            )
            audit_logger.log_event(event)
        
        # Wait for flush
        time.sleep(0.2)
        
        # Query events
        events = audit_logger.query_events(limit=10)
        assert len(events) == 5
        
        # Query with filters
        filtered_events = audit_logger.query_events(
            event_type=AuditEventType.TOOL_EXECUTED,
            session_id="session-2"
        )
        assert len(filtered_events) == 1
        assert filtered_events[0]['session_id'] == "session-2"


class TestConfigEncryption:
    """Test configuration encryption."""
    
    @pytest.fixture
    def encryption_password(self):
        """Test encryption password."""
        return "test-password-123"
    
    @pytest.fixture
    def config_encryption(self, encryption_password):
        """Create config encryption fixture."""
        return ConfigEncryption(encryption_password)
    
    @pytest.fixture
    def temp_config_file(self):
        """Create temporary config file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name
        yield temp_path
        Path(temp_path).unlink(missing_ok=True)
    
    def test_data_encryption_decryption(self, config_encryption):
        """Test basic data encryption and decryption."""
        test_data = {
            "database_password": "secret123",
            "api_key": "abc-def-ghi",
            "settings": {
                "debug": True,
                "timeout": 30
            }
        }
        
        # Encrypt data
        encrypted_config = config_encryption.encrypt_data(test_data)
        
        assert isinstance(encrypted_config, EncryptedConfig)
        assert encrypted_config.encrypted_data
        assert encrypted_config.salt
        
        # Decrypt data
        decrypted_data = config_encryption.decrypt_data(encrypted_config)
        
        assert decrypted_data == test_data
    
    def test_file_encryption_decryption(self, config_encryption, temp_config_file):
        """Test file encryption and decryption."""
        # Create test config file
        test_config = {
            "server": {
                "host": "localhost",
                "port": 8080,
                "secret_key": "very-secret-key"
            },
            "database": {
                "url": "postgresql://user:pass@localhost/db"
            }
        }
        
        with open(temp_config_file, 'w') as f:
            json.dump(test_config, f, indent=2)
        
        # Encrypt file
        encrypted_file = temp_config_file + ".encrypted"
        config_encryption.encrypt_file(temp_config_file, encrypted_file)
        
        assert Path(encrypted_file).exists()
        
        # Verify encrypted file format
        with open(encrypted_file, 'r') as f:
            encrypted_data = json.load(f)
        
        assert 'encrypted_data' in encrypted_data
        assert 'salt' in encrypted_data
        assert 'algorithm' in encrypted_data
        
        # Decrypt file
        decrypted_file = temp_config_file + ".decrypted"
        config_encryption.decrypt_file(encrypted_file, decrypted_file)
        
        # Verify decrypted content
        with open(decrypted_file, 'r') as f:
            decrypted_config = json.load(f)
        
        assert decrypted_config == test_config
        
        # Cleanup
        Path(encrypted_file).unlink(missing_ok=True)
        Path(decrypted_file).unlink(missing_ok=True)
    
    def test_load_save_encrypted_config(self, config_encryption, temp_config_file):
        """Test loading and saving encrypted configuration."""
        test_config = {
            "sensitive_data": "secret-value",
            "normal_data": "public-value"
        }
        
        # Save encrypted config
        config_encryption.save_encrypted_config(test_config, temp_config_file)
        
        # Verify file is encrypted
        assert config_encryption.is_file_encrypted(temp_config_file)
        
        # Load encrypted config
        loaded_config = config_encryption.load_encrypted_config(temp_config_file)
        
        assert loaded_config == test_config
    
    def test_password_change(self, temp_config_file):
        """Test changing encryption password."""
        old_password = "old-password"
        new_password = "new-password"
        
        test_config = {"secret": "value"}
        
        # Save with old password
        old_encryption = ConfigEncryption(old_password)
        old_encryption.save_encrypted_config(test_config, temp_config_file)
        
        # Change password
        new_encryption = ConfigEncryption(new_password)
        new_encryption.change_password(old_password, new_password, temp_config_file)
        
        # Verify can load with new password
        loaded_config = new_encryption.load_encrypted_config(temp_config_file)
        assert loaded_config == test_config
        
        # Verify cannot load with old password
        with pytest.raises(Exception):
            old_encryption.load_encrypted_config(temp_config_file)


class TestSecurityIntegration:
    """Test integration of all security components."""
    
    @pytest.fixture
    def security_system(self):
        """Create integrated security system."""
        # Set up components
        access_controller = AccessController()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.log') as f:
            audit_log_file = f.name
        
        audit_logger = AuditLogger({
            'enabled': True,
            'log_file': audit_log_file,
            'flush_interval': 0.1
        })
        
        code_validator = CodeSecurityValidator()
        
        yield {
            'access_controller': access_controller,
            'audit_logger': audit_logger,
            'code_validator': code_validator,
            'audit_log_file': audit_log_file
        }
        
        # Cleanup
        audit_logger.shutdown()
        Path(audit_log_file).unlink(missing_ok=True)
    
    def test_secure_code_execution_flow(self, security_system):
        """Test complete secure code execution flow."""
        access_controller = security_system['access_controller']
        audit_logger = security_system['audit_logger']
        code_validator = security_system['code_validator']
        
        session_id = "test-session"
        user_id = "test-user"
        
        # Create session
        access_controller.create_session(session_id, user_id)
        
        # Test safe code
        safe_code = "x <- c(1, 2, 3); mean(x)"
        
        # 1. Check code security
        violations = code_validator.validate_code(safe_code)
        is_safe = len(violations) == 0
        
        # 2. Check execution permission
        can_execute = access_controller.check_access(
            session_id, ResourceType.TOOL, "execute_r_code", Permission.EXECUTE
        )
        
        # 3. Log the attempt
        if is_safe and can_execute:
            audit_logger.log_code_execution(
                session_id, user_id, safe_code, "success", 0.1
            )
        else:
            audit_logger.log_security_violation(
                session_id, user_id, "code_execution", "high", 
                "Unsafe code or insufficient permissions"
            )
        
        # Verify safe code passes all checks
        assert is_safe
        assert can_execute
        
        # Test dangerous code
        dangerous_code = "system('rm -rf /')"
        
        violations = code_validator.validate_code(dangerous_code)
        is_safe = len(violations) == 0
        
        if not is_safe:
            audit_logger.log_security_violation(
                session_id, user_id, "blocked_function", "critical",
                f"Dangerous code detected: {violations[0].message}"
            )
        
        # Verify dangerous code is blocked
        assert not is_safe
        
        # Wait for audit log flush
        time.sleep(0.2)
        
        # Verify audit events were logged
        stats = audit_logger.get_statistics()
        assert stats['events_logged'] >= 2
    
    def test_resource_access_with_audit(self, security_system):
        """Test resource access with audit logging."""
        access_controller = security_system['access_controller']
        audit_logger = security_system['audit_logger']
        
        session_id = "test-session"
        user_id = "test-user"
        
        access_controller.create_session(session_id, user_id)
        
        # Test allowed access
        resource_path = "/tmp/test.txt"
        permission = Permission.READ
        
        access_granted = access_controller.check_access(
            session_id, ResourceType.FILE, resource_path, permission
        )
        
        if access_granted:
            audit_logger.log_access_granted(
                session_id, user_id, "file", resource_path, "read"
            )
        else:
            audit_logger.log_access_denied(
                session_id, user_id, "file", resource_path, "read", "Permission denied"
            )
        
        # Test denied access
        restricted_path = "/etc/passwd"
        
        access_granted = access_controller.check_access(
            session_id, ResourceType.FILE, restricted_path, Permission.WRITE
        )
        
        if access_granted:
            audit_logger.log_access_granted(
                session_id, user_id, "file", restricted_path, "write"
            )
        else:
            audit_logger.log_access_denied(
                session_id, user_id, "file", restricted_path, "write", "Permission denied"
            )
        
        # Wait for audit log flush
        time.sleep(0.2)
        
        # Query audit events
        events = audit_logger.query_events(session_id=session_id)
        
        # Should have both granted and denied events
        event_types = [event['event_type'] for event in events]
        assert 'access_granted' in event_types
        assert 'access_denied' in event_types