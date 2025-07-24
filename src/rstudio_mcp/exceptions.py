"""Exception classes for RStudio MCP Server."""

from typing import Optional, Any, Dict


class RStudioMCPError(Exception):
    """Base exception class for RStudio MCP Server."""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize exception.
        
        Args:
            message: Error message
            error_code: Optional error code for categorization
            details: Optional additional error details
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary representation.
        
        Returns:
            Dictionary with error information
        """
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details
        }


class ConfigurationError(RStudioMCPError):
    """Configuration-related errors."""
    pass


class EnvironmentError(RStudioMCPError):
    """Environment management errors."""
    pass


class ExecutionError(RStudioMCPError):
    """Code execution errors."""
    pass


class ProjectError(RStudioMCPError):
    """Project management errors."""
    pass


class PackageError(RStudioMCPError):
    """Package management errors."""
    pass


class RStudioConnectionError(RStudioMCPError):
    """RStudio connection errors."""
    pass


class SecurityError(RStudioMCPError):
    """Security-related errors."""
    pass


class ValidationError(RStudioMCPError):
    """Data validation errors."""
    pass


class TimeoutError(RStudioMCPError):
    """Operation timeout errors."""
    pass


class ResourceNotFoundError(RStudioMCPError):
    """Resource not found errors."""
    pass


class PermissionError(RStudioMCPError):
    """Permission-related errors."""
    pass


# Error code constants
class ErrorCodes:
    """Standard error codes for the MCP server."""
    
    # Configuration errors
    CONFIG_INVALID = "CONFIG_INVALID"
    CONFIG_NOT_FOUND = "CONFIG_NOT_FOUND"
    
    # Environment errors
    ENV_NOT_FOUND = "ENV_NOT_FOUND"
    ENV_CREATION_FAILED = "ENV_CREATION_FAILED"
    ENV_DELETION_FAILED = "ENV_DELETION_FAILED"
    ENV_SWITCH_FAILED = "ENV_SWITCH_FAILED"
    
    # Execution errors
    EXEC_TIMEOUT = "EXEC_TIMEOUT"
    EXEC_SYNTAX_ERROR = "EXEC_SYNTAX_ERROR"
    EXEC_RUNTIME_ERROR = "EXEC_RUNTIME_ERROR"
    
    # Project errors
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    PROJECT_CREATION_FAILED = "PROJECT_CREATION_FAILED"
    PROJECT_LOAD_FAILED = "PROJECT_LOAD_FAILED"
    
    # Package errors
    PACKAGE_NOT_FOUND = "PACKAGE_NOT_FOUND"
    PACKAGE_INSTALL_FAILED = "PACKAGE_INSTALL_FAILED"
    PACKAGE_UPDATE_FAILED = "PACKAGE_UPDATE_FAILED"
    
    # Connection errors
    RSTUDIO_NOT_FOUND = "RSTUDIO_NOT_FOUND"
    RSTUDIO_CONNECTION_FAILED = "RSTUDIO_CONNECTION_FAILED"
    R_CONNECTION_FAILED = "R_CONNECTION_FAILED"
    
    # Security errors
    SECURITY_VIOLATION = "SECURITY_VIOLATION"
    BLOCKED_FUNCTION = "BLOCKED_FUNCTION"
    UNAUTHORIZED_PACKAGE = "UNAUTHORIZED_PACKAGE"
    
    # Resource errors
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_ACCESS_DENIED = "RESOURCE_ACCESS_DENIED"
    RESOURCE_CORRUPTED = "RESOURCE_CORRUPTED"


def handle_exception(func):
    """Decorator to handle exceptions and convert them to MCP-compatible format.
    
    Args:
        func: Function to wrap
        
    Returns:
        Wrapped function
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except RStudioMCPError:
            # Re-raise our custom exceptions as-is
            raise
        except FileNotFoundError as e:
            raise ResourceNotFoundError(
                message=f"File not found: {e}",
                error_code=ErrorCodes.RESOURCE_NOT_FOUND
            )
        except PermissionError as e:
            raise PermissionError(
                message=f"Permission denied: {e}",
                error_code=ErrorCodes.RESOURCE_ACCESS_DENIED
            )
        except TimeoutError as e:
            raise TimeoutError(
                message=f"Operation timed out: {e}",
                error_code=ErrorCodes.EXEC_TIMEOUT
            )
        except Exception as e:
            # Convert unexpected exceptions to generic RStudioMCPError
            raise RStudioMCPError(
                message=f"Unexpected error: {e}",
                details={"original_exception": str(type(e).__name__)}
            )
    
    return wrapper


async def handle_async_exception(func):
    """Async version of exception handler decorator.
    
    Args:
        func: Async function to wrap
        
    Returns:
        Wrapped async function
    """
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except RStudioMCPError:
            # Re-raise our custom exceptions as-is
            raise
        except FileNotFoundError as e:
            raise ResourceNotFoundError(
                message=f"File not found: {e}",
                error_code=ErrorCodes.RESOURCE_NOT_FOUND
            )
        except PermissionError as e:
            raise PermissionError(
                message=f"Permission denied: {e}",
                error_code=ErrorCodes.RESOURCE_ACCESS_DENIED
            )
        except TimeoutError as e:
            raise TimeoutError(
                message=f"Operation timed out: {e}",
                error_code=ErrorCodes.EXEC_TIMEOUT
            )
        except Exception as e:
            # Convert unexpected exceptions to generic RStudioMCPError
            raise RStudioMCPError(
                message=f"Unexpected error: {e}",
                details={"original_exception": str(type(e).__name__)}
            )
    
    return wrapper