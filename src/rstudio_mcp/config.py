"""Configuration management for RStudio MCP Server."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field, validator


class LoggingConfig(BaseModel):
    """Logging configuration."""
    
    level: str = Field(default="INFO", description="Log level")
    file: Optional[str] = Field(default=None, description="Log file path")
    max_size: str = Field(default="10MB", description="Maximum log file size")
    backup_count: int = Field(default=5, description="Number of backup log files")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string"
    )
    
    @validator('level')
    def validate_level(cls, v):
        """Validate log level."""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v.upper()


class RStudioConfig(BaseModel):
    """RStudio-specific configuration."""
    
    installation_path: Optional[str] = Field(
        default=None, 
        description="Path to RStudio installation"
    )
    default_r_version: str = Field(
        default="4.3.0", 
        description="Default R version to use"
    )
    r_home: Optional[str] = Field(
        default=None,
        description="R_HOME environment variable override"
    )
    
    @validator('installation_path')
    def validate_installation_path(cls, v):
        """Validate RStudio installation path."""
        if v and not Path(v).exists():
            raise ValueError(f"RStudio installation path does not exist: {v}")
        return v


class EnvironmentConfig(BaseModel):
    """Environment management configuration."""
    
    default_location: str = Field(
        default="~/.rstudio-mcp/environments",
        description="Default location for R environments"
    )
    auto_cleanup: bool = Field(
        default=True,
        description="Automatically cleanup unused environments"
    )
    max_environments: int = Field(
        default=10,
        description="Maximum number of environments to maintain"
    )
    
    @validator('default_location')
    def expand_path(cls, v):
        """Expand user path."""
        return str(Path(v).expanduser().resolve())


class SecurityConfig(BaseModel):
    """Security configuration."""
    
    allowed_packages: List[str] = Field(
        default_factory=lambda: ["base", "utils", "stats", "graphics", "datasets"],
        description="List of allowed R packages"
    )
    blocked_functions: List[str] = Field(
        default_factory=lambda: ["system", "shell", "system2"],
        description="List of blocked R functions"
    )
    execution_timeout: int = Field(
        default=300,
        description="Code execution timeout in seconds"
    )
    max_memory_mb: int = Field(
        default=1024,
        description="Maximum memory usage in MB"
    )


class ServerConfig(BaseModel):
    """Main server configuration."""
    
    name: str = Field(default="rstudio-mcp", description="Server name")
    version: str = Field(default="1.0.0", description="Server version")
    host: str = Field(default="localhost", description="Server host")
    port: int = Field(default=8080, description="Server port")
    
    # Sub-configurations
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    rstudio: RStudioConfig = Field(default_factory=RStudioConfig)
    environments: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    
    # Additional settings
    debug: bool = Field(default=False, description="Enable debug mode")
    auto_start_rstudio: bool = Field(
        default=False,
        description="Automatically start RStudio if not running"
    )
    
    @classmethod
    def from_yaml(cls, config_path: Union[str, Path]) -> "ServerConfig":
        """Load configuration from YAML file.
        
        Args:
            config_path: Path to YAML configuration file
            
        Returns:
            ServerConfig instance
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML parsing fails
            ValueError: If configuration validation fails
        """
        config_path = Path(config_path)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Failed to parse YAML configuration: {e}")
        
        if config_data is None:
            config_data = {}
        
        return cls(**config_data)
    
    def to_yaml(self, config_path: Union[str, Path]) -> None:
        """Save configuration to YAML file.
        
        Args:
            config_path: Path to save YAML configuration file
        """
        config_path = Path(config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(
                self.dict(),
                f,
                default_flow_style=False,
                allow_unicode=True,
                indent=2
            )
    
    @classmethod
    def get_default_config_path(cls) -> Path:
        """Get default configuration file path."""
        return Path.home() / ".rstudio-mcp" / "config.yaml"
    
    @classmethod
    def load_or_create_default(cls, config_path: Optional[Union[str, Path]] = None) -> "ServerConfig":
        """Load configuration or create default if not exists.
        
        Args:
            config_path: Optional path to configuration file
            
        Returns:
            ServerConfig instance
        """
        if config_path is None:
            config_path = cls.get_default_config_path()
        else:
            config_path = Path(config_path)
        
        if config_path.exists():
            return cls.from_yaml(config_path)
        else:
            # Create default configuration
            config = cls()
            config.to_yaml(config_path)
            return config
    
    def get_environment_path(self, env_name: str) -> Path:
        """Get path for a specific environment.
        
        Args:
            env_name: Name of the environment
            
        Returns:
            Path to the environment directory
        """
        return Path(self.environments.default_location) / env_name
    
    def get_log_file_path(self) -> Optional[Path]:
        """Get log file path if configured.
        
        Returns:
            Path to log file or None if not configured
        """
        if self.logging.file:
            log_path = Path(self.logging.file).expanduser()
            log_path.parent.mkdir(parents=True, exist_ok=True)
            return log_path
        return None