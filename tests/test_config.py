"""Tests for configuration management."""

import tempfile
from pathlib import Path

import pytest
import yaml

from rstudio_mcp.config import ServerConfig, LoggingConfig, RStudioConfig


class TestLoggingConfig:
    """Test logging configuration."""
    
    def test_default_config(self):
        """Test default logging configuration."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.file is None
        assert config.max_size == "10MB"
        assert config.backup_count == 5
    
    def test_level_validation(self):
        """Test log level validation."""
        # Valid levels
        for level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            config = LoggingConfig(level=level)
            assert config.level == level
        
        # Invalid level
        with pytest.raises(ValueError):
            LoggingConfig(level="INVALID")


class TestRStudioConfig:
    """Test RStudio configuration."""
    
    def test_default_config(self):
        """Test default RStudio configuration."""
        config = RStudioConfig()
        assert config.installation_path is None
        assert config.default_r_version == "4.3.0"
        assert config.r_home is None


class TestServerConfig:
    """Test server configuration."""
    
    def test_default_config(self):
        """Test default server configuration."""
        config = ServerConfig()
        assert config.name == "rstudio-mcp"
        assert config.version == "1.0.0"
        assert config.host == "localhost"
        assert config.port == 8080
        assert not config.debug
        assert not config.auto_start_rstudio
    
    def test_yaml_roundtrip(self):
        """Test YAML serialization and deserialization."""
        original_config = ServerConfig(
            name="test-server",
            debug=True,
            logging=LoggingConfig(level="DEBUG")
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            # Save to YAML
            original_config.to_yaml(temp_path)
            
            # Load from YAML
            loaded_config = ServerConfig.from_yaml(temp_path)
            
            # Compare
            assert loaded_config.name == original_config.name
            assert loaded_config.debug == original_config.debug
            assert loaded_config.logging.level == original_config.logging.level
        finally:
            temp_path.unlink()
    
    def test_load_nonexistent_file(self):
        """Test loading non-existent configuration file."""
        with pytest.raises(FileNotFoundError):
            ServerConfig.from_yaml("/nonexistent/config.yaml")
    
    def test_load_invalid_yaml(self):
        """Test loading invalid YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(yaml.YAMLError):
                ServerConfig.from_yaml(temp_path)
        finally:
            temp_path.unlink()
    
    def test_load_or_create_default(self):
        """Test load or create default configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            
            # Should create default config
            config = ServerConfig.load_or_create_default(config_path)
            assert config.name == "rstudio-mcp"
            assert config_path.exists()
            
            # Should load existing config
            config2 = ServerConfig.load_or_create_default(config_path)
            assert config2.name == config.name
    
    def test_get_environment_path(self):
        """Test environment path generation."""
        config = ServerConfig()
        env_path = config.get_environment_path("test_env")
        assert env_path.name == "test_env"
        assert str(env_path).endswith("environments/test_env")
    
    def test_get_log_file_path(self):
        """Test log file path generation."""
        # No log file configured
        config = ServerConfig()
        assert config.get_log_file_path() is None
        
        # Log file configured
        config.logging.file = "~/test.log"
        log_path = config.get_log_file_path()
        assert log_path is not None
        assert log_path.name == "test.log"