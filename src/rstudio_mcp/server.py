"""Core MCP server implementation for RStudio integration."""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from mcp.server import FastMCP
from mcp.types import TextContent

from .config import ServerConfig
from .exceptions import RStudioMCPError
from .logging_config import setup_logging
from .monitoring.cache_manager import CacheManager
from .monitoring.error_recovery import (
    ErrorRecoveryManager,
    RecoveryAction,
    RecoveryStrategy,
)
from .monitoring.metrics_collector import MetricsCollector
from .monitoring.performance_monitor import PerformanceMonitor, performance_monitor
from .monitoring.resource_monitor import ResourceMonitor
from .prompts import PromptManager
from .resources import ResourceManager
from .security import (
    AccessController,
    AuditLogger,
    CodeSecurityValidator,
    Permission,
    ResourceType,
    SecurityLevel,
)
from .tools import ToolManager
from .transport import SSETransport


class RStudioMCPServer:
    """Main MCP server class for RStudio integration."""

    def __init__(self, config: ServerConfig):
        """Initialize the RStudio MCP server.

        Args:
            config: Server configuration object
        """
        self.config = config
        self.logger = setup_logging(config.logging)
        self.server = FastMCP(
            name=config.name,
            instructions="RStudio MCP Server providing AI assistants with deep RStudio integration capabilities",
        )

        # Initialize managers
        self.tool_manager = ToolManager()
        self.resource_manager = ResourceManager()
        self.prompt_manager = PromptManager()

        # Initialize security components
        self.access_controller = AccessController(
            config.security.dict() if hasattr(config, "security") else {}
        )
        self.code_validator = CodeSecurityValidator(
            config.security.dict() if hasattr(config, "security") else {}
        )

        # Initialize audit logger
        audit_config = {
            "enabled": True,
            "log_file": config.get_log_file_path() or "~/.rstudio-mcp/audit.log",
            "flush_interval": 5.0,
        }
        self.audit_logger = AuditLogger(audit_config)

        # Initialize performance monitoring components
        self._performance_monitor = PerformanceMonitor(max_metrics=10000)
        self._metrics_collector = MetricsCollector(max_series=100)
        self._cache_manager = CacheManager()
        self._resource_monitor = ResourceMonitor()

        # Initialize error recovery manager
        self._error_recovery_manager = ErrorRecoveryManager()
        self._setup_error_recovery()

        # Initialize custom SSE transport
        self.sse_transport: Optional[SSETransport] = None

        self._setup_basic_tools()
        self._setup_tool_handlers()
        self._setup_resource_handlers()
        self._setup_prompt_handlers()

        # Start performance monitoring
        self._start_monitoring()

        self.logger.info(
            f"RStudio MCP Server initialized: {config.name} v{config.version}"
        )

    def _start_monitoring(self) -> None:
        """Start performance monitoring systems."""
        try:
            # Start performance monitoring
            self._performance_monitor.start_monitoring(interval=5.0)

            # Start resource monitoring
            self._resource_monitor.start_monitoring(interval=10.0)

            # Start cache cleanup task
            self._cache_manager.start_cleanup_task()

            # Set up default caches
            self._cache_manager.create_cache(
                "tool_results", max_size=500, max_memory_mb=50
            )
            self._cache_manager.create_cache(
                "resource_data", max_size=200, max_memory_mb=100
            )
            self._cache_manager.create_cache(
                "prompt_templates", max_size=100, max_memory_mb=10
            )

            self.logger.info("Performance monitoring started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start performance monitoring: {e}")

    def _setup_error_recovery(self) -> None:
        """Set up error recovery system with custom recovery actions."""
        try:
            # Register custom recovery actions for RStudio-specific errors
            self._error_recovery_manager.register_recovery_action(
                "RRuntimeError",
                RecoveryAction(
                    strategy=RecoveryStrategy.RETRY,
                    max_attempts=2,
                    delay_seconds=1.0,
                    backoff_multiplier=1.5,
                ),
            )

            self._error_recovery_manager.register_recovery_action(
                "ExecutionError",
                RecoveryAction(
                    strategy=RecoveryStrategy.FALLBACK,
                    max_attempts=1,
                    fallback_function=self._r_execution_fallback,
                ),
            )

            self._error_recovery_manager.register_recovery_action(
                "EnvironmentError",
                RecoveryAction(strategy=RecoveryStrategy.RESTART, max_attempts=1),
            )

            # Register health checks
            self._error_recovery_manager.register_health_check(
                "server_health", self._check_server_health
            )
            self._error_recovery_manager.register_health_check(
                "resource_health", self._check_resource_health
            )
            self._error_recovery_manager.register_health_check(
                "tool_manager_health", self._check_tool_manager_health
            )

            # Add error recovery tools
            self._setup_error_recovery_tools()

            self.logger.info("Error recovery system initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize error recovery system: {e}")

    def _r_execution_fallback(self, error: Exception) -> str:
        """Fallback function for R execution errors."""
        self.logger.warning(f"R execution failed, using fallback: {error}")
        return f"R execution failed with error: {str(error)}. Please check your R code and try again."

    def _check_server_health(self) -> bool:
        """Check overall server health."""
        try:
            # Check if core components are available
            return (
                self.tool_manager is not None
                and self.resource_manager is not None
                and self.prompt_manager is not None
                and self._performance_monitor is not None
            )
        except Exception:
            return False

    def _check_resource_health(self) -> bool:
        """Check resource monitoring health."""
        try:
            return self._resource_monitor.is_healthy()
        except Exception:
            return False

    def _check_tool_manager_health(self) -> bool:
        """Check tool manager health."""
        try:
            # Check if tool manager can list tools
            tools = self.tool_manager.list_tools()
            return isinstance(tools, list)
        except Exception:
            return False

    def _setup_error_recovery_tools(self) -> None:
        """Set up tools for error recovery management."""

        @self.server.tool()
        async def get_error_statistics(hours: int = 24) -> str:
            """Get error statistics for the specified time period."""
            stats = self._error_recovery_manager.get_error_statistics(hours)

            result = [
                f"Error Statistics (Last {hours} hours):",
                f"- Total errors: {stats['total_errors']}",
                f"- Error rate: {stats['error_rate']:.2f} errors/hour",
                f"- Recovery attempts: {stats['recovery_attempts']}",
                f"- Successful recoveries: {stats['successful_recoveries']}",
                f"- Recovery rate: {stats['recovery_rate']:.1%}",
                f"",
                f"Error Types:",
            ]

            for error_type, count in stats["error_types"].items():
                result.append(f"- {error_type}: {count}")

            result.append("")
            result.append("Severity Distribution:")
            for severity, count in stats["severity_distribution"].items():
                result.append(f"- {severity}: {count}")

            return "\n".join(result)

        @self.server.tool()
        async def get_system_health() -> str:
            """Get overall system health status."""
            health = self._error_recovery_manager.get_system_health()
            health_checks = await self._error_recovery_manager.run_health_checks()

            result = [
                f"System Health Status: {health['status'].upper()}",
                f"- Error rate: {health['error_rate_per_hour']:.2f} errors/hour",
                f"- Recovery rate: {health['recovery_rate']:.1%}",
                f"- Critical errors: {health['critical_errors']}",
                f"- Circuit breakers: {health['total_circuit_breakers']} total, {health['open_circuit_breakers']} open",
                f"",
                f"Health Checks:",
            ]

            for check_name, status in health_checks.items():
                status_str = "PASS" if status else "FAIL"
                result.append(f"- {check_name}: {status_str}")

            return "\n".join(result)

        @self.server.tool()
        def clear_error_history() -> str:
            """Clear error history and reset error recovery state."""
            self._error_recovery_manager.clear_error_history()

            # Reset circuit breakers
            for breaker in self._error_recovery_manager.circuit_breakers.values():
                breaker.failure_count = 0
                breaker.last_failure_time = None
                breaker.state = "closed"

            return "Error history cleared and recovery state reset successfully."

        @self.server.tool()
        async def trigger_health_checks() -> str:
            """Manually trigger all health checks."""
            results = await self._error_recovery_manager.run_health_checks()

            result = ["Health Check Results:"]
            all_passed = True

            for check_name, status in results.items():
                status_str = "PASS" if status else "FAIL"
                result.append(f"- {check_name}: {status_str}")
                if not status:
                    all_passed = False

            result.append("")
            result.append(f"Overall Status: {'HEALTHY' if all_passed else 'UNHEALTHY'}")

            return "\n".join(result)

    def _setup_basic_tools(self) -> None:
        """Set up basic tools for testing."""

        @self.server.tool()
        def get_server_info() -> str:
            """Get information about the RStudio MCP server."""
            return f"RStudio MCP Server v{self.config.version} - Status: Running"

        @self.server.tool()
        def get_config_info() -> str:
            """Get server configuration information."""
            return f"Server: {self.config.name}, Debug: {self.config.debug}, Host: {self.config.host}:{self.config.port}"

        @self.server.tool()
        def get_performance_stats() -> str:
            """Get current performance statistics."""
            summary = self._performance_monitor.get_performance_summary()
            metrics = self._metrics_collector.get_all_metrics()
            health = self._resource_monitor.get_health_status()

            stats = [
                f"Performance Summary:",
                f"- Total metrics: {summary.get('total_metrics', 0)}",
                f"- Active operations: {summary.get('active_operations', 0)}",
                f"- Operation types: {summary.get('operation_count', 0)}",
                f"",
                f"System Health:",
                f"- Healthy: {health.get('healthy', False)}",
                f"- CPU: {health.get('current_usage', {}).get('cpu_percent', 0):.1f}%",
                f"- Memory: {health.get('current_usage', {}).get('memory_percent', 0):.1f}%",
                f"- Process Memory: {health.get('current_usage', {}).get('process_memory_mb', 0):.1f}MB",
                f"",
                f"Cache Statistics:",
                f"- Total caches: {self._cache_manager.get_stats().get('total_caches', 0)}",
            ]

            return "\n".join(stats)

        @self.server.tool()
        def get_operation_metrics(operation_name: str = None) -> str:
            """Get detailed metrics for operations."""
            stats = self._performance_monitor.get_operation_stats(operation_name)

            if not stats:
                return "No operation statistics available."

            result = []
            for name, op_stats in stats.items():
                if op_stats:
                    result.append(f"Operation: {name}")
                    result.append(f"- Total calls: {op_stats.total_calls}")
                    result.append(f"- Average time: {op_stats.avg_time:.4f}s")
                    result.append(f"- Min time: {op_stats.min_time:.4f}s")
                    result.append(f"- Max time: {op_stats.max_time:.4f}s")
                    result.append(f"- Error count: {op_stats.error_count}")
                    result.append(
                        f"- Error rate: {(op_stats.error_count / op_stats.total_calls * 100):.1f}%"
                    )
                    result.append("")

            return "\n".join(result) if result else "No operation statistics found."

        @self.server.tool()
        def clear_performance_data() -> str:
            """Clear all performance monitoring data."""
            self._performance_monitor.clear_metrics()
            self._metrics_collector.clear_metrics()
            self._cache_manager.clear_all_caches()
            self._resource_monitor.clear_alerts()

            return "Performance monitoring data cleared successfully."

    def _setup_tool_handlers(self) -> None:
        """Set up MCP tool handlers for the tool manager."""

        @self.server.tool()
        def list_available_tools() -> str:
            """List all available tools in the tool manager."""
            tools = self.tool_manager.list_tools()
            if not tools:
                return "No tools are currently registered."

            tool_info = []
            for tool_name in tools:
                info = self.tool_manager.get_tool_info(tool_name)
                if info:
                    tool_info.append(f"- {tool_name}: {info['description']}")
                else:
                    tool_info.append(f"- {tool_name}: (description unavailable)")

            return "Available tools:\n" + "\n".join(tool_info)

        @self.server.tool()
        async def execute_managed_tool(
            name: str, arguments: dict = None, session_id: str = None
        ) -> str:
            """Execute a tool through the tool manager with security validation.

            Args:
                name: Name of the tool to execute
                arguments: Tool arguments as a dictionary
                session_id: Optional session ID for access control
            """
            if arguments is None:
                arguments = {}

            # Generate session ID if not provided
            if session_id is None:
                import uuid

                session_id = str(uuid.uuid4())
                self.access_controller.create_session(session_id)

            start_time = time.time()

            try:
                # Check tool execution permission
                if not self.access_controller.check_access(
                    session_id, ResourceType.TOOL, name, Permission.EXECUTE
                ):
                    error_msg = f"Access denied: insufficient permissions to execute tool '{name}'"
                    self.audit_logger.log_access_denied(
                        session_id,
                        None,
                        "tool",
                        name,
                        "execute",
                        "Insufficient permissions",
                    )
                    return error_msg

                # Special handling for code execution tools
                if name == "execute_r_code" and "code" in arguments:
                    code = arguments["code"]

                    # Validate code security
                    violations = self.code_validator.validate_code(code)
                    if violations:
                        # Check if violations are acceptable
                        critical_violations = [
                            v for v in violations if v.level == SecurityLevel.CRITICAL
                        ]
                        if critical_violations:
                            error_msg = f"Code execution blocked: {critical_violations[0].message}"
                            self.audit_logger.log_security_violation(
                                session_id,
                                None,
                                "code_execution",
                                "critical",
                                f"Blocked code execution: {critical_violations[0].message}",
                                {"code_snippet": code[:100]},
                            )
                            return error_msg

                        # Log security violations but allow execution
                        for violation in violations:
                            self.audit_logger.log_security_violation(
                                session_id,
                                None,
                                "code_execution",
                                violation.level.value,
                                violation.message,
                                {
                                    "code_snippet": code[:100],
                                    "line_number": violation.line_number,
                                },
                            )

                # Execute the tool
                result = await self.tool_manager.execute_tool(name, arguments)
                execution_time = time.time() - start_time

                # Log tool execution
                self.audit_logger.log_tool_execution(
                    session_id,
                    None,
                    name,
                    arguments,
                    "success" if result.success else "failure",
                    execution_time,
                )

                if result.success:
                    # Format the result content
                    if result.content:
                        content_parts = []
                        for item in result.content:
                            if item.get("type") == "text":
                                content_parts.append(item.get("text", ""))
                            elif item.get("type") == "image":
                                content_parts.append(
                                    f"[Image: {item.get('mimeType', 'unknown')}]"
                                )
                            elif item.get("type") == "resource":
                                resource = item.get("resource", {})
                                content_parts.append(
                                    f"[Resource: {resource.get('uri', 'unknown')}]"
                                )

                        return (
                            "\n".join(content_parts)
                            if content_parts
                            else "Tool executed successfully (no output)"
                        )
                    return "Tool executed successfully (no output)"
                else:
                    return f"Tool execution failed: {result.error}"

            except Exception as e:
                execution_time = time.time() - start_time
                self.audit_logger.log_tool_execution(
                    session_id,
                    None,
                    name,
                    arguments,
                    "error",
                    execution_time,
                    {"error": str(e)},
                )
                return f"Tool execution error: {str(e)}"

    def _setup_resource_handlers(self) -> None:
        """Set up MCP resource handlers for the resource manager."""

        @self.server.resource("rstudio://resources")
        async def list_available_resources() -> str:
            """List all available resources in the resource manager."""
            resources = await self.resource_manager.list_all_resources()
            if not resources:
                return "No resources are currently available."

            resource_info = []
            for resource in resources:
                resource_info.append(
                    f"- {resource.uri}: {resource.name} ({resource.mime_type})"
                )

            return "Available resources:\n" + "\n".join(resource_info)

        @self.server.resource("rstudio://resource/{uri}")
        async def read_managed_resource(uri: str) -> str:
            """Read a resource through the resource manager.

            Args:
                uri: URI of the resource to read
            """
            result = await self.resource_manager.read_resource(uri)

            if result.success:
                if result.is_text():
                    return (
                        result.get_text_content()
                        or "Resource read successfully (no text content)"
                    )
                elif result.is_binary():
                    return f"Binary resource read successfully ({len(result.get_binary_content() or b'')} bytes)"
                else:
                    return "Resource read successfully"
            else:
                return f"Resource read failed: {result.error}"

    def _setup_prompt_handlers(self) -> None:
        """Set up MCP prompt handlers for the prompt manager."""

        @self.server.prompt()
        def list_available_prompts() -> str:
            """List all available prompts in the prompt manager."""
            prompts = self.prompt_manager.list_prompts()
            if not prompts:
                return "No prompts are currently registered."

            prompt_info = []
            for prompt_name in prompts:
                info = self.prompt_manager.get_prompt_info(prompt_name)
                if info:
                    args_desc = ", ".join(
                        [
                            f"{arg['name']}{'*' if arg['required'] else ''}"
                            for arg in info["arguments"]
                        ]
                    )
                    prompt_info.append(
                        f"- {prompt_name}: {info['description']} (args: {args_desc})"
                    )
                else:
                    prompt_info.append(f"- {prompt_name}: (description unavailable)")

            return "Available prompts:\n" + "\n".join(prompt_info)

        @self.server.prompt()
        async def generate_managed_prompt(name: str, arguments: dict = None) -> str:
            """Generate a prompt through the prompt manager.

            Args:
                name: Name of the prompt to generate
                arguments: Prompt arguments as a dictionary
            """
            if arguments is None:
                arguments = {}

            result = await self.prompt_manager.generate_prompt(name, arguments)

            if result.success:
                if result.messages:
                    message_parts = []
                    for msg in result.messages:
                        message_parts.append(f"[{msg.role.upper()}]: {msg.content}")
                    return "\n\n".join(message_parts)
                else:
                    return "Prompt generated successfully (no messages)"
            else:
                return f"Prompt generation failed: {result.error}"

    async def run_stdio(self) -> None:
        """Run the server with STDIO transport."""
        self.logger.info("Starting MCP server with STDIO transport")
        try:
            await self.server.run_stdio_async()
        except Exception as e:
            self.logger.error(f"Server error: {e}")
            raise

    async def run_sse(self, host: str = "localhost", port: int = 3000) -> None:
        """Run the server with enhanced SSE transport."""
        host = host or self.config.host
        port = port or self.config.port

        self.logger.info(
            f"Starting MCP server with enhanced SSE transport on {host}:{port}"
        )

        try:
            # Initialize custom SSE transport
            self.sse_transport = SSETransport(
                host=host, port=port, heartbeat_interval=30
            )

            # Set up transport event handlers
            self._setup_sse_handlers()

            # Start the transport
            await self.sse_transport.start()

            # Also start the FastMCP SSE server for MCP protocol compatibility
            await asyncio.gather(
                self.server.run_sse_async(host=host, port=port + 1),  # MCP on port+1
                self._keep_sse_transport_alive(),  # Keep our transport running
            )

        except Exception as e:
            self.logger.error(f"SSE server error: {e}")
            if self.sse_transport:
                await self.sse_transport.stop()
            raise

    def _setup_sse_handlers(self) -> None:
        """Set up SSE transport event handlers."""
        if not self.sse_transport:
            return

        # Connection event handlers
        self.sse_transport.register_connection_handler(
            "connect", self._handle_sse_connect
        )
        self.sse_transport.register_connection_handler(
            "disconnect", self._handle_sse_disconnect
        )
        self.sse_transport.register_connection_handler(
            "transport_started", self._handle_sse_transport_started
        )
        self.sse_transport.register_connection_handler(
            "transport_stopped", self._handle_sse_transport_stopped
        )

        # Message handlers
        self.sse_transport.register_message_handler(
            "mcp_request", self._handle_sse_mcp_request
        )

        # Error handlers
        self.sse_transport.register_error_handler(
            "connection_error", self._handle_sse_connection_error
        )
        self.sse_transport.register_error_handler(
            "transport_error", self._handle_sse_transport_error
        )

    async def _handle_sse_connect(self, connection_id: str) -> None:
        """Handle SSE client connection."""
        self.logger.info(f"SSE client connected: {connection_id}")

        # Send welcome message
        welcome_message = {
            "type": "welcome",
            "data": {
                "server": self.config.name,
                "version": self.config.version,
                "connection_id": connection_id,
                "capabilities": {"tools": True, "resources": True, "prompts": True},
            },
        }

        if self.sse_transport:
            await self.sse_transport.send_to_connection(connection_id, welcome_message)

    async def _handle_sse_disconnect(self, connection_id: str) -> None:
        """Handle SSE client disconnection."""
        self.logger.info(f"SSE client disconnected: {connection_id}")

    async def _handle_sse_transport_started(self, host: str, port: int) -> None:
        """Handle SSE transport started event."""
        self.logger.info(f"SSE transport started successfully on {host}:{port}")

    async def _handle_sse_transport_stopped(self) -> None:
        """Handle SSE transport stopped event."""
        self.logger.info("SSE transport stopped")

    async def _handle_sse_mcp_request(
        self, message_data: Dict[str, Any], connection_id: str
    ) -> None:
        """Handle MCP request via SSE."""
        try:
            # Process MCP request (simplified - in real implementation,
            # this would integrate with the MCP protocol handler)
            request_type = message_data.get("method", "unknown")
            request_params = message_data.get("params", {})

            self.logger.debug(f"Processing MCP request via SSE: {request_type}")

            # Send response back to specific connection
            response = {
                "type": "mcp_response",
                "data": {
                    "id": message_data.get("id"),
                    "result": f"Processed {request_type}",
                    "success": True,
                },
            }

            if self.sse_transport:
                await self.sse_transport.send_to_connection(connection_id, response)

        except Exception as e:
            self.logger.error(f"Error processing SSE MCP request: {e}")

            # Send error response
            error_response = {
                "type": "mcp_error",
                "data": {
                    "id": message_data.get("id"),
                    "error": str(e),
                    "success": False,
                },
            }

            if self.sse_transport:
                await self.sse_transport.send_to_connection(
                    connection_id, error_response
                )

    async def _handle_sse_connection_error(self, error: Exception) -> None:
        """Handle SSE connection error."""
        self.logger.error(f"SSE connection error: {error}")

        # Implement reconnection logic if needed
        if self.sse_transport and hasattr(self.sse_transport, "connection_manager"):
            connection_count = (
                self.sse_transport.connection_manager.get_connection_count()
            )
            if connection_count == 0:
                self.logger.warning("No active SSE connections remaining")

    async def _handle_sse_transport_error(self, error: Exception) -> None:
        """Handle SSE transport error."""
        self.logger.error(f"SSE transport error: {error}")

        # Implement transport recovery logic
        try:
            if self.sse_transport:
                self.logger.info("Attempting to restart SSE transport...")
                await self.sse_transport.stop()
                await asyncio.sleep(5)  # Wait before restart
                await self.sse_transport.start()
                self.logger.info("SSE transport restarted successfully")
        except Exception as restart_error:
            self.logger.error(f"Failed to restart SSE transport: {restart_error}")

    async def _keep_sse_transport_alive(self) -> None:
        """Keep the SSE transport running."""
        try:
            while self.sse_transport and self.sse_transport.state.value == "connected":
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"Error in SSE transport keep-alive: {e}")

    async def broadcast_sse_message(self, message: Dict[str, Any]) -> int:
        """Broadcast message to all SSE connections.

        Args:
            message: Message to broadcast

        Returns:
            Number of connections that received the message
        """
        if not self.sse_transport:
            return 0

        try:
            return await self.sse_transport.send_message(message)
        except Exception as e:
            self.logger.error(f"Error broadcasting SSE message: {e}")
            return 0

    async def shutdown(self) -> None:
        """Gracefully shutdown the server."""
        self.logger.info("Shutting down RStudio MCP server")

        # Stop SSE transport first
        if self.sse_transport:
            try:
                await self.sse_transport.stop()
                self.logger.info("SSE transport stopped successfully")
            except Exception as e:
                self.logger.error(f"Error stopping SSE transport: {e}")

        # Cleanup security components
        if hasattr(self, "audit_logger") and self.audit_logger:
            try:
                self.audit_logger.shutdown()
                self.logger.info("Audit logger stopped successfully")
            except Exception as e:
                self.logger.error(f"Error stopping audit logger: {e}")

        if hasattr(self, "access_controller") and self.access_controller:
            try:
                # Cleanup expired sessions
                self.access_controller.cleanup_expired_sessions(max_age_seconds=0)
                self.logger.info("Access controller cleaned up successfully")
            except Exception as e:
                self.logger.error(f"Error cleaning up access controller: {e}")

        # Cleanup performance monitoring
        if hasattr(self, "_performance_monitor") and self._performance_monitor:
            try:
                await self._performance_monitor.stop_monitoring()
                self.logger.info("Performance monitor stopped successfully")
            except Exception as e:
                self.logger.error(f"Error stopping performance monitor: {e}")

        if hasattr(self, "_resource_monitor") and self._resource_monitor:
            try:
                await self._resource_monitor.stop_monitoring()
                self.logger.info("Resource monitor stopped successfully")
            except Exception as e:
                self.logger.error(f"Error stopping resource monitor: {e}")

        if hasattr(self, "_cache_manager") and self._cache_manager:
            try:
                await self._cache_manager.stop_cleanup_task()
                self.logger.info("Cache manager stopped successfully")
            except Exception as e:
                self.logger.error(f"Error stopping cache manager: {e}")

        if hasattr(self, "_error_recovery_manager") and self._error_recovery_manager:
            try:
                # Log final error statistics
                stats = self._error_recovery_manager.get_error_statistics(hours=24)
                self.logger.info(
                    f"Final error statistics: {stats['total_errors']} errors, "
                    f"{stats['recovery_rate']:.1%} recovery rate"
                )
                self.logger.info("Error recovery manager stopped successfully")
            except Exception as e:
                self.logger.error(f"Error stopping error recovery manager: {e}")

        # Cleanup managers
        if hasattr(self, "tool_manager") and self.tool_manager:
            if hasattr(self.tool_manager, "cleanup"):
                await self.tool_manager.cleanup()
        if hasattr(self, "resource_manager") and self.resource_manager:
            if hasattr(self.resource_manager, "cleanup"):
                await self.resource_manager.cleanup()
        if hasattr(self, "prompt_manager") and self.prompt_manager:
            if hasattr(self.prompt_manager, "cleanup"):
                await self.prompt_manager.cleanup()

        self.logger.info("RStudio MCP server shutdown complete")
