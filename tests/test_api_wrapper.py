"""Tests for RStudio API wrapper."""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.rstudio_mcp.api_wrapper import ExecutionResult, RStudioAPIWrapper
from src.rstudio_mcp.exceptions import EnvironmentError, ExecutionError


class TestExecutionResult:
    """Test ExecutionResult class."""
    
    def test_execution_result_creation(self):
        """Test ExecutionResult creation with default values."""
        result = ExecutionResult(success=True, output="test output")
        
        assert result.success is True
        assert result.output == "test output"
        assert result.error is None
        assert result.plots == []
        assert result.execution_time == 0.0
        assert result.warnings == []
    
    def test_execution_result_with_all_fields(self):
        """Test ExecutionResult creation with all fields."""
        plots = ["/path/to/plot1.png", "/path/to/plot2.png"]
        warnings = ["Warning 1", "Warning 2"]
        
        result = ExecutionResult(
            success=False,
            output="output",
            error="error message",
            plots=plots,
            execution_time=1.5,
            warnings=warnings,
        )
        
        assert result.success is False
        assert result.output == "output"
        assert result.error == "error message"
        assert result.plots == plots
        assert result.execution_time == 1.5
        assert result.warnings == warnings
    
    def test_execution_result_repr(self):
        """Test ExecutionResult string representation."""
        result = ExecutionResult(
            success=True,
            output="test output",
            plots=["/path/to/plot.png"],
            execution_time=2.5,
        )
        
        repr_str = repr(result)
        assert "ExecutionResult" in repr_str
        assert "success=True" in repr_str
        assert "output_length=11" in repr_str
        assert "plots=1" in repr_str
        assert "execution_time=2.500s" in repr_str


class TestRStudioAPIWrapper:
    """Test RStudioAPIWrapper class."""
    
    @pytest.fixture
    def mock_r_interface(self):
        """Mock R interface components."""
        with patch('src.rstudio_mcp.api_wrapper.robjects') as mock_robjects, \
             patch('src.rstudio_mcp.api_wrapper.pandas2ri') as mock_pandas2ri, \
             patch('src.rstudio_mcp.api_wrapper.importr') as mock_importr:
            
            # Mock robjects.r
            mock_r = Mock()
            mock_robjects.r = mock_r
            
            # Mock importr for utils and rstudioapi
            mock_utils = Mock()
            mock_rstudioapi = Mock()
            
            def importr_side_effect(package_name):
                if package_name == 'utils':
                    return mock_utils
                elif package_name == 'rstudioapi':
                    return mock_rstudioapi
                else:
                    raise ImportError(f"No module named '{package_name}'")
            
            mock_importr.side_effect = importr_side_effect
            
            yield {
                'robjects': mock_robjects,
                'pandas2ri': mock_pandas2ri,
                'importr': mock_importr,
                'r': mock_r,
                'utils': mock_utils,
                'rstudioapi': mock_rstudioapi,
            }
    
    def test_initialization_success(self, mock_r_interface):
        """Test successful initialization of RStudioAPIWrapper."""
        wrapper = RStudioAPIWrapper(timeout=60)
        
        assert wrapper.timeout == 60
        assert wrapper._r_initialized is True
        assert wrapper._rstudioapi is not None
        assert wrapper._base_r is not None
        assert wrapper._utils is not None
        
        # Verify pandas2ri was activated
        mock_r_interface['pandas2ri'].activate.assert_called_once()
    
    def test_initialization_without_rstudioapi(self, mock_r_interface):
        """Test initialization when rstudioapi is not available."""
        # Make rstudioapi import fail
        def importr_side_effect(package_name):
            if package_name == 'utils':
                return Mock()
            elif package_name == 'rstudioapi':
                raise ImportError("rstudioapi not available")
            else:
                raise ImportError(f"No module named '{package_name}'")
        
        mock_r_interface['importr'].side_effect = importr_side_effect
        
        wrapper = RStudioAPIWrapper()
        
        assert wrapper._r_initialized is True
        assert wrapper._rstudioapi is None
        assert wrapper._base_r is not None
        assert wrapper._utils is not None
    
    def test_initialization_failure(self, mock_r_interface):
        """Test initialization failure."""
        # Make R initialization fail
        mock_r_interface['importr'].side_effect = Exception("R initialization failed")
        
        with pytest.raises(EnvironmentError, match="R initialization failed"):
            RStudioAPIWrapper()
    
    def test_r_home_environment_variable(self, mock_r_interface):
        """Test setting R_HOME environment variable."""
        import os
        
        r_home_path = "/custom/r/home"
        
        with patch.dict(os.environ, {}, clear=True):
            RStudioAPIWrapper(r_home=r_home_path)
            assert os.environ.get('R_HOME') == r_home_path
    
    @pytest.mark.asyncio
    async def test_execute_r_code_success(self, mock_r_interface):
        """Test successful R code execution."""
        wrapper = RStudioAPIWrapper()
        
        # Mock the sync execution method
        mock_result = {'output': 'Hello, World!', 'warnings': []}
        
        with patch.object(wrapper, '_execute_r_code_sync', return_value=mock_result):
            result = await wrapper.execute_r_code("print('Hello, World!')")
        
        assert result.success is True
        assert result.output == 'Hello, World!'
        assert result.error is None
        assert result.execution_time > 0
    
    @pytest.mark.asyncio
    async def test_execute_r_code_timeout(self, mock_r_interface):
        """Test R code execution timeout."""
        wrapper = RStudioAPIWrapper(timeout=1)
        
        # Mock the sync execution method to hang
        async def slow_execution(*args, **kwargs):
            await asyncio.sleep(2)  # Longer than timeout
            return {'output': '', 'warnings': []}
        
        with patch.object(wrapper, '_execute_r_code_sync', side_effect=slow_execution):
            result = await wrapper.execute_r_code("Sys.sleep(10)", timeout=1)
        
        assert result.success is False
        assert "timed out" in result.error
        assert result.execution_time > 0
    
    @pytest.mark.asyncio
    async def test_execute_r_code_with_plots(self, mock_r_interface):
        """Test R code execution with plot capture."""
        wrapper = RStudioAPIWrapper()
        
        # Create a temporary directory with mock plot files
        with tempfile.TemporaryDirectory() as temp_dir:
            plot_file = Path(temp_dir) / "plot_test.png"
            plot_file.touch()  # Create empty plot file
            
            mock_result = {'output': 'Plot created', 'warnings': []}
            
            with patch.object(wrapper, '_execute_r_code_sync', return_value=mock_result), \
                 patch('tempfile.mkdtemp', return_value=temp_dir):
                
                result = await wrapper.execute_r_code(
                    "plot(1:10)", capture_plots=True
                )
            
            assert result.success is True
            assert len(result.plots) == 1
            assert str(plot_file) in result.plots
    
    @pytest.mark.asyncio
    async def test_check_rstudio_available(self, mock_r_interface):
        """Test checking RStudio availability."""
        wrapper = RStudioAPIWrapper()
        
        # With rstudioapi available
        assert await wrapper.check_rstudio_available() is True
        
        # Without rstudioapi
        wrapper._rstudioapi = None
        assert await wrapper.check_rstudio_available() is False
    
    @pytest.mark.asyncio
    async def test_get_active_project(self, mock_r_interface):
        """Test getting active project."""
        wrapper = RStudioAPIWrapper()
        
        # Mock successful project retrieval
        mock_result = {'output': '"/path/to/project"', 'warnings': []}
        
        with patch.object(wrapper, '_execute_r_code_sync', return_value=mock_result):
            project_path = await wrapper.get_active_project()
        
        assert project_path == "/path/to/project"
    
    @pytest.mark.asyncio
    async def test_get_active_project_none(self, mock_r_interface):
        """Test getting active project when none is active."""
        wrapper = RStudioAPIWrapper()
        
        # Mock NULL result
        mock_result = {'output': 'NULL', 'warnings': []}
        
        with patch.object(wrapper, '_execute_r_code_sync', return_value=mock_result):
            project_path = await wrapper.get_active_project()
        
        assert project_path is None
    
    @pytest.mark.asyncio
    async def test_get_active_project_no_rstudioapi(self, mock_r_interface):
        """Test getting active project without rstudioapi."""
        wrapper = RStudioAPIWrapper()
        wrapper._rstudioapi = None
        
        project_path = await wrapper.get_active_project()
        assert project_path is None
    
    @pytest.mark.asyncio
    async def test_get_r_version(self, mock_r_interface):
        """Test getting R version."""
        wrapper = RStudioAPIWrapper()
        
        mock_result = {'output': '"4.3.0"', 'warnings': []}
        
        with patch.object(wrapper, '_execute_r_code_sync', return_value=mock_result):
            version = await wrapper.get_r_version()
        
        assert version == "4.3.0"
    
    @pytest.mark.asyncio
    async def test_list_installed_packages(self, mock_r_interface):
        """Test listing installed packages."""
        wrapper = RStudioAPIWrapper()
        
        mock_packages = [
            {"name": "base", "version": "4.3.0", "description": "Base R"},
            {"name": "utils", "version": "4.3.0", "description": "R Utilities"},
        ]
        
        mock_result = ExecutionResult(
            success=True,
            output=json.dumps(mock_packages)
        )
        
        with patch.object(wrapper, 'execute_r_code', return_value=mock_result):
            packages = await wrapper.list_installed_packages()
        
        assert len(packages) == 2
        assert packages[0]["name"] == "base"
        assert packages[1]["name"] == "utils"
    
    @pytest.mark.asyncio
    async def test_install_package(self, mock_r_interface):
        """Test package installation."""
        wrapper = RStudioAPIWrapper()
        
        mock_result = ExecutionResult(success=True)
        
        with patch.object(wrapper, 'execute_r_code', return_value=mock_result):
            success = await wrapper.install_package("ggplot2")
        
        assert success is True
    
    @pytest.mark.asyncio
    async def test_install_package_with_version(self, mock_r_interface):
        """Test package installation with specific version."""
        wrapper = RStudioAPIWrapper()
        
        mock_result = ExecutionResult(success=True)
        
        with patch.object(wrapper, 'execute_r_code', return_value=mock_result) as mock_exec:
            success = await wrapper.install_package("ggplot2", version="3.4.0")
        
        assert success is True
        # Verify the correct installation command was used
        call_args = mock_exec.call_args[0][0]
        assert "remotes::install_version" in call_args
        assert "ggplot2" in call_args
        assert "3.4.0" in call_args
    
    @pytest.mark.asyncio
    async def test_get_workspace_objects(self, mock_r_interface):
        """Test getting workspace objects."""
        wrapper = RStudioAPIWrapper()
        
        mock_objects = [
            {
                "name": "x",
                "class": "numeric",
                "type": "double",
                "size": 56,
                "summary": "num [1:10] 1 2 3 4 5 6 7 8 9 10"
            }
        ]
        
        mock_result = ExecutionResult(
            success=True,
            output=json.dumps(mock_objects)
        )
        
        with patch.object(wrapper, 'execute_r_code', return_value=mock_result):
            objects = await wrapper.get_workspace_objects()
        
        assert len(objects) == 1
        assert objects[0]["name"] == "x"
        assert objects[0]["class"] == "numeric"
    
    @pytest.mark.asyncio
    async def test_clear_workspace(self, mock_r_interface):
        """Test clearing workspace."""
        wrapper = RStudioAPIWrapper()
        
        mock_result = ExecutionResult(success=True)
        
        with patch.object(wrapper, 'execute_r_code', return_value=mock_result):
            success = await wrapper.clear_workspace()
        
        assert success is True
    
    @pytest.mark.asyncio
    async def test_save_workspace(self, mock_r_interface):
        """Test saving workspace."""
        wrapper = RStudioAPIWrapper()
        
        mock_result = ExecutionResult(success=True)
        
        with patch.object(wrapper, 'execute_r_code', return_value=mock_result):
            success = await wrapper.save_workspace("/path/to/workspace.RData")
        
        assert success is True
    
    @pytest.mark.asyncio
    async def test_load_workspace(self, mock_r_interface):
        """Test loading workspace."""
        wrapper = RStudioAPIWrapper()
        
        mock_result = ExecutionResult(success=True)
        
        with patch.object(wrapper, 'execute_r_code', return_value=mock_result):
            success = await wrapper.load_workspace("/path/to/workspace.RData")
        
        assert success is True
    
    def test_cleanup(self, mock_r_interface):
        """Test cleanup method."""
        wrapper = RStudioAPIWrapper()
        
        # Should not raise any exceptions
        wrapper.cleanup()
        
        # Verify pandas2ri was deactivated
        mock_r_interface['pandas2ri'].deactivate.assert_called_once()
    
    def test_ensure_r_initialized_failure(self, mock_r_interface):
        """Test _ensure_r_initialized with uninitialized R."""
        wrapper = RStudioAPIWrapper()
        wrapper._r_initialized = False
        
        with pytest.raises(EnvironmentError, match="R interface not initialized"):
            wrapper._ensure_r_initialized()


@pytest.mark.integration
class TestRStudioAPIWrapperIntegration:
    """Integration tests for RStudioAPIWrapper (require R installation)."""
    
    @pytest.mark.skipif(
        not Path("/usr/bin/R").exists() and not Path("/usr/local/bin/R").exists(),
        reason="R not installed"
    )
    @pytest.mark.asyncio
    async def test_real_r_execution(self):
        """Test actual R code execution (requires R installation)."""
        try:
            wrapper = RStudioAPIWrapper(timeout=30)
            
            # Test simple arithmetic
            result = await wrapper.execute_r_code("2 + 2")
            assert result.success is True
            assert "4" in result.output
            
            # Test R version
            version = await wrapper.get_r_version()
            assert version != "unknown"
            assert "." in version  # Should be in format like "4.3.0"
            
        except EnvironmentError:
            pytest.skip("R environment not properly configured")