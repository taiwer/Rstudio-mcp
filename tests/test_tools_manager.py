"""Tests for the ToolManager class."""

import pytest
from typing import Any, Dict, List
from unittest.mock import Mock, patch, AsyncMock

from src.rstudio_mcp.tools.manager import ToolManager
from src.rstudio_mcp.tools.base import BaseTool, ToolResult, ToolParameter, ToolValidationError


class MockTool(BaseTool):
    """Mock tool for testing."""
    
    def __init__(self, name: str = "mock_tool", should_fail: bool = False):
        super().__init__()
        self._name = name
        self._should_fail = should_fail
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return f"Mock tool: {self._name}"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="input",
                type="string",
                description="Input text",
                required=True
            )
        ]
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Mock execution."""
        if self._should_fail:
            return ToolResult(success=False, error="Mock execution failed")
        
        result = ToolResult(success=True)
        result.add_text_content(f"Mock output: {arguments.get('input', '')}")
        return result


class MockToolClass:
    """Mock tool class for testing class registration."""
    
    def __init__(self):
        pass
    
    @property
    def name(self) -> str:
        return "mock_class_tool"
    
    @property
    def description(self) -> str:
        return "Mock tool from class"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return []
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        result = ToolResult(success=True)
        result.add_text_content("Mock class tool executed")
        return result
    
    def to_mcp_tool(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {"type": "object", "properties": {}}
        }


class TestToolManager:
    """Test ToolManager class."""
    
    def test_init(self):
        """Test ToolManager initialization."""
        manager = ToolManager()
        
        assert manager._tools == {}
        assert manager._tool_classes == {}
        assert manager.logger is not None
    
    def test_register_tool_success(self):
        """Test successful tool registration."""
        manager = ToolManager()
        tool = MockTool("test_tool")
        
        manager.register_tool(tool)
        
        assert "test_tool" in manager._tools
        assert manager._tools["test_tool"] is tool
    
    def test_register_tool_duplicate(self):
        """Test registration of duplicate tool name."""
        manager = ToolManager()
        tool1 = MockTool("duplicate")
        tool2 = MockTool("duplicate")
        
        manager.register_tool(tool1)
        
        with pytest.raises(ValueError, match="already registered"):
            manager.register_tool(tool2)
    
    def test_register_tool_class_success(self):
        """Test successful tool class registration."""
        manager = ToolManager()
        
        manager.register_tool_class(MockTool, "class_tool")
        
        assert "class_tool" in manager._tool_classes
        assert manager._tool_classes["class_tool"] is MockTool
    
    def test_register_tool_class_auto_name(self):
        """Test tool class registration with automatic name detection."""
        manager = ToolManager()
        
        # Create a mock class that returns a specific name
        class TestTool(BaseTool):
            @property
            def name(self) -> str:
                return "auto_named_tool"
            
            @property
            def description(self) -> str:
                return "Auto named tool"
            
            @property
            def parameters(self) -> List[ToolParameter]:
                return []
            
            async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
                return ToolResult(success=True)
        
        manager.register_tool_class(TestTool)
        
        assert "auto_named_tool" in manager._tool_classes
    
    def test_register_tool_class_duplicate(self):
        """Test registration of duplicate tool class name."""
        manager = ToolManager()
        
        manager.register_tool_class(MockTool, "duplicate")
        
        with pytest.raises(ValueError, match="already registered"):
            manager.register_tool_class(MockTool, "duplicate")
    
    def test_unregister_tool_instance(self):
        """Test unregistering a tool instance."""
        manager = ToolManager()
        tool = MockTool("test_tool")
        
        manager.register_tool(tool)
        assert "test_tool" in manager._tools
        
        result = manager.unregister_tool("test_tool")
        
        assert result is True
        assert "test_tool" not in manager._tools
    
    def test_unregister_tool_class(self):
        """Test unregistering a tool class."""
        manager = ToolManager()
        
        manager.register_tool_class(MockTool, "class_tool")
        assert "class_tool" in manager._tool_classes
        
        result = manager.unregister_tool("class_tool")
        
        assert result is True
        assert "class_tool" not in manager._tool_classes
    
    def test_unregister_tool_not_found(self):
        """Test unregistering a non-existent tool."""
        manager = ToolManager()
        
        result = manager.unregister_tool("nonexistent")
        
        assert result is False
    
    def test_get_tool_instance(self):
        """Test getting a registered tool instance."""
        manager = ToolManager()
        tool = MockTool("test_tool")
        
        manager.register_tool(tool)
        
        retrieved = manager.get_tool("test_tool")
        
        assert retrieved is tool
    
    def test_get_tool_from_class(self):
        """Test getting a tool by instantiating from class."""
        manager = ToolManager()
        
        manager.register_tool_class(MockTool, "class_tool")
        
        retrieved = manager.get_tool("class_tool")
        
        assert retrieved is not None
        assert retrieved.name == "class_tool"
        assert "class_tool" in manager._tools  # Should be moved to instances
        assert "class_tool" not in manager._tool_classes  # Should be removed from classes
    
    def test_get_tool_not_found(self):
        """Test getting a non-existent tool."""
        manager = ToolManager()
        
        retrieved = manager.get_tool("nonexistent")
        
        assert retrieved is None
    
    def test_get_tool_instantiation_error(self):
        """Test handling of tool instantiation errors."""
        manager = ToolManager()
        
        # Mock a class that raises an exception during instantiation
        class FailingTool:
            def __init__(self):
                raise Exception("Instantiation failed")
        
        manager._tool_classes["failing_tool"] = FailingTool
        
        with patch.object(manager.logger, 'error') as mock_error:
            retrieved = manager.get_tool("failing_tool")
            
            assert retrieved is None
            mock_error.assert_called_once()
    
    def test_list_tools_empty(self):
        """Test listing tools when none are registered."""
        manager = ToolManager()
        
        tools = manager.list_tools()
        
        assert tools == []
    
    def test_list_tools_with_instances_and_classes(self):
        """Test listing tools with both instances and classes."""
        manager = ToolManager()
        
        tool = MockTool("instance_tool")
        manager.register_tool(tool)
        manager.register_tool_class(MockTool, "class_tool")
        
        tools = manager.list_tools()
        
        assert "instance_tool" in tools
        assert "class_tool" in tools
        assert len(tools) == 2
    
    def test_get_tool_definitions_instances(self):
        """Test getting tool definitions from instances."""
        manager = ToolManager()
        tool = MockTool("test_tool")
        
        manager.register_tool(tool)
        
        definitions = manager.get_tool_definitions()
        
        assert len(definitions) == 1
        assert definitions[0]["name"] == "test_tool"
        assert definitions[0]["description"] == "Mock tool: test_tool"
    
    def test_get_tool_definitions_classes(self):
        """Test getting tool definitions from classes."""
        manager = ToolManager()
        
        manager.register_tool_class(MockTool, "class_tool")
        
        definitions = manager.get_tool_definitions()
        
        assert len(definitions) == 1
        assert definitions[0]["name"] == "class_tool"
    
    def test_get_tool_definitions_error_handling(self):
        """Test error handling in get_tool_definitions."""
        manager = ToolManager()
        
        # Create a mock tool that raises an exception in to_mcp_tool
        tool = MockTool("error_tool")
        with patch.object(tool, 'to_mcp_tool', side_effect=Exception("Definition error")):
            manager.register_tool(tool)
            
            with patch.object(manager.logger, 'error') as mock_error:
                definitions = manager.get_tool_definitions()
                
                assert definitions == []
                mock_error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_tool_success(self):
        """Test successful tool execution."""
        manager = ToolManager()
        tool = MockTool("test_tool")
        
        manager.register_tool(tool)
        
        result = await manager.execute_tool("test_tool", {"input": "hello"})
        
        assert result.success is True
        assert len(result.content) == 1
        assert "hello" in result.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self):
        """Test executing a non-existent tool."""
        manager = ToolManager()
        
        result = await manager.execute_tool("nonexistent", {})
        
        assert result.success is False
        assert "not found" in result.error
    
    @pytest.mark.asyncio
    async def test_execute_tool_from_class(self):
        """Test executing a tool from class registration."""
        manager = ToolManager()
        
        manager.register_tool_class(MockTool, "class_tool")
        
        result = await manager.execute_tool("class_tool", {"input": "test"})
        
        assert result.success is True
    
    def test_validate_tool_arguments_success(self):
        """Test successful argument validation."""
        manager = ToolManager()
        tool = MockTool("test_tool")
        
        manager.register_tool(tool)
        
        validated = manager.validate_tool_arguments("test_tool", {"input": "hello"})
        
        assert validated["input"] == "hello"
    
    def test_validate_tool_arguments_not_found(self):
        """Test argument validation for non-existent tool."""
        manager = ToolManager()
        
        with pytest.raises(ValueError, match="not found"):
            manager.validate_tool_arguments("nonexistent", {})
    
    def test_validate_tool_arguments_validation_error(self):
        """Test argument validation error."""
        manager = ToolManager()
        tool = MockTool("test_tool")
        
        manager.register_tool(tool)
        
        with pytest.raises(ValidationError):
            manager.validate_tool_arguments("test_tool", {})  # Missing required 'input'
    
    def test_get_tool_schema_success(self):
        """Test getting tool schema."""
        manager = ToolManager()
        tool = MockTool("test_tool")
        
        manager.register_tool(tool)
        
        schema = manager.get_tool_schema("test_tool")
        
        assert schema is not None
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "input" in schema["properties"]
    
    def test_get_tool_schema_not_found(self):
        """Test getting schema for non-existent tool."""
        manager = ToolManager()
        
        schema = manager.get_tool_schema("nonexistent")
        
        assert schema is None
    
    def test_get_tool_info_success(self):
        """Test getting tool information."""
        manager = ToolManager()
        tool = MockTool("test_tool")
        
        manager.register_tool(tool)
        
        info = manager.get_tool_info("test_tool")
        
        assert info is not None
        assert info["name"] == "test_tool"
        assert info["description"] == "Mock tool: test_tool"
        assert "parameters" in info
        assert "schema" in info
        assert "class" in info
        assert "module" in info
    
    def test_get_tool_info_not_found(self):
        """Test getting info for non-existent tool."""
        manager = ToolManager()
        
        info = manager.get_tool_info("nonexistent")
        
        assert info is None
    
    def test_clear_tools(self):
        """Test clearing all tools."""
        manager = ToolManager()
        
        tool = MockTool("test_tool")
        manager.register_tool(tool)
        manager.register_tool_class(MockTool, "class_tool")
        
        assert len(manager._tools) == 1
        assert len(manager._tool_classes) == 1
        
        manager.clear_tools()
        
        assert len(manager._tools) == 0
        assert len(manager._tool_classes) == 0
    
    @pytest.mark.asyncio
    async def test_cleanup_with_cleanup_methods(self):
        """Test cleanup with tools that have cleanup methods."""
        manager = ToolManager()
        
        # Create a mock tool with cleanup method
        tool = MockTool("test_tool")
        tool.cleanup = AsyncMock()
        
        manager.register_tool(tool)
        
        await manager.cleanup()
        
        tool.cleanup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_with_sync_cleanup(self):
        """Test cleanup with synchronous cleanup methods."""
        manager = ToolManager()
        
        # Create a mock tool with sync cleanup method
        tool = MockTool("test_tool")
        tool.cleanup = Mock()
        
        manager.register_tool(tool)
        
        await manager.cleanup()
        
        tool.cleanup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_error_handling(self):
        """Test cleanup error handling."""
        manager = ToolManager()
        
        # Create a mock tool with failing cleanup method
        tool = MockTool("test_tool")
        tool.cleanup = Mock(side_effect=Exception("Cleanup failed"))
        
        manager.register_tool(tool)
        
        with patch.object(manager.logger, 'warning') as mock_warning:
            await manager.cleanup()
            
            mock_warning.assert_called_once()
    
    def test_discover_tools_success(self):
        """Test successful tool discovery."""
        manager = ToolManager()
        
        # Mock the importlib and inspect modules
        with patch('importlib.import_module') as mock_import, \
             patch('inspect.getmembers') as mock_getmembers, \
             patch('inspect.isclass') as mock_isclass, \
             patch('inspect.isabstract') as mock_isabstract:
            
            # Mock module with tool classes
            mock_module = Mock()
            mock_import.return_value = mock_module
            
            # Mock tool class
            mock_tool_class = Mock()
            mock_tool_class.__name__ = "TestTool"
            
            mock_getmembers.return_value = [("TestTool", mock_tool_class)]
            mock_isclass.return_value = True
            mock_isabstract.return_value = False
            
            # Mock issubclass to return True for our mock class
            with patch('builtins.issubclass', return_value=True):
                # Mock the tool class instantiation
                mock_instance = Mock()
                mock_instance.name = "discovered_tool"
                mock_tool_class.return_value = mock_instance
                
                count = manager.discover_tools("test.module")
                
                assert count == 1
                assert "discovered_tool" in manager._tool_classes
    
    def test_discover_tools_import_error(self):
        """Test tool discovery with import error."""
        manager = ToolManager()
        
        with patch('importlib.import_module', side_effect=ImportError("Module not found")):
            with patch.object(manager.logger, 'error') as mock_error:
                count = manager.discover_tools("nonexistent.module")
                
                assert count == 0
                mock_error.assert_called_once()
    
    def test_discover_tools_registration_error(self):
        """Test tool discovery with registration error."""
        manager = ToolManager()
        
        with patch('importlib.import_module') as mock_import, \
             patch('inspect.getmembers') as mock_getmembers, \
             patch('inspect.isclass') as mock_isclass, \
             patch('inspect.isabstract') as mock_isabstract:
            
            mock_module = Mock()
            mock_import.return_value = mock_module
            
            mock_tool_class = Mock()
            mock_tool_class.__name__ = "TestTool"
            
            mock_getmembers.return_value = [("TestTool", mock_tool_class)]
            mock_isclass.return_value = True
            mock_isabstract.return_value = False
            
            with patch('builtins.issubclass', return_value=True):
                # Mock register_tool_class to raise ValueError
                with patch.object(manager, 'register_tool_class', side_effect=ValueError("Duplicate tool")):
                    with patch.object(manager.logger, 'warning') as mock_warning:
                        count = manager.discover_tools("test.module")
                        
                        assert count == 0
                        mock_warning.assert_called_once()


class TestToolManagerIntegration:
    """Integration tests for ToolManager."""
    
    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test complete workflow from registration to execution."""
        manager = ToolManager()
        
        # Register tool class
        manager.register_tool_class(MockTool, "workflow_tool")
        
        # List tools
        tools = manager.list_tools()
        assert "workflow_tool" in tools
        
        # Get tool definitions
        definitions = manager.get_tool_definitions()
        assert len(definitions) == 1
        assert definitions[0]["name"] == "workflow_tool"
        
        # Execute tool (this should instantiate it)
        result = await manager.execute_tool("workflow_tool", {"input": "test"})
        assert result.success is True
        
        # Verify tool was moved to instances
        assert "workflow_tool" in manager._tools
        assert "workflow_tool" not in manager._tool_classes
        
        # Get tool info
        info = manager.get_tool_info("workflow_tool")
        assert info is not None
        assert info["name"] == "workflow_tool"