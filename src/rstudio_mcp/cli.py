"""Command-line interface for RStudio MCP Server."""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional

from .config import ServerConfig
from .server import RStudioMCPServer
from .logging_config import get_logger


def create_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser.
    
    Returns:
        Configured argument parser
    """
    parser = argparse.ArgumentParser(
        prog="rstudio-mcp",
        description="RStudio MCP Server - AI assistant integration for RStudio",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  rstudio-mcp                           # Run with default config
  rstudio-mcp --config custom.yaml     # Run with custom config
  rstudio-mcp --debug                  # Run in debug mode
  rstudio-mcp --init-config            # Create default config file
        """
    )
    
    parser.add_argument(
        "--config", "-c",
        type=str,
        help="Path to configuration file (default: ~/.rstudio-mcp/config.yaml)"
    )
    
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug mode"
    )
    
    parser.add_argument(
        "--init-config",
        action="store_true",
        help="Create default configuration file and exit"
    )
    
    parser.add_argument(
        "--version", "-v",
        action="version",
        version="%(prog)s 1.0.0"
    )
    
    return parser


def init_config(config_path: Optional[str] = None) -> None:
    """Initialize default configuration file.
    
    Args:
        config_path: Optional path for config file
    """
    if config_path:
        config_file = Path(config_path)
    else:
        config_file = ServerConfig.get_default_config_path()
    
    if config_file.exists():
        print(f"Configuration file already exists: {config_file}")
        response = input("Overwrite? (y/N): ").strip().lower()
        if response not in ('y', 'yes'):
            print("Configuration initialization cancelled.")
            return
    
    # Create default configuration
    config = ServerConfig()
    config.to_yaml(config_file)
    
    print(f"Default configuration created: {config_file}")
    print("\nYou can now edit the configuration file and run:")
    print(f"  rstudio-mcp --config {config_file}")


async def run_server(config: ServerConfig) -> None:
    """Run the MCP server.
    
    Args:
        config: Server configuration
    """
    logger = get_logger("cli")
    server = None
    
    try:
        server = RStudioMCPServer(config)
        logger.info("Starting RStudio MCP Server...")
        
        # Run server with STDIO transport
        await server.run_stdio()
        
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise
    finally:
        if server:
            await server.shutdown()


def main() -> None:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Handle init-config command
    if args.init_config:
        init_config(args.config)
        return
    
    try:
        # Load configuration
        if args.config:
            config = ServerConfig.from_yaml(args.config)
        else:
            config = ServerConfig.load_or_create_default()
        
        # Override debug setting if specified
        if args.debug:
            config.debug = True
            config.logging.level = "DEBUG"
        
        # Run the server
        asyncio.run(run_server(config))
        
    except FileNotFoundError as e:
        print(f"Error: Configuration file not found: {e}", file=sys.stderr)
        print("Use --init-config to create a default configuration file.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()