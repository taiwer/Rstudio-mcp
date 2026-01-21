"""Server-Sent Events (SSE) transport implementation."""

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Set
from urllib.parse import parse_qs, urlparse

from aiohttp import WSMsgType, web
from aiohttp.web import Request, Response, StreamResponse

from .transport_base import ConnectionState, TransportBase


class SSEConnection:
    """Represents an SSE connection."""

    def __init__(self, connection_id: str, request: Request, response: StreamResponse):
        """Initialize SSE connection.

        Args:
            connection_id: Unique connection identifier
            request: HTTP request object
            response: HTTP response stream
        """
        self.connection_id = connection_id
        self.request = request
        self.response = response
        self.created_at = time.time()
        self.last_heartbeat = time.time()
        self.is_active = True
        self.logger = logging.getLogger(f"{__name__}.{connection_id}")

    async def send_event(
        self, event_type: str, data: Dict[str, Any], event_id: Optional[str] = None
    ) -> bool:
        """Send an SSE event.

        Args:
            event_type: Type of event
            data: Event data
            event_id: Optional event ID

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_active:
            return False

        try:
            # Format SSE message
            message_parts = []

            if event_id:
                message_parts.append(f"id: {event_id}")

            message_parts.append(f"event: {event_type}")
            message_parts.append(f"data: {json.dumps(data)}")
            message_parts.append("")  # Empty line to end event

            message = "\n".join(message_parts) + "\n"

            await self.response.write(message.encode("utf-8"))
            await self.response.drain()

            self.logger.debug(f"Sent SSE event: {event_type}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send SSE event: {e}")
            self.is_active = False
            return False

    async def send_heartbeat(self) -> bool:
        """Send heartbeat event.

        Returns:
            True if sent successfully, False otherwise
        """
        heartbeat_data = {"timestamp": time.time(), "connection_id": self.connection_id}

        success = await self.send_event("heartbeat", heartbeat_data)
        if success:
            self.last_heartbeat = time.time()

        return success

    def close(self) -> None:
        """Close the connection."""
        self.is_active = False
        self.logger.info(f"SSE connection closed: {self.connection_id}")


class SSEConnectionManager:
    """Manages SSE connections."""

    def __init__(self, heartbeat_interval: int = 30):
        """Initialize connection manager.

        Args:
            heartbeat_interval: Heartbeat interval in seconds
        """
        self.connections: Dict[str, SSEConnection] = {}
        self.heartbeat_interval = heartbeat_interval
        self.logger = logging.getLogger(__name__)
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

    async def add_connection(self, request: Request) -> SSEConnection:
        """Add a new SSE connection.

        Args:
            request: HTTP request object

        Returns:
            SSE connection object
        """
        connection_id = str(uuid.uuid4())

        # Set up SSE response
        response = StreamResponse(
            status=200,
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
            },
        )

        await response.prepare(request)

        # Create connection
        connection = SSEConnection(connection_id, request, response)
        self.connections[connection_id] = connection

        self.logger.info(
            f"New SSE connection: {connection_id} (total: {len(self.connections)})"
        )

        # Send initial connection event
        await connection.send_event(
            "connected", {"connection_id": connection_id, "timestamp": time.time()}
        )

        return connection

    def remove_connection(self, connection_id: str) -> None:
        """Remove an SSE connection.

        Args:
            connection_id: Connection ID to remove
        """
        if connection_id in self.connections:
            connection = self.connections[connection_id]
            connection.close()
            del self.connections[connection_id]
            self.logger.info(
                f"Removed SSE connection: {connection_id} (remaining: {len(self.connections)})"
            )

    async def broadcast_event(
        self, event_type: str, data: Dict[str, Any], event_id: Optional[str] = None
    ) -> int:
        """Broadcast event to all active connections.

        Args:
            event_type: Type of event
            data: Event data
            event_id: Optional event ID

        Returns:
            Number of connections that received the event
        """
        if not self.connections:
            return 0

        sent_count = 0
        failed_connections = []

        for connection_id, connection in self.connections.items():
            if await connection.send_event(event_type, data, event_id):
                sent_count += 1
            else:
                failed_connections.append(connection_id)

        # Remove failed connections
        for connection_id in failed_connections:
            self.remove_connection(connection_id)

        self.logger.debug(f"Broadcast event '{event_type}' to {sent_count} connections")
        return sent_count

    async def send_to_connection(
        self,
        connection_id: str,
        event_type: str,
        data: Dict[str, Any],
        event_id: Optional[str] = None,
    ) -> bool:
        """Send event to specific connection.

        Args:
            connection_id: Target connection ID
            event_type: Type of event
            data: Event data
            event_id: Optional event ID

        Returns:
            True if sent successfully, False otherwise
        """
        if connection_id not in self.connections:
            return False

        connection = self.connections[connection_id]
        success = await connection.send_event(event_type, data, event_id)

        if not success:
            self.remove_connection(connection_id)

        return success

    async def start_background_tasks(self) -> None:
        """Start background tasks for heartbeat and cleanup."""
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        self.logger.info("Started SSE background tasks")

    async def stop_background_tasks(self) -> None:
        """Stop background tasks."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        self.logger.info("Stopped SSE background tasks")

    async def _heartbeat_loop(self) -> None:
        """Background task for sending heartbeats."""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)

                if self.connections:
                    failed_connections = []

                    for connection_id, connection in self.connections.items():
                        if not await connection.send_heartbeat():
                            failed_connections.append(connection_id)

                    # Remove failed connections
                    for connection_id in failed_connections:
                        self.remove_connection(connection_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in heartbeat loop: {e}")

    async def _cleanup_loop(self) -> None:
        """Background task for cleaning up stale connections."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                current_time = time.time()
                stale_connections = []

                for connection_id, connection in self.connections.items():
                    # Remove connections that haven't sent heartbeat in 2x interval
                    if current_time - connection.last_heartbeat > (
                        self.heartbeat_interval * 2
                    ):
                        stale_connections.append(connection_id)

                for connection_id in stale_connections:
                    self.logger.warning(f"Removing stale connection: {connection_id}")
                    self.remove_connection(connection_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")

    def get_connection_count(self) -> int:
        """Get number of active connections.

        Returns:
            Number of active connections
        """
        return len(self.connections)

    def get_connection_info(self) -> List[Dict[str, Any]]:
        """Get information about all connections.

        Returns:
            List of connection information
        """
        info = []
        current_time = time.time()

        for connection_id, connection in self.connections.items():
            info.append(
                {
                    "connection_id": connection_id,
                    "created_at": connection.created_at,
                    "last_heartbeat": connection.last_heartbeat,
                    "age_seconds": current_time - connection.created_at,
                    "is_active": connection.is_active,
                    "remote_addr": connection.request.remote,
                }
            )

        return info


class SSETransport(TransportBase):
    """SSE transport implementation."""

    def __init__(
        self, host: str = "localhost", port: int = 8080, heartbeat_interval: int = 30
    ):
        """Initialize SSE transport.

        Args:
            host: Server host
            port: Server port
            heartbeat_interval: Heartbeat interval in seconds
        """
        super().__init__("sse")
        self.host = host
        self.port = port
        self.heartbeat_interval = heartbeat_interval

        self.app = web.Application()
        self.connection_manager = SSEConnectionManager(heartbeat_interval)
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None

        self._setup_routes()

    def _setup_routes(self) -> None:
        """Set up HTTP routes."""
        self.app.router.add_get("/sse", self._handle_sse_connection)
        self.app.router.add_post("/message", self._handle_message_post)
        self.app.router.add_get("/status", self._handle_status)
        self.app.router.add_get("/health", self._handle_health)
        self.app.router.add_get("/connections", self._handle_connections_info)

        # Add CORS middleware
        self.app.middlewares.append(self._cors_middleware)

    @web.middleware
    async def _cors_middleware(self, request: Request, handler) -> Response:
        """CORS middleware."""
        if request.method == "OPTIONS":
            return web.Response(
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization",
                }
            )

        response = await handler(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    async def _handle_sse_connection(self, request: Request) -> StreamResponse:
        """Handle SSE connection endpoint.

        Args:
            request: HTTP request

        Returns:
            SSE stream response
        """
        try:
            connection = await self.connection_manager.add_connection(request)

            # Notify connection handlers
            await self._handle_connection_event("connect", connection.connection_id)

            # Keep connection alive until client disconnects
            try:
                while connection.is_active:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass
            finally:
                self.connection_manager.remove_connection(connection.connection_id)
                await self._handle_connection_event(
                    "disconnect", connection.connection_id
                )

            return connection.response

        except Exception as e:
            self.logger.error(f"Error handling SSE connection: {e}")
            await self._handle_error("sse_connection_error", e)
            raise web.HTTPInternalServerError(text=str(e))

    async def _handle_message_post(self, request: Request) -> Response:
        """Handle message POST endpoint.

        Args:
            request: HTTP request

        Returns:
            JSON response
        """
        try:
            data = await request.json()

            # Extract message information
            message_type = data.get("type", "message")
            message_data = data.get("data", {})
            connection_id = data.get("connection_id")

            # Handle the message
            await self._handle_message(message_type, message_data, connection_id)

            return web.json_response(
                {"status": "success", "message": "Message processed"}
            )

        except Exception as e:
            self.logger.error(f"Error handling message POST: {e}")
            await self._handle_error("message_post_error", e)
            return web.json_response({"status": "error", "error": str(e)}, status=500)

    async def _handle_status(self, request: Request) -> Response:
        """Handle status endpoint.

        Args:
            request: HTTP request

        Returns:
            JSON response with server status
        """
        return web.json_response(
            {
                "status": "running",
                "transport": "sse",
                "host": self.host,
                "port": self.port,
                "state": self.state.value,
                "connections": self.connection_manager.get_connection_count(),
                "heartbeat_interval": self.heartbeat_interval,
            }
        )

    async def _handle_health(self, request: Request) -> Response:
        """Handle health check endpoint.

        Args:
            request: HTTP request

        Returns:
            JSON response with health status
        """
        return web.json_response(
            {
                "status": "healthy",
                "server": "rstudio-mcp",
                "version": "1.0.0",
                "timestamp": time.time(),
                "transport": "sse",
                "connections": self.connection_manager.get_connection_count(),
            }
        )

    async def _handle_connections_info(self, request: Request) -> Response:
        """Handle connections info endpoint.

        Args:
            request: HTTP request

        Returns:
            JSON response with connection information
        """
        return web.json_response(
            {"connections": self.connection_manager.get_connection_info()}
        )

    async def start(self, **kwargs) -> None:
        """Start the SSE transport.

        Args:
            **kwargs: Additional arguments (host, port)
        """
        host = kwargs.get("host", self.host)
        port = kwargs.get("port", self.port)

        self._set_state(ConnectionState.CONNECTING)

        try:
            # Start connection manager background tasks
            await self.connection_manager.start_background_tasks()

            # Start HTTP server
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()

            self.site = web.TCPSite(self.runner, host, port)
            await self.site.start()

            self._set_state(ConnectionState.CONNECTED)
            self.logger.info(f"SSE transport started on {host}:{port}")

            # Notify connection handlers
            await self._handle_connection_event("transport_started", host, port)

        except Exception as e:
            self._set_state(ConnectionState.ERROR)
            await self._handle_error("transport_start_error", e)
            raise

    async def stop(self) -> None:
        """Stop the SSE transport."""
        self._set_state(ConnectionState.DISCONNECTED)

        try:
            # Stop connection manager background tasks
            await self.connection_manager.stop_background_tasks()

            # Close all connections
            for connection_id in list(self.connection_manager.connections.keys()):
                self.connection_manager.remove_connection(connection_id)

            # Stop HTTP server
            if self.site:
                await self.site.stop()
                self.site = None

            if self.runner:
                await self.runner.cleanup()
                self.runner = None

            self.logger.info("SSE transport stopped")

            # Notify connection handlers
            await self._handle_connection_event("transport_stopped")

        except Exception as e:
            await self._handle_error("transport_stop_error", e)
            raise

    async def send_message(self, message: Dict[str, Any]) -> None:
        """Send message to all connected clients.

        Args:
            message: Message to send
        """
        if self.state != ConnectionState.CONNECTED:
            raise RuntimeError(f"Transport not connected (state: {self.state.value})")

        event_type = message.get("type", "message")
        event_data = message.get("data", message)
        event_id = message.get("id")

        sent_count = await self.connection_manager.broadcast_event(
            event_type, event_data, event_id
        )
        self.logger.debug(f"Sent message to {sent_count} connections")

    async def send_to_connection(
        self, connection_id: str, message: Dict[str, Any]
    ) -> bool:
        """Send message to specific connection.

        Args:
            connection_id: Target connection ID
            message: Message to send

        Returns:
            True if sent successfully, False otherwise
        """
        if self.state != ConnectionState.CONNECTED:
            return False

        event_type = message.get("type", "message")
        event_data = message.get("data", message)
        event_id = message.get("id")

        return await self.connection_manager.send_to_connection(
            connection_id, event_type, event_data, event_id
        )
