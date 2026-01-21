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
            parser.parse_args(["--help"])

    def test_parser_arguments(self):
        """Test parser handles arguments correctly."""
        parser = create_parser()

        # Test default arguments
        args = parser.parse_args([])
        assert args.config is None
        assert not args.debug
        assert not args.init_config
        assert args.mode == "stdio"
        assert args.host == "localhost"
        assert args.port == 3000

        # Test with arguments
        args = parser.parse_args(["--config", "test.yaml", "--debug"])
        assert args.config == "test.yaml"
        assert args.debug

        # Test init-config
        args = parser.parse_args(["--init-config"])
        assert args.init_config

    def test_parser_mode_argument(self):
        """Test mode argument parsing."""
        parser = create_parser()

        # Test stdio mode (default)
        args = parser.parse_args([])
        assert args.mode == "stdio"

        # Test explicit stdio mode
        args = parser.parse_args(["--mode", "stdio"])
        assert args.mode == "stdio"

        # Test SSE mode
        args = parser.parse_args(["--mode", "sse"])
        assert args.mode == "sse"

        # Test short form
        args = parser.parse_args(["-m", "sse"])
        assert args.mode == "sse"

    def test_parser_host_and_port_arguments(self):
        """Test host and port argument parsing."""
        parser = create_parser()

        # Test default values
        args = parser.parse_args([])
        assert args.host == "localhost"
        assert args.port == 3000

        # Test custom host
        args = parser.parse_args(["--host", "0.0.0.0"])
        assert args.host == "0.0.0.0"

        # Test custom port
        args = parser.parse_args(["--port", "8080"])
        assert args.port == 8080

        # Test short form for port
        args = parser.parse_args(["-p", "9000"])
        assert args.port == 9000

        # Test combined with mode
        args = parser.parse_args(
            ["--mode", "sse", "--host", "127.0.0.1", "--port", "5000"]
        )
        assert args.mode == "sse"
        assert args.host == "127.0.0.1"
        assert args.port == 5000

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
            with patch("builtins.input", return_value="n"):
                init_config(str(config_path))

            # File should remain unchanged
            loaded_config = ServerConfig.from_yaml(config_path)
            assert loaded_config.name == "initial"
