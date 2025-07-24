"""Integration tests for code execution tools."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.rstudio_mcp.api_wrapper import ExecutionResult, RStudioAPIWrapper
from src.rstudio_mcp.environment_manager import Environment, EnvironmentManager
from src.rstudio_mcp.tools.code_execution_tools import (
    ClearExecutionHistoryTool,
    ExecuteRCodeTool,
    ExecutionHistory,
    GetExecutionHistoryTool,
)
from src.rstudio_mcp.tools.manager import ToolManager


class TestCodeExecutionToolsIntegration:
    """Integration tests for code execution tools with tool manager."""

    @pytest.fixture
    def mock_api_wrapper(self):
        """Mock API wrapper."""
        api = Mock(spec=RStudioAPIWrapper)
        api.execute_r_code = AsyncMock()
        api.get_r_version = AsyncMock(return_value="4.3.0")
        return api

    @pytest.fixture
    def mock_env_manager(self):
        """Mock environment manager."""
        env_manager = Mock(spec=EnvironmentManager)
        env_manager.get_environment = AsyncMock()
        env_manager.switch_environment = AsyncMock()
        env_manager.list_environments = AsyncMock(return_value=[])
        return env_manager

    @pytest.fixture
    def tool_manager_with_code_tools(self, mock_api_wrapper, mock_env_manager):
        """Create tool manager with code execution tools."""
        manager = ToolManager()
        
        # Create shared execution history
        execution_history = ExecutionHistory()
        
        # Register code execution tools
        execute_tool = ExecuteRCodeTool(mock_api_wrapper, mock_env_manager)
        history_tool = GetExecutionHistoryTool(execution_history)
        clear_tool = ClearExecutionHistoryTool(execution_history)
        
        # Share the same history instance
        execute_tool.history = execution_history
        
        manager.register_tool(execute_tool)
        manager.register_tool(history_tool)
        manager.register_tool(clear_tool)
        
        return manager, execution_history

    @pytest.mark.asyncio
    async def test_tool_registration(self, tool_manager_with_code_tools):
        """Test that code execution tools are properly registered."""
        manager, _ = tool_manager_with_code_tools
        
        tools = manager.list_tools()
        assert "execute_r_code" in tools
        assert "get_execution_history" in tools
        assert "clear_execution_history" in tools

    @pytest.mark.asyncio
    async def test_tool_definitions(self, tool_manager_with_code_tools):
        """Test that tool definitions are properly generated."""
        manager, _ = tool_manager_with_code_tools
        
        definitions = manager.get_tool_definitions()
        tool_names = [d["name"] for d in definitions]
        
        assert "execute_r_code" in tool_names
        assert "get_execution_history" in tool_names
        assert "clear_execution_history" in tool_names
        
        # Check execute_r_code definition
        execute_def = next(d for d in definitions if d["name"] == "execute_r_code")
        assert "inputSchema" in execute_def
        assert "properties" in execute_def["inputSchema"]
        assert "code" in execute_def["inputSchema"]["properties"]

    @pytest.mark.asyncio
    async def test_execute_code_workflow(self, tool_manager_with_code_tools, mock_api_wrapper):
        """Test complete code execution workflow."""
        manager, history = tool_manager_with_code_tools
        
        # Setup mock execution result
        mock_result = ExecutionResult(
            success=True,
            output="[1] 42",
            execution_time=0.15,
            plots=[],
            warnings=[]
        )
        mock_api_wrapper.execute_r_code.return_value = mock_result
        
        # Execute R code
        execute_result = await manager.execute_tool("execute_r_code", {
            "code": "6 * 7",
            "save_to_history": True
        })
        
        assert execute_result.success is True
        assert "R代码执行成功" in execute_result.content[0]["text"]
        assert "[1] 42" in execute_result.content[1]["text"]
        
        # Verify history was saved
        assert len(history.entries) == 1
        assert history.entries[0]["code"] == "6 * 7"
        assert history.entries[0]["success"] is True

    @pytest.mark.asyncio
    async def test_history_retrieval_workflow(self, tool_manager_with_code_tools, mock_api_wrapper):
        """Test history retrieval workflow."""
        manager, history = tool_manager_with_code_tools
        
        # Setup and execute some code first
        mock_result = ExecutionResult(
            success=True,
            output="[1] 10",
            execution_time=0.1
        )
        mock_api_wrapper.execute_r_code.return_value = mock_result
        
        # Execute multiple R commands
        codes = ["2 + 3", "4 * 5", "sqrt(16)"]
        for code in codes:
            await manager.execute_tool("execute_r_code", {
                "code": code,
                "save_to_history": True
            })
        
        # Get execution history
        history_result = await manager.execute_tool("get_execution_history", {
            "limit": 2,
            "include_code": True
        })
        
        assert history_result.success is True
        content = history_result.content[0]["text"]
        assert "执行历史记录" in content
        assert "共 2 条" in content
        assert "sqrt(16)" in content  # Most recent
        assert "4 * 5" in content    # Second most recent

    @pytest.mark.asyncio
    async def test_clear_history_workflow(self, tool_manager_with_code_tools, mock_api_wrapper):
        """Test clear history workflow."""
        manager, history = tool_manager_with_code_tools
        
        # Setup and execute some code first
        mock_result = ExecutionResult(success=True, output="test")
        mock_api_wrapper.execute_r_code.return_value = mock_result
        
        await manager.execute_tool("execute_r_code", {
            "code": "1 + 1",
            "save_to_history": True
        })
        
        # Verify history has entries
        assert len(history.entries) == 1
        
        # Clear history
        clear_result = await manager.execute_tool("clear_execution_history", {
            "confirm": True
        })
        
        assert clear_result.success is True
        assert "已清除 1 条" in clear_result.content[0]["text"]
        assert len(history.entries) == 0

    @pytest.mark.asyncio
    async def test_error_handling_workflow(self, tool_manager_with_code_tools, mock_api_wrapper):
        """Test error handling in execution workflow."""
        manager, history = tool_manager_with_code_tools
        
        # Setup mock execution error
        mock_result = ExecutionResult(
            success=False,
            error="object 'undefined_var' not found",
            execution_time=0.05
        )
        mock_api_wrapper.execute_r_code.return_value = mock_result
        
        # Execute failing code
        execute_result = await manager.execute_tool("execute_r_code", {
            "code": "print(undefined_var)",
            "save_to_history": True
        })
        
        assert execute_result.success is False
        assert "代码执行失败" in execute_result.content[0]["text"]
        assert "undefined_var" in execute_result.error
        
        # Verify error was still saved to history
        assert len(history.entries) == 1
        assert history.entries[0]["success"] is False
        assert history.entries[0]["error"] == "object 'undefined_var' not found"

    @pytest.mark.asyncio
    async def test_environment_switching_workflow(self, tool_manager_with_code_tools, 
                                                 mock_api_wrapper, mock_env_manager):
        """Test environment switching in execution workflow."""
        manager, _ = tool_manager_with_code_tools
        
        # Setup environment mock
        test_env = Environment(
            name="test_env",
            r_version="4.3.0",
            path="/tmp/test_env"
        )
        mock_env_manager.get_environment.return_value = test_env
        mock_env_manager.switch_environment.return_value = True
        
        # Setup execution mock
        mock_result = ExecutionResult(
            success=True,
            output="Environment: test_env",
            execution_time=0.1
        )
        mock_api_wrapper.execute_r_code.return_value = mock_result
        
        # Execute code in specific environment
        execute_result = await manager.execute_tool("execute_r_code", {
            "code": "Sys.getenv('R_ENVIRON')",
            "environment": "test_env"
        })
        
        assert execute_result.success is True
        assert "test_env" in execute_result.content[0]["text"]
        
        # Verify environment operations were called
        mock_env_manager.get_environment.assert_called_once_with("test_env")
        mock_env_manager.switch_environment.assert_called_once_with("test_env")

    @pytest.mark.asyncio
    async def test_plot_generation_workflow(self, tool_manager_with_code_tools, mock_api_wrapper):
        """Test plot generation workflow."""
        manager, _ = tool_manager_with_code_tools
        
        # Create temporary plot file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake_plot_data_for_testing")
            plot_path = f.name
        
        try:
            # Setup mock with plot
            mock_result = ExecutionResult(
                success=True,
                output="Plot generated",
                plots=[plot_path],
                execution_time=0.3
            )
            mock_api_wrapper.execute_r_code.return_value = mock_result
            
            # Execute plotting code
            execute_result = await manager.execute_tool("execute_r_code", {
                "code": "plot(1:10, 1:10)",
                "capture_plots": True
            })
            
            assert execute_result.success is True
            
            # Check for image content
            has_image = any(
                content.get("type") == "image" 
                for content in execute_result.content
            )
            assert has_image
            
            # Check metadata
            assert execute_result.metadata["plot_count"] == 1
            
        finally:
            # Cleanup
            Path(plot_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_timeout_handling_workflow(self, tool_manager_with_code_tools, mock_api_wrapper):
        """Test timeout handling workflow."""
        manager, _ = tool_manager_with_code_tools
        
        # Setup timeout mock
        mock_api_wrapper.execute_r_code.side_effect = asyncio.TimeoutError()
        
        # Execute code with short timeout
        execute_result = await manager.execute_tool("execute_r_code", {
            "code": "Sys.sleep(10)",
            "timeout": 1
        })
        
        assert execute_result.success is False
        assert "超时" in execute_result.error

    @pytest.mark.asyncio
    async def test_argument_validation_workflow(self, tool_manager_with_code_tools):
        """Test argument validation workflow."""
        manager, _ = tool_manager_with_code_tools
        
        # Test missing required argument
        execute_result = await manager.execute_tool("execute_r_code", {})
        
        assert execute_result.success is False
        assert "Missing required parameters" in execute_result.error

    @pytest.mark.asyncio
    async def test_concurrent_executions(self, tool_manager_with_code_tools, mock_api_wrapper):
        """Test concurrent code executions."""
        manager, history = tool_manager_with_code_tools
        
        # Setup mock
        mock_result = ExecutionResult(
            success=True,
            output="[1] result",
            execution_time=0.1
        )
        mock_api_wrapper.execute_r_code.return_value = mock_result
        
        # Execute multiple codes concurrently
        tasks = []
        for i in range(3):
            task = manager.execute_tool("execute_r_code", {
                "code": f"result_{i} <- {i} + 1",
                "save_to_history": True
            })
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(r.success for r in results)
        
        # All should be saved to history
        assert len(history.entries) == 3

    @pytest.mark.asyncio
    async def test_tool_cleanup(self, tool_manager_with_code_tools):
        """Test tool cleanup workflow."""
        manager, _ = tool_manager_with_code_tools
        
        # Test cleanup doesn't raise errors
        await manager.cleanup()
        
        # Tools should still be accessible after cleanup
        tools = manager.list_tools()
        assert "execute_r_code" in tools

    @pytest.mark.asyncio
    async def test_history_persistence_across_executions(self, tool_manager_with_code_tools, 
                                                        mock_api_wrapper):
        """Test that history persists across multiple executions."""
        manager, history = tool_manager_with_code_tools
        
        # Setup mock
        mock_result = ExecutionResult(success=True, output="test")
        mock_api_wrapper.execute_r_code.return_value = mock_result
        
        # Execute code multiple times
        codes = ["a <- 1", "b <- 2", "c <- a + b"]
        
        for code in codes:
            result = await manager.execute_tool("execute_r_code", {
                "code": code,
                "save_to_history": True
            })
            assert result.success is True
        
        # Check that all executions are in history
        assert len(history.entries) == 3
        
        # Get history and verify all entries are there
        history_result = await manager.execute_tool("get_execution_history", {
            "limit": 10
        })
        
        content = history_result.content[0]["text"]
        assert "共 3 条" in content
        
        # Verify chronological order (most recent first in display)
        for code in codes:
            assert code in content

    @pytest.mark.asyncio
    async def test_shared_history_between_tools(self, mock_api_wrapper, mock_env_manager):
        """Test that history is properly shared between tools."""
        # Create shared history
        shared_history = ExecutionHistory()
        
        # Create tools with shared history
        execute_tool = ExecuteRCodeTool(mock_api_wrapper, mock_env_manager)
        execute_tool.history = shared_history
        
        history_tool = GetExecutionHistoryTool(shared_history)
        clear_tool = ClearExecutionHistoryTool(shared_history)
        
        # Setup mock
        mock_result = ExecutionResult(success=True, output="test")
        mock_api_wrapper.execute_r_code.return_value = mock_result
        
        # Execute code
        await execute_tool.execute({"code": "test_code", "save_to_history": True})
        
        # Verify history tool sees the entry
        history_result = await history_tool.execute({"limit": 1})
        assert "test_code" in history_result.content[0]["text"]
        
        # Clear history
        await clear_tool.execute({"confirm": True})
        
        # Verify execute tool's history is also cleared
        assert len(execute_tool.history.entries) == 0