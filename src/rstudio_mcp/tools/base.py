"""Base tool classes and interfaces for RStudio MCP Server."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class ToolValidationError(Exception):
    """Custom validation error for tool arguments."""
    pass


class ToolResult(BaseModel):
    """Result of tool execution."""
    
    success: bool = Field(..., description="Whether the tool execution was successful")
    content: List[Dict[str, Any]] = Field(default_factory=list, description="Tool output content")
    error: Optional[str] = Field(None, description="Error message if execution failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    def add_text_content(self, text: str) -> None:
        """Add text content to the result.
        
        Args:
            text: Text content to add
        """
        self.content.append({
            "type": "text",
            "text": text
        })
    
    def add_image_content(self, data: bytes, mime_type: str = "image/png") -> None:
        """Add image content to the result.
        
        Args:
            data: Image data bytes
            mime_type: MIME type of the image
        """
        import base64
        
        self.content.append({
            "type": "image",
            "data": base64.b64encode(data).decode('utf-8'),
            "mimeType": mime_type
        })
    
    def add_resource_content(self, uri: str, text: Optional[str] = None, 
                           blob: Optional[bytes] = None, mime_type: str = "text/plain") -> None:
        """Add resource content to the result.
        
        Args:
            uri: Resource URI
            text: Text content (for text resources)
            blob: Binary content (for binary resources)
            mime_type: MIME type of the resource
        """
        content = {
            "type": "resource",
            "resource": {
                "uri": uri,
                "mimeType": mime_type
            }
        }
        
        if text is not None:
            content["resource"]["text"] = text
        elif blob is not None:
            import base64
            content["resource"]["blob"] = base64.b64encode(blob).decode('utf-8')
        
        self.content.append(content)


class ToolParameter(BaseModel):
    """Tool parameter definition."""
    
    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter type (string, number, boolean, array, object)")
    description: str = Field(..., description="Parameter description")
    required: bool = Field(default=False, description="Whether parameter is required")
    default: Optional[Any] = Field(None, description="Default value")
    enum: Optional[List[Any]] = Field(None, description="Allowed values for enum types")
    items: Optional[Dict[str, Any]] = Field(None, description="Item schema for array types")
    properties: Optional[Dict[str, Any]] = Field(None, description="Properties for object types")
    
    def to_json_schema(self) -> Dict[str, Any]:
        """Convert to JSON Schema format.
        
        Returns:
            JSON Schema representation
        """
        schema = {
            "type": self.type,
            "description": self.description
        }
        
        if self.enum is not None:
            schema["enum"] = self.enum
        
        if self.items is not None:
            schema["items"] = self.items
        
        if self.properties is not None:
            schema["properties"] = self.properties
        
        if self.default is not None:
            schema["default"] = self.default
        
        return schema


class BaseTool(ABC):
    """Abstract base class for all MCP tools."""
    
    def __init__(self):
        """Initialize the tool."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description."""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> List[ToolParameter]:
        """Tool parameters."""
        pass
    
    @abstractmethod
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the tool with given arguments.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        pass
    
    def get_json_schema(self) -> Dict[str, Any]:
        """Get JSON Schema for tool parameters.
        
        Returns:
            JSON Schema for tool input validation
        """
        properties = {}
        required = []
        
        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)
        
        schema = {
            "type": "object",
            "properties": properties
        }
        
        if required:
            schema["required"] = required
        
        return schema
    
    def validate_arguments(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Validate tool arguments against schema.
        
        Args:
            arguments: Arguments to validate
            
        Returns:
            Validated arguments with defaults applied
            
        Raises:
            ValidationError: If validation fails
        """
        schema = self.get_json_schema()
        
        # Apply defaults
        validated_args = arguments.copy()
        for param in self.parameters:
            if param.name not in validated_args and param.default is not None:
                validated_args[param.name] = param.default
        
        # Basic validation
        required_params = [p.name for p in self.parameters if p.required]
        missing_params = [p for p in required_params if p not in validated_args]
        
        if missing_params:
            raise ToolValidationError(f"Missing required parameters: {missing_params}")
        
        # Type validation
        for param in self.parameters:
            if param.name in validated_args:
                value = validated_args[param.name]
                if not self._validate_type(value, param.type):
                    raise ToolValidationError(f"Parameter '{param.name}' must be of type {param.type}")
                
                # Enum validation
                if param.enum is not None and value not in param.enum:
                    raise ToolValidationError(f"Parameter '{param.name}' must be one of: {param.enum}")
        
        return validated_args
    
    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Validate value type.
        
        Args:
            value: Value to validate
            expected_type: Expected type string
            
        Returns:
            True if type is valid
        """
        type_mapping = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict
        }
        
        expected_python_type = type_mapping.get(expected_type)
        if expected_python_type is None:
            return True  # Unknown type, skip validation
        
        return isinstance(value, expected_python_type)
    
    async def safe_execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Safely execute the tool with error handling.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        try:
            # Validate arguments
            validated_args = self.validate_arguments(arguments)
            
            # Execute tool
            self.logger.info(f"Executing tool '{self.name}' with arguments: {validated_args}")
            result = await self.execute(validated_args)
            
            if result.success:
                self.logger.info(f"Tool '{self.name}' executed successfully")
            else:
                self.logger.warning(f"Tool '{self.name}' execution failed: {result.error}")
            
            return result
            
        except ToolValidationError as e:
            error_msg = f"Argument validation failed: {str(e)}"
            self.logger.error(error_msg)
            return ToolResult(
                success=False,
                error=error_msg
            )
        
        except Exception as e:
            error_msg = f"Unexpected error during tool execution: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return ToolResult(
                success=False,
                error=error_msg
            )
    
    def to_mcp_tool(self) -> Dict[str, Any]:
        """Convert to MCP tool format.
        
        Returns:
            MCP tool definition
        """
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.get_json_schema()
        }