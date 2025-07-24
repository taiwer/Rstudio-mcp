"""Tests for environment management tools."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
from pathlib import Path

from src.rstudio_mcp.tools.environment_tools import (
    CreateEnvironmentTool,
    ListEnvironmentsTool,
    SwitchEnvironmentTool,
    DeleteEnvironmentTool
)
from src.rstudio_mcp.environment_manager import Environment, EnvironmentStatus
from src.rstudio_mcp.exceptions import EnvironmentError


@pytest.fixture
def mock_environment_manager():
    """Create a mock environment manager."""
    manager = Mock()
    manager.create_environment = AsyncMock()
    manager.list_environments = AsyncMock()
    manager.get_environment = AsyncMock()
    manager.switch_environment = AsyncMock()
    manager.delete_environment = AsyncMock()
    manager.get_environment_status = AsyncMock()
    return manager


@pytest.fixture
def sample_environment():
    """Create a sample environment for testing."""
    return Environment(
        name="test_env",
        r_version="4.3.0",
        path="/tmp/test_env",
        packages=["ggplot2", "dplyr"],
        is_active=False,
        created_at=datetime(2024, 1, 1, 12, 0, 0),
        description="Test environment"
    )


@pytest.fixture
def sample_environment_status():
    """Create a sample environment status for testing."""
    return EnvironmentStatus(
        name="test_env",
        is_active=False,
        r_version="4.3.0",
        package_count=2,
        health_status="healthy"
    )


class TestCreateEnvironmentTool:
    """Tests for CreateEnvironmentTool."""

    def test_tool_properties(self, mock_environment_manager):
        """Test tool properties."""
        tool = CreateEnvironmentTool(mock_environment_manager)
        
        assert tool.name == "create_environment"
        assert "创建新的R环境" in tool.description
        
        # Check parameters
        param_names = [p.name for p in tool.parameters]
        assert "name" in param_names
        assert "r_version" in param_names
        assert "description" in param_names
        assert "packages" in param_names
        assert "copy_from" in param_names
        
        # Check required parameters
        required_params = [p.name for p in tool.parameters if p.required]
        assert "name" in required_params
        assert len(required_params) == 1

    @pytest.mark.asyncio
    async def test_create_environment_success(self, mock_environment_manager, sample_environment):
        """Test successful environment creation."""
        mock_environment_manager.create_environment.return_value = sample_environment
        
        tool = CreateEnvironmentTool(mock_environment_manager)
        arguments = {
            "name": "test_env",
            "r_version": "4.3.0",
            "description": "Test environment",
            "packages": ["ggplot2", "dplyr"]
        }
        
        result = await tool.execute(arguments)
        
        assert result.success is True
        assert len(result.content) >= 1
        assert "成功创建环境" in result.content[0]["text"]
        assert "test_env" in result.content[0]["text"]
        
        # Verify environment manager was called correctly
        mock_environment_manager.create_environment.assert_called_once()
        call_args = mock_environment_manager.create_environment.call_args[0][0]
        assert call_args.name == "test_env"
        assert call_args.r_version == "4.3.0"
        assert call_args.description == "Test environment"
        assert call_args.packages == ["ggplot2", "dplyr"]

    @pytest.mark.asyncio
    async def test_create_environment_minimal_args(self, mock_environment_manager, sample_environment):
        """Test environment creation with minimal arguments."""
        mock_environment_manager.create_environment.return_value = sample_environment
        
        tool = CreateEnvironmentTool(mock_environment_manager)
        arguments = {"name": "minimal_env"}
        
        result = await tool.execute(arguments)
        
        assert result.success is True
        mock_environment_manager.create_environment.assert_called_once()
        call_args = mock_environment_manager.create_environment.call_args[0][0]
        assert call_args.name == "minimal_env"
        assert call_args.r_version is None
        assert call_args.packages == []

    @pytest.mark.asyncio
    async def test_create_environment_error(self, mock_environment_manager):
        """Test environment creation error handling."""
        mock_environment_manager.create_environment.side_effect = EnvironmentError("Environment already exists")
        
        tool = CreateEnvironmentTool(mock_environment_manager)
        arguments = {"name": "existing_env"}
        
        result = await tool.execute(arguments)
        
        assert result.success is False
        assert "环境创建失败" in result.error
        assert "Environment already exists" in result.error

    @pytest.mark.asyncio
    async def test_create_environment_unexpected_error(self, mock_environment_manager):
        """Test unexpected error handling."""
        mock_environment_manager.create_environment.side_effect = Exception("Unexpected error")
        
        tool = CreateEnvironmentTool(mock_environment_manager)
        arguments = {"name": "test_env"}
        
        result = await tool.execute(arguments)
        
        assert result.success is False
        assert "意外错误" in result.error


class TestListEnvironmentsTool:
    """Tests for ListEnvironmentsTool."""

    def test_tool_properties(self, mock_environment_manager):
        """Test tool properties."""
        tool = ListEnvironmentsTool(mock_environment_manager)
        
        assert tool.name == "list_environments"
        assert "列出所有可用的R环境" in tool.description
        
        # Check parameters
        param_names = [p.name for p in tool.parameters]
        assert "include_status" in param_names
        
        # Check no required parameters
        required_params = [p.name for p in tool.parameters if p.required]
        assert len(required_params) == 0

    @pytest.mark.asyncio
    async def test_list_environments_success(self, mock_environment_manager, sample_environment, sample_environment_status):
        """Test successful environment listing."""
        # Create multiple environments
        env1 = sample_environment
        env2 = Environment(
            name="env2",
            r_version="4.2.0",
            path="/tmp/env2",
            packages=["base"],
            is_active=True,
            created_at=datetime(2024, 1, 2, 12, 0, 0)
        )
        
        mock_environment_manager.list_environments.return_value = [env1, env2]
        mock_environment_manager.get_environment_status.return_value = sample_environment_status
        
        tool = ListEnvironmentsTool(mock_environment_manager)
        arguments = {"include_status": True}
        
        result = await tool.execute(arguments)
        
        assert result.success is True
        assert len(result.content) == 1
        content_text = result.content[0]["text"]
        
        assert "找到 2 个R环境" in content_text
        assert "test_env" in content_text
        assert "env2" in content_text
        assert "●" in content_text  # Active environment indicator
        assert "○" in content_text  # Inactive environment indicator

    @pytest.mark.asyncio
    async def test_list_environments_no_status(self, mock_environment_manager, sample_environment):
        """Test environment listing without status information."""
        mock_environment_manager.list_environments.return_value = [sample_environment]
        
        tool = ListEnvironmentsTool(mock_environment_manager)
        arguments = {"include_status": False}
        
        result = await tool.execute(arguments)
        
        assert result.success is True
        # Should not call get_environment_status when include_status is False
        mock_environment_manager.get_environment_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_environments_empty(self, mock_environment_manager):
        """Test listing when no environments exist."""
        mock_environment_manager.list_environments.return_value = []
        
        tool = ListEnvironmentsTool(mock_environment_manager)
        arguments = {}
        
        result = await tool.execute(arguments)
        
        assert result.success is True
        assert "未找到任何R环境" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_list_environments_error(self, mock_environment_manager):
        """Test error handling in environment listing."""
        mock_environment_manager.list_environments.side_effect = Exception("Database error")
        
        tool = ListEnvironmentsTool(mock_environment_manager)
        arguments = {}
        
        result = await tool.execute(arguments)
        
        assert result.success is False
        assert "列出环境时发生错误" in result.error


class TestSwitchEnvironmentTool:
    """Tests for SwitchEnvironmentTool."""

    def test_tool_properties(self, mock_environment_manager):
        """Test tool properties."""
        tool = SwitchEnvironmentTool(mock_environment_manager)
        
        assert tool.name == "switch_environment"
        assert "切换到指定的R环境" in tool.description
        
        # Check parameters
        param_names = [p.name for p in tool.parameters]
        assert "name" in param_names
        
        # Check required parameters
        required_params = [p.name for p in tool.parameters if p.required]
        assert "name" in required_params
        assert len(required_params) == 1

    @pytest.mark.asyncio
    async def test_switch_environment_success(self, mock_environment_manager, sample_environment):
        """Test successful environment switching."""
        mock_environment_manager.get_environment.return_value = sample_environment
        mock_environment_manager.switch_environment.return_value = True
        
        tool = SwitchEnvironmentTool(mock_environment_manager)
        arguments = {"name": "test_env"}
        
        result = await tool.execute(arguments)
        
        assert result.success is True
        assert "成功切换到环境" in result.content[0]["text"]
        assert "test_env" in result.content[0]["text"]
        
        mock_environment_manager.get_environment.assert_called_once_with("test_env")
        mock_environment_manager.switch_environment.assert_called_once_with("test_env")

    @pytest.mark.asyncio
    async def test_switch_environment_not_found(self, mock_environment_manager):
        """Test switching to non-existent environment."""
        mock_environment_manager.get_environment.return_value = None
        
        tool = SwitchEnvironmentTool(mock_environment_manager)
        arguments = {"name": "nonexistent_env"}
        
        result = await tool.execute(arguments)
        
        assert result.success is False
        assert "不存在" in result.error
        assert "nonexistent_env" in result.error
        
        # Should not attempt to switch if environment doesn't exist
        mock_environment_manager.switch_environment.assert_not_called()

    @pytest.mark.asyncio
    async def test_switch_environment_failure(self, mock_environment_manager, sample_environment):
        """Test environment switching failure."""
        mock_environment_manager.get_environment.return_value = sample_environment
        mock_environment_manager.switch_environment.return_value = False
        
        tool = SwitchEnvironmentTool(mock_environment_manager)
        arguments = {"name": "test_env"}
        
        result = await tool.execute(arguments)
        
        assert result.success is False
        assert "切换到环境" in result.error
        assert "失败" in result.error

    @pytest.mark.asyncio
    async def test_switch_environment_error(self, mock_environment_manager, sample_environment):
        """Test environment switching error handling."""
        mock_environment_manager.get_environment.return_value = sample_environment
        mock_environment_manager.switch_environment.side_effect = EnvironmentError("Switch failed")
        
        tool = SwitchEnvironmentTool(mock_environment_manager)
        arguments = {"name": "test_env"}
        
        result = await tool.execute(arguments)
        
        assert result.success is False
        assert "环境切换失败" in result.error
        assert "Switch failed" in result.error


class TestDeleteEnvironmentTool:
    """Tests for DeleteEnvironmentTool."""

    def test_tool_properties(self, mock_environment_manager):
        """Test tool properties."""
        tool = DeleteEnvironmentTool(mock_environment_manager)
        
        assert tool.name == "delete_environment"
        assert "安全删除指定的R环境" in tool.description
        
        # Check parameters
        param_names = [p.name for p in tool.parameters]
        assert "name" in param_names
        assert "force" in param_names
        
        # Check required parameters
        required_params = [p.name for p in tool.parameters if p.required]
        assert "name" in required_params
        assert len(required_params) == 1

    @pytest.mark.asyncio
    async def test_delete_environment_success(self, mock_environment_manager, sample_environment):
        """Test successful environment deletion."""
        mock_environment_manager.get_environment.return_value = sample_environment
        mock_environment_manager.delete_environment.return_value = True
        
        tool = DeleteEnvironmentTool(mock_environment_manager)
        arguments = {"name": "test_env", "force": False}
        
        result = await tool.execute(arguments)
        
        assert result.success is True
        assert "成功删除环境" in result.content[0]["text"]
        assert "test_env" in result.content[0]["text"]
        
        mock_environment_manager.get_environment.assert_called_once_with("test_env")
        mock_environment_manager.delete_environment.assert_called_once_with("test_env", force=False)

    @pytest.mark.asyncio
    async def test_delete_environment_not_found(self, mock_environment_manager):
        """Test deleting non-existent environment."""
        mock_environment_manager.get_environment.return_value = None
        
        tool = DeleteEnvironmentTool(mock_environment_manager)
        arguments = {"name": "nonexistent_env"}
        
        result = await tool.execute(arguments)
        
        assert result.success is False
        assert "不存在" in result.error
        assert "nonexistent_env" in result.error
        
        # Should not attempt to delete if environment doesn't exist
        mock_environment_manager.delete_environment.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_active_environment_without_force(self, mock_environment_manager, sample_environment):
        """Test deleting active environment without force flag."""
        active_env = sample_environment
        active_env.is_active = True
        mock_environment_manager.get_environment.return_value = active_env
        
        tool = DeleteEnvironmentTool(mock_environment_manager)
        arguments = {"name": "test_env", "force": False}
        
        result = await tool.execute(arguments)
        
        assert result.success is False
        assert "无法删除活动环境" in result.error
        assert "force=true" in result.error
        
        # Should not attempt to delete active environment without force
        mock_environment_manager.delete_environment.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_active_environment_with_force(self, mock_environment_manager, sample_environment):
        """Test deleting active environment with force flag."""
        active_env = sample_environment
        active_env.is_active = True
        mock_environment_manager.get_environment.return_value = active_env
        mock_environment_manager.delete_environment.return_value = True
        
        tool = DeleteEnvironmentTool(mock_environment_manager)
        arguments = {"name": "test_env", "force": True}
        
        result = await tool.execute(arguments)
        
        assert result.success is True
        assert "成功删除环境" in result.content[0]["text"]
        
        mock_environment_manager.delete_environment.assert_called_once_with("test_env", force=True)

    @pytest.mark.asyncio
    async def test_delete_environment_failure(self, mock_environment_manager, sample_environment):
        """Test environment deletion failure."""
        mock_environment_manager.get_environment.return_value = sample_environment
        mock_environment_manager.delete_environment.return_value = False
        
        tool = DeleteEnvironmentTool(mock_environment_manager)
        arguments = {"name": "test_env"}
        
        result = await tool.execute(arguments)
        
        assert result.success is False
        assert "删除环境" in result.error
        assert "失败" in result.error

    @pytest.mark.asyncio
    async def test_delete_environment_error(self, mock_environment_manager, sample_environment):
        """Test environment deletion error handling."""
        mock_environment_manager.get_environment.return_value = sample_environment
        mock_environment_manager.delete_environment.side_effect = EnvironmentError("Deletion failed")
        
        tool = DeleteEnvironmentTool(mock_environment_manager)
        arguments = {"name": "test_env"}
        
        result = await tool.execute(arguments)
        
        assert result.success is False
        assert "环境删除失败" in result.error
        assert "Deletion failed" in result.error


class TestToolIntegration:
    """Integration tests for environment tools."""

    @pytest.mark.asyncio
    async def test_tool_argument_validation(self, mock_environment_manager):
        """Test argument validation for all tools."""
        tools = [
            CreateEnvironmentTool(mock_environment_manager),
            ListEnvironmentsTool(mock_environment_manager),
            SwitchEnvironmentTool(mock_environment_manager),
            DeleteEnvironmentTool(mock_environment_manager)
        ]
        
        for tool in tools:
            # Test with empty arguments for tools that require parameters
            required_params = [p.name for p in tool.parameters if p.required]
            if required_params:
                result = await tool.safe_execute({})
                assert result.success is False
                assert "Missing required parameters" in result.error

    @pytest.mark.asyncio
    async def test_tool_mcp_format(self, mock_environment_manager):
        """Test MCP tool format generation."""
        tools = [
            CreateEnvironmentTool(mock_environment_manager),
            ListEnvironmentsTool(mock_environment_manager),
            SwitchEnvironmentTool(mock_environment_manager),
            DeleteEnvironmentTool(mock_environment_manager)
        ]
        
        for tool in tools:
            mcp_tool = tool.to_mcp_tool()
            
            # Check required MCP fields
            assert "name" in mcp_tool
            assert "description" in mcp_tool
            assert "inputSchema" in mcp_tool
            
            # Check schema structure
            schema = mcp_tool["inputSchema"]
            assert schema["type"] == "object"
            assert "properties" in schema
            
            # Check required parameters are in schema
            required_params = [p.name for p in tool.parameters if p.required]
            if required_params:
                assert "required" in schema
                for param in required_params:
                    assert param in schema["required"]