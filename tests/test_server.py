"""Tests for MCP server implementation."""

import pytest
from unittest.mock import Mock, AsyncMock

from rstudio_mcp.config import ServerConfig
from rstudio_mcp.server import RStudioMCPServer


class TestRStudioMCPServer:
    """Test RStudio MCP Server."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return ServerConfig(
            name="test-server",
            version="1.0.0",
            debug=True
        )
    
    @pytest.fixture
    def server(self, config):
        """Create test server instance."""
        return RStudioMCPServer(config)
    
    def test_server_initialization(self, server, config):
        """Test server initialization."""
        assert server.config == config
        assert server.server is not None
        assert server.logger is not None
        assert server.tool_manager is None  # Not initialized yet
        assert server.resource_manager is None  # Not initialized yet
        assert server.prompt_manager is None  # Not initialized yet
    
    def test_server_name_and_version(self, server, config):
        """Test server name and version."""
        assert server.config.name == config.name
        assert server.config.version == config.version
    
    @pytest.mark.asyncio
    async def test_shutdown(self, server):
        """Test server shutdown."""
        # Mock managers
        server.tool_manager = Mock()
        server.tool_manager.cleanup = AsyncMock()
        server.resource_manager = Mock()
        server.resource_manager.cleanup = AsyncMock()
        server.prompt_manager = Mock()
        server.prompt_manager.cleanup = AsyncMock()
        
        # Should not raise any exceptions
        await server.shutdown()
        
        # Verify cleanup was called
        server.tool_manager.cleanup.assert_called_once()
        server.resource_manager.cleanup.assert_called_once()
        server.prompt_manager.cleanup.assert_called_once()