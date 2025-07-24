"""Environment resource handler for RStudio MCP Server."""

import json
from typing import Any, Dict, List, Optional

from ..api_wrapper import RStudioAPIWrapper
from ..environment_manager import EnvironmentManager
from .base import BaseResource, ResourceInfo, ResourceResult


class EnvironmentResource(BaseResource):
    """Resource handler for RStudio environments."""
    
    def __init__(self, api_wrapper: Optional[RStudioAPIWrapper] = None,
                 environment_manager: Optional[EnvironmentManager] = None):
        """Initialize the environment resource handler.
        
        Args:
            api_wrapper: Optional RStudio API wrapper instance
            environment_manager: Optional environment manager instance
        """
        super().__init__()
        self.api_wrapper = api_wrapper
        self.environment_manager = environment_manager
    
    @property
    def scheme(self) -> str:
        """URI scheme handled by this resource."""
        return "rstudio-environment"
    
    @property
    def description(self) -> str:
        """Resource handler description."""
        return "RStudio environment information and status"
    
    async def list_resources(self, uri_prefix: Optional[str] = None) -> List[ResourceInfo]:
        """List available environment resources.
        
        Args:
            uri_prefix: Optional URI prefix to filter resources
            
        Returns:
            List of available environment resources
        """
        resources = []
        
        try:
            # Add general environment resources
            resources.extend([
                ResourceInfo(
                    uri="rstudio-environment://current",
                    name="Current Environment",
                    description="Information about the current R environment",
                    mime_type="application/json",
                    metadata={"special": "current"}
                ),
                ResourceInfo(
                    uri="rstudio-environment://all",
                    name="All Environments",
                    description="List of all available R environments",
                    mime_type="application/json",
                    metadata={"special": "all"}
                ),
                ResourceInfo(
                    uri="rstudio-environment://system",
                    name="System Information",
                    description="R system and session information",
                    mime_type="application/json",
                    metadata={"special": "system"}
                )
            ])
            
            # Add specific environment resources if environment manager is available
            if self.environment_manager:
                try:
                    environments = await self.environment_manager.list_environments()
                    for env in environments:
                        resources.append(ResourceInfo(
                            uri=f"rstudio-environment://{env.name}",
                            name=f"Environment: {env.name}",
                            description=f"R environment {env.name} (R {env.r_version})",
                            mime_type="application/json",
                            metadata={
                                "environment_name": env.name,
                                "r_version": env.r_version,
                                "is_active": env.is_active
                            }
                        ))
                except Exception as e:
                    self.logger.warning(f"Failed to list environments: {e}")
        
        except Exception as e:
            self.logger.error(f"Error listing environment resources: {e}")
        
        return resources
    
    async def read_resource(self, uri: str) -> ResourceResult:
        """Read environment resource content.
        
        Args:
            uri: Resource URI
            
        Returns:
            Resource content and metadata
        """
        try:
            uri_parts = self.parse_uri(uri)
            resource_name = uri_parts["path"].strip("/")
            
            if not resource_name:
                return self.create_error_result("Invalid environment URI: missing resource name")
            
            # Handle special resources
            if resource_name == "current":
                return await self._read_current_environment()
            elif resource_name == "all":
                return await self._read_all_environments()
            elif resource_name == "system":
                return await self._read_system_info()
            else:
                # Handle specific environment
                return await self._read_specific_environment(resource_name)
        
        except Exception as e:
            return self.create_error_result(f"Error reading environment resource: {str(e)}")
    
    async def _read_current_environment(self) -> ResourceResult:
        """Read current environment information.
        
        Returns:
            Current environment information as JSON
        """
        try:
            current_env = {
                "name": "current",
                "r_version": "unknown",
                "working_directory": "unknown",
                "loaded_packages": [],
                "search_path": [],
                "memory_info": {},
                "session_info": {}
            }
            
            if not self.api_wrapper:
                current_env["error"] = "No API wrapper available"
                return self.create_json_result(current_env)
            
            # Get R version
            try:
                current_env["r_version"] = await self.api_wrapper.get_r_version()
            except Exception as e:
                self.logger.warning(f"Failed to get R version: {e}")
            
            # Get working directory
            try:
                result = await self.api_wrapper.execute_r_code("getwd()", capture_plots=False)
                if result.success:
                    current_env["working_directory"] = result.output.strip().strip('"')
            except Exception as e:
                self.logger.warning(f"Failed to get working directory: {e}")
            
            # Get loaded packages
            try:
                result = await self.api_wrapper.execute_r_code("(.packages())", capture_plots=False)
                if result.success:
                    # Simple parsing of R output
                    packages_output = result.output.strip()
                    if packages_output:
                        current_env["loaded_packages"] = self._parse_r_vector_output(packages_output)
            except Exception as e:
                self.logger.warning(f"Failed to get loaded packages: {e}")
            
            # Get search path
            try:
                result = await self.api_wrapper.execute_r_code("search()", capture_plots=False)
                if result.success:
                    search_output = result.output.strip()
                    if search_output:
                        current_env["search_path"] = self._parse_r_vector_output(search_output)
            except Exception as e:
                self.logger.warning(f"Failed to get search path: {e}")
            
            # Get memory info
            try:
                result = await self.api_wrapper.execute_r_code("gc()", capture_plots=False)
                if result.success:
                    current_env["memory_info"] = {"gc_output": result.output.strip()}
            except Exception as e:
                self.logger.warning(f"Failed to get memory info: {e}")
            
            # Get session info
            try:
                result = await self.api_wrapper.execute_r_code("sessionInfo()", capture_plots=False)
                if result.success:
                    current_env["session_info"] = {"session_output": result.output.strip()}
            except Exception as e:
                self.logger.warning(f"Failed to get session info: {e}")
            
            return self.create_json_result(current_env)
        
        except Exception as e:
            return self.create_error_result(f"Error reading current environment: {str(e)}")
    
    async def _read_all_environments(self) -> ResourceResult:
        """Read information about all environments.
        
        Returns:
            All environments information as JSON
        """
        try:
            all_envs = {
                "environments": [],
                "total_count": 0,
                "active_environment": None
            }
            
            if self.environment_manager:
                try:
                    environments = await self.environment_manager.list_environments()
                    all_envs["total_count"] = len(environments)
                    
                    for env in environments:
                        env_info = {
                            "name": env.name,
                            "r_version": env.r_version,
                            "path": env.path,
                            "is_active": env.is_active,
                            "created_at": env.created_at.isoformat() if hasattr(env, 'created_at') else None,
                            "packages": env.packages if hasattr(env, 'packages') else []
                        }
                        
                        all_envs["environments"].append(env_info)
                        
                        if env.is_active:
                            all_envs["active_environment"] = env.name
                
                except Exception as e:
                    all_envs["error"] = f"Failed to get environments: {str(e)}"
            else:
                all_envs["error"] = "No environment manager available"
            
            return self.create_json_result(all_envs)
        
        except Exception as e:
            return self.create_error_result(f"Error reading all environments: {str(e)}")
    
    async def _read_system_info(self) -> ResourceResult:
        """Read system information.
        
        Returns:
            System information as JSON
        """
        try:
            system_info = {
                "r_version": "unknown",
                "platform": "unknown",
                "os": "unknown",
                "locale": "unknown",
                "timezone": "unknown",
                "capabilities": {}
            }
            
            if not self.api_wrapper:
                system_info["error"] = "No API wrapper available"
                return self.create_json_result(system_info)
            
            # Get R version info
            try:
                result = await self.api_wrapper.execute_r_code("R.version.string", capture_plots=False)
                if result.success:
                    system_info["r_version"] = result.output.strip().strip('"')
            except Exception as e:
                self.logger.warning(f"Failed to get R version string: {e}")
            
            # Get platform info
            try:
                result = await self.api_wrapper.execute_r_code("R.version$platform", capture_plots=False)
                if result.success:
                    system_info["platform"] = result.output.strip().strip('"')
            except Exception as e:
                self.logger.warning(f"Failed to get platform info: {e}")
            
            # Get OS info
            try:
                result = await self.api_wrapper.execute_r_code("Sys.info()['sysname']", capture_plots=False)
                if result.success:
                    system_info["os"] = result.output.strip().strip('"')
            except Exception as e:
                self.logger.warning(f"Failed to get OS info: {e}")
            
            # Get locale info
            try:
                result = await self.api_wrapper.execute_r_code("Sys.getlocale()", capture_plots=False)
                if result.success:
                    system_info["locale"] = result.output.strip().strip('"')
            except Exception as e:
                self.logger.warning(f"Failed to get locale info: {e}")
            
            # Get timezone
            try:
                result = await self.api_wrapper.execute_r_code("Sys.timezone()", capture_plots=False)
                if result.success:
                    system_info["timezone"] = result.output.strip().strip('"')
            except Exception as e:
                self.logger.warning(f"Failed to get timezone: {e}")
            
            # Get capabilities
            try:
                result = await self.api_wrapper.execute_r_code("capabilities()", capture_plots=False)
                if result.success:
                    system_info["capabilities"] = {"raw_output": result.output.strip()}
            except Exception as e:
                self.logger.warning(f"Failed to get capabilities: {e}")
            
            return self.create_json_result(system_info)
        
        except Exception as e:
            return self.create_error_result(f"Error reading system info: {str(e)}")
    
    async def _read_specific_environment(self, env_name: str) -> ResourceResult:
        """Read information about a specific environment.
        
        Args:
            env_name: Name of the environment
            
        Returns:
            Environment information as JSON
        """
        try:
            if not self.environment_manager:
                return self.create_error_result("No environment manager available")
            
            # Get environment info from manager
            try:
                env_status = await self.environment_manager.get_environment_status(env_name)
                
                env_info = {
                    "name": env_name,
                    "exists": env_status is not None,
                    "status": "unknown"
                }
                
                if env_status:
                    env_info.update({
                        "status": "active" if env_status.is_active else "inactive",
                        "r_version": env_status.r_version if hasattr(env_status, 'r_version') else "unknown",
                        "path": env_status.path if hasattr(env_status, 'path') else "unknown",
                        "packages": env_status.packages if hasattr(env_status, 'packages') else [],
                        "created_at": env_status.created_at.isoformat() if hasattr(env_status, 'created_at') else None
                    })
                else:
                    env_info["error"] = f"Environment '{env_name}' not found"
                
                return self.create_json_result(env_info)
                
            except Exception as e:
                return self.create_error_result(f"Failed to get environment status: {str(e)}")
        
        except Exception as e:
            return self.create_error_result(f"Error reading specific environment: {str(e)}")
    
    def _parse_r_vector_output(self, output: str) -> List[str]:
        """Parse R vector output into a Python list.
        
        Args:
            output: R vector output string
            
        Returns:
            List of parsed values
        """
        try:
            # Remove R vector numbering like [1] at the beginning
            if output.startswith('['):
                # Find the first space after the closing bracket
                bracket_end = output.find(']')
                if bracket_end != -1:
                    output = output[bracket_end + 1:].strip()
            
            # Split by quotes and filter out empty strings and quotes
            parts = output.split('"')
            values = [part.strip() for part in parts if part.strip() and part.strip() != '"']
            
            # Filter out non-meaningful parts (like spaces between quotes)
            meaningful_values = []
            for value in values:
                if value and not value.isspace() and value != '"':
                    meaningful_values.append(value)
            
            return meaningful_values
        
        except Exception as e:
            self.logger.warning(f"Failed to parse R vector output: {e}")
            return [output]  # Return original as fallback