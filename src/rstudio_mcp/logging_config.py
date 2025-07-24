"""Logging configuration for RStudio MCP Server."""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional

from .config import LoggingConfig


def setup_logging(config: LoggingConfig) -> logging.Logger:
    """Set up logging configuration.
    
    Args:
        config: Logging configuration object
        
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("rstudio_mcp")
    logger.setLevel(getattr(logging, config.level))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(config.format)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, config.level))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if configured)
    if config.file:
        log_path = Path(config.file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Parse max_size (e.g., "10MB" -> 10 * 1024 * 1024)
        max_bytes = _parse_size(config.max_size)
        
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_path,
            maxBytes=max_bytes,
            backupCount=config.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, config.level))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger


def _parse_size(size_str: str) -> int:
    """Parse size string to bytes.
    
    Args:
        size_str: Size string like "10MB", "1GB", etc.
        
    Returns:
        Size in bytes
        
    Raises:
        ValueError: If size string format is invalid
    """
    size_str = size_str.upper().strip()
    
    # Extract number and unit
    if size_str.endswith('KB'):
        return int(size_str[:-2]) * 1024
    elif size_str.endswith('MB'):
        return int(size_str[:-2]) * 1024 * 1024
    elif size_str.endswith('GB'):
        return int(size_str[:-2]) * 1024 * 1024 * 1024
    elif size_str.endswith('B'):
        return int(size_str[:-1])
    elif size_str.isdigit():
        return int(size_str)
    else:
        raise ValueError(f"Invalid size format: {size_str}")


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger instance.
    
    Args:
        name: Logger name (defaults to rstudio_mcp)
        
    Returns:
        Logger instance
    """
    if name is None:
        name = "rstudio_mcp"
    elif not name.startswith("rstudio_mcp"):
        name = f"rstudio_mcp.{name}"
    
    return logging.getLogger(name)