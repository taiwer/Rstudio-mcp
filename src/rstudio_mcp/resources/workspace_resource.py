"""Workspace resource handler for RStudio MCP Server."""

import json
from typing import Any, Dict, List, Optional

from ..api_wrapper import RStudioAPIWrapper
from .base import BaseResource, ResourceInfo, ResourceResult


class WorkspaceResource(BaseResource):
    """Resource handler for RStudio workspace objects."""
    
    def __init__(self, api_wrapper: Optional[RStudioAPIWrapper] = None):
        """Initialize the workspace resource handler.
        
        Args:
            api_wrapper: Optional RStudio API wrapper instance
        """
        super().__init__()
        self.api_wrapper = api_wrapper
    
    @property
    def scheme(self) -> str:
        """URI scheme handled by this resource."""
        return "rstudio-workspace"
    
    @property
    def description(self) -> str:
        """Resource handler description."""
        return "RStudio workspace objects and environment information"
    
    async def list_resources(self, uri_prefix: Optional[str] = None) -> List[ResourceInfo]:
        """List available workspace resources.
        
        Args:
            uri_prefix: Optional URI prefix to filter resources
            
        Returns:
            List of available workspace resources
        """
        resources = []
        
        if not self.api_wrapper:
            self.logger.warning("No API wrapper available for workspace resources")
            return resources
        
        try:
            # Get workspace objects
            workspace_objects = await self.api_wrapper.get_workspace_objects()
            
            for obj_info in workspace_objects:
                if isinstance(obj_info, dict):
                    obj_name = obj_info.get('name', 'unknown')
                    obj_class = obj_info.get('class', 'unknown')
                    obj_type = obj_info.get('type', 'unknown')
                    obj_size = obj_info.get('size', 0)
                    
                    resources.append(ResourceInfo(
                        uri=f"rstudio-workspace://{obj_name}",
                        name=f"Object: {obj_name}",
                        description=f"R object of class {obj_class} (type: {obj_type})",
                        mime_type="application/json",
                        size=obj_size if isinstance(obj_size, int) else None,
                        metadata={
                            "object_name": obj_name,
                            "object_class": obj_class,
                            "object_type": obj_type,
                            "object_size": obj_size
                        }
                    ))
            
            # Add special workspace resources
            resources.extend([
                ResourceInfo(
                    uri="rstudio-workspace://summary",
                    name="Workspace Summary",
                    description="Summary of all workspace objects",
                    mime_type="application/json",
                    metadata={"special": "summary"}
                ),
                ResourceInfo(
                    uri="rstudio-workspace://environment",
                    name="Environment Info",
                    description="Current R environment information",
                    mime_type="application/json",
                    metadata={"special": "environment"}
                )
            ])
        
        except Exception as e:
            self.logger.error(f"Error listing workspace resources: {e}")
        
        return resources
    
    async def read_resource(self, uri: str) -> ResourceResult:
        """Read workspace resource content.
        
        Args:
            uri: Resource URI
            
        Returns:
            Resource content and metadata
        """
        if not self.api_wrapper:
            return self.create_error_result("No API wrapper available for workspace resources")
        
        try:
            uri_parts = self.parse_uri(uri)
            # For workspace URIs, the object name can be in netloc or path
            object_name = uri_parts["netloc"] or uri_parts["path"].strip("/")
            
            if not object_name:
                return self.create_error_result("Invalid workspace URI: missing object name")
            
            # Handle special resources
            if object_name == "summary":
                return await self._read_workspace_summary()
            elif object_name == "environment":
                return await self._read_environment_info()
            else:
                # Handle specific workspace object
                return await self._read_workspace_object(object_name)
        
        except Exception as e:
            return self.create_error_result(f"Error reading workspace resource: {str(e)}")
    
    async def _read_workspace_summary(self) -> ResourceResult:
        """Read workspace summary.
        
        Returns:
            Workspace summary as JSON
        """
        try:
            workspace_objects = await self.api_wrapper.get_workspace_objects()
            
            summary = {
                "total_objects": len(workspace_objects),
                "objects_by_class": {},
                "objects_by_type": {},
                "total_size": 0,
                "objects": []
            }
            
            for obj_info in workspace_objects:
                if isinstance(obj_info, dict):
                    obj_name = obj_info.get('name', 'unknown')
                    obj_class = obj_info.get('class', 'unknown')
                    obj_type = obj_info.get('type', 'unknown')
                    obj_size = obj_info.get('size', 0)
                    
                    # Count by class
                    summary["objects_by_class"][obj_class] = summary["objects_by_class"].get(obj_class, 0) + 1
                    
                    # Count by type
                    summary["objects_by_type"][obj_type] = summary["objects_by_type"].get(obj_type, 0) + 1
                    
                    # Add to total size
                    if isinstance(obj_size, (int, float)):
                        summary["total_size"] += obj_size
                    
                    # Add to objects list
                    summary["objects"].append({
                        "name": obj_name,
                        "class": obj_class,
                        "type": obj_type,
                        "size": obj_size,
                        "summary": obj_info.get('summary', '')
                    })
            
            return self.create_json_result(summary)
        
        except Exception as e:
            return self.create_error_result(f"Error reading workspace summary: {str(e)}")
    
    async def _read_environment_info(self) -> ResourceResult:
        """Read environment information.
        
        Returns:
            Environment information as JSON
        """
        try:
            env_info = {
                "r_version": "unknown",
                "working_directory": "unknown",
                "search_path": [],
                "loaded_packages": [],
                "memory_usage": {}
            }
            
            # Get R version
            try:
                env_info["r_version"] = await self.api_wrapper.get_r_version()
            except Exception as e:
                self.logger.warning(f"Failed to get R version: {e}")
            
            # Get working directory
            try:
                result = await self.api_wrapper.execute_r_code("getwd()", capture_plots=False)
                if result.success:
                    env_info["working_directory"] = result.output.strip().strip('"')
            except Exception as e:
                self.logger.warning(f"Failed to get working directory: {e}")
            
            # Get search path
            try:
                result = await self.api_wrapper.execute_r_code("search()", capture_plots=False)
                if result.success:
                    # Parse search path from R output
                    search_output = result.output.strip()
                    if search_output.startswith('['):
                        # Remove R vector formatting
                        search_output = search_output.split('] ', 1)[-1] if '] ' in search_output else search_output
                        env_info["search_path"] = [item.strip().strip('"') for item in search_output.split('"') if item.strip() and item.strip() != '"']
            except Exception as e:
                self.logger.warning(f"Failed to get search path: {e}")
            
            # Get loaded packages
            try:
                result = await self.api_wrapper.execute_r_code(
                    "(.packages())", 
                    capture_plots=False
                )
                if result.success:
                    # Parse loaded packages from R output
                    packages_output = result.output.strip()
                    if packages_output.startswith('['):
                        packages_output = packages_output.split('] ', 1)[-1] if '] ' in packages_output else packages_output
                        env_info["loaded_packages"] = [pkg.strip().strip('"') for pkg in packages_output.split('"') if pkg.strip() and pkg.strip() != '"']
            except Exception as e:
                self.logger.warning(f"Failed to get loaded packages: {e}")
            
            # Get memory usage
            try:
                result = await self.api_wrapper.execute_r_code(
                    "list(used = gc()[2,2], max_used = gc()[2,6])", 
                    capture_plots=False
                )
                if result.success and result.output:
                    # This is a simplified approach - in practice you might want better parsing
                    env_info["memory_usage"] = {"info": result.output.strip()}
            except Exception as e:
                self.logger.warning(f"Failed to get memory usage: {e}")
            
            return self.create_json_result(env_info)
        
        except Exception as e:
            return self.create_error_result(f"Error reading environment info: {str(e)}")
    
    async def _read_workspace_object(self, object_name: str) -> ResourceResult:
        """Read information about a specific workspace object.
        
        Args:
            object_name: Name of the workspace object
            
        Returns:
            Object information as JSON
        """
        try:
            # Get detailed object information
            code = f"""
            if (exists("{object_name}")) {{
                obj <- get("{object_name}")
                list(
                    name = "{object_name}",
                    class = class(obj),
                    type = typeof(obj),
                    mode = mode(obj),
                    length = length(obj),
                    size = object.size(obj),
                    attributes = attributes(obj),
                    summary = capture.output(summary(obj)),
                    structure = capture.output(str(obj, max.level = 2))
                )
            }} else {{
                list(error = "Object not found")
            }}
            """
            
            result = await self.api_wrapper.execute_r_code(code, capture_plots=False)
            
            if not result.success:
                return self.create_error_result(f"Failed to get object information: {result.error}")
            
            # Try to parse the R output as JSON-like structure
            # This is simplified - in practice you might want to use jsonlite in R
            try:
                # For now, return the raw R output as text
                object_info = {
                    "name": object_name,
                    "raw_info": result.output,
                    "warnings": result.warnings
                }
                
                # Try to get basic info with simpler commands
                basic_info_code = f"""
                if (exists("{object_name}")) {{
                    obj <- get("{object_name}")
                    cat("Class:", paste(class(obj), collapse=", "), "\\n")
                    cat("Type:", typeof(obj), "\\n")
                    cat("Length:", length(obj), "\\n")
                    cat("Size:", as.numeric(object.size(obj)), "\\n")
                }} else {{
                    cat("Error: Object not found\\n")
                }}
                """
                
                basic_result = await self.api_wrapper.execute_r_code(basic_info_code, capture_plots=False)
                if basic_result.success:
                    object_info["basic_info"] = basic_result.output
                
                return self.create_json_result(object_info)
                
            except Exception as e:
                self.logger.warning(f"Failed to parse object info: {e}")
                # Return raw output as fallback
                return self.create_text_result(result.output, "text/plain")
        
        except Exception as e:
            return self.create_error_result(f"Error reading workspace object: {str(e)}")