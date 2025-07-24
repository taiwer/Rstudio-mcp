"""Integration tests for environment management tools."""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from src.rstudio_mcp.tools.environment_tools import (
    CreateEnvironmentTool,
    ListEnvironmentsTool,
    SwitchEnvironmentTool,
    DeleteEnvironmentTool
)
from src.rstudio_mcp.environment_manager import EnvironmentManager
from src.rstudio_mcp.api_wrapper import RStudioAPIWrapper, ExecutionResult


@pytest.fixture
def temp_env_dir():
    """Create a temporary directory for environment testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_api_wrapper():
    """Create a mock RStudio API wrapper."""
    api = Mock(spec=RStudioAPIWrapper)
    api.get_r_version = AsyncMock(return_value="4.3.0")
    api.execute_r_code = AsyncMock(return_value=ExecutionResult(
        success=True,
        output="Package installed successfully",
        error=None,
        plots=[],
        execution_time=1.0
    ))
    return api


@pytest.fixture
def environment_manager(mock_api_wrapper, temp_env_dir):
    """Create an environment manager with temporary directory."""
    return EnvironmentManager(mock_api_wrapper, temp_env_dir)


@pytest.fixture
def environment_tools(environment_manager):
    """Create all environment management tools."""
    return {
        'create': CreateEnvironmentTool(environment_manager),
        'list': ListEnvironmentsTool(environment_manager),
        'switch': SwitchEnvironmentTool(environment_manager),
        'delete': DeleteEnvironmentTool(environment_manager)
    }


class TestEnvironmentToolsIntegration:
    """Integration tests for environment management tools."""

    @pytest.mark.asyncio
    async def test_complete_environment_lifecycle(self, environment_tools, temp_env_dir):
        """Test complete environment lifecycle: create, list, switch, delete."""
        create_tool = environment_tools['create']
        list_tool = environment_tools['list']
        switch_tool = environment_tools['switch']
        delete_tool = environment_tools['delete']

        # 1. Initially no environments
        result = await list_tool.execute({})
        assert result.success is True
        assert "未找到任何R环境" in result.content[0]["text"]

        # 2. Create first environment
        result = await create_tool.execute({
            "name": "test_env_1",
            "r_version": "4.3.0",
            "description": "First test environment"
        })
        assert result.success is True
        assert "成功创建环境 'test_env_1'" in result.content[0]["text"]

        # Verify environment directory was created
        env_path = Path(temp_env_dir) / "test_env_1"
        assert env_path.exists()
        assert (env_path / ".Rprofile").exists()
        assert (env_path / "library").exists()

        # 3. Create second environment
        result = await create_tool.execute({
            "name": "test_env_2",
            "r_version": "4.2.0",
            "packages": ["ggplot2"]
        })
        assert result.success is True

        # 4. List environments
        result = await list_tool.execute({"include_status": True})
        assert result.success is True
        content = result.content[0]["text"]
        assert "找到 2 个R环境" in content
        assert "test_env_1" in content
        assert "test_env_2" in content

        # 5. Switch to first environment
        result = await switch_tool.execute({"name": "test_env_1"})
        assert result.success is True
        assert "成功切换到环境 'test_env_1'" in result.content[0]["text"]

        # 6. Try to delete active environment without force (should fail)
        result = await delete_tool.execute({"name": "test_env_1", "force": False})
        assert result.success is False
        assert "无法删除活动环境" in result.error

        # 7. Switch to second environment
        result = await switch_tool.execute({"name": "test_env_2"})
        assert result.success is True

        # 8. Delete first environment (now inactive)
        result = await delete_tool.execute({"name": "test_env_1"})
        assert result.success is True
        assert "成功删除环境 'test_env_1'" in result.content[0]["text"]

        # Verify environment directory was removed
        assert not env_path.exists()

        # 9. List environments (should only show one)
        result = await list_tool.execute({})
        assert result.success is True
        content = result.content[0]["text"]
        assert "找到 1 个R环境" in content
        assert "test_env_2" in content
        assert "test_env_1" not in content

        # 10. Delete remaining environment with force
        result = await delete_tool.execute({"name": "test_env_2", "force": True})
        assert result.success is True

    @pytest.mark.asyncio
    async def test_create_environment_with_packages(self, environment_tools, mock_api_wrapper):
        """Test creating environment with package installation."""
        create_tool = environment_tools['create']

        # Mock successful package installation
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=True,
            output="Installing package 'ggplot2'...\nDone",
            error=None,
            plots=[],
            execution_time=2.0
        )

        result = await create_tool.execute({
            "name": "pkg_env",
            "packages": ["ggplot2", "dplyr"]
        })

        assert result.success is True
        assert "成功创建环境 'pkg_env'" in result.content[0]["text"]
        
        # Verify package installation was attempted
        assert mock_api_wrapper.execute_r_code.call_count >= 2  # One call per package

    @pytest.mark.asyncio
    async def test_create_duplicate_environment(self, environment_tools):
        """Test creating environment with duplicate name."""
        create_tool = environment_tools['create']

        # Create first environment
        result = await create_tool.execute({"name": "duplicate_env"})
        assert result.success is True

        # Try to create environment with same name
        result = await create_tool.execute({"name": "duplicate_env"})
        assert result.success is False
        assert "环境创建失败" in result.error

    @pytest.mark.asyncio
    async def test_switch_to_nonexistent_environment(self, environment_tools):
        """Test switching to non-existent environment."""
        switch_tool = environment_tools['switch']

        result = await switch_tool.execute({"name": "nonexistent_env"})
        assert result.success is False
        assert "不存在" in result.error

    @pytest.mark.asyncio
    async def test_delete_nonexistent_environment(self, environment_tools):
        """Test deleting non-existent environment."""
        delete_tool = environment_tools['delete']

        result = await delete_tool.execute({"name": "nonexistent_env"})
        assert result.success is False
        assert "不存在" in result.error

    @pytest.mark.asyncio
    async def test_environment_validation_after_creation(self, environment_tools, environment_manager):
        """Test environment validation after creation."""
        create_tool = environment_tools['create']

        # Create environment
        result = await create_tool.execute({
            "name": "validation_env",
            "description": "Environment for validation testing"
        })
        assert result.success is True

        # Validate environment
        validation_result = await environment_manager.validate_environment("validation_env")
        assert validation_result["valid"] is True
        assert validation_result["checks"]["directory_exists"] is True
        assert validation_result["checks"]["r_profile_exists"] is True
        assert validation_result["checks"]["library_directory_exists"] is True

    @pytest.mark.asyncio
    async def test_environment_status_tracking(self, environment_tools, environment_manager):
        """Test environment status tracking."""
        create_tool = environment_tools['create']
        switch_tool = environment_tools['switch']

        # Create two environments
        await create_tool.execute({"name": "env_a"})
        await create_tool.execute({"name": "env_b"})

        # Initially no environment should be active
        env_a = await environment_manager.get_environment("env_a")
        env_b = await environment_manager.get_environment("env_b")
        assert env_a.is_active is False
        assert env_b.is_active is False

        # Switch to env_a
        result = await switch_tool.execute({"name": "env_a"})
        assert result.success is True

        # Check status
        env_a = await environment_manager.get_environment("env_a")
        env_b = await environment_manager.get_environment("env_b")
        assert env_a.is_active is True
        assert env_b.is_active is False

        # Switch to env_b
        result = await switch_tool.execute({"name": "env_b"})
        assert result.success is True

        # Check status again
        env_a = await environment_manager.get_environment("env_a")
        env_b = await environment_manager.get_environment("env_b")
        assert env_a.is_active is False
        assert env_b.is_active is True

    @pytest.mark.asyncio
    async def test_environment_copy_functionality(self, environment_tools, mock_api_wrapper):
        """Test copying from existing environment."""
        create_tool = environment_tools['create']

        # Create source environment with packages
        result = await create_tool.execute({
            "name": "source_env",
            "packages": ["base", "utils"]
        })
        assert result.success is True

        # Create target environment copying from source
        result = await create_tool.execute({
            "name": "target_env",
            "copy_from": "source_env"
        })
        assert result.success is True

        # Verify package installation was called for copied packages
        # Should be called for source packages + copy packages
        assert mock_api_wrapper.execute_r_code.call_count >= 4

    @pytest.mark.asyncio
    async def test_tool_error_handling_with_api_failures(self, environment_tools, mock_api_wrapper):
        """Test tool error handling when API calls fail."""
        create_tool = environment_tools['create']
        switch_tool = environment_tools['switch']

        # Mock API failure for R version retrieval
        mock_api_wrapper.get_r_version.side_effect = Exception("R not available")

        result = await create_tool.execute({"name": "fail_env"})
        assert result.success is False
        assert "创建环境时发生意外错误" in result.error

        # Reset mock for switch test
        mock_api_wrapper.get_r_version.side_effect = None
        mock_api_wrapper.get_r_version.return_value = "4.3.0"

        # Create environment successfully
        result = await create_tool.execute({"name": "switch_test_env"})
        assert result.success is True

        # Mock API failure for environment switching
        mock_api_wrapper.execute_r_code.side_effect = Exception("R execution failed")

        result = await switch_tool.execute({"name": "switch_test_env"})
        assert result.success is False
        assert "环境切换失败" in result.error

    @pytest.mark.asyncio
    async def test_concurrent_environment_operations(self, environment_tools):
        """Test concurrent environment operations."""
        import asyncio
        
        create_tool = environment_tools['create']
        list_tool = environment_tools['list']

        # Create multiple environments concurrently
        tasks = []
        for i in range(3):
            task = create_tool.execute({
                "name": f"concurrent_env_{i}",
                "description": f"Concurrent environment {i}"
            })
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed
        for result in results:
            assert not isinstance(result, Exception)
            assert result.success is True

        # List should show all environments
        result = await list_tool.execute({})
        assert result.success is True
        content = result.content[0]["text"]
        assert "找到 3 个R环境" in content
        for i in range(3):
            assert f"concurrent_env_{i}" in content


class TestToolRegistration:
    """Test tool registration with tool manager."""

    @pytest.mark.asyncio
    async def test_tools_can_be_registered(self, environment_manager):
        """Test that environment tools can be registered with tool manager."""
        from src.rstudio_mcp.tools.manager import ToolManager

        tool_manager = ToolManager()
        
        # Register environment tools
        tools = [
            CreateEnvironmentTool(environment_manager),
            ListEnvironmentsTool(environment_manager),
            SwitchEnvironmentTool(environment_manager),
            DeleteEnvironmentTool(environment_manager)
        ]

        for tool in tools:
            tool_manager.register_tool(tool)

        # Verify all tools are registered
        tool_names = tool_manager.list_tools()
        expected_names = [
            "create_environment",
            "list_environments", 
            "switch_environment",
            "delete_environment"
        ]

        for name in expected_names:
            assert name in tool_names

        # Test tool execution through manager
        result = await tool_manager.execute_tool("list_environments", {})
        assert result.success is True

    @pytest.mark.asyncio
    async def test_tool_definitions_for_mcp(self, environment_manager):
        """Test that tools provide proper MCP definitions."""
        from src.rstudio_mcp.tools.manager import ToolManager

        tool_manager = ToolManager()
        
        # Register tools
        tools = [
            CreateEnvironmentTool(environment_manager),
            ListEnvironmentsTool(environment_manager),
            SwitchEnvironmentTool(environment_manager),
            DeleteEnvironmentTool(environment_manager)
        ]

        for tool in tools:
            tool_manager.register_tool(tool)

        # Get MCP tool definitions
        definitions = tool_manager.get_tool_definitions()
        assert len(definitions) == 4

        # Verify each definition has required MCP fields
        for definition in definitions:
            assert "name" in definition
            assert "description" in definition
            assert "inputSchema" in definition
            
            schema = definition["inputSchema"]
            assert schema["type"] == "object"
            assert "properties" in schema