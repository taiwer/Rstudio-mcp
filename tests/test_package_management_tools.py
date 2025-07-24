"""Tests for package management tools."""

import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

from src.rstudio_mcp.api_wrapper import RStudioAPIWrapper, ExecutionResult
from src.rstudio_mcp.environment_manager import EnvironmentManager, Environment
from src.rstudio_mcp.tools.package_management_tools import (
    InstallPackageTool,
    UpdatePackageTool,
    UninstallPackageTool,
    ListPackagesTool
)
from src.rstudio_mcp.tools.base import ToolResult


@pytest.fixture
def mock_api_wrapper():
    """Create a mock API wrapper."""
    api = Mock(spec=RStudioAPIWrapper)
    api.execute_r_code = AsyncMock()
    return api


@pytest.fixture
def mock_environment_manager():
    """Create a mock environment manager."""
    env_manager = Mock(spec=EnvironmentManager)
    env_manager.get_environment = AsyncMock()
    env_manager.switch_environment = AsyncMock()
    return env_manager


@pytest.fixture
def mock_environment():
    """Create a mock environment."""
    return Environment(
        name="test_env",
        r_version="4.3.0",
        path="/path/to/env",
        packages=["base", "utils"],
        is_active=True,
        created_at=datetime.now()
    )


class TestInstallPackageTool:
    """Tests for InstallPackageTool."""

    @pytest.fixture
    def install_tool(self, mock_api_wrapper, mock_environment_manager):
        """Create InstallPackageTool instance."""
        return InstallPackageTool(mock_api_wrapper, mock_environment_manager)

    @pytest.mark.asyncio
    async def test_install_package_success(self, install_tool, mock_api_wrapper, mock_environment_manager, mock_environment):
        """Test successful package installation."""
        # Setup mocks
        mock_environment_manager.get_environment.return_value = mock_environment
        mock_environment_manager.switch_environment.return_value = True
        
        # Mock package not installed initially
        mock_api_wrapper.execute_r_code.side_effect = [
            ExecutionResult(success=True, output="FALSE"),  # Package not installed check
            ExecutionResult(success=True, output="Installation successful"),  # Install command
            ExecutionResult(success=True, output="TRUE"),  # Package installed verification
            ExecutionResult(success=True, output='"1.0.0"'),  # Package version
            ExecutionResult(success=True, output="character(0)")  # Dependencies
        ]

        # Execute tool
        result = await install_tool.execute({
            "package": "ggplot2",
            "environment": "test_env"
        })

        # Verify result
        assert result.success
        assert "成功安装包 'ggplot2'" in result.content[0]["text"]
        assert "版本: 1.0.0" in result.content[0]["text"]
        
        # Verify API calls
        mock_environment_manager.get_environment.assert_called_once_with("test_env")
        mock_environment_manager.switch_environment.assert_called_once_with("test_env")

    @pytest.mark.asyncio
    async def test_install_package_already_installed(self, install_tool, mock_api_wrapper):
        """Test installing already installed package."""
        # Mock package already installed
        mock_api_wrapper.execute_r_code.side_effect = [
            ExecutionResult(success=True, output="TRUE"),  # Package installed check
            ExecutionResult(success=True, output='"1.0.0"')  # Package version
        ]

        # Execute tool
        result = await install_tool.execute({
            "package": "ggplot2"
        })

        # Verify result
        assert result.success
        assert "包 'ggplot2' 已安装" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_install_package_with_version(self, install_tool, mock_api_wrapper):
        """Test installing specific package version."""
        # Mock package not installed initially
        mock_api_wrapper.execute_r_code.side_effect = [
            ExecutionResult(success=True, output="FALSE"),  # Package not installed check
            ExecutionResult(success=True, output="Installation successful"),  # Install command
            ExecutionResult(success=True, output="TRUE"),  # Package installed verification
            ExecutionResult(success=True, output='"2.0.0"'),  # Package version
            ExecutionResult(success=True, output="character(0)")  # Dependencies
        ]

        # Execute tool
        result = await install_tool.execute({
            "package": "ggplot2",
            "version": "2.0.0"
        })

        # Verify result
        assert result.success
        assert "成功安装包 'ggplot2'" in result.content[0]["text"]
        assert "版本: 2.0.0" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_install_package_failure(self, install_tool, mock_api_wrapper):
        """Test package installation failure."""
        # Mock installation failure
        mock_api_wrapper.execute_r_code.side_effect = [
            ExecutionResult(success=True, output="FALSE"),  # Package not installed check
            ExecutionResult(success=False, error="Installation failed", output="Error log")  # Install command
        ]

        # Execute tool
        result = await install_tool.execute({
            "package": "nonexistent_package"
        })

        # Verify result
        assert not result.success
        assert "包 'nonexistent_package' 安装失败" in result.error
        assert "安装日志:" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_install_package_empty_name(self, install_tool):
        """Test installing package with empty name."""
        result = await install_tool.execute({
            "package": ""
        })

        assert not result.success
        assert "包名称不能为空" in result.error

    @pytest.mark.asyncio
    async def test_install_package_environment_not_exists(self, install_tool, mock_environment_manager):
        """Test installing package in non-existent environment."""
        mock_environment_manager.get_environment.return_value = None

        result = await install_tool.execute({
            "package": "ggplot2",
            "environment": "nonexistent_env"
        })

        assert not result.success
        assert "环境 'nonexistent_env' 不存在" in result.error


class TestUpdatePackageTool:
    """Tests for UpdatePackageTool."""

    @pytest.fixture
    def update_tool(self, mock_api_wrapper, mock_environment_manager):
        """Create UpdatePackageTool instance."""
        return UpdatePackageTool(mock_api_wrapper, mock_environment_manager)

    @pytest.mark.asyncio
    async def test_update_specific_package_success(self, update_tool, mock_api_wrapper):
        """Test successful specific package update."""
        # Mock package installed and update successful
        mock_api_wrapper.execute_r_code.side_effect = [
            ExecutionResult(success=True, output="TRUE"),  # Package installed check
            ExecutionResult(success=True, output='"1.0.0"'),  # Current version
            ExecutionResult(success=True, output="Update successful"),  # Update command
            ExecutionResult(success=True, output='"1.1.0"')  # New version
        ]

        # Execute tool
        result = await update_tool.execute({
            "package": "ggplot2"
        })

        # Verify result
        assert result.success
        assert "成功更新包 'ggplot2'" in result.content[0]["text"]
        assert "旧版本: 1.0.0" in result.content[0]["text"]
        assert "新版本: 1.1.0" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_update_package_already_latest(self, update_tool, mock_api_wrapper):
        """Test updating package that's already latest version."""
        # Mock package installed and no update needed
        mock_api_wrapper.execute_r_code.side_effect = [
            ExecutionResult(success=True, output="TRUE"),  # Package installed check
            ExecutionResult(success=True, output='"1.0.0"'),  # Current version
            ExecutionResult(success=True, output="No updates available"),  # Update command
            ExecutionResult(success=True, output='"1.0.0"')  # Same version
        ]

        # Execute tool
        result = await update_tool.execute({
            "package": "ggplot2"
        })

        # Verify result
        assert result.success
        assert "包 'ggplot2' 已是最新版本" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_update_all_packages(self, update_tool, mock_api_wrapper):
        """Test updating all packages."""
        # Mock update all packages
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=True, 
            output="Updated multiple packages"
        )

        # Execute tool
        result = await update_tool.execute({})

        # Verify result
        assert result.success
        assert "包更新操作完成" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_update_package_not_installed(self, update_tool, mock_api_wrapper):
        """Test updating package that's not installed."""
        # Mock package not installed
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=True, 
            output="FALSE"
        )

        # Execute tool
        result = await update_tool.execute({
            "package": "nonexistent_package"
        })

        # Verify result
        assert not result.success
        assert "包 'nonexistent_package' 未安装，无法更新" in result.error

    @pytest.mark.asyncio
    async def test_update_package_failure(self, update_tool, mock_api_wrapper):
        """Test package update failure."""
        # Mock update failure
        mock_api_wrapper.execute_r_code.side_effect = [
            ExecutionResult(success=True, output="TRUE"),  # Package installed check
            ExecutionResult(success=True, output='"1.0.0"'),  # Current version
            ExecutionResult(success=False, error="Update failed", output="Error log")  # Update command
        ]

        # Execute tool
        result = await update_tool.execute({
            "package": "ggplot2"
        })

        # Verify result
        assert not result.success
        assert "包更新失败" in result.error


class TestUninstallPackageTool:
    """Tests for UninstallPackageTool."""

    @pytest.fixture
    def uninstall_tool(self, mock_api_wrapper, mock_environment_manager):
        """Create UninstallPackageTool instance."""
        return UninstallPackageTool(mock_api_wrapper, mock_environment_manager)

    @pytest.mark.asyncio
    async def test_uninstall_package_success(self, uninstall_tool, mock_api_wrapper):
        """Test successful package uninstallation."""
        # Mock package installed, no dependents, and uninstall successful
        mock_api_wrapper.execute_r_code.side_effect = [
            ExecutionResult(success=True, output="TRUE"),  # Package installed check
            ExecutionResult(success=True, output='"1.0.0"'),  # Package version
            ExecutionResult(success=True, output="character(0)"),  # No dependents
            ExecutionResult(success=True, output="Uninstall successful"),  # Uninstall command
            ExecutionResult(success=True, output="FALSE")  # Package uninstalled verification
        ]

        # Execute tool
        result = await uninstall_tool.execute({
            "package": "ggplot2"
        })

        # Verify result
        assert result.success
        assert "成功卸载包 'ggplot2'" in result.content[0]["text"]
        assert "版本: 1.0.0" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_uninstall_package_with_dependents(self, uninstall_tool, mock_api_wrapper):
        """Test uninstalling package with dependents without force."""
        # Mock package installed with dependents
        mock_api_wrapper.execute_r_code.side_effect = [
            ExecutionResult(success=True, output="TRUE"),  # Package installed check
            ExecutionResult(success=True, output='"1.0.0"'),  # Package version
            ExecutionResult(success=True, output='"dependent1" "dependent2"')  # Has dependents
        ]

        # Execute tool
        result = await uninstall_tool.execute({
            "package": "ggplot2"
        })

        # Verify result
        assert not result.success
        assert "以下包依赖于它" in result.error
        assert "dependent1" in result.error
        assert "force=true" in result.error

    @pytest.mark.asyncio
    async def test_uninstall_package_force_with_dependents(self, uninstall_tool, mock_api_wrapper):
        """Test force uninstalling package with dependents."""
        # Mock package installed with dependents but force uninstall
        mock_api_wrapper.execute_r_code.side_effect = [
            ExecutionResult(success=True, output="TRUE"),  # Package installed check
            ExecutionResult(success=True, output='"1.0.0"'),  # Package version
            ExecutionResult(success=True, output="Uninstall successful"),  # Uninstall command (force)
            ExecutionResult(success=True, output="FALSE")  # Package uninstalled verification
        ]

        # Execute tool
        result = await uninstall_tool.execute({
            "package": "ggplot2",
            "force": True
        })

        # Verify result
        assert result.success
        assert "成功卸载包 'ggplot2'" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_uninstall_package_not_installed(self, uninstall_tool, mock_api_wrapper):
        """Test uninstalling package that's not installed."""
        # Mock package not installed
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=True, 
            output="FALSE"
        )

        # Execute tool
        result = await uninstall_tool.execute({
            "package": "nonexistent_package"
        })

        # Verify result
        assert not result.success
        assert "包 'nonexistent_package' 未安装" in result.error

    @pytest.mark.asyncio
    async def test_uninstall_package_empty_name(self, uninstall_tool):
        """Test uninstalling package with empty name."""
        result = await uninstall_tool.execute({
            "package": ""
        })

        assert not result.success
        assert "包名称不能为空" in result.error

    @pytest.mark.asyncio
    async def test_uninstall_package_failure(self, uninstall_tool, mock_api_wrapper):
        """Test package uninstallation failure."""
        # Mock uninstall failure
        mock_api_wrapper.execute_r_code.side_effect = [
            ExecutionResult(success=True, output="TRUE"),  # Package installed check
            ExecutionResult(success=True, output='"1.0.0"'),  # Package version
            ExecutionResult(success=True, output="character(0)"),  # No dependents
            ExecutionResult(success=False, error="Uninstall failed", output="Error log")  # Uninstall command
        ]

        # Execute tool
        result = await uninstall_tool.execute({
            "package": "ggplot2"
        })

        # Verify result
        assert not result.success
        assert "包 'ggplot2' 卸载失败" in result.error

    @pytest.mark.asyncio
    async def test_uninstall_with_dependency_removal(self, uninstall_tool, mock_api_wrapper):
        """Test uninstalling package with dependency removal."""
        # Mock successful uninstall with dependency removal
        mock_api_wrapper.execute_r_code.side_effect = [
            ExecutionResult(success=True, output="TRUE"),  # Package installed check
            ExecutionResult(success=True, output='"1.0.0"'),  # Package version
            ExecutionResult(success=True, output="character(0)"),  # No dependents
            ExecutionResult(success=True, output="Uninstall successful"),  # Uninstall command
            ExecutionResult(success=True, output="FALSE"),  # Package uninstalled verification
            ExecutionResult(success=True, output="character(0)")  # No unused dependencies
        ]

        # Execute tool
        result = await uninstall_tool.execute({
            "package": "ggplot2",
            "remove_dependencies": True
        })

        # Verify result
        assert result.success
        assert "成功卸载包 'ggplot2'" in result.content[0]["text"]


class TestListPackagesTool:
    """Tests for ListPackagesTool."""

    @pytest.fixture
    def list_tool(self, mock_api_wrapper, mock_environment_manager):
        """Create ListPackagesTool instance."""
        return ListPackagesTool(mock_api_wrapper, mock_environment_manager)

    @pytest.mark.asyncio
    async def test_list_packages_success(self, list_tool, mock_api_wrapper):
        """Test successful package listing."""
        # Mock package list
        package_data = [
            {
                "name": "ggplot2",
                "version": "3.4.0",
                "description": "Create Elegant Data Visualisations Using the Grammar of Graphics",
                "built": "4.3.0"
            },
            {
                "name": "dplyr",
                "version": "1.1.0",
                "description": "A Grammar of Data Manipulation",
                "built": "4.3.0"
            }
        ]
        
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=True,
            output=json.dumps(package_data)
        )

        # Execute tool
        result = await list_tool.execute({})

        # Verify result
        assert result.success
        assert "已安装包 (共 2 个)" in result.content[0]["text"]
        assert "ggplot2 (3.4.0)" in result.content[0]["text"]
        assert "dplyr (1.1.0)" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_list_packages_with_pattern(self, list_tool, mock_api_wrapper):
        """Test listing packages with pattern filter."""
        # Mock filtered package list
        package_data = [
            {
                "name": "ggplot2",
                "version": "3.4.0",
                "description": "Create Elegant Data Visualisations Using the Grammar of Graphics",
                "built": "4.3.0"
            }
        ]
        
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=True,
            output=json.dumps(package_data)
        )

        # Execute tool
        result = await list_tool.execute({
            "pattern": "ggplot"
        })

        # Verify result
        assert result.success
        assert "已安装包 (共 1 个)" in result.content[0]["text"]
        assert "ggplot2 (3.4.0)" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_list_packages_with_dependencies(self, list_tool, mock_api_wrapper):
        """Test listing packages with dependency information."""
        # Mock package list and dependencies
        package_data = [
            {
                "name": "ggplot2",
                "version": "3.4.0",
                "description": "Create Elegant Data Visualisations Using the Grammar of Graphics",
                "built": "4.3.0"
            }
        ]
        
        mock_api_wrapper.execute_r_code.side_effect = [
            ExecutionResult(success=True, output=json.dumps(package_data)),  # Package list
            ExecutionResult(success=True, output='"grid" "scales" "gtable"')  # Dependencies
        ]

        # Execute tool
        result = await list_tool.execute({
            "include_dependencies": True
        })

        # Verify result
        assert result.success
        assert "ggplot2 (3.4.0)" in result.content[0]["text"]
        assert "依赖: grid, scales, gtable" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_list_packages_empty_result(self, list_tool, mock_api_wrapper):
        """Test listing packages with no results."""
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=True,
            output="[]"
        )

        # Execute tool
        result = await list_tool.execute({
            "pattern": "nonexistent"
        })

        # Verify result
        assert result.success
        assert "未找到匹配的包" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_list_packages_with_limit(self, list_tool, mock_api_wrapper):
        """Test listing packages with result limit."""
        # Mock large package list
        package_data = [
            {"name": f"package{i}", "version": "1.0.0", "description": f"Package {i}", "built": "4.3.0"}
            for i in range(10)
        ]
        
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=True,
            output=json.dumps(package_data[:5])  # Simulate limit applied
        )

        # Execute tool
        result = await list_tool.execute({
            "limit": 5
        })

        # Verify result
        assert result.success
        assert "已安装包 (共 5 个)" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_list_packages_environment_not_exists(self, list_tool, mock_environment_manager):
        """Test listing packages in non-existent environment."""
        mock_environment_manager.get_environment.return_value = None

        result = await list_tool.execute({
            "environment": "nonexistent_env"
        })

        assert not result.success
        assert "环境 'nonexistent_env' 不存在" in result.error

    @pytest.mark.asyncio
    async def test_list_packages_api_failure(self, list_tool, mock_api_wrapper):
        """Test listing packages with API failure."""
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=False,
            error="Failed to get package list"
        )

        # Execute tool
        result = await list_tool.execute({})

        # Verify result
        assert result.success  # Tool should handle API failure gracefully
        assert "未找到匹配的包" in result.content[0]["text"]


class TestPackageManagementToolsIntegration:
    """Integration tests for package management tools."""

    @pytest.mark.asyncio
    async def test_install_and_list_workflow(self, mock_api_wrapper, mock_environment_manager):
        """Test install package then list packages workflow."""
        install_tool = InstallPackageTool(mock_api_wrapper, mock_environment_manager)
        list_tool = ListPackagesTool(mock_api_wrapper, mock_environment_manager)

        # Mock install workflow
        mock_api_wrapper.execute_r_code.side_effect = [
            ExecutionResult(success=True, output="FALSE"),  # Package not installed
            ExecutionResult(success=True, output="Installation successful"),  # Install
            ExecutionResult(success=True, output="TRUE"),  # Verify installed
            ExecutionResult(success=True, output='"1.0.0"'),  # Version
            ExecutionResult(success=True, output="character(0)"),  # Dependencies
            # List packages
            ExecutionResult(success=True, output=json.dumps([{
                "name": "ggplot2",
                "version": "1.0.0",
                "description": "Data visualization",
                "built": "4.3.0"
            }]))
        ]

        # Install package
        install_result = await install_tool.execute({"package": "ggplot2"})
        assert install_result.success

        # List packages
        list_result = await list_tool.execute({})
        assert list_result.success
        assert "ggplot2 (1.0.0)" in list_result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_update_and_uninstall_workflow(self, mock_api_wrapper, mock_environment_manager):
        """Test update package then uninstall workflow."""
        update_tool = UpdatePackageTool(mock_api_wrapper, mock_environment_manager)
        uninstall_tool = UninstallPackageTool(mock_api_wrapper, mock_environment_manager)

        # Mock workflow
        mock_api_wrapper.execute_r_code.side_effect = [
            # Update package
            ExecutionResult(success=True, output="TRUE"),  # Package installed
            ExecutionResult(success=True, output='"1.0.0"'),  # Current version
            ExecutionResult(success=True, output="Update successful"),  # Update
            ExecutionResult(success=True, output='"1.1.0"'),  # New version
            # Uninstall package
            ExecutionResult(success=True, output="TRUE"),  # Package installed
            ExecutionResult(success=True, output='"1.1.0"'),  # Version
            ExecutionResult(success=True, output="character(0)"),  # No dependents
            ExecutionResult(success=True, output="Uninstall successful"),  # Uninstall
            ExecutionResult(success=True, output="FALSE")  # Verify uninstalled
        ]

        # Update package
        update_result = await update_tool.execute({"package": "ggplot2"})
        assert update_result.success
        assert "成功更新包 'ggplot2'" in update_result.content[0]["text"]

        # Uninstall package
        uninstall_result = await uninstall_tool.execute({"package": "ggplot2"})
        assert uninstall_result.success
        assert "成功卸载包 'ggplot2'" in uninstall_result.content[0]["text"]