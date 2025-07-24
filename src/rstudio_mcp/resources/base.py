"""Base resource classes and interfaces for RStudio MCP Server."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from pydantic import BaseModel, Field


class ResourceResult(BaseModel):
    """Result of resource operation."""
    
    success: bool = Field(..., description="Whether the resource operation was successful")
    content: Optional[Union[str, bytes]] = Field(None, description="Resource content")
    mime_type: str = Field(default="text/plain", description="MIME type of the content")
    error: Optional[str] = Field(None, description="Error message if operation failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    def is_text(self) -> bool:
        """Check if content is text-based.
        
        Returns:
            True if content is text-based
        """
        return self.mime_type.startswith("text/") or self.mime_type == "application/json"
    
    def is_binary(self) -> bool:
        """Check if content is binary.
        
        Returns:
            True if content is binary
        """
        return not self.is_text()
    
    def get_text_content(self) -> Optional[str]:
        """Get content as text.
        
        Returns:
            Text content or None if not text-based
        """
        if self.is_text() and isinstance(self.content, str):
            return self.content
        return None
    
    def get_binary_content(self) -> Optional[bytes]:
        """Get content as binary.
        
        Returns:
            Binary content or None if not binary
        """
        if self.is_binary() and isinstance(self.content, bytes):
            return self.content
        return None


class ResourceInfo(BaseModel):
    """Information about a resource."""
    
    uri: str = Field(..., description="Resource URI")
    name: str = Field(..., description="Human-readable resource name")
    description: str = Field(..., description="Resource description")
    mime_type: str = Field(default="text/plain", description="MIME type")
    size: Optional[int] = Field(None, description="Resource size in bytes")
    modified: Optional[str] = Field(None, description="Last modified timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    def to_mcp_resource(self) -> Dict[str, Any]:
        """Convert to MCP resource format.
        
        Returns:
            MCP resource definition
        """
        resource = {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type
        }
        
        if self.metadata:
            resource.update(self.metadata)
        
        return resource


class BaseResource(ABC):
    """Abstract base class for all MCP resources."""
    
    def __init__(self):
        """Initialize the resource."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @property
    @abstractmethod
    def scheme(self) -> str:
        """URI scheme handled by this resource."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Resource handler description."""
        pass
    
    @abstractmethod
    async def list_resources(self, uri_prefix: Optional[str] = None) -> List[ResourceInfo]:
        """List available resources.
        
        Args:
            uri_prefix: Optional URI prefix to filter resources
            
        Returns:
            List of available resources
        """
        pass
    
    @abstractmethod
    async def read_resource(self, uri: str) -> ResourceResult:
        """Read resource content.
        
        Args:
            uri: Resource URI
            
        Returns:
            Resource content and metadata
        """
        pass
    
    def validate_uri(self, uri: str) -> bool:
        """Validate if URI is supported by this resource handler.
        
        Args:
            uri: URI to validate
            
        Returns:
            True if URI is valid for this handler
        """
        try:
            parsed = urlparse(uri)
            return parsed.scheme == self.scheme
        except Exception:
            return False
    
    def parse_uri(self, uri: str) -> Dict[str, str]:
        """Parse URI into components.
        
        Args:
            uri: URI to parse
            
        Returns:
            Dictionary with URI components
        """
        parsed = urlparse(uri)
        return {
            "scheme": parsed.scheme,
            "netloc": parsed.netloc,
            "path": parsed.path,
            "params": parsed.params,
            "query": parsed.query,
            "fragment": parsed.fragment
        }
    
    async def safe_read_resource(self, uri: str) -> ResourceResult:
        """Safely read resource with error handling.
        
        Args:
            uri: Resource URI
            
        Returns:
            Resource result with error handling
        """
        try:
            if not self.validate_uri(uri):
                return ResourceResult(
                    success=False,
                    error=f"Invalid URI for {self.scheme} resource: {uri}"
                )
            
            self.logger.info(f"Reading resource: {uri}")
            result = await self.read_resource(uri)
            
            if result.success:
                self.logger.info(f"Successfully read resource: {uri}")
            else:
                self.logger.warning(f"Failed to read resource {uri}: {result.error}")
            
            return result
            
        except Exception as e:
            error_msg = f"Unexpected error reading resource {uri}: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return ResourceResult(
                success=False,
                error=error_msg
            )
    
    async def safe_list_resources(self, uri_prefix: Optional[str] = None) -> List[ResourceInfo]:
        """Safely list resources with error handling.
        
        Args:
            uri_prefix: Optional URI prefix to filter resources
            
        Returns:
            List of resources with error handling
        """
        try:
            self.logger.info(f"Listing resources for scheme: {self.scheme}")
            resources = await self.list_resources(uri_prefix)
            
            self.logger.info(f"Found {len(resources)} resources for scheme: {self.scheme}")
            return resources
            
        except Exception as e:
            error_msg = f"Unexpected error listing resources for scheme {self.scheme}: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return []
    
    def create_text_result(self, content: str, mime_type: str = "text/plain", 
                          metadata: Optional[Dict[str, Any]] = None) -> ResourceResult:
        """Create a successful text resource result.
        
        Args:
            content: Text content
            mime_type: MIME type
            metadata: Optional metadata
            
        Returns:
            ResourceResult with text content
        """
        return ResourceResult(
            success=True,
            content=content,
            mime_type=mime_type,
            metadata=metadata or {}
        )
    
    def create_binary_result(self, content: bytes, mime_type: str, 
                           metadata: Optional[Dict[str, Any]] = None) -> ResourceResult:
        """Create a successful binary resource result.
        
        Args:
            content: Binary content
            mime_type: MIME type
            metadata: Optional metadata
            
        Returns:
            ResourceResult with binary content
        """
        return ResourceResult(
            success=True,
            content=content,
            mime_type=mime_type,
            metadata=metadata or {}
        )
    
    def create_json_result(self, data: Any, metadata: Optional[Dict[str, Any]] = None) -> ResourceResult:
        """Create a successful JSON resource result.
        
        Args:
            data: Data to serialize as JSON
            metadata: Optional metadata
            
        Returns:
            ResourceResult with JSON content
        """
        try:
            content = json.dumps(data, indent=2, ensure_ascii=False)
            return self.create_text_result(content, "application/json", metadata)
        except Exception as e:
            return ResourceResult(
                success=False,
                error=f"Failed to serialize data as JSON: {str(e)}"
            )
    
    def create_error_result(self, error: str) -> ResourceResult:
        """Create an error resource result.
        
        Args:
            error: Error message
            
        Returns:
            ResourceResult with error
        """
        return ResourceResult(
            success=False,
            error=error
        )