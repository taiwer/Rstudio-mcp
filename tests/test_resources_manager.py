"""Tests for resource manager."""

import pytest
from unittest.mock import AsyncMock, Mock

from src.rstudio_mcp.resources.manager import ResourceManager
from src.rstudio_mcp.resources.base import BaseResource, ResourceInfo, ResourceResult


class MockResourceA(BaseResource):
    """Mock resource A for testing."""
    
    @property
    def scheme(self) -> str:
        return "test-a"
    
    @property
    def description(self) -> str:
        return "Test resource A"
    
    async def list_resources(self, uri_prefix=None):
        return [
            ResourceInfo(
                uri="test-a://resource1",
                name="Resource A1",
                description="First resource from A",
                mime_type="text/plain"
            ),
            ResourceInfo(
                uri="test-a://resource2",
                name="Resource A2",
                description="Second resource from A",
                mime_type="application/json"
            )
        ]
    
    async def read_resource(self, uri: str):
        if uri == "test-a://resource1":
            return self.create_text_result("Content from A1")
        elif uri == "test-a://resource2":
            return self.create_json_result({"source": "A2"})
        else:
            return self.create_error_result("Resource not found")


class MockResourceB(BaseResource):
    """Mock resource B for testing."""
    
    @property
    def scheme(self) -> str:
        return "test-b"
    
    @property
    def description(self) -> str:
        return "Test resource B"
    
    async def list_resources(self, uri_prefix=None):
        return [
            ResourceInfo(
                uri="test-b://resource1",
                name="Resource B1",
                description="First resource from B",
                mime_type="text/plain"
            )
        ]
    
    async def read_resource(self, uri: str):
        if uri == "test-b://resource1":
            return self.create_text_result("Content from B1")
        else:
            return self.create_error_result("Resource not found")


class TestResourceManager:
    """Test ResourceManager class."""
    
    @pytest.fixture
    def manager(self):
        """Create a resource manager for testing."""
        return ResourceManager()
    
    @pytest.fixture
    def mock_resource_a(self):
        """Create mock resource A."""
        return MockResourceA()
    
    @pytest.fixture
    def mock_resource_b(self):
        """Create mock resource B."""
        return MockResourceB()
    
    def test_register_resource(self, manager, mock_resource_a):
        """Test registering a resource handler."""
        manager.register_resource(mock_resource_a)
        
        assert "test-a" in manager.list_schemes()
        assert manager.get_resource_handler("test-a") is mock_resource_a
    
    def test_register_duplicate_resource(self, manager, mock_resource_a):
        """Test registering duplicate resource handler."""
        manager.register_resource(mock_resource_a)
        
        with pytest.raises(ValueError, match="already registered"):
            manager.register_resource(mock_resource_a)
    
    def test_register_resource_class(self, manager):
        """Test registering a resource class."""
        manager.register_resource_class(MockResourceA)
        
        assert "test-a" in manager.list_schemes()
        
        # Should instantiate when accessed
        handler = manager.get_resource_handler("test-a")
        assert isinstance(handler, MockResourceA)
        assert handler.scheme == "test-a"
    
    def test_register_duplicate_resource_class(self, manager):
        """Test registering duplicate resource class."""
        manager.register_resource_class(MockResourceA)
        
        with pytest.raises(ValueError, match="already registered"):
            manager.register_resource_class(MockResourceA)
    
    def test_unregister_resource(self, manager, mock_resource_a):
        """Test unregistering a resource handler."""
        manager.register_resource(mock_resource_a)
        assert "test-a" in manager.list_schemes()
        
        result = manager.unregister_resource("test-a")
        assert result is True
        assert "test-a" not in manager.list_schemes()
        
        # Unregistering non-existent resource should return False
        result = manager.unregister_resource("non-existent")
        assert result is False
    
    def test_get_nonexistent_resource_handler(self, manager):
        """Test getting non-existent resource handler."""
        handler = manager.get_resource_handler("non-existent")
        assert handler is None
    
    def test_list_schemes(self, manager, mock_resource_a, mock_resource_b):
        """Test listing resource schemes."""
        assert manager.list_schemes() == []
        
        manager.register_resource(mock_resource_a)
        assert set(manager.list_schemes()) == {"test-a"}
        
        manager.register_resource_class(MockResourceB)
        assert set(manager.list_schemes()) == {"test-a", "test-b"}
    
    @pytest.mark.asyncio
    async def test_list_all_resources(self, manager, mock_resource_a, mock_resource_b):
        """Test listing all resources."""
        manager.register_resource(mock_resource_a)
        manager.register_resource(mock_resource_b)
        
        resources = await manager.list_all_resources()
        
        assert len(resources) == 3  # 2 from A, 1 from B
        
        uris = [r.uri for r in resources]
        assert "test-a://resource1" in uris
        assert "test-a://resource2" in uris
        assert "test-b://resource1" in uris
    
    @pytest.mark.asyncio
    async def test_list_resources_with_prefix(self, manager, mock_resource_a, mock_resource_b):
        """Test listing resources with URI prefix."""
        manager.register_resource(mock_resource_a)
        manager.register_resource(mock_resource_b)
        
        # Filter by scheme
        resources = await manager.list_all_resources("test-a://")
        
        assert len(resources) == 2  # Only from A
        uris = [r.uri for r in resources]
        assert "test-a://resource1" in uris
        assert "test-a://resource2" in uris
        assert "test-b://resource1" not in uris
    
    @pytest.mark.asyncio
    async def test_read_resource(self, manager, mock_resource_a):
        """Test reading a resource."""
        manager.register_resource(mock_resource_a)
        
        result = await manager.read_resource("test-a://resource1")
        
        assert result.success
        assert result.get_text_content() == "Content from A1"
    
    @pytest.mark.asyncio
    async def test_read_json_resource(self, manager, mock_resource_a):
        """Test reading a JSON resource."""
        manager.register_resource(mock_resource_a)
        
        result = await manager.read_resource("test-a://resource2")
        
        assert result.success
        assert result.mime_type == "application/json"
        
        import json
        data = json.loads(result.get_text_content())
        assert data["source"] == "A2"
    
    @pytest.mark.asyncio
    async def test_read_nonexistent_resource(self, manager, mock_resource_a):
        """Test reading non-existent resource."""
        manager.register_resource(mock_resource_a)
        
        result = await manager.read_resource("test-a://nonexistent")
        
        assert not result.success
        assert "Resource not found" in result.error
    
    @pytest.mark.asyncio
    async def test_read_resource_invalid_uri(self, manager):
        """Test reading resource with invalid URI."""
        result = await manager.read_resource("invalid-uri")
        
        assert not result.success
        assert "missing scheme" in result.error
    
    @pytest.mark.asyncio
    async def test_read_resource_unknown_scheme(self, manager):
        """Test reading resource with unknown scheme."""
        result = await manager.read_resource("unknown://resource")
        
        assert not result.success
        assert "No resource handler found" in result.error
    
    def test_get_resource_definitions(self, manager, mock_resource_a):
        """Test getting resource definitions."""
        manager.register_resource(mock_resource_a)
        manager.register_resource_class(MockResourceB)
        
        definitions = manager.get_resource_definitions()
        
        assert len(definitions) == 2
        
        schemes = [d["scheme"] for d in definitions]
        assert "test-a" in schemes
        assert "test-b" in schemes
    
    def test_get_resource_info(self, manager, mock_resource_a):
        """Test getting resource info."""
        manager.register_resource(mock_resource_a)
        
        info = manager.get_resource_info("test-a")
        
        assert info is not None
        assert info["scheme"] == "test-a"
        assert info["description"] == "Test resource A"
        assert info["class"] == "MockResourceA"
    
    def test_get_resource_info_nonexistent(self, manager):
        """Test getting info for non-existent resource."""
        info = manager.get_resource_info("non-existent")
        assert info is None
    
    def test_cache_operations(self, manager):
        """Test cache operations."""
        # Test cache enabled/disabled
        assert manager._cache_enabled is True
        
        manager.set_cache_enabled(False)
        assert manager._cache_enabled is False
        
        manager.set_cache_enabled(True)
        assert manager._cache_enabled is True
        
        # Test cache TTL
        manager.set_cache_ttl(600)
        assert manager._cache_ttl == 600
        
        # Test cache clearing
        manager._cache["test"] = "value"
        assert len(manager._cache) == 1
        
        manager.clear_cache()
        assert len(manager._cache) == 0
    
    def test_clear_resources(self, manager, mock_resource_a):
        """Test clearing all resources."""
        manager.register_resource(mock_resource_a)
        manager.register_resource_class(MockResourceB)
        
        assert len(manager.list_schemes()) == 2
        
        manager.clear_resources()
        
        assert len(manager.list_schemes()) == 0
    
    @pytest.mark.asyncio
    async def test_cleanup(self, manager):
        """Test cleanup method."""
        # Create a mock resource with cleanup method
        mock_resource = Mock(spec=BaseResource)
        mock_resource.scheme = "test-cleanup"
        mock_resource.cleanup = AsyncMock()
        
        manager._resources["test-cleanup"] = mock_resource
        
        await manager.cleanup()
        
        mock_resource.cleanup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_caching_behavior(self, manager, mock_resource_a):
        """Test resource caching behavior."""
        manager.register_resource(mock_resource_a)
        
        # First read should call the resource handler
        result1 = await manager.read_resource("test-a://resource1")
        assert result1.success
        
        # Second read should use cache (we can't easily test this without mocking,
        # but we can verify the cache key exists)
        result2 = await manager.read_resource("test-a://resource1")
        assert result2.success
        
        # Cache should contain the result
        cache_key = "test-a:read:test-a://resource1"
        assert cache_key in manager._cache
    
    def test_discover_resources(self, manager):
        """Test resource discovery from module."""
        # This is a basic test - in practice you'd need a real module with resources
        count = manager.discover_resources("non.existent.module")
        assert count == 0  # Should handle import errors gracefully