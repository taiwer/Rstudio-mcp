"""Environment management for RStudio MCP Server."""

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator

from .api_wrapper import RStudioAPIWrapper
from .exceptions import EnvironmentError


class Environment(BaseModel):
    """R environment data model."""
    
    name: str = Field(..., description="Environment name")
    r_version: str = Field(..., description="R version")
    path: str = Field(..., description="Environment path")
    packages: List[str] = Field(default_factory=list, description="Installed packages")
    is_active: bool = Field(default=False, description="Whether environment is active")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    description: Optional[str] = Field(None, description="Environment description")
    
    @validator('name')
    def validate_name(cls, v):
        """Validate environment name."""
        if not v or not v.strip():
            raise ValueError("Environment name cannot be empty")
        
        # Check for invalid characters
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        if any(char in v for char in invalid_chars):
            raise ValueError(f"Environment name contains invalid characters: {invalid_chars}")
        
        return v.strip()
    
    @validator('path')
    def validate_path(cls, v):
        """Validate and expand environment path."""
        return str(Path(v).expanduser().resolve())
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class EnvironmentStatus(BaseModel):
    """Environment status information."""
    
    name: str
    is_active: bool
    r_version: str
    package_count: int
    memory_usage: Optional[int] = None  # in MB
    last_used: Optional[datetime] = None
    health_status: str = Field(default="unknown")  # healthy, warning, error, unknown
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class EnvironmentConfig(BaseModel):
    """Environment configuration for creation."""
    
    name: str
    r_version: Optional[str] = None
    description: Optional[str] = None
    packages: List[str] = Field(default_factory=list)
    copy_from: Optional[str] = None  # Copy from existing environment
    
    @validator('name')
    def validate_name(cls, v):
        """Validate environment name."""
        if not v or not v.strip():
            raise ValueError("Environment name cannot be empty")
        return v.strip()


class EnvironmentManager:
    """Manager for R environments."""
    
    def __init__(self, api_wrapper: RStudioAPIWrapper, base_path: str):
        """Initialize environment manager.
        
        Args:
            api_wrapper: RStudio API wrapper instance
            base_path: Base path for storing environments
        """
        self.api = api_wrapper
        self.base_path = Path(base_path).expanduser().resolve()
        self.logger = logging.getLogger(__name__)
        
        # Ensure base path exists
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Environment registry file
        self.registry_file = self.base_path / "environments.json"
        
        # Load existing environments
        self._environments: Dict[str, Environment] = {}
        self._load_registry()
    
    def _load_registry(self) -> None:
        """Load environment registry from file."""
        if self.registry_file.exists():
            try:
                with open(self.registry_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for env_data in data.get('environments', []):
                    env = Environment(**env_data)
                    self._environments[env.name] = env
                    
                self.logger.info(f"Loaded {len(self._environments)} environments from registry")
                
            except Exception as e:
                self.logger.error(f"Failed to load environment registry: {e}")
                self._environments = {}
        else:
            self.logger.info("No existing environment registry found")
    
    def _save_registry(self) -> None:
        """Save environment registry to file."""
        try:
            data = {
                'version': '1.0',
                'updated_at': datetime.now().isoformat(),
                'environments': [json.loads(env.json()) for env in self._environments.values()]
            }
            
            # Write to temporary file first, then rename for atomicity
            temp_file = self.registry_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            temp_file.rename(self.registry_file)
            self.logger.debug("Environment registry saved")
            
        except Exception as e:
            self.logger.error(f"Failed to save environment registry: {e}")
            raise EnvironmentError(f"Failed to save environment registry: {e}")
    
    async def create_environment(self, config: EnvironmentConfig) -> Environment:
        """Create a new R environment.
        
        Args:
            config: Environment configuration
            
        Returns:
            Created environment
            
        Raises:
            EnvironmentError: If environment creation fails
        """
        if config.name in self._environments:
            raise EnvironmentError(f"Environment '{config.name}' already exists")
        
        # Determine R version
        r_version = config.r_version
        if not r_version:
            r_version = await self.api.get_r_version()
        
        # Create environment directory
        env_path = self.base_path / config.name
        if env_path.exists():
            raise EnvironmentError(f"Environment directory already exists: {env_path}")
        
        try:
            env_path.mkdir(parents=True)
            self.logger.info(f"Created environment directory: {env_path}")
            
            # Create environment metadata
            environment = Environment(
                name=config.name,
                r_version=r_version,
                path=str(env_path),
                description=config.description,
                created_at=datetime.now()
            )
            
            # Initialize R environment
            await self._initialize_r_environment(environment, config)
            
            # Install requested packages
            if config.packages:
                await self._install_packages(environment, config.packages)
            
            # Copy from existing environment if requested
            if config.copy_from:
                await self._copy_environment(config.copy_from, environment)
            
            # Register environment
            self._environments[config.name] = environment
            self._save_registry()
            
            self.logger.info(f"Successfully created environment: {config.name}")
            return environment
            
        except Exception as e:
            # Cleanup on failure
            if env_path.exists():
                shutil.rmtree(env_path, ignore_errors=True)
            
            # Remove from in-memory registry if it was added
            if config.name in self._environments:
                del self._environments[config.name]
            
            self.logger.error(f"Failed to create environment '{config.name}': {e}")
            raise EnvironmentError(f"Failed to create environment: {e}")
    
    async def _initialize_r_environment(self, environment: Environment, config: EnvironmentConfig) -> None:
        """Initialize R environment with basic setup.
        
        Args:
            environment: Environment to initialize
            config: Environment configuration
        """
        # Create R library directory
        lib_path = Path(environment.path) / "library"
        lib_path.mkdir(exist_ok=True)
        
        # Create environment-specific R profile
        r_profile = Path(environment.path) / ".Rprofile"
        profile_content = f'''
# RStudio MCP Environment: {environment.name}
# Created: {environment.created_at.isoformat()}
# R Version: {environment.r_version}

# Set library path
.libPaths(c("{lib_path}", .libPaths()))

# Environment metadata
.rstudio_mcp_env <- list(
    name = "{environment.name}",
    path = "{environment.path}",
    created_at = "{environment.created_at.isoformat()}",
    r_version = "{environment.r_version}"
)

# Welcome message
cat("RStudio MCP Environment:", "{environment.name}\\n")
cat("R Version:", R.version.string, "\\n")
cat("Library Path:", "{lib_path}", "\\n")
'''
        
        with open(r_profile, 'w', encoding='utf-8') as f:
            f.write(profile_content)
        
        self.logger.debug(f"Created R profile for environment: {environment.name}")
    
    async def _install_packages(self, environment: Environment, packages: List[str]) -> None:
        """Install packages in the environment.
        
        Args:
            environment: Target environment
            packages: List of package names to install
        """
        lib_path = Path(environment.path) / "library"
        
        for package in packages:
            try:
                # Install package to environment-specific library
                install_code = f'''
                install.packages("{package}", lib = "{lib_path}", 
                               repos = "https://cran.r-project.org/")
                '''
                
                result = await self.api.execute_r_code(install_code, capture_plots=False)
                
                if result.success:
                    environment.packages.append(package)
                    self.logger.info(f"Installed package '{package}' in environment '{environment.name}'")
                else:
                    self.logger.warning(f"Failed to install package '{package}': {result.error}")
                    
            except Exception as e:
                self.logger.error(f"Error installing package '{package}': {e}")
    
    async def _copy_environment(self, source_name: str, target_env: Environment) -> None:
        """Copy packages and settings from source environment.
        
        Args:
            source_name: Name of source environment
            target_env: Target environment
        """
        if source_name not in self._environments:
            raise EnvironmentError(f"Source environment '{source_name}' not found")
        
        source_env = self._environments[source_name]
        
        # Copy packages
        if source_env.packages:
            await self._install_packages(target_env, source_env.packages)
        
        self.logger.info(f"Copied environment '{source_name}' to '{target_env.name}'")
    
    async def list_environments(self) -> List[Environment]:
        """List all available environments.
        
        Returns:
            List of environments
        """
        # Update environment status
        for env in self._environments.values():
            await self._update_environment_status(env)
        
        return list(self._environments.values())
    
    async def get_environment(self, name: str) -> Optional[Environment]:
        """Get environment by name.
        
        Args:
            name: Environment name
            
        Returns:
            Environment or None if not found
        """
        env = self._environments.get(name)
        if env:
            await self._update_environment_status(env)
        return env
    
    async def delete_environment(self, name: str, force: bool = False) -> bool:
        """Delete an environment.
        
        Args:
            name: Environment name
            force: Force deletion even if active
            
        Returns:
            True if deleted successfully
            
        Raises:
            EnvironmentError: If environment cannot be deleted
        """
        if name not in self._environments:
            raise EnvironmentError(f"Environment '{name}' not found")
        
        environment = self._environments[name]
        
        # Check if environment is active
        if environment.is_active and not force:
            raise EnvironmentError(f"Cannot delete active environment '{name}'. Use force=True to override.")
        
        try:
            # Remove environment directory
            env_path = Path(environment.path)
            if env_path.exists():
                shutil.rmtree(env_path)
                self.logger.info(f"Removed environment directory: {env_path}")
            
            # Remove from registry
            del self._environments[name]
            self._save_registry()
            
            self.logger.info(f"Successfully deleted environment: {name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete environment '{name}': {e}")
            raise EnvironmentError(f"Failed to delete environment: {e}")
    
    async def switch_environment(self, name: str) -> bool:
        """Switch to a different environment.
        
        Args:
            name: Environment name to switch to
            
        Returns:
            True if switched successfully
            
        Raises:
            EnvironmentError: If environment switch fails
        """
        if name not in self._environments:
            raise EnvironmentError(f"Environment '{name}' not found")
        
        target_env = self._environments[name]
        
        try:
            # Deactivate current environment
            current_active = None
            for env in self._environments.values():
                if env.is_active:
                    current_active = env
                    env.is_active = False
            
            # Set R library path to target environment
            lib_path = Path(target_env.path) / "library"
            switch_code = f'''
            .libPaths(c("{lib_path}", .libPaths()))
            
            # Load environment profile if exists
            profile_path <- "{Path(target_env.path) / '.Rprofile'}"
            if (file.exists(profile_path)) {{
                source(profile_path)
            }}
            '''
            
            result = await self.api.execute_r_code(switch_code, capture_plots=False)
            
            if result.success:
                target_env.is_active = True
                self._save_registry()
                
                self.logger.info(f"Switched to environment: {name}")
                return True
            else:
                # Restore previous active environment on failure
                if current_active:
                    current_active.is_active = True
                
                raise EnvironmentError(f"Failed to switch environment: {result.error}")
                
        except Exception as e:
            self.logger.error(f"Failed to switch to environment '{name}': {e}")
            raise EnvironmentError(f"Failed to switch environment: {e}")
    
    async def get_environment_status(self, name: str) -> Optional[EnvironmentStatus]:
        """Get detailed status of an environment.
        
        Args:
            name: Environment name
            
        Returns:
            Environment status or None if not found
        """
        if name not in self._environments:
            return None
        
        environment = self._environments[name]
        await self._update_environment_status(environment)
        
        # Get package count
        lib_path = Path(environment.path) / "library"
        package_count = len(list(lib_path.glob("*"))) if lib_path.exists() else 0
        
        # Check health status
        health_status = "healthy"
        if not Path(environment.path).exists():
            health_status = "error"
        elif package_count == 0:
            health_status = "warning"
        
        return EnvironmentStatus(
            name=environment.name,
            is_active=environment.is_active,
            r_version=environment.r_version,
            package_count=package_count,
            health_status=health_status,
            last_used=environment.created_at  # TODO: Track actual last used time
        )
    
    async def _update_environment_status(self, environment: Environment) -> None:
        """Update environment status information.
        
        Args:
            environment: Environment to update
        """
        # Check if environment directory still exists
        env_path = Path(environment.path)
        if not env_path.exists():
            self.logger.warning(f"Environment directory missing: {environment.name}")
            return
        
        # Update package list
        lib_path = env_path / "library"
        if lib_path.exists():
            try:
                # Get installed packages in this environment
                packages = [p.name for p in lib_path.iterdir() if p.is_dir()]
                environment.packages = packages
            except Exception as e:
                self.logger.warning(f"Failed to update package list for '{environment.name}': {e}")
    
    async def validate_environment(self, name: str) -> Dict[str, Any]:
        """Validate environment integrity.
        
        Args:
            name: Environment name
            
        Returns:
            Validation results
        """
        if name not in self._environments:
            return {"valid": False, "error": f"Environment '{name}' not found"}
        
        environment = self._environments[name]
        results = {
            "valid": True,
            "name": name,
            "checks": {}
        }
        
        # Check directory exists
        env_path = Path(environment.path)
        results["checks"]["directory_exists"] = env_path.exists()
        
        # Check R profile exists
        r_profile = env_path / ".Rprofile"
        results["checks"]["r_profile_exists"] = r_profile.exists()
        
        # Check library directory
        lib_path = env_path / "library"
        results["checks"]["library_directory_exists"] = lib_path.exists()
        
        # Check package integrity
        if lib_path.exists():
            try:
                package_dirs = [p for p in lib_path.iterdir() if p.is_dir()]
                results["checks"]["package_count"] = len(package_dirs)
                results["checks"]["packages_accessible"] = True
            except Exception:
                results["checks"]["packages_accessible"] = False
        
        # Overall validity
        results["valid"] = all([
            results["checks"]["directory_exists"],
            results["checks"]["r_profile_exists"],
            results["checks"]["library_directory_exists"]
        ])
        
        return results
    
    def cleanup(self) -> None:
        """Clean up resources."""
        try:
            # Save final state
            self._save_registry()
            self.logger.info("Environment manager cleaned up")
        except Exception as e:
            self.logger.warning(f"Error during environment manager cleanup: {e}")