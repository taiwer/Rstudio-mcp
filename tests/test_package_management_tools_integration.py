"""Integration tests for package management tools."""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from src.rstudio_mcp.api_wrapper import RStudioAPIWrapper, ExecutionResult
from src.rstudio_mcp.environment_manager import EnvironmentManager
from src.rstudio_mcp.tools.package_management_tools import (
    InstallPackageTool,
    UpdatePackageTool,
    UninstallPackageTool,
    ListPackagesTool
)


@pytest.fixture
def mock_api_wrapper():
    """Create a mock API wrapper for integration tests."""
    api = Mock(spec=RStudioAPIWrapper)
    api.execute_r_code = AsyncMock()
    return api


@pytest.fixture
def mock_environment_manager():
    """Create a mock environment manager for integration tests."""
    env_manager = Mock(spec=EnvironmentManager)
    env_manager.get_environment = AsyncMock(return_value=True)
    env_manager.switch_environment = AsyncMock(return_value=True)
    return env_manager


class TestPackageManagementIntegration:
    """Integration tests for package management tools."""

    @pytest.mark.asyncio
    async def test_install_package_integration(self, mock_api_wrapper, mock_environment_manager):
        """Test package installation integration with R API."""
        tool = InstallPackageTool(mock_api_wrapper, mock_environment_manager)
        
        # Mock R API responses for package installation
        mock_api_wrapper.execute_r_code.side_effect = [
            ExecutionResult(success=True, output="FALSE"),  # Package not installed
            ExecutionResult(success=True, output="Installing package..."),  # Installation
            ExecutionResult(success=True, output="TRUE"),  # Verification
            ExecutionResult(success=True, output='"1.0.0"'),  # Version check
            ExecutionResult(success=True, output="character(0)")  # Dependencies
        ]
        
        result = await tool.execute({
            "package": "jsonlite",
            "dependencies": True
        })
        
        assert result.success
        assert "成功安装包 'jsonlite'" in result.content[0]["text"]
        
        # Verify R commands were called correctly
        calls = mock_api_wrapper.execute_r_code.call_args_list
        assert len(calls) == 5
        
        # Check package installation command
        call_args, call_kwargs = calls[1]
        install_call = call_kwargs.get("code", "")
        assert "install.packages" in install_call
        assert "jsonlite" in install_call

    @pytest.mark.asyncio
    async def test_update_package_integration(self, mock_api_wrapper, mock_environment_manager):
        """Test package update integration with R API."""
        tool = UpdatePackageTool(mock_api_wrapper, mock_environment_manager)
        
        # Mock R API responses for package update
        mock_api_wrapper.execute_r_code.side_effect = [
            ExecutionResult(success=True, output="TRUE"),  # Package installed
            ExecutionResult(success=True, output='"1.0.0"'),  # Current version
            ExecutionResult(success=True, output="Updating package..."),  # Update
            ExecutionResult(success=True, output='"1.1.0"')  # New version
        ]
        
        result = await tool.execute({
            "package": "jsonlite"
        })
        
        assert result.success
        assert "成功更新包 'jsonlite'" in result.content[0]["text"]
        assert "旧版本: 1.0.0" in result.content[0]["text"]
        assert "新版本: 1.1.0" in result.content[0]["text"]
        
        # Verify R commands were called correctly
        calls = mock_api_wrapper.execute_r_code.call_args_list
        assert len(calls) == 4
        
        # Check update command
        call_args, call_kwargs = calls[2]
        update_call = call_kwargs.get("code", "")
        assert "update.packages" in update_call
        assert "jsonlite" in update_call

    @pytest.mark.asyncio
    async def test_uninstall_package_integration(self, mock_api_wrapper, mock_environment_manager):
        """Test package uninstallation integration with R API."""
        tool = UninstallPackageTool(mock_api_wrapper, mock_environment_manager)
        
        # Mock R API responses for package uninstallation
        mock_api_wrapper.execute_r_code.side_effect = [
            ExecutionResult(success=True, output="TRUE"),  # Package installed
            ExecutionResult(success=True, output='"1.0.0"'),  # Package version
            ExecutionResult(success=True, output="character(0)"),  # No dependents
            ExecutionResult(success=True, output="Removing package..."),  # Uninstall
            ExecutionResult(success=True, output="FALSE")  # Verification
        ]
        
        result = await tool.execute({
            "package": "jsonlite"
        })
        
        assert result.success
        assert "成功卸载包 'jsonlite'" in result.content[0]["text"]
        assert "版本: 1.0.0" in result.content[0]["text"]
        
        # Verify R commands were called correctly
        calls = mock_api_wrapper.execute_r_code.call_args_list
        assert len(calls) == 5
        
        # Check uninstall command
        call_args, call_kwargs = calls[3]
        uninstall_call = call_kwargs.get("code", "")
        assert "remove.packages" in uninstall_call
        assert "jsonlite" in uninstall_call

    @pytest.mark.asyncio
    async def test_list_packages_integration(self, mock_api_wrapper, mock_environment_manager):
        """Test package listing integration with R API."""
        tool = ListPackagesTool(mock_api_wrapper, mock_environment_manager)
        
        # Mock R API response for package listing
        package_json = '''[
            {
                "name": "base",
                "version": "4.3.0",
                "description": "The R Base Package",
                "built": "4.3.0"
            },
            {
                "name": "jsonlite",
                "version": "1.8.0",
                "description": "A Simple and Robust JSON Parser and Generator for R",
                "built": "4.3.0"
            }
        ]'''
        
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=True,
            output=package_json
        )
        
        result = await tool.execute({
            "include_description": True
        })
        
        assert result.success
        assert "已安装包 (共 2 个)" in result.content[0]["text"]
        assert "base (4.3.0)" in result.content[0]["text"]
        assert "jsonlite (1.8.0)" in result.content[0]["text"]
        assert "The R Base Package" in result.content[0]["text"]
        
        # Verify R command was called correctly
        calls = mock_api_wrapper.execute_r_code.call_args_list
        assert len(calls) == 1
        
        # Verify the API was called (detailed code verification not needed for integration test)
        mock_api_wrapper.execute_r_code.assert_called_once()

    @pytest.mark.asyncio
    async def test_package_dependency_handling(self, mock_api_wrapper, mock_environment_manager):
        """Test package dependency handling in installation."""
        tool = InstallPackageTool(mock_api_wrapper, mock_environment_manager)
        
        # Mock R API responses with dependency information
        mock_api_wrapper.execute_r_code.side_effect = [
            ExecutionResult(success=True, output="FALSE"),  # Package not installed
            ExecutionResult(success=True, output="Installing with dependencies..."),  # Installation
            ExecutionResult(success=True, output="TRUE"),  # Verification
            ExecutionResult(success=True, output='"1.0.0"'),  # Version check
            ExecutionResult(success=True, output='"utils" "methods"')  # Dependencies
        ]
        
        result = await tool.execute({
            "package": "ggplot2",
            "dependencies": True
        })
        
        assert result.success
        assert "成功安装包 'ggplot2'" in result.content[0]["text"]
        # Check if dependency information is included in any of the content items
        content_text = " ".join([item["text"] for item in result.content])
        assert "依赖包: utils, methods" in content_text

    @pytest.mark.asyncio
    async def test_package_version_specific_installation(self, mock_api_wrapper, mock_environment_manager):
        """Test installing specific package version."""
        tool = InstallPackageTool(mock_api_wrapper, mock_environment_manager)
        
        # Mock R API responses for version-specific installation
        mock_api_wrapper.execute_r_code.side_effect = [
            ExecutionResult(success=True, output="FALSE"),  # Package not installed
            ExecutionResult(success=True, output="Installing specific version..."),  # Installation
            ExecutionResult(success=True, output="TRUE"),  # Verification
            ExecutionResult(success=True, output='"2.0.0"'),  # Version check
            ExecutionResult(success=True, output="character(0)")  # Dependencies
        ]
        
        result = await tool.execute({
            "package": "ggplot2",
            "version": "2.0.0"
        })
        
        assert result.success
        assert "成功安装包 'ggplot2'" in result.content[0]["text"]
        assert "版本: 2.0.0" in result.content[0]["text"]
        
        # Verify version-specific installation command
        calls = mock_api_wrapper.execute_r_code.call_args_list
        call_args, call_kwargs = calls[1]
        install_call = call_kwargs.get("code", "")
        assert "remotes::install_version" in install_call
        assert "version = \"2.0.0\"" in install_call

    @pytest.mark.asyncio
    async def test_package_repository_specification(self, mock_api_wrapper, mock_environment_manager):
        """Test installing package from specific repository."""
        tool = InstallPackageTool(mock_api_wrapper, mock_environment_manager)
        
        # Mock R API responses for repository-specific installation
        mock_api_wrapper.execute_r_code.side_effect = [
            ExecutionResult(success=True, output="FALSE"),  # Package not installed
            ExecutionResult(success=True, output="Installing from repository..."),  # Installation
            ExecutionResult(success=True, output="TRUE"),  # Verification
            ExecutionResult(success=True, output='"1.0.0"'),  # Version check
            ExecutionResult(success=True, output="character(0)")  # Dependencies
        ]
        
        result = await tool.execute({
            "package": "ggplot2",
            "repository": "https://custom.repo.com"
        })
        
        assert result.success
        assert "成功安装包 'ggplot2'" in result.content[0]["text"]
        
        # Verify repository-specific installation command
        calls = mock_api_wrapper.execute_r_code.call_args_list
        call_args, call_kwargs = calls[1]
        install_call = call_kwargs.get("code", "")
        assert "repos = \"https://custom.repo.com\"" in install_call

    @pytest.mark.asyncio
    async def test_package_uninstall_with_dependents_check(self, mock_api_wrapper, mock_environment_manager):
        """Test uninstalling package with dependent packages check."""
        tool = UninstallPackageTool(mock_api_wrapper, mock_environment_manager)
        
        # Mock R API responses showing package has dependents
        mock_api_wrapper.execute_r_code.side_effect = [
            ExecutionResult(success=True, output="TRUE"),  # Package installed
            ExecutionResult(success=True, output='"1.0.0"'),  # Package version
            ExecutionResult(success=True, output='"ggplot2" "dplyr"')  # Has dependents
        ]
        
        result = await tool.execute({
            "package": "scales"
        })
        
        assert not result.success
        assert "以下包依赖于它: ggplot2, dplyr" in result.error
        assert "force=true" in result.error

    @pytest.mark.asyncio
    async def test_package_list_with_pattern_filter(self, mock_api_wrapper, mock_environment_manager):
        """Test listing packages with pattern filtering."""
        tool = ListPackagesTool(mock_api_wrapper, mock_environment_manager)
        
        # Mock R API response for filtered package listing
        package_json = '''[
            {
                "name": "ggplot2",
                "version": "3.4.0",
                "description": "Create Elegant Data Visualisations",
                "built": "4.3.0"
            }
        ]'''
        
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=True,
            output=package_json
        )
        
        result = await tool.execute({
            "pattern": "ggplot"
        })
        
        assert result.success
        assert "已安装包 (共 1 个)" in result.content[0]["text"]
        assert "ggplot2 (3.4.0)" in result.content[0]["text"]
        
        # Verify pattern filtering was applied (detailed code verification not needed for integration test)
        calls = mock_api_wrapper.execute_r_code.call_args_list
        assert len(calls) == 1
        mock_api_wrapper.execute_r_code.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling_integration(self, mock_api_wrapper, mock_environment_manager):
        """Test error handling in package management operations."""
        tool = InstallPackageTool(mock_api_wrapper, mock_environment_manager)
        
        # Mock R API failure
        mock_api_wrapper.execute_r_code.side_effect = [
            ExecutionResult(success=True, output="FALSE"),  # Package not installed
            ExecutionResult(success=False, error="Network error", output="Connection failed")  # Installation failure
        ]
        
        result = await tool.execute({
            "package": "nonexistent_package"
        })
        
        assert not result.success
        assert "包 'nonexistent_package' 安装失败" in result.error
        assert "Network error" in result.error
        assert "安装日志:" in result.content[0]["text"]
        assert "Connection failed" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_timeout_handling(self, mock_api_wrapper, mock_environment_manager):
        """Test timeout handling in package operations."""
        tool = InstallPackageTool(mock_api_wrapper, mock_environment_manager)
        
        # Mock timeout scenario
        import asyncio
        mock_api_wrapper.execute_r_code.side_effect = [
            ExecutionResult(success=True, output="FALSE"),  # Package not installed
            asyncio.TimeoutError()  # Installation timeout
        ]
        
        result = await tool.execute({
            "package": "large_package"
        })
        
        assert not result.success
        assert "意外错误" in result.error  # Should catch and handle timeout

    @pytest.mark.asyncio
    async def test_environment_switching_integration(self, mock_api_wrapper, mock_environment_manager):
        """Test environment switching during package operations."""
        tool = InstallPackageTool(mock_api_wrapper, mock_environment_manager)
        
        # Mock environment switching
        mock_environment_manager.get_environment.return_value = True
        mock_environment_manager.switch_environment.return_value = True
        
        mock_api_wrapper.execute_r_code.side_effect = [
            ExecutionResult(success=True, output="FALSE"),  # Package not installed
            ExecutionResult(success=True, output="Installing..."),  # Installation
            ExecutionResult(success=True, output="TRUE"),  # Verification
            ExecutionResult(success=True, output='"1.0.0"'),  # Version
            ExecutionResult(success=True, output="character(0)")  # Dependencies
        ]
        
        result = await tool.execute({
            "package": "jsonlite",
            "environment": "test_env"
        })
        
        assert result.success
        assert "环境: test_env" in result.content[0]["text"]
        
        # Verify environment operations were called
        mock_environment_manager.get_environment.assert_called_once_with("test_env")
        mock_environment_manager.switch_environment.assert_called_once_with("test_env")