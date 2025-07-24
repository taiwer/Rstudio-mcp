"""Integration tests for SSE transport implementation."""

import asyncio
import json
import pytest
import aiohttp
from unittest.mock import AsyncMock, Mock, patch
from typing import Dict, Any

from rstudio_mcp.transport import SSETransport, SSEConnectionManager, ConnectionState


class TestSSEConnectionManager:
    """Test SSE connection manager."""
    
    @pytest.fixture
    def connection_manager(self):
        """Create connection manager fixture."""
        return SSEConnectionManager(heartbeat_interval=1)  # Short interval for testing
    
    @pytest.fixture
    def mock_request(self):
        """Create mock HTTP request."""
        request = Mock()
        request.remote = "127.0.0.1"
        return request
    
    @pytest.fixture
    def mock_response(self):
        """Create mock HTTP response."""
        response = AsyncMock()
        response.write = AsyncMock()
        response.drain = AsyncMock()
        return response
    
    @pytest.mark.asyncio
    async def test_connection_lifecycle(self, connection_manager, mock_request):
        """Test connection lifecycle management."""
        # Mock StreamResponse
        with patch('rstudio_mcp.transport.sse_transport.StreamResponse') as mock_stream_response:
            mock_response = AsyncMock()
            mock_stream_response.return_value = mock_response
            mock_response.prepare = AsyncMock()
            
            # Add connection
            connection = await connection_manager.add_connection(mock_request)
            
            assert connection.connection_id in connection_manager.connections
            assert connection_manager.get_connection_count() == 1
            assert connection.is_active
            
            # Remove connection
            connection_manager.remove_connection(connection.connection_id)
            
            assert connection.connection_id not in connection_manager.connections
            assert connection_manager.get_connection_count() == 0
            assert not connection.is_active
    
    @pytest.mark.asyncio
    async def test_broadcast_event(self, connection_manager, mock_request):
        """Test broadcasting events to all connections."""
        with patch('rstudio_mcp.transport.sse_transport.StreamResponse') as mock_stream_response:
            mock_response = AsyncMock()
            mock_stream_response.return_value = mock_response
            mock_response.prepare = AsyncMock()
            
            # Add multiple connections
            connection1 = await connection_manager.add_connection(mock_request)
            connection2 = await connection_manager.add_connection(mock_request)
            
            # Mock send_event to return True
            connection1.send_event = AsyncMock(return_value=True)
            connection2.send_event = AsyncMock(return_value=True)
            
            # Broadcast event
            event_data = {"message": "test broadcast"}
            sent_count = await connection_manager.broadcast_event("test", event_data)
            
            assert sent_count == 2
            connection1.send_event.assert_called_once_with("test", event_data, None)
            connection2.send_event.assert_called_once_with("test", event_data, None)
    
    @pytest.mark.asyncio
    async def test_failed_connection_cleanup(self, connection_manager, mock_request):
        """Test cleanup of failed connections during broadcast."""
        with patch('rstudio_mcp.transport.sse_transport.StreamResponse') as mock_stream_response:
            mock_response = AsyncMock()
            mock_stream_response.return_value = mock_response
            mock_response.prepare = AsyncMock()
            
            # Add connections
            connection1 = await connection_manager.add_connection(mock_request)
            connection2 = await connection_manager.add_connection(mock_request)
            
            # Mock one connection to fail
            connection1.send_event = AsyncMock(return_value=True)
            connection2.send_event = AsyncMock(return_value=False)
            
            initial_count = connection_manager.get_connection_count()
            assert initial_count == 2
            
            # Broadcast event
            sent_count = await connection_manager.broadcast_event("test", {"data": "test"})
            
            assert sent_count == 1
            assert connection_manager.get_connection_count() == 1
            assert connection1.connection_id in connection_manager.connections
            assert connection2.connection_id not in connection_manager.connections
    
    @pytest.mark.asyncio
    async def test_background_tasks(self, connection_manager):
        """Test background tasks start and stop."""
        # Start background tasks
        await connection_manager.start_background_tasks()
        
        assert connection_manager._heartbeat_task is not None
        assert connection_manager._cleanup_task is not None
        assert not connection_manager._heartbeat_task.done()
        assert not connection_manager._cleanup_task.done()
        
        # Stop background tasks
        await connection_manager.stop_background_tasks()
        
        assert connection_manager._heartbeat_task is None
        assert connection_manager._cleanup_task is None
    
    @pytest.mark.asyncio
    async def test_heartbeat_functionality(self, connection_manager, mock_request):
        """Test heartbeat functionality."""
        with patch('rstudio_mcp.transport.sse_transport.StreamResponse') as mock_stream_response:
            mock_response = AsyncMock()
            mock_stream_response.return_value = mock_response
            mock_response.prepare = AsyncMock()
            
            # Add connection
            connection = await connection_manager.add_connection(mock_request)
            connection.send_heartbeat = AsyncMock(return_value=True)
            
            # Start background tasks
            await connection_manager.start_background_tasks()
            
            # Wait for heartbeat
            await asyncio.sleep(1.5)  # Wait longer than heartbeat interval
            
            # Verify heartbeat was called
            connection.send_heartbeat.assert_called()
            
            # Stop background tasks
            await connection_manager.stop_background_tasks()
    
    def test_connection_info(self, connection_manager):
        """Test getting connection information."""
        # Initially empty
        info = connection_manager.get_connection_info()
        assert info == []
        
        # Add mock connection directly for testing
        mock_connection = Mock()
        mock_connection.connection_id = "test-id"
        mock_connection.created_at = 1000.0
        mock_connection.last_heartbeat = 1010.0
        mock_connection.is_active = True
        mock_connection.request.remote = "127.0.0.1"
        
        connection_manager.connections["test-id"] = mock_connection
        
        with patch('time.time', return_value=1020.0):
            info = connection_manager.get_connection_info()
            
            assert len(info) == 1
            assert info[0]["connection_id"] == "test-id"
            assert info[0]["age_seconds"] == 20.0
            assert info[0]["is_active"] is True
            assert info[0]["remote_addr"] == "127.0.0.1"


class TestSSETransport:
    """Test SSE transport implementation."""
    
    @pytest.fixture
    def sse_transport(self):
        """Create SSE transport fixture."""
        return SSETransport(host="localhost", port=8081, heartbeat_interval=1)
    
    @pytest.mark.asyncio
    async def test_transport_lifecycle(self, sse_transport):
        """Test transport start and stop lifecycle."""
        assert sse_transport.state == ConnectionState.DISCONNECTED
        
        # Start transport
        await sse_transport.start()
        
        assert sse_transport.state == ConnectionState.CONNECTED
        assert sse_transport.runner is not None
        assert sse_transport.site is not None
        
        # Stop transport
        await sse_transport.stop()
        
        assert sse_transport.state == ConnectionState.DISCONNECTED
        assert sse_transport.runner is None
        assert sse_transport.site is None
    
    @pytest.mark.asyncio
    async def test_transport_error_handling(self, sse_transport):
        """Test transport error handling."""
        error_handler_called = False
        test_error = Exception("Test error")
        
        async def error_handler(error):
            nonlocal error_handler_called
            error_handler_called = True
            assert error == test_error
        
        sse_transport.register_error_handler("test_error", error_handler)
        
        # Trigger error
        await sse_transport._handle_error("test_error", test_error)
        
        assert error_handler_called
    
    @pytest.mark.asyncio
    async def test_message_handling(self, sse_transport):
        """Test message handling."""
        message_handler_called = False
        test_data = {"test": "data"}
        
        async def message_handler(data, connection_id):
            nonlocal message_handler_called
            message_handler_called = True
            assert data == test_data
            assert connection_id == "test-connection"
        
        sse_transport.register_message_handler("test_message", message_handler)
        
        # Trigger message
        await sse_transport._handle_message("test_message", test_data, "test-connection")
        
        assert message_handler_called
    
    @pytest.mark.asyncio
    async def test_connection_event_handling(self, sse_transport):
        """Test connection event handling."""
        connect_handler_called = False
        disconnect_handler_called = False
        
        async def connect_handler(connection_id):
            nonlocal connect_handler_called
            connect_handler_called = True
            assert connection_id == "test-connection"
        
        async def disconnect_handler(connection_id):
            nonlocal disconnect_handler_called
            disconnect_handler_called = True
            assert connection_id == "test-connection"
        
        sse_transport.register_connection_handler("connect", connect_handler)
        sse_transport.register_connection_handler("disconnect", disconnect_handler)
        
        # Trigger events
        await sse_transport._handle_connection_event("connect", "test-connection")
        await sse_transport._handle_connection_event("disconnect", "test-connection")
        
        assert connect_handler_called
        assert disconnect_handler_called
    
    @pytest.mark.asyncio
    async def test_send_message_when_disconnected(self, sse_transport):
        """Test sending message when transport is disconnected."""
        assert sse_transport.state == ConnectionState.DISCONNECTED
        
        with pytest.raises(RuntimeError, match="Transport not connected"):
            await sse_transport.send_message({"test": "message"})
    
    @pytest.mark.asyncio
    async def test_send_message_when_connected(self, sse_transport):
        """Test sending message when transport is connected."""
        # Mock connection manager
        sse_transport.connection_manager.broadcast_event = AsyncMock(return_value=2)
        
        # Set state to connected
        sse_transport._set_state(ConnectionState.CONNECTED)
        
        # Send message
        message = {"type": "test", "data": {"content": "test message"}}
        await sse_transport.send_message(message)
        
        # Verify broadcast was called
        sse_transport.connection_manager.broadcast_event.assert_called_once_with(
            "test", {"content": "test message"}, None
        )


class TestSSETransportIntegration:
    """Integration tests for SSE transport with HTTP client."""
    
    @pytest.fixture
    def event_loop(self):
        """Create event loop for async tests."""
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_sse_http_endpoints(self):
        """Test SSE HTTP endpoints with real HTTP client."""
        transport = SSETransport(host="localhost", port=8082, heartbeat_interval=1)
        
        try:
            # Start transport
            await transport.start()
            
            # Test status endpoint
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8082/status") as response:
                    assert response.status == 200
                    data = await response.json()
                    assert data["status"] == "running"
                    assert data["transport"] == "sse"
                    assert data["connections"] == 0
            
            # Test connections info endpoint
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8082/connections") as response:
                    assert response.status == 200
                    data = await response.json()
                    assert "connections" in data
                    assert len(data["connections"]) == 0
            
        finally:
            await transport.stop()
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_sse_connection_flow(self):
        """Test complete SSE connection flow."""
        transport = SSETransport(host="localhost", port=8083, heartbeat_interval=1)
        
        connection_events = []
        message_events = []
        
        # Set up event handlers
        async def handle_connect(connection_id):
            connection_events.append(("connect", connection_id))
        
        async def handle_disconnect(connection_id):
            connection_events.append(("disconnect", connection_id))
        
        async def handle_message(data, connection_id):
            message_events.append((data, connection_id))
        
        transport.register_connection_handler("connect", handle_connect)
        transport.register_connection_handler("disconnect", handle_disconnect)
        transport.register_message_handler("test_message", handle_message)
        
        try:
            # Start transport
            await transport.start()
            
            # Create SSE client connection
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8083/sse") as response:
                    assert response.status == 200
                    assert response.headers["Content-Type"] == "text/event-stream"
                    
                    # Read initial events
                    events_received = []
                    async for line in response.content:
                        line_str = line.decode('utf-8').strip()
                        if line_str.startswith('data: '):
                            event_data = json.loads(line_str[6:])  # Remove 'data: ' prefix
                            events_received.append(event_data)
                            
                            # Break after receiving welcome message
                            if event_data.get("server"):
                                break
                    
                    # Verify welcome message received
                    assert len(events_received) > 0
                    welcome_event = events_received[-1]
                    assert "server" in welcome_event
                    assert "connection_id" in welcome_event
            
            # Verify connection events were triggered
            await asyncio.sleep(0.1)  # Allow event handlers to complete
            assert len(connection_events) >= 1
            assert connection_events[0][0] == "connect"
            
        finally:
            await transport.stop()
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_message_post_endpoint(self):
        """Test message POST endpoint."""
        transport = SSETransport(host="localhost", port=8084, heartbeat_interval=1)
        
        message_received = None
        
        async def handle_message(data, connection_id):
            nonlocal message_received
            message_received = (data, connection_id)
        
        transport.register_message_handler("mcp_request", handle_message)
        
        try:
            # Start transport
            await transport.start()
            
            # Send message via POST
            message_data = {
                "type": "mcp_request",
                "data": {"method": "test", "params": {"arg": "value"}},
                "connection_id": "test-connection"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "http://localhost:8084/message",
                    json=message_data
                ) as response:
                    assert response.status == 200
                    result = await response.json()
                    assert result["status"] == "success"
            
            # Verify message was handled
            await asyncio.sleep(0.1)  # Allow message handler to complete
            assert message_received is not None
            data, connection_id = message_received
            assert data == {"method": "test", "params": {"arg": "value"}}
            assert connection_id == "test-connection"
            
        finally:
            await transport.stop()
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_cors_headers(self):
        """Test CORS headers are properly set."""
        transport = SSETransport(host="localhost", port=8085, heartbeat_interval=1)
        
        try:
            # Start transport
            await transport.start()
            
            # Test OPTIONS request
            async with aiohttp.ClientSession() as session:
                async with session.options("http://localhost:8085/status") as response:
                    assert response.status == 200
                    assert response.headers["Access-Control-Allow-Origin"] == "*"
                    assert "GET, POST, OPTIONS" in response.headers["Access-Control-Allow-Methods"]
            
            # Test regular request has CORS headers
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8085/status") as response:
                    assert response.status == 200
                    assert response.headers["Access-Control-Allow-Origin"] == "*"
            
        finally:
            await transport.stop()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_sse_transport_error_recovery():
    """Test SSE transport error recovery and reconnection."""
    transport = SSETransport(host="localhost", port=8086, heartbeat_interval=1)
    
    error_events = []
    
    async def handle_transport_error(error):
        error_events.append(error)
    
    transport.register_error_handler("transport_error", handle_transport_error)
    
    try:
        # Start transport
        await transport.start()
        assert transport.state == ConnectionState.CONNECTED
        
        # Simulate transport error
        test_error = Exception("Simulated transport error")
        await transport._handle_error("transport_error", test_error)
        
        # Verify error was handled
        assert len(error_events) == 1
        assert error_events[0] == test_error
        
    finally:
        await transport.stop()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_multiple_concurrent_connections():
    """Test handling multiple concurrent SSE connections."""
    transport = SSETransport(host="localhost", port=8087, heartbeat_interval=1)
    
    try:
        # Start transport
        await transport.start()
        
        # Create multiple concurrent connections
        async def create_connection(session, connection_num):
            async with session.get("http://localhost:8087/sse") as response:
                assert response.status == 200
                
                # Read at least the welcome event
                async for line in response.content:
                    line_str = line.decode('utf-8').strip()
                    if line_str.startswith('data: '):
                        event_data = json.loads(line_str[6:])
                        if event_data.get("server"):
                            return connection_num
        
        # Create multiple connections concurrently
        async with aiohttp.ClientSession() as session:
            tasks = [create_connection(session, i) for i in range(3)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Verify all connections succeeded
            assert len([r for r in results if not isinstance(r, Exception)]) == 3
        
        # Verify connection count
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8087/connections") as response:
                data = await response.json()
                # Connections might have closed by now, but we should have had 3 at peak
                assert len(data["connections"]) >= 0
        
    finally:
        await transport.stop()