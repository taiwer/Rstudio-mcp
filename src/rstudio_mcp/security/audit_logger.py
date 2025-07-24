"""Audit logging and monitoring system."""

import json
import logging
import time
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import threading
from queue import Queue, Empty


class AuditLevel(Enum):
    """Audit event levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditEventType(Enum):
    """Types of audit events."""
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    CODE_EXECUTION = "code_execution"
    SECURITY_VIOLATION = "security_violation"
    SESSION_CREATED = "session_created"
    SESSION_DESTROYED = "session_destroyed"
    TOOL_EXECUTED = "tool_executed"
    RESOURCE_ACCESSED = "resource_accessed"
    CONFIG_CHANGED = "config_changed"
    ERROR_OCCURRED = "error_occurred"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"


@dataclass
class AuditEvent:
    """Represents an audit event."""
    
    event_type: AuditEventType
    level: AuditLevel
    message: str
    timestamp: float
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_path: Optional[str] = None
    action: Optional[str] = None
    result: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert audit event to dictionary.
        
        Returns:
            Dictionary representation of the event
        """
        data = asdict(self)
        # Convert enums to strings
        data['event_type'] = self.event_type.value
        data['level'] = self.level.value
        return data
    
    def to_json(self) -> str:
        """Convert audit event to JSON string.
        
        Returns:
            JSON representation of the event
        """
        return json.dumps(self.to_dict(), default=str)


class AuditLogger:
    """Audit logging system with async processing."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize audit logger.
        
        Args:
            config: Audit logging configuration
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Configuration
        self.enabled = self.config.get('enabled', True)
        self.log_file = self.config.get('log_file', '~/.rstudio-mcp/audit.log')
        self.max_file_size = self.config.get('max_file_size', 10 * 1024 * 1024)  # 10MB
        self.backup_count = self.config.get('backup_count', 5)
        self.buffer_size = self.config.get('buffer_size', 1000)
        self.flush_interval = self.config.get('flush_interval', 5.0)  # seconds
        
        # Expand log file path
        self.log_file = Path(self.log_file).expanduser().resolve()
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Event queue for async processing
        self.event_queue: Queue = Queue(maxsize=self.buffer_size)
        self.processing_thread: Optional[threading.Thread] = None
        self.shutdown_event = threading.Event()
        
        # Statistics
        self.stats = {
            'events_logged': 0,
            'events_dropped': 0,
            'last_flush': time.time(),
            'errors': 0
        }
        
        if self.enabled:
            self._start_processing_thread()
            self.logger.info(f"Audit logger initialized: {self.log_file}")
    
    def _start_processing_thread(self) -> None:
        """Start the background processing thread."""
        if self.processing_thread is None or not self.processing_thread.is_alive():
            self.processing_thread = threading.Thread(
                target=self._process_events,
                daemon=True,
                name="AuditLogProcessor"
            )
            self.processing_thread.start()
    
    def _process_events(self) -> None:
        """Background thread to process audit events."""
        events_buffer = []
        last_flush = time.time()
        
        while not self.shutdown_event.is_set():
            try:
                # Get events from queue with timeout
                try:
                    event = self.event_queue.get(timeout=1.0)
                    events_buffer.append(event)
                    self.event_queue.task_done()
                except Empty:
                    pass
                
                current_time = time.time()
                
                # Flush if buffer is full or flush interval reached
                should_flush = (
                    len(events_buffer) >= 100 or  # Buffer size threshold
                    (events_buffer and current_time - last_flush >= self.flush_interval)
                )
                
                if should_flush:
                    self._flush_events(events_buffer)
                    events_buffer.clear()
                    last_flush = current_time
                    self.stats['last_flush'] = current_time
                
            except Exception as e:
                self.logger.error(f"Error processing audit events: {e}")
                self.stats['errors'] += 1
        
        # Flush remaining events on shutdown
        if events_buffer:
            self._flush_events(events_buffer)
    
    def _flush_events(self, events: List[AuditEvent]) -> None:
        """Flush events to log file.
        
        Args:
            events: List of events to flush
        """
        if not events:
            return
        
        try:
            # Check if log rotation is needed
            if self.log_file.exists() and self.log_file.stat().st_size > self.max_file_size:
                self._rotate_log_file()
            
            # Write events to file
            with open(self.log_file, 'a', encoding='utf-8') as f:
                for event in events:
                    f.write(event.to_json() + '\n')
            
            self.stats['events_logged'] += len(events)
            
        except Exception as e:
            self.logger.error(f"Error flushing audit events: {e}")
            self.stats['errors'] += 1
    
    def _rotate_log_file(self) -> None:
        """Rotate log files when size limit is reached."""
        try:
            # Move existing backup files
            for i in range(self.backup_count - 1, 0, -1):
                old_file = self.log_file.with_suffix(f'.{i}')
                new_file = self.log_file.with_suffix(f'.{i + 1}')
                
                if old_file.exists():
                    if new_file.exists():
                        new_file.unlink()
                    old_file.rename(new_file)
            
            # Move current log to .1
            if self.log_file.exists():
                backup_file = self.log_file.with_suffix('.1')
                if backup_file.exists():
                    backup_file.unlink()
                self.log_file.rename(backup_file)
            
            self.logger.info(f"Rotated audit log file: {self.log_file}")
            
        except Exception as e:
            self.logger.error(f"Error rotating audit log file: {e}")
    
    def log_event(self, event: AuditEvent) -> bool:
        """Log an audit event.
        
        Args:
            event: Audit event to log
            
        Returns:
            True if event was queued successfully, False otherwise
        """
        if not self.enabled:
            return True
        
        try:
            # Add to queue (non-blocking)
            self.event_queue.put_nowait(event)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to queue audit event: {e}")
            self.stats['events_dropped'] += 1
            return False
    
    def log_access_granted(self, session_id: str, user_id: Optional[str],
                          resource_type: str, resource_path: str,
                          action: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Log access granted event.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            resource_type: Type of resource
            resource_path: Resource path
            action: Action performed
            metadata: Additional metadata
        """
        event = AuditEvent(
            event_type=AuditEventType.ACCESS_GRANTED,
            level=AuditLevel.INFO,
            message=f"Access granted: {action} on {resource_type}:{resource_path}",
            timestamp=time.time(),
            session_id=session_id,
            user_id=user_id,
            resource_type=resource_type,
            resource_path=resource_path,
            action=action,
            result="granted",
            metadata=metadata
        )
        self.log_event(event)
    
    def log_access_denied(self, session_id: str, user_id: Optional[str],
                         resource_type: str, resource_path: str,
                         action: str, reason: str,
                         metadata: Optional[Dict[str, Any]] = None) -> None:
        """Log access denied event.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            resource_type: Type of resource
            resource_path: Resource path
            action: Action attempted
            reason: Reason for denial
            metadata: Additional metadata
        """
        event = AuditEvent(
            event_type=AuditEventType.ACCESS_DENIED,
            level=AuditLevel.WARNING,
            message=f"Access denied: {action} on {resource_type}:{resource_path} - {reason}",
            timestamp=time.time(),
            session_id=session_id,
            user_id=user_id,
            resource_type=resource_type,
            resource_path=resource_path,
            action=action,
            result="denied",
            metadata={"reason": reason, **(metadata or {})}
        )
        self.log_event(event)
    
    def log_code_execution(self, session_id: str, user_id: Optional[str],
                          code: str, result: str, execution_time: float,
                          metadata: Optional[Dict[str, Any]] = None) -> None:
        """Log code execution event.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            code: Code that was executed
            result: Execution result
            execution_time: Time taken to execute
            metadata: Additional metadata
        """
        # Truncate code for logging
        code_snippet = code[:200] + "..." if len(code) > 200 else code
        
        event = AuditEvent(
            event_type=AuditEventType.CODE_EXECUTION,
            level=AuditLevel.INFO,
            message=f"Code executed: {len(code)} characters in {execution_time:.2f}s",
            timestamp=time.time(),
            session_id=session_id,
            user_id=user_id,
            action="execute_code",
            result=result,
            metadata={
                "code_snippet": code_snippet,
                "code_length": len(code),
                "execution_time": execution_time,
                **(metadata or {})
            }
        )
        self.log_event(event)
    
    def log_security_violation(self, session_id: str, user_id: Optional[str],
                              violation_type: str, severity: str,
                              details: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Log security violation event.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            violation_type: Type of violation
            severity: Severity level
            details: Violation details
            metadata: Additional metadata
        """
        level_map = {
            'low': AuditLevel.INFO,
            'medium': AuditLevel.WARNING,
            'high': AuditLevel.ERROR,
            'critical': AuditLevel.CRITICAL
        }
        
        event = AuditEvent(
            event_type=AuditEventType.SECURITY_VIOLATION,
            level=level_map.get(severity.lower(), AuditLevel.WARNING),
            message=f"Security violation: {violation_type} - {details}",
            timestamp=time.time(),
            session_id=session_id,
            user_id=user_id,
            action="security_check",
            result="violation",
            metadata={
                "violation_type": violation_type,
                "severity": severity,
                "details": details,
                **(metadata or {})
            }
        )
        self.log_event(event)
    
    def log_tool_execution(self, session_id: str, user_id: Optional[str],
                          tool_name: str, arguments: Dict[str, Any],
                          result: str, execution_time: float,
                          metadata: Optional[Dict[str, Any]] = None) -> None:
        """Log tool execution event.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            tool_name: Name of tool executed
            arguments: Tool arguments
            result: Execution result
            execution_time: Time taken to execute
            metadata: Additional metadata
        """
        event = AuditEvent(
            event_type=AuditEventType.TOOL_EXECUTED,
            level=AuditLevel.INFO,
            message=f"Tool executed: {tool_name} in {execution_time:.2f}s",
            timestamp=time.time(),
            session_id=session_id,
            user_id=user_id,
            action="execute_tool",
            result=result,
            metadata={
                "tool_name": tool_name,
                "arguments": arguments,
                "execution_time": execution_time,
                **(metadata or {})
            }
        )
        self.log_event(event)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get audit logging statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            **self.stats,
            'queue_size': self.event_queue.qsize(),
            'enabled': self.enabled,
            'log_file': str(self.log_file),
            'processing_thread_alive': (
                self.processing_thread is not None and 
                self.processing_thread.is_alive()
            )
        }
    
    def query_events(self, start_time: Optional[float] = None,
                    end_time: Optional[float] = None,
                    event_type: Optional[AuditEventType] = None,
                    session_id: Optional[str] = None,
                    user_id: Optional[str] = None,
                    limit: int = 1000) -> List[Dict[str, Any]]:
        """Query audit events from log file.
        
        Args:
            start_time: Start timestamp filter
            end_time: End timestamp filter
            event_type: Event type filter
            session_id: Session ID filter
            user_id: User ID filter
            limit: Maximum number of events to return
            
        Returns:
            List of matching events
        """
        events = []
        
        try:
            if not self.log_file.exists():
                return events
            
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if len(events) >= limit:
                        break
                    
                    try:
                        event_data = json.loads(line.strip())
                        
                        # Apply filters
                        if start_time and event_data.get('timestamp', 0) < start_time:
                            continue
                        if end_time and event_data.get('timestamp', 0) > end_time:
                            continue
                        if event_type and event_data.get('event_type') != event_type.value:
                            continue
                        if session_id and event_data.get('session_id') != session_id:
                            continue
                        if user_id and event_data.get('user_id') != user_id:
                            continue
                        
                        events.append(event_data)
                        
                    except json.JSONDecodeError:
                        continue
            
        except Exception as e:
            self.logger.error(f"Error querying audit events: {e}")
        
        # Return most recent events first
        return list(reversed(events))
    
    def shutdown(self, timeout: float = 10.0) -> None:
        """Shutdown the audit logger.
        
        Args:
            timeout: Maximum time to wait for shutdown
        """
        if not self.enabled:
            return
        
        self.logger.info("Shutting down audit logger")
        
        # Signal shutdown
        self.shutdown_event.set()
        
        # Wait for processing thread to finish
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=timeout)
        
        # Wait for queue to be processed
        try:
            self.event_queue.join()
        except Exception:
            pass
        
        self.logger.info("Audit logger shutdown complete")