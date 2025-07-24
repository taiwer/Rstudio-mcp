"""RStudio API wrapper for integrating with R and RStudio functionality."""

import asyncio
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import rpy2.robjects as robjects
from rpy2.rinterface_lib.embedded import RRuntimeError
from rpy2.robjects import pandas2ri
from rpy2.robjects.packages import importr

from .exceptions import (
    ExecutionError,
    EnvironmentError,
    PackageError,
    ProjectError,
    RStudioMCPError,
)
from .monitoring.performance_monitor import PerformanceMonitor, performance_monitor
from .monitoring.cache_manager import CacheManager, cached
from .monitoring.error_recovery import ErrorRecoveryManager, error_recovery


class ExecutionResult:
    """Result of R code execution."""
    
    def __init__(
        self,
        success: bool,
        output: str = "",
        error: Optional[str] = None,
        plots: Optional[List[str]] = None,
        execution_time: float = 0.0,
        warnings: Optional[List[str]] = None,
    ):
        self.success = success
        self.output = output
        self.error = error
        self.plots = plots or []
        self.execution_time = execution_time
        self.warnings = warnings or []
    
    def __repr__(self) -> str:
        return (
            f"ExecutionResult(success={self.success}, "
            f"output_length={len(self.output)}, "
            f"error={self.error is not None}, "
            f"plots={len(self.plots)}, "
            f"execution_time={self.execution_time:.3f}s)"
        )


class RStudioAPIWrapper:
    """Wrapper for RStudio API integration using rpy2."""
    
    def __init__(self, r_home: Optional[str] = None, timeout: int = 300):
        """Initialize the RStudio API wrapper.
        
        Args:
            r_home: Optional R_HOME path override
            timeout: Default timeout for R operations in seconds
        """
        self.logger = logging.getLogger(__name__)
        self.timeout = timeout
        self._r_initialized = False
        self._rstudioapi = None
        self._base_r = None
        self._utils = None
        
        # Initialize performance monitoring components
        self._performance_monitor = PerformanceMonitor(max_metrics=5000)
        self._cache_manager = CacheManager()
        self._error_recovery_manager = ErrorRecoveryManager()
        
        # Set up caches for common operations
        self._cache_manager.create_cache("package_info", max_size=100, max_memory_mb=10)
        self._cache_manager.create_cache("workspace_objects", max_size=50, max_memory_mb=20)
        self._cache_manager.create_cache("r_version", max_size=1, max_memory_mb=1)
        
        # Set R_HOME if provided
        if r_home:
            os.environ['R_HOME'] = r_home
        
        self._initialize_r()
    
    def _initialize_r(self) -> None:
        """Initialize R interface and load required packages."""
        try:
            # Initialize pandas2ri for better data conversion
            pandas2ri.activate()
            
            # Get base R interface
            self._base_r = robjects.r
            
            # Load essential R packages
            self._utils = importr('utils')
            
            # Try to load rstudioapi if available
            try:
                self._rstudioapi = importr('rstudioapi')
                self.logger.info("RStudio API package loaded successfully")
            except Exception as e:
                self.logger.warning(f"RStudio API package not available: {e}")
                self._rstudioapi = None
            
            self._r_initialized = True
            self.logger.info("R interface initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize R interface: {e}")
            raise EnvironmentError(f"R initialization failed: {e}")
    
    def _ensure_r_initialized(self) -> None:
        """Ensure R interface is initialized."""
        if not self._r_initialized:
            raise EnvironmentError("R interface not initialized")
    
    @performance_monitor("r_code_execution")
    @error_recovery()
    async def execute_r_code(
        self,
        code: str,
        capture_output: bool = True,
        capture_plots: bool = True,
        timeout: Optional[int] = None,
    ) -> ExecutionResult:
        """Execute R code and return results.
        
        Args:
            code: R code to execute
            capture_output: Whether to capture output
            capture_plots: Whether to capture generated plots
            timeout: Execution timeout in seconds
            
        Returns:
            ExecutionResult with execution details
            
        Raises:
            ExecutionError: If code execution fails
        """
        self._ensure_r_initialized()
        
        if timeout is None:
            timeout = self.timeout
        
        start_time = time.time()
        output = ""
        error = None
        plots = []
        warnings = []
        
        try:
            # Create temporary directory for plots if needed
            plot_dir = None
            if capture_plots:
                plot_dir = tempfile.mkdtemp(prefix="rstudio_mcp_plots_")
                # Set up plot capture
                plot_setup_code = f"""
                options(device = function(...) {{
                    png(filename = file.path("{plot_dir}", paste0("plot_", 
                        format(Sys.time(), "%Y%m%d_%H%M%S_"), 
                        sprintf("%03d", sample(1:999, 1)), ".png")), 
                        width = 800, height = 600, ...)
                }})
                """
                self._base_r(plot_setup_code)
            
            # Execute the code with timeout
            result = await asyncio.wait_for(
                self._execute_r_code_sync(code, capture_output),
                timeout=timeout
            )
            
            output = result.get('output', '')
            warnings = result.get('warnings', [])
            
            # Capture plots if enabled
            if capture_plots and plot_dir:
                plots = self._collect_plots(plot_dir)
            
            execution_time = time.time() - start_time
            
            return ExecutionResult(
                success=True,
                output=output,
                plots=plots,
                execution_time=execution_time,
                warnings=warnings,
            )
            
        except asyncio.TimeoutError:
            error = f"Code execution timed out after {timeout} seconds"
            self.logger.error(error)
            
        except RRuntimeError as e:
            error = f"R runtime error: {str(e)}"
            self.logger.error(error)
            
        except Exception as e:
            error = f"Unexpected error during code execution: {str(e)}"
            self.logger.error(error)
        
        execution_time = time.time() - start_time
        
        return ExecutionResult(
            success=False,
            output=output,
            error=error,
            plots=plots,
            execution_time=execution_time,
            warnings=warnings,
        )
    
    async def _execute_r_code_sync(
        self, code: str, capture_output: bool = True
    ) -> Dict[str, Any]:
        """Synchronous R code execution wrapper for async context.
        
        Args:
            code: R code to execute
            capture_output: Whether to capture output
            
        Returns:
            Dictionary with execution results
        """
        # Execute directly in the main thread to avoid context variable issues
        result = {'output': '', 'warnings': []}
        
        if capture_output:
            # Use capture.output() to capture R output
            try:
                # Wrap the code in capture.output to get the output
                wrapped_code = f'capture.output({code})'
                r_result = self._base_r(wrapped_code)
                
                # Convert R result to Python string
                if hasattr(r_result, '__iter__'):
                    result['output'] = '\n'.join(str(item) for item in r_result)
                else:
                    result['output'] = str(r_result)
                    
            except Exception:
                # Fallback to direct execution if capture.output fails
                self._base_r(code)
        else:
            # Execute without capturing output
            self._base_r(code)
        
        return result
    
    def _collect_plots(self, plot_dir: str) -> List[str]:
        """Collect generated plot files.
        
        Args:
            plot_dir: Directory containing plot files
            
        Returns:
            List of plot file paths
        """
        plots = []
        try:
            plot_path = Path(plot_dir)
            if plot_path.exists():
                for plot_file in plot_path.glob("*.png"):
                    plots.append(str(plot_file))
                    self.logger.debug(f"Captured plot: {plot_file}")
        except Exception as e:
            self.logger.warning(f"Failed to collect plots: {e}")
        
        return plots
    
    async def check_rstudio_available(self) -> bool:
        """Check if RStudio API is available.
        
        Returns:
            True if RStudio API is available, False otherwise
        """
        return self._rstudioapi is not None
    
    async def get_active_project(self) -> Optional[str]:
        """Get the currently active RStudio project path.
        
        Returns:
            Path to active project or None if no project is active
        """
        if not self._rstudioapi:
            return None
        
        try:
            result = await self._execute_r_code_sync(
                "rstudioapi::getActiveProject()", capture_output=True
            )
            project_path = result.get('output', '').strip()
            
            # Handle R NULL result
            if project_path and project_path != 'NULL':
                return project_path.strip('"')
            
        except Exception as e:
            self.logger.warning(f"Failed to get active project: {e}")
        
        return None
    
    async def get_r_version(self) -> str:
        """Get the current R version.
        
        Returns:
            R version string
        """
        try:
            result = await self._execute_r_code_sync(
                "paste(R.version$major, R.version$minor, sep='.')",
                capture_output=True
            )
            return result.get('output', '').strip().strip('"')
        except Exception as e:
            self.logger.error(f"Failed to get R version: {e}")
            return "unknown"
    
    async def list_installed_packages(self) -> List[Dict[str, str]]:
        """List installed R packages.
        
        Returns:
            List of package information dictionaries
        """
        try:
            code = """
            installed_pkgs <- installed.packages()
            pkg_info <- data.frame(
                name = installed_pkgs[, "Package"],
                version = installed_pkgs[, "Version"],
                description = installed_pkgs[, "Title"],
                stringsAsFactors = FALSE
            )
            jsonlite::toJSON(pkg_info, pretty = TRUE)
            """
            
            result = await self.execute_r_code(code, capture_plots=False)
            if result.success and result.output:
                import json
                return json.loads(result.output)
        except Exception as e:
            self.logger.error(f"Failed to list installed packages: {e}")
        
        return []
    
    async def install_package(
        self,
        package_name: str,
        repository: Optional[str] = None,
        version: Optional[str] = None,
    ) -> bool:
        """Install an R package.
        
        Args:
            package_name: Name of the package to install
            repository: Optional repository URL
            version: Optional specific version to install
            
        Returns:
            True if installation succeeded, False otherwise
        """
        try:
            # Build install command
            if version:
                # Install specific version using devtools or remotes
                code = f"""
                if (!require(remotes, quietly = TRUE)) {{
                    install.packages("remotes")
                }}
                remotes::install_version("{package_name}", version = "{version}")
                """
            elif repository:
                code = f'install.packages("{package_name}", repos = "{repository}")'
            else:
                code = f'install.packages("{package_name}")'
            
            result = await self.execute_r_code(code, capture_plots=False)
            return result.success
            
        except Exception as e:
            self.logger.error(f"Failed to install package {package_name}: {e}")
            return False
    
    async def get_workspace_objects(self) -> List[Dict[str, Any]]:
        """Get information about objects in the current workspace.
        
        Returns:
            List of workspace object information
        """
        try:
            code = """
            obj_names <- ls(envir = .GlobalEnv)
            obj_info <- lapply(obj_names, function(name) {
                obj <- get(name, envir = .GlobalEnv)
                list(
                    name = name,
                    class = class(obj)[1],
                    type = typeof(obj),
                    size = object.size(obj),
                    summary = capture.output(str(obj, max.level = 1))[1]
                )
            })
            names(obj_info) <- obj_names
            jsonlite::toJSON(obj_info, pretty = TRUE)
            """
            
            result = await self.execute_r_code(code, capture_plots=False)
            if result.success and result.output:
                import json
                return json.loads(result.output)
        except Exception as e:
            self.logger.error(f"Failed to get workspace objects: {e}")
        
        return []
    
    async def clear_workspace(self) -> bool:
        """Clear all objects from the workspace.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            result = await self.execute_r_code("rm(list = ls())", capture_plots=False)
            return result.success
        except Exception as e:
            self.logger.error(f"Failed to clear workspace: {e}")
            return False
    
    async def save_workspace(self, file_path: str) -> bool:
        """Save the current workspace to a file.
        
        Args:
            file_path: Path to save the workspace file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            code = f'save.image("{file_path}")'
            result = await self.execute_r_code(code, capture_plots=False)
            return result.success
        except Exception as e:
            self.logger.error(f"Failed to save workspace: {e}")
            return False
    
    async def load_workspace(self, file_path: str) -> bool:
        """Load a workspace from a file.
        
        Args:
            file_path: Path to the workspace file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            code = f'load("{file_path}")'
            result = await self.execute_r_code(code, capture_plots=False)
            return result.success
        except Exception as e:
            self.logger.error(f"Failed to load workspace: {e}")
            return False
    
    def cleanup(self) -> None:
        """Clean up resources."""
        try:
            if self._r_initialized:
                # Deactivate pandas2ri
                pandas2ri.deactivate()
                self.logger.info("R interface cleaned up")
        except Exception as e:
            self.logger.warning(f"Error during cleanup: {e}")