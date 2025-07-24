"""RStudio MCP Server - A Model Context Protocol server for RStudio integration."""

__version__ = "1.0.0"
__author__ = "RStudio MCP Team"
__description__ = "MCP server providing AI assistants with deep RStudio integration capabilities"

from .server import RStudioMCPServer
from .config import ServerConfig

__all__ = ["RStudioMCPServer", "ServerConfig"]