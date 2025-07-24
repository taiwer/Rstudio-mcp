"""Tool manager for RStudio MCP Server."""

import logging
from typing import Any, Dict, List, Optional, Type

from .base import BaseTool, ToolResult


class ToolManager:
    """Manager for MCP tools."""
    
    def __init__(self):
        """Initialize the tool manager."""
        self.logger = logging.getLogger(__name__)
        self._tools: Dict[str, BaseTool] = {}
        self._tool_classes: Dict[str, Type[BaseTool]] = {}
    
    def register_tool(self, tool: BaseTool) -> None:
        """Register a tool instance.
        
        Args:
            tool: Tool instance to register
            
        Raises:
            ValueError: If tool name already exists
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        
        self._tools[tool.name] = tool
        self.logger.info(f"Registered tool: {tool.name}")
    
    def register_tool_class(self, tool_class: Type[BaseTool], name: Optional[str] = None) -> None:
        """Register a tool class for lazy instantiation.
        
        Args:
            tool_class: Tool class to register
            name: Optional name override (uses class name if not provided)
            
        Raises:
            ValueError: If tool name already exists
        """
        # Get tool name from class if not provided
        if name is None:
            # Create temporary instance to get name
            temp_instance = tool_class()
            name = temp_instance.name
        
        if name in self._tool_classes or name in self._tools:
            raise ValueError(f"Tool '{name}' is already registered")
        
        self._tool_classes[name] = tool_class
        self.logger.info(f"Registered tool class: {name}")
    
    def unregister_tool(self, name: str) -> bool:
        """Unregister a tool.
        
        Args:
            name: Tool name to unregister
            
        Returns:
            True if tool was unregistered, False if not found
        """
        removed = False
        
        if name in self._tools:
            del self._tools[name]
            removed = True
        
        if name in self._tool_classes:
            del self._tool_classes[name]
            removed = True
        
        if removed:
            self.logger.info(f"Unregistered tool: {name}")
        
        return removed
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool instance by name.
        
        Args:
            name: Tool name
            
        Returns:
            Tool instance or None if not found
        """
        # Check if already instantiated
        if name in self._tools:
            return self._tools[name]
        
        # Check if we have a class to instantiate
        if name in self._tool_classes:
            try:
                tool_class = self._tool_classes[name]
                tool_instance = tool_class()
                
                # Move from class registry to instance registry
                self._tools[name] = tool_instance
                del self._tool_classes[name]
                
                self.logger.debug(f"Instantiated tool: {name}")
                return tool_instance
                
            except Exception as e:
                self.logger.error(f"Failed to instantiate tool '{name}': {e}")
                return None
        
        return None
    
    def list_tools(self) -> List[str]:
        """List all available tool names.
        
        Returns:
            List of tool names
        """
        return list(set(self._tools.keys()) | set(self._tool_classes.keys()))
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get MCP tool definitions for all registered tools.
        
        Returns:
            List of MCP tool definitions
        """
        definitions = []
        
        # Get definitions from instantiated tools
        for tool in self._tools.values():
            try:
                definitions.append(tool.to_mcp_tool())
            except Exception as e:
                self.logger.error(f"Failed to get definition for tool '{tool.name}': {e}")
        
        # Get definitions from tool classes (instantiate temporarily)
        for name, tool_class in self._tool_classes.items():
            try:
                temp_instance = tool_class()
                definitions.append(temp_instance.to_mcp_tool())
            except Exception as e:
                self.logger.error(f"Failed to get definition for tool class '{name}': {e}")
        
        return definitions
    
    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute a tool by name.
        
        Args:
            name: Tool name
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        tool = self.get_tool(name)
        
        if tool is None:
            error_msg = f"Tool '{name}' not found"
            self.logger.error(error_msg)
            return ToolResult(
                success=False,
                error=error_msg
            )
        
        return await tool.safe_execute(arguments)
    
    def validate_tool_arguments(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Validate arguments for a specific tool.
        
        Args:
            name: Tool name
            arguments: Arguments to validate
            
        Returns:
            Validated arguments
            
        Raises:
            ValueError: If tool not found
            ValidationError: If validation fails
        """
        tool = self.get_tool(name)
        
        if tool is None:
            raise ValueError(f"Tool '{name}' not found")
        
        return tool.validate_arguments(arguments)
    
    def get_tool_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """Get JSON schema for a tool's parameters.
        
        Args:
            name: Tool name
            
        Returns:
            JSON schema or None if tool not found
        """
        tool = self.get_tool(name)
        
        if tool is None:
            return None
        
        return tool.get_json_schema()
    
    def discover_tools(self, module_path: str) -> int:
        """Discover and register tools from a module.
        
        Args:
            module_path: Python module path to search for tools
            
        Returns:
            Number of tools discovered and registered
        """
        import importlib
        import inspect
        
        try:
            module = importlib.import_module(module_path)
            discovered_count = 0
            
            # Find all BaseTool subclasses in the module
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, BaseTool) and 
                    obj is not BaseTool and 
                    not inspect.isabstract(obj)):
                    
                    try:
                        self.register_tool_class(obj)
                        discovered_count += 1
                    except ValueError as e:
                        self.logger.warning(f"Skipped tool class '{name}': {e}")
            
            self.logger.info(f"Discovered {discovered_count} tools from module: {module_path}")
            return discovered_count
            
        except Exception as e:
            self.logger.error(f"Failed to discover tools from module '{module_path}': {e}")
            return 0
    
    def get_tool_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a tool.
        
        Args:
            name: Tool name
            
        Returns:
            Tool information dictionary or None if not found
        """
        tool = self.get_tool(name)
        
        if tool is None:
            return None
        
        return {
            "name": tool.name,
            "description": tool.description,
            "parameters": [param.dict() for param in tool.parameters],
            "schema": tool.get_json_schema(),
            "class": tool.__class__.__name__,
            "module": tool.__class__.__module__
        }
    
    def clear_tools(self) -> None:
        """Clear all registered tools."""
        count = len(self._tools) + len(self._tool_classes)
        self._tools.clear()
        self._tool_classes.clear()
        self.logger.info(f"Cleared {count} tools")
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        # Call cleanup on tools that support it
        for tool in self._tools.values():
            if hasattr(tool, 'cleanup') and callable(getattr(tool, 'cleanup')):
                try:
                    cleanup_method = getattr(tool, 'cleanup')
                    if inspect.iscoroutinefunction(cleanup_method):
                        await cleanup_method()
                    else:
                        cleanup_method()
                except Exception as e:
                    self.logger.warning(f"Error during cleanup of tool '{tool.name}': {e}")
        
        self.logger.info("Tool manager cleaned up")