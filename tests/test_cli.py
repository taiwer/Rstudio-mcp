"""Tests for CLI functionality."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from rstudio_mcp.cli import create_parser, init_config
from rstudio_mcp.config import ServerConfig


class TestCLI:
    """Test CLI functionality."""
    
    def test_create_parser(self):
        """Test argument parser creation."""
        parser = create_parser()
        
        # Test help doesn't raise
        with pytest.raises(SystemExit):
            parser.parse_args(['--help'])
    
    def test_parser_arguments(self):
        """Test parser handles arguments correctly."""
        parser = create_parser()
        
        # Test default arguments
        args = parser.parse_args([])
        assert args.config is None
        assert not args.debug
        assert not args.init_config
        
        # Test with arguments
        args = parser.parse_args(['--config', 'test.yaml', '--debug'])
        assert args.config == 'test.yaml'
        assert args.debug
        
        # Test init-config
        args = parser.parse_args(['--init-config'])
        assert args.init_config
    
    def test_init_config_new_file(self):
        """Test creating new config file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.yaml"
            
            # Should create new file
            init_config(str(config_path))
            assert config_path.exists()
            
            # Should be able to load the created config
            config = ServerConfig.from_yaml(config_path)
            assert config.name == "rstudio-mcp"
    
    def test_init_config_existing_file(self):
        """Test handling existing config file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.yaml"
            
            # Create initial file
            config = ServerConfig(name="initial")
            config.to_yaml(config_path)
            
            # Mock user input to decline overwrite
            with patch('builtins.input', return_value='n'):
                init_config(str(config_path))
            
            # File should remain unchanged
            loaded_config = ServerConfig.from_yaml(config_path)
            assert loaded_config.name == "initial"