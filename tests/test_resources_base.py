"""Tests for resource base classes."""

import pytest
from unittest.mock import AsyncMock, Mock

from src.rstudio_mcp.resources.base import BaseResource, ResourceInfo, ResourceResult


class MockResource(BaseResource):
    """Mock resource for testing."""
    
    @property
    def scheme(self) -> str:
        return "test"
    
    @property
    def description(self) -> str:
        return "Test resource handler"
    
    async def list_resources(self, uri_prefix=None):
        return [
            ResourceInfo(
                uri="test://example",
                name="Test Resource",
                description="A test resource",
                mime_type="text/plain"
            )
        ]
    
    async def read_resource(self, uri: str):
        if uri == "test://example":
            return self.create_text_result("Hello, World!")
        elif uri == "test://json":
            return self.create_json_result({"message": "Hello, JSON!"})
        elif uri == "test://binary":
            return self.create_binary_result(b"binary data", "application/octet-stream")
        elif uri == "test://error":
            return self.create_error_result("Test error")
        else:
            return self.create_error_result("Resource not found")


class TestResourceResult:
    """Test ResourceResult class."""
    
    def test_text_result(self):
        """Test text result creation and methods."""
        result = ResourceResult(
            success=True,
            content="Hello, World!",
            mime_type="text/plain"
        )
        
        assert result.success
        assert result.is_text()
        assert not result.is_binary()
        assert result.get_text_content() == "Hello, World!"
        assert result.get_binary_content() is None
    
    def test_binary_result(self):
        """Test binary result creation and methods."""
        binary_data = b"binary content"
        result = ResourceResult(
            success=True,
            content=binary_data,
            mime_type="application/octet-stream"
        )
        
        assert result.success
        assert not result.is_text()
        assert result.is_binary()
        assert result.get_text_content() is None
        assert result.get_binary_content() == binary_data
    
    def test_json_result(self):
        """Test JSON result detection."""
        result = ResourceResult(
            success=True,
            content='{"key": "value"}',
            mime_type="application/json"
        )
        
        assert result.success
        assert result.is_text()
        assert not result.is_binary()
        assert result.get_text_content() == '{"key": "value"}'
    
    def test_error_result(self):
        """Test error result."""
        result = ResourceResult(
            success=False,
            error="Something went wrong"
        )
        
        assert not result.success
        assert result.error == "Something went wrong"
        assert result.content is None


class TestResourceInfo:
    """Test ResourceInfo class."""
    
    def test_basic_info(self):
        """Test basic resource info."""
        info = ResourceInfo(
            uri="test://example",
            name="Test Resource",
            description="A test resource",
            mime_type="text/plain"
        )
        
        assert info.uri == "test://example"
        assert info.name == "Test Resource"
        assert info.description == "A test resource"
        assert info.mime_type == "text/plain"
    
    def test_to_mcp_resource(self):
        """Test conversion to MCP resource format."""
        info = ResourceInfo(
            uri="test://example",
            name="Test Resource",
            description="A test resource",
            mime_type="text/plain",
            metadata={"custom": "value"}
        )
        
        mcp_resource = info.to_mcp_resource()
        
        assert mcp_resource["uri"] == "test://example"
        assert mcp_resource["name"] == "Test Resource"
        assert mcp_resource["description"] == "A test resource"
        assert mcp_resource["mimeType"] == "text/plain"
        assert mcp_resource["custom"] == "value"


class TestBaseResource:
    """Test BaseResource class."""
    
    @pytest.fixture
    def mock_resource(self):
        """Create a mock resource for testing."""
        return MockResource()
    
    def test_scheme_and_description(self, mock_resource):
        """Test scheme and description properties."""
        assert mock_resource.scheme == "test"
        assert mock_resource.description == "Test resource handler"
    
    def test_validate_uri(self, mock_resource):
        """Test URI validation."""
        assert mock_resource.validate_uri("test://example")
        assert not mock_resource.validate_uri("http://example.com")
        assert not mock_resource.validate_uri("invalid-uri")
    
    def test_parse_uri(self, mock_resource):
        """Test URI parsing."""
        components = mock_resource.parse_uri("test://host/path?query=value#fragment")
        
        assert components["scheme"] == "test"
        assert components["netloc"] == "host"
        assert components["path"] == "/path"
        assert components["query"] == "query=value"
        assert components["fragment"] == "fragment"
    
    @pytest.mark.asyncio
    async def test_list_resources(self, mock_resource):
        """Test resource listing."""
        resources = await mock_resource.list_resources()
        
        assert len(resources) == 1
        assert resources[0].uri == "test://example"
        assert resources[0].name == "Test Resource"
    
    @pytest.mark.asyncio
    async def test_read_text_resource(self, mock_resource):
        """Test reading text resource."""
        result = await mock_resource.read_resource("test://example")
        
        assert result.success
        assert result.get_text_content() == "Hello, World!"
        assert result.mime_type == "text/plain"
    
    @pytest.mark.asyncio
    async def test_read_json_resource(self, mock_resource):
        """Test reading JSON resource."""
        result = await mock_resource.read_resource("test://json")
        
        assert result.success
        assert result.mime_type == "application/json"
        assert '"message": "Hello, JSON!"' in result.get_text_content()
    
    @pytest.mark.asyncio
    async def test_read_binary_resource(self, mock_resource):
        """Test reading binary resource."""
        result = await mock_resource.read_resource("test://binary")
        
        assert result.success
        assert result.get_binary_content() == b"binary data"
        assert result.mime_type == "application/octet-stream"
    
    @pytest.mark.asyncio
    async def test_read_error_resource(self, mock_resource):
        """Test reading resource that returns error."""
        result = await mock_resource.read_resource("test://error")
        
        assert not result.success
        assert result.error == "Test error"
    
    @pytest.mark.asyncio
    async def test_read_nonexistent_resource(self, mock_resource):
        """Test reading nonexistent resource."""
        result = await mock_resource.read_resource("test://nonexistent")
        
        assert not result.success
        assert "Resource not found" in result.error
    
    @pytest.mark.asyncio
    async def test_safe_read_resource_invalid_uri(self, mock_resource):
        """Test safe read with invalid URI."""
        result = await mock_resource.safe_read_resource("http://invalid")
        
        assert not result.success
        assert "Invalid URI" in result.error
    
    @pytest.mark.asyncio
    async def test_safe_list_resources(self, mock_resource):
        """Test safe resource listing."""
        resources = await mock_resource.safe_list_resources()
        
        assert len(resources) == 1
        assert resources[0].uri == "test://example"
    
    def test_create_text_result(self, mock_resource):
        """Test creating text result."""
        result = mock_resource.create_text_result("test content", "text/plain")
        
        assert result.success
        assert result.get_text_content() == "test content"
        assert result.mime_type == "text/plain"
    
    def test_create_binary_result(self, mock_resource):
        """Test creating binary result."""
        data = b"binary data"
        result = mock_resource.create_binary_result(data, "application/octet-stream")
        
        assert result.success
        assert result.get_binary_content() == data
        assert result.mime_type == "application/octet-stream"
    
    def test_create_json_result(self, mock_resource):
        """Test creating JSON result."""
        data = {"key": "value", "number": 42}
        result = mock_resource.create_json_result(data)
        
        assert result.success
        assert result.mime_type == "application/json"
        
        import json
        parsed_data = json.loads(result.get_text_content())
        assert parsed_data == data
    
    def test_create_json_result_error(self, mock_resource):
        """Test creating JSON result with non-serializable data."""
        # Create an object that can't be JSON serialized
        class NonSerializable:
            pass
        
        result = mock_resource.create_json_result(NonSerializable())
        
        assert not result.success
        assert "Failed to serialize" in result.error
    
    def test_create_error_result(self, mock_resource):
        """Test creating error result."""
        result = mock_resource.create_error_result("Test error message")
        
        assert not result.success
        assert result.error == "Test error message"