"""Access control and permission management."""

import logging
from enum import Enum
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import fnmatch


class Permission(Enum):
    """Permission types."""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELETE = "delete"
    CREATE = "create"
    ADMIN = "admin"


class ResourceType(Enum):
    """Resource types for access control."""
    FILE = "file"
    DIRECTORY = "directory"
    ENVIRONMENT = "environment"
    PROJECT = "project"
    PACKAGE = "package"
    TOOL = "tool"
    RESOURCE = "resource"
    PROMPT = "prompt"


@dataclass
class AccessRule:
    """Represents an access control rule."""
    
    resource_type: ResourceType
    resource_pattern: str  # Glob pattern for resource matching
    permissions: Set[Permission]
    user_id: Optional[str] = None  # None means applies to all users
    description: Optional[str] = None
    priority: int = 0  # Higher priority rules override lower priority ones


class ResourceAccessControl:
    """Manages resource access control."""
    
    def __init__(self):
        """Initialize resource access control."""
        self.logger = logging.getLogger(__name__)
        self.rules: List[AccessRule] = []
        self._setup_default_rules()
    
    def _setup_default_rules(self) -> None:
        """Set up default access control rules."""
        # Default file system rules
        self.add_rule(AccessRule(
            resource_type=ResourceType.FILE,
            resource_pattern="/etc/*",
            permissions=set(),  # No permissions - blocked
            description="Block access to system configuration files"
        ))
        
        self.add_rule(AccessRule(
            resource_type=ResourceType.FILE,
            resource_pattern="/usr/*",
            permissions={Permission.READ},
            description="Read-only access to system files"
        ))
        
        self.add_rule(AccessRule(
            resource_type=ResourceType.FILE,
            resource_pattern="/tmp/*",
            permissions={Permission.READ, Permission.WRITE, Permission.CREATE, Permission.DELETE},
            description="Full access to temporary files"
        ))
        
        self.add_rule(AccessRule(
            resource_type=ResourceType.DIRECTORY,
            resource_pattern="~/.rstudio-mcp/*",
            permissions={Permission.READ, Permission.WRITE, Permission.CREATE},
            description="Access to RStudio MCP user directory"
        ))
        
        # Default environment rules
        self.add_rule(AccessRule(
            resource_type=ResourceType.ENVIRONMENT,
            resource_pattern="*",
            permissions={Permission.READ, Permission.WRITE, Permission.CREATE, Permission.DELETE},
            description="Full access to R environments"
        ))
        
        # Default project rules
        self.add_rule(AccessRule(
            resource_type=ResourceType.PROJECT,
            resource_pattern="*",
            permissions={Permission.READ, Permission.WRITE, Permission.CREATE},
            description="Standard project access"
        ))
        
        # Default package rules
        self.add_rule(AccessRule(
            resource_type=ResourceType.PACKAGE,
            resource_pattern="base",
            permissions={Permission.READ, Permission.EXECUTE},
            description="Access to base R package"
        ))
        
        self.add_rule(AccessRule(
            resource_type=ResourceType.PACKAGE,
            resource_pattern="utils",
            permissions={Permission.READ, Permission.EXECUTE},
            description="Access to utils package"
        ))
        
        # Default tool rules
        self.add_rule(AccessRule(
            resource_type=ResourceType.TOOL,
            resource_pattern="*",
            permissions={Permission.EXECUTE},
            description="Execute access to all tools"
        ))
    
    def add_rule(self, rule: AccessRule) -> None:
        """Add an access control rule.
        
        Args:
            rule: Access rule to add
        """
        self.rules.append(rule)
        # Sort by priority (higher priority first)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
        self.logger.info(f"Added access rule: {rule.resource_type.value}:{rule.resource_pattern}")
    
    def remove_rule(self, resource_type: ResourceType, resource_pattern: str, 
                   user_id: Optional[str] = None) -> bool:
        """Remove an access control rule.
        
        Args:
            resource_type: Type of resource
            resource_pattern: Resource pattern
            user_id: Optional user ID
            
        Returns:
            True if rule was removed, False if not found
        """
        for i, rule in enumerate(self.rules):
            if (rule.resource_type == resource_type and 
                rule.resource_pattern == resource_pattern and
                rule.user_id == user_id):
                del self.rules[i]
                self.logger.info(f"Removed access rule: {resource_type.value}:{resource_pattern}")
                return True
        return False
    
    def check_permission(self, resource_type: ResourceType, resource_path: str,
                        permission: Permission, user_id: Optional[str] = None) -> bool:
        """Check if a permission is granted for a resource.
        
        Args:
            resource_type: Type of resource
            resource_path: Path or identifier of resource
            permission: Permission to check
            user_id: Optional user ID
            
        Returns:
            True if permission is granted, False otherwise
        """
        # Find matching rules (highest priority first)
        matching_rules = []
        
        for rule in self.rules:
            if rule.resource_type != resource_type:
                continue
            
            # Check user match
            if rule.user_id is not None and rule.user_id != user_id:
                continue
            
            # Check pattern match
            if fnmatch.fnmatch(resource_path, rule.resource_pattern):
                matching_rules.append(rule)
        
        if not matching_rules:
            # No matching rules - default deny
            self.logger.warning(f"No access rules found for {resource_type.value}:{resource_path}")
            return False
        
        # Use highest priority rule
        rule = matching_rules[0]
        granted = permission in rule.permissions
        
        self.logger.debug(f"Access check: {resource_type.value}:{resource_path} "
                         f"permission:{permission.value} granted:{granted}")
        
        return granted
    
    def get_permissions(self, resource_type: ResourceType, resource_path: str,
                       user_id: Optional[str] = None) -> Set[Permission]:
        """Get all permissions for a resource.
        
        Args:
            resource_type: Type of resource
            resource_path: Path or identifier of resource
            user_id: Optional user ID
            
        Returns:
            Set of granted permissions
        """
        # Find matching rules
        matching_rules = []
        
        for rule in self.rules:
            if rule.resource_type != resource_type:
                continue
            
            if rule.user_id is not None and rule.user_id != user_id:
                continue
            
            if fnmatch.fnmatch(resource_path, rule.resource_pattern):
                matching_rules.append(rule)
        
        if not matching_rules:
            return set()
        
        # Use highest priority rule
        return matching_rules[0].permissions.copy()
    
    def list_rules(self, resource_type: Optional[ResourceType] = None,
                  user_id: Optional[str] = None) -> List[AccessRule]:
        """List access control rules.
        
        Args:
            resource_type: Optional filter by resource type
            user_id: Optional filter by user ID
            
        Returns:
            List of matching access rules
        """
        rules = self.rules
        
        if resource_type is not None:
            rules = [r for r in rules if r.resource_type == resource_type]
        
        if user_id is not None:
            rules = [r for r in rules if r.user_id == user_id or r.user_id is None]
        
        return rules
    
    def clear_rules(self) -> None:
        """Clear all access control rules."""
        count = len(self.rules)
        self.rules.clear()
        self.logger.info(f"Cleared {count} access rules")


class AccessController:
    """Main access controller that integrates all access control mechanisms."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize access controller.
        
        Args:
            config: Access control configuration
        """
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
        # Initialize components
        self.resource_access = ResourceAccessControl()
        
        # Session tracking
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        
        # Rate limiting
        self.rate_limits: Dict[str, Dict[str, Any]] = {}
        
        self.logger.info("Access controller initialized")
    
    def create_session(self, session_id: str, user_id: Optional[str] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> None:
        """Create a new access control session.
        
        Args:
            session_id: Unique session identifier
            user_id: Optional user identifier
            metadata: Optional session metadata
        """
        self.active_sessions[session_id] = {
            "user_id": user_id,
            "created_at": self._get_current_time(),
            "last_activity": self._get_current_time(),
            "metadata": metadata or {},
            "permissions_cache": {}
        }
        
        self.logger.info(f"Created access session: {session_id} (user: {user_id})")
    
    def destroy_session(self, session_id: str) -> bool:
        """Destroy an access control session.
        
        Args:
            session_id: Session identifier to destroy
            
        Returns:
            True if session was destroyed, False if not found
        """
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
            self.logger.info(f"Destroyed access session: {session_id}")
            return True
        return False
    
    def check_access(self, session_id: str, resource_type: ResourceType,
                    resource_path: str, permission: Permission) -> bool:
        """Check access permission for a session.
        
        Args:
            session_id: Session identifier
            resource_type: Type of resource
            resource_path: Resource path or identifier
            permission: Permission to check
            
        Returns:
            True if access is granted, False otherwise
        """
        # Check if session exists
        if session_id not in self.active_sessions:
            self.logger.warning(f"Access check for unknown session: {session_id}")
            return False
        
        session = self.active_sessions[session_id]
        user_id = session.get("user_id")
        
        # Update last activity
        session["last_activity"] = self._get_current_time()
        
        # Check rate limiting
        if not self._check_rate_limit(session_id, resource_type, permission):
            self.logger.warning(f"Rate limit exceeded for session: {session_id}")
            return False
        
        # Check resource access
        access_granted = self.resource_access.check_permission(
            resource_type, resource_path, permission, user_id
        )
        
        # Cache result
        cache_key = f"{resource_type.value}:{resource_path}:{permission.value}"
        session["permissions_cache"][cache_key] = access_granted
        
        # Log access attempt
        self.logger.info(f"Access check: session={session_id} "
                        f"resource={resource_type.value}:{resource_path} "
                        f"permission={permission.value} granted={access_granted}")
        
        return access_granted
    
    def _check_rate_limit(self, session_id: str, resource_type: ResourceType,
                         permission: Permission) -> bool:
        """Check if session is within rate limits.
        
        Args:
            session_id: Session identifier
            resource_type: Resource type
            permission: Permission type
            
        Returns:
            True if within limits, False if exceeded
        """
        # Simple rate limiting implementation
        current_time = self._get_current_time()
        
        if session_id not in self.rate_limits:
            self.rate_limits[session_id] = {}
        
        rate_key = f"{resource_type.value}:{permission.value}"
        
        if rate_key not in self.rate_limits[session_id]:
            self.rate_limits[session_id][rate_key] = {
                "count": 0,
                "window_start": current_time
            }
        
        rate_info = self.rate_limits[session_id][rate_key]
        
        # Reset window if needed (1 minute window)
        if current_time - rate_info["window_start"] > 60:
            rate_info["count"] = 0
            rate_info["window_start"] = current_time
        
        # Check limits (configurable per resource type)
        limits = self.config.get("rate_limits", {})
        default_limit = limits.get("default", 100)
        resource_limit = limits.get(resource_type.value, default_limit)
        
        if rate_info["count"] >= resource_limit:
            return False
        
        rate_info["count"] += 1
        return True
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session information or None if not found
        """
        if session_id not in self.active_sessions:
            return None
        
        session = self.active_sessions[session_id].copy()
        # Don't expose the permissions cache
        session.pop("permissions_cache", None)
        return session
    
    def list_active_sessions(self) -> List[Dict[str, Any]]:
        """List all active sessions.
        
        Returns:
            List of session information
        """
        sessions = []
        for session_id, session_data in self.active_sessions.items():
            session_info = session_data.copy()
            session_info["session_id"] = session_id
            session_info.pop("permissions_cache", None)
            sessions.append(session_info)
        
        return sessions
    
    def cleanup_expired_sessions(self, max_age_seconds: int = 3600) -> int:
        """Clean up expired sessions.
        
        Args:
            max_age_seconds: Maximum session age in seconds
            
        Returns:
            Number of sessions cleaned up
        """
        current_time = self._get_current_time()
        expired_sessions = []
        
        for session_id, session_data in self.active_sessions.items():
            age = current_time - session_data["last_activity"]
            if age > max_age_seconds:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            self.destroy_session(session_id)
        
        if expired_sessions:
            self.logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
        
        return len(expired_sessions)
    
    def add_access_rule(self, rule: AccessRule) -> None:
        """Add an access control rule.
        
        Args:
            rule: Access rule to add
        """
        self.resource_access.add_rule(rule)
    
    def remove_access_rule(self, resource_type: ResourceType, resource_pattern: str,
                          user_id: Optional[str] = None) -> bool:
        """Remove an access control rule.
        
        Args:
            resource_type: Resource type
            resource_pattern: Resource pattern
            user_id: Optional user ID
            
        Returns:
            True if rule was removed
        """
        return self.resource_access.remove_rule(resource_type, resource_pattern, user_id)
    
    def get_access_rules(self, resource_type: Optional[ResourceType] = None) -> List[AccessRule]:
        """Get access control rules.
        
        Args:
            resource_type: Optional filter by resource type
            
        Returns:
            List of access rules
        """
        return self.resource_access.list_rules(resource_type)
    
    def _get_current_time(self) -> float:
        """Get current time as timestamp.
        
        Returns:
            Current timestamp
        """
        import time
        return time.time()