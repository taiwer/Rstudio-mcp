"""Tests for the base tool classes."""

import pytest
from typing import Any, Dict, List
from unittest.mock import Mock, patch

from src.rstudio_mcp.tools.base import BaseTool, ToolResult, ToolParameter, ToolValidationError


class MockTool(BaseTool):
    """Mock tool for testing."""
    
    @property
    def name(self) -> str:
        return "mock_tool"
    
    @property
    def description(self) -> str:
        return "A mock tool for testing"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="text",
                type="string",
                description="Text input",
                required=True
            ),
            ToolParameter(
                name="count",
                type="number",
                description="Count parameter",
                required=False,
                default=1
            ),
            ToolParameter(
                name="mode",
                type="string",
                description="Mode selection",
                required=False,
                enum=["fast", "slow", "medium"]
            )
        ]
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Mock execution."""
        result = ToolResult(success=True)
        result.add_text_content(f"Processed: {arguments.get('text', '')} (count: {arguments.get('count', 1)})")
        return result


class TestToolResult:
    """Test ToolResult class."""
    
    def test_init_success(self):
        """Test successful initialization."""
        result = ToolResult(success=True)
        assert result.success is True
        assert result.content == []
        assert result.error is None
        assert result.metadata == {}
    
    def test_init_failure(self):
        """Test failure initialization."""
        result = ToolResult(success=False, error="Test error")
        assert result.success is False
        assert result.error == "Test error"
    
    def test_add_text_content(self):
        """Test adding text content."""
        result = ToolResult(success=True)
        result.add_text_content("Hello, world!")
        
        assert len(result.content) == 1
        assert result.content[0]["type"] == "text"
        assert result.content[0]["text"] == "Hello, world!"
    
    def test_add_image_content(self):
        """Test adding image content."""
        result = ToolResult(success=True)
        image_data = b"fake_image_data"
        result.add_image_content(image_data, "image/jpeg")
        
        assert len(result.content) == 1
        assert result.content[0]["type"] == "image"
        assert result.content[0]["mimeType"] == "image/jpeg"
        assert "data" in result.content[0]
    
    def test_add_resource_content_text(self):
        """Test adding text resource content."""
        result = ToolResult(success=True)
        result.add_resource_content("file://test.txt", text="Hello", mime_type="text/plain")
        
        assert len(result.content) == 1
        assert result.content[0]["type"] == "resource"
        assert result.content[0]["resource"]["uri"] == "file://test.txt"
        assert result.content[0]["resource"]["text"] == "Hello"
        assert result.content[0]["resource"]["mimeType"] == "text/plain"
    
    def test_add_resource_content_blob(self):
        """Test adding binary resource content."""
        result = ToolResult(success=True)
        blob_data = b"binary_data"
        result.add_resource_content("file://test.bin", blob=blob_data, mime_type="application/octet-stream")
        
        assert len(result.content) == 1
        assert result.content[0]["type"] == "resource"
        assert result.content[0]["resource"]["uri"] == "file://test.bin"
        assert "blob" in result.content[0]["resource"]
        assert result.content[0]["resource"]["mimeType"] == "application/octet-stream"


class TestToolParameter:
    """Test ToolParameter class."""
    
    def test_basic_parameter(self):
        """Test basic parameter creation."""
        param = ToolParameter(
            name="test_param",
            type="string",
            description="Test parameter",
            required=True
        )
        
        assert param.name == "test_param"
        assert param.type == "string"
        assert param.description == "Test parameter"
        assert param.required is True
        assert param.default is None
    
    def test_parameter_with_default(self):
        """Test parameter with default value."""
        param = ToolParameter(
            name="count",
            type="number",
            description="Count parameter",
            required=False,
            default=10
        )
        
        assert param.default == 10
        assert param.required is False
    
    def test_parameter_with_enum(self):
        """Test parameter with enum values."""
        param = ToolParameter(
            name="mode",
            type="string",
            description="Mode selection",
            enum=["fast", "slow", "medium"]
        )
        
        assert param.enum == ["fast", "slow", "medium"]
    
    def test_to_json_schema_basic(self):
        """Test JSON schema generation for basic parameter."""
        param = ToolParameter(
            name="text",
            type="string",
            description="Text input"
        )
        
        schema = param.to_json_schema()
        expected = {
            "type": "string",
            "description": "Text input"
        }
        
        assert schema == expected
    
    def test_to_json_schema_with_enum(self):
        """Test JSON schema generation with enum."""
        param = ToolParameter(
            name="mode",
            type="string",
            description="Mode selection",
            enum=["fast", "slow"]
        )
        
        schema = param.to_json_schema()
        assert schema["enum"] == ["fast", "slow"]
    
    def test_to_json_schema_with_default(self):
        """Test JSON schema generation with default."""
        param = ToolParameter(
            name="count",
            type="number",
            description="Count parameter",
            default=5
        )
        
        schema = param.to_json_schema()
        assert schema["default"] == 5


class TestBaseTool:
    """Test BaseTool abstract class."""
    
    def test_mock_tool_properties(self):
        """Test mock tool properties."""
        tool = MockTool()
        
        assert tool.name == "mock_tool"
        assert tool.description == "A mock tool for testing"
        assert len(tool.parameters) == 3
        assert tool.parameters[0].name == "text"
        assert tool.parameters[0].required is True
    
    def test_get_json_schema(self):
        """Test JSON schema generation."""
        tool = MockTool()
        schema = tool.get_json_schema()
        
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        
        # Check properties
        assert "text" in schema["properties"]
        assert "count" in schema["properties"]
        assert "mode" in schema["properties"]
        
        # Check required fields
        assert "text" in schema["required"]
        assert "count" not in schema["required"]
        assert "mode" not in schema["required"]
        
        # Check parameter details
        assert schema["properties"]["text"]["type"] == "string"
        assert schema["properties"]["count"]["type"] == "number"
        assert schema["properties"]["count"]["default"] == 1
        assert schema["properties"]["mode"]["enum"] == ["fast", "slow", "medium"]
    
    def test_validate_arguments_success(self):
        """Test successful argument validation."""
        tool = MockTool()
        
        arguments = {"text": "hello"}
        validated = tool.validate_arguments(arguments)
        
        assert validated["text"] == "hello"
        assert validated["count"] == 1  # Default applied
    
    def test_validate_arguments_with_optional(self):
        """Test argument validation with optional parameters."""
        tool = MockTool()
        
        arguments = {"text": "hello", "count": 5, "mode": "fast"}
        validated = tool.validate_arguments(arguments)
        
        assert validated["text"] == "hello"
        assert validated["count"] == 5
        assert validated["mode"] == "fast"
    
    def test_validate_arguments_missing_required(self):
        """Test validation failure with missing required parameter."""
        tool = MockTool()
        
        arguments = {"count": 5}  # Missing required 'text'
        
        with pytest.raises(ToolValidationError, match="Missing required parameters"):
            tool.validate_arguments(arguments)
    
    def test_validate_arguments_invalid_enum(self):
        """Test validation failure with invalid enum value."""
        tool = MockTool()
        
        arguments = {"text": "hello", "mode": "invalid"}
        
        with pytest.raises(ToolValidationError, match="must be one of"):
            tool.validate_arguments(arguments)
    
    def test_validate_type_string(self):
        """Test type validation for string."""
        tool = MockTool()
        
        assert tool._validate_type("hello", "string") is True
        assert tool._validate_type(123, "string") is False
    
    def test_validate_type_number(self):
        """Test type validation for number."""
        tool = MockTool()
        
        assert tool._validate_type(123, "number") is True
        assert tool._validate_type(123.45, "number") is True
        assert tool._validate_type("123", "number") is False
    
    def test_validate_type_boolean(self):
        """Test type validation for boolean."""
        tool = MockTool()
        
        assert tool._validate_type(True, "boolean") is True
        assert tool._validate_type(False, "boolean") is True
        assert tool._validate_type(1, "boolean") is False
    
    def test_validate_type_array(self):
        """Test type validation for array."""
        tool = MockTool()
        
        assert tool._validate_type([1, 2, 3], "array") is True
        assert tool._validate_type([], "array") is True
        assert tool._validate_type("not_array", "array") is False
    
    def test_validate_type_object(self):
        """Test type validation for object."""
        tool = MockTool()
        
        assert tool._validate_type({"key": "value"}, "object") is True
        assert tool._validate_type({}, "object") is True
        assert tool._validate_type("not_object", "object") is False
    
    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful tool execution."""
        tool = MockTool()
        
        arguments = {"text": "test", "count": 2}
        result = await tool.execute(arguments)
        
        assert result.success is True
        assert len(result.content) == 1
        assert "test" in result.content[0]["text"]
        assert "count: 2" in result.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_safe_execute_success(self):
        """Test safe execution with valid arguments."""
        tool = MockTool()
        
        arguments = {"text": "test"}
        result = await tool.safe_execute(arguments)
        
        assert result.success is True
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_safe_execute_validation_error(self):
        """Test safe execution with validation error."""
        tool = MockTool()
        
        arguments = {}  # Missing required 'text'
        result = await tool.safe_execute(arguments)
        
        assert result.success is False
        assert "Argument validation failed" in result.error
    
    @pytest.mark.asyncio
    async def test_safe_execute_execution_error(self):
        """Test safe execution with execution error."""
        tool = MockTool()
        
        # Mock the execute method to raise an exception
        with patch.object(tool, 'execute', side_effect=Exception("Test error")):
            arguments = {"text": "test"}
            result = await tool.safe_execute(arguments)
            
            assert result.success is False
            assert "Unexpected error during tool execution" in result.error
    
    def test_to_mcp_tool(self):
        """Test MCP tool format conversion."""
        tool = MockTool()
        mcp_tool = tool.to_mcp_tool()
        
        assert mcp_tool["name"] == "mock_tool"
        assert mcp_tool["description"] == "A mock tool for testing"
        assert "inputSchema" in mcp_tool
        
        schema = mcp_tool["inputSchema"]
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema


class TestToolParameterEdgeCases:
    """Test edge cases for ToolParameter."""
    
    def test_parameter_with_items(self):
        """Test parameter with items schema for arrays."""
        param = ToolParameter(
            name="tags",
            type="array",
            description="List of tags",
            items={"type": "string"}
        )
        
        schema = param.to_json_schema()
        assert schema["items"] == {"type": "string"}
    
    def test_parameter_with_properties(self):
        """Test parameter with properties for objects."""
        param = ToolParameter(
            name="config",
            type="object",
            description="Configuration object",
            properties={
                "name": {"type": "string"},
                "value": {"type": "number"}
            }
        )
        
        schema = param.to_json_schema()
        assert schema["properties"]["name"]["type"] == "string"
        assert schema["properties"]["value"]["type"] == "number"


class TestBaseToolEdgeCases:
    """Test edge cases for BaseTool."""
    
    def test_validate_unknown_type(self):
        """Test validation with unknown type."""
        tool = MockTool()
        
        # Unknown types should pass validation
        assert tool._validate_type("anything", "unknown_type") is True
    
    @pytest.mark.asyncio
    async def test_safe_execute_with_logger(self):
        """Test that safe_execute uses logger correctly."""
        tool = MockTool()
        
        with patch.object(tool.logger, 'info') as mock_info, \
             patch.object(tool.logger, 'warning') as mock_warning:
            
            # Test successful execution
            arguments = {"text": "test"}
            result = await tool.safe_execute(arguments)
            
            assert result.success is True
            mock_info.assert_called()
            
            # Test failed execution
            with patch.object(tool, 'execute', return_value=ToolResult(success=False, error="Test error")):
                result = await tool.safe_execute(arguments)
                
                assert result.success is False
                mock_warning.assert_called()