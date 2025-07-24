"""Tests for code execution tools."""

import asyncio
import json
import tempfile
from datetime import datetime
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


class TestExecutionHistory:
    """Test execution history management."""

    def test_init(self):
        """Test initialization."""
        history = ExecutionHistory(max_entries=100)
        assert history.max_entries == 100
        assert len(history.entries) == 0

    def test_add_entry(self):
        """Test adding execution entry."""
        history = ExecutionHistory()
        
        result = ExecutionResult(
            success=True,
            output="[1] 42",
            execution_time=0.1
        )
        
        entry_id = history.add_entry("1 + 1", result, "test_env")
        
        assert entry_id.startswith("exec_")
        assert len(history.entries) == 1
        
        entry = history.entries[0]
        assert entry["id"] == entry_id
        assert entry["code"] == "1 + 1"
        assert entry["environment"] == "test_env"
        assert entry["success"] is True
        assert entry["output"] == "[1] 42"
        assert entry["execution_time"] == 0.1

    def test_add_entry_with_error(self):
        """Test adding entry with execution error."""
        history = ExecutionHistory()
        
        result = ExecutionResult(
            success=False,
            error="Syntax error",
            execution_time=0.05
        )
        
        entry_id = history.add_entry("invalid code", result)
        
        entry = history.entries[0]
        assert entry["success"] is False
        assert entry["error"] == "Syntax error"

    def test_max_entries_limit(self):
        """Test maximum entries limit."""
        history = ExecutionHistory(max_entries=3)
        
        result = ExecutionResult(success=True, output="test")
        
        # Add 5 entries
        for i in range(5):
            history.add_entry(f"code_{i}", result)
        
        # Should only keep last 3
        assert len(history.entries) == 3
        assert history.entries[0]["code"] == "code_2"
        assert history.entries[2]["code"] == "code_4"

    def test_get_entry(self):
        """Test getting entry by ID."""
        history = ExecutionHistory()
        result = ExecutionResult(success=True, output="test")
        
        entry_id = history.add_entry("test code", result)
        
        entry = history.get_entry(entry_id)
        assert entry is not None
        assert entry["id"] == entry_id
        assert entry["code"] == "test code"
        
        # Test non-existent entry
        assert history.get_entry("nonexistent") is None

    def test_get_recent_entries(self):
        """Test getting recent entries."""
        history = ExecutionHistory()
        result = ExecutionResult(success=True, output="test")
        
        # Add 5 entries
        for i in range(5):
            history.add_entry(f"code_{i}", result)
        
        # Get last 3
        recent = history.get_recent_entries(3)
        assert len(recent) == 3
        assert recent[0]["code"] == "code_2"
        assert recent[2]["code"] == "code_4"
        
        # Get more than available
        all_entries = history.get_recent_entries(10)
        assert len(all_entries) == 5

    def test_clear_history(self):
        """Test clearing history."""
        history = ExecutionHistory()
        result = ExecutionResult(success=True, output="test")
        
        # Add entries
        for i in range(3):
            history.add_entry(f"code_{i}", result)
        
        assert len(history.entries) == 3
        
        cleared_count = history.clear_history()
        assert cleared_count == 3
        assert len(history.entries) == 0


class TestExecuteRCodeTool:
    """Test R code execution tool."""

    @pytest.fixture
    def mock_api_wrapper(self):
        """Mock API wrapper."""
        api = Mock(spec=RStudioAPIWrapper)
        api.execute_r_code = AsyncMock()
        return api

    @pytest.fixture
    def mock_env_manager(self):
        """Mock environment manager."""
        env_manager = Mock(spec=EnvironmentManager)
        env_manager.get_environment = AsyncMock()
        env_manager.switch_environment = AsyncMock()
        return env_manager

    @pytest.fixture
    def execute_tool(self, mock_api_wrapper, mock_env_manager):
        """Create execute R code tool."""
        return ExecuteRCodeTool(mock_api_wrapper, mock_env_manager)

    def test_tool_properties(self, execute_tool):
        """Test tool properties."""
        assert execute_tool.name == "execute_r_code"
        assert "执行R代码" in execute_tool.description
        
        params = {p.name: p for p in execute_tool.parameters}
        assert "code" in params
        assert params["code"].required is True
        assert "environment" in params
        assert "timeout" in params
        assert params["timeout"].default == 300

    @pytest.mark.asyncio
    async def test_execute_simple_code(self, execute_tool, mock_api_wrapper):
        """Test executing simple R code."""
        # Setup mock
        mock_result = ExecutionResult(
            success=True,
            output="[1] 2",
            execution_time=0.1
        )
        mock_api_wrapper.execute_r_code.return_value = mock_result
        
        # Execute
        arguments = {"code": "1 + 1"}
        result = await execute_tool.execute(arguments)
        
        # Verify
        assert result.success is True
        assert "R代码执行成功" in result.content[0]["text"]
        assert "[1] 2" in result.content[1]["text"]
        
        # Verify API call
        mock_api_wrapper.execute_r_code.assert_called_once_with(
            code="1 + 1",
            capture_output=True,
            capture_plots=True,
            timeout=300
        )

    @pytest.mark.asyncio
    async def test_execute_with_environment(self, execute_tool, mock_api_wrapper, mock_env_manager):
        """Test executing code in specific environment."""
        # Setup mocks
        mock_env = Environment(
            name="test_env",
            r_version="4.3.0",
            path="/tmp/test_env"
        )
        mock_env_manager.get_environment.return_value = mock_env
        mock_env_manager.switch_environment.return_value = True
        
        mock_result = ExecutionResult(
            success=True,
            output="[1] 42",
            execution_time=0.2
        )
        mock_api_wrapper.execute_r_code.return_value = mock_result
        
        # Execute
        arguments = {
            "code": "6 * 7",
            "environment": "test_env"
        }
        result = await execute_tool.execute(arguments)
        
        # Verify
        assert result.success is True
        assert "test_env" in result.content[0]["text"]
        
        # Verify environment operations
        mock_env_manager.get_environment.assert_called_once_with("test_env")
        mock_env_manager.switch_environment.assert_called_once_with("test_env")

    @pytest.mark.asyncio
    async def test_execute_with_nonexistent_environment(self, execute_tool, mock_env_manager):
        """Test executing code with non-existent environment."""
        # Setup mock
        mock_env_manager.get_environment.return_value = None
        
        # Execute
        arguments = {
            "code": "1 + 1",
            "environment": "nonexistent"
        }
        result = await execute_tool.execute(arguments)
        
        # Verify
        assert result.success is False
        assert "不存在" in result.error

    @pytest.mark.asyncio
    async def test_execute_with_plots(self, execute_tool, mock_api_wrapper):
        """Test executing code that generates plots."""
        # Create temporary plot file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake_plot_data")
            plot_path = f.name
        
        try:
            # Setup mock
            mock_result = ExecutionResult(
                success=True,
                output="Plot created",
                plots=[plot_path],
                execution_time=0.5
            )
            mock_api_wrapper.execute_r_code.return_value = mock_result
            
            # Execute
            arguments = {"code": "plot(1:10)"}
            result = await execute_tool.execute(arguments)
            
            # Verify
            assert result.success is True
            assert any("image" in content.get("type", "") for content in result.content)
            assert "生成图表" in str(result.content)
            
        finally:
            # Cleanup
            Path(plot_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_execute_with_error(self, execute_tool, mock_api_wrapper):
        """Test executing code that fails."""
        # Setup mock
        mock_result = ExecutionResult(
            success=False,
            error="object 'x' not found",
            execution_time=0.1
        )
        mock_api_wrapper.execute_r_code.return_value = mock_result
        
        # Execute
        arguments = {"code": "print(x)"}
        result = await execute_tool.execute(arguments)
        
        # Verify
        assert result.success is False
        assert "代码执行失败" in result.content[0]["text"]
        assert "object 'x' not found" in result.error

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, execute_tool, mock_api_wrapper):
        """Test executing code with timeout."""
        # Setup mock to raise timeout
        mock_api_wrapper.execute_r_code.side_effect = asyncio.TimeoutError()
        
        # Execute
        arguments = {
            "code": "Sys.sleep(10)",
            "timeout": 1
        }
        result = await execute_tool.execute(arguments)
        
        # Verify
        assert result.success is False
        assert "超时" in result.error

    @pytest.mark.asyncio
    async def test_execute_empty_code(self, execute_tool):
        """Test executing empty code."""
        arguments = {"code": ""}
        result = await execute_tool.execute(arguments)
        
        assert result.success is False
        assert "不能为空" in result.error

    @pytest.mark.asyncio
    async def test_execute_with_warnings(self, execute_tool, mock_api_wrapper):
        """Test executing code with warnings."""
        # Setup mock
        mock_result = ExecutionResult(
            success=True,
            output="[1] 1",
            warnings=["Warning: deprecated function"],
            execution_time=0.1
        )
        mock_api_wrapper.execute_r_code.return_value = mock_result
        
        # Execute
        arguments = {"code": "old_function()"}
        result = await execute_tool.execute(arguments)
        
        # Verify
        assert result.success is True
        assert "警告" in str(result.content)
        assert "deprecated function" in str(result.content)

    @pytest.mark.asyncio
    async def test_execute_history_tracking(self, execute_tool, mock_api_wrapper):
        """Test execution history tracking."""
        # Setup mock
        mock_result = ExecutionResult(
            success=True,
            output="[1] 3",
            execution_time=0.1
        )
        mock_api_wrapper.execute_r_code.return_value = mock_result
        
        # Execute
        arguments = {"code": "1 + 2", "save_to_history": True}
        result = await execute_tool.execute(arguments)
        
        # Verify history was saved
        assert result.success is True
        assert len(execute_tool.history.entries) == 1
        assert execute_tool.history.entries[0]["code"] == "1 + 2"
        assert "历史记录ID" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_execute_no_history(self, execute_tool, mock_api_wrapper):
        """Test executing without saving to history."""
        # Setup mock
        mock_result = ExecutionResult(
            success=True,
            output="[1] 4",
            execution_time=0.1
        )
        mock_api_wrapper.execute_r_code.return_value = mock_result
        
        # Execute
        arguments = {"code": "2 + 2", "save_to_history": False}
        result = await execute_tool.execute(arguments)
        
        # Verify no history was saved
        assert result.success is True
        assert len(execute_tool.history.entries) == 0

    def test_format_output(self, execute_tool):
        """Test output formatting."""
        # Test basic formatting
        formatted = execute_tool._format_output("[1] 42\n[2] 84")
        assert "```r" in formatted
        assert "[1] 42" in formatted
        assert "[2] 84" in formatted

    def test_format_execution_summary(self, execute_tool):
        """Test execution summary formatting."""
        result = ExecutionResult(
            success=True,
            output="test",
            execution_time=0.123,
            plots=["plot1.png"],
            warnings=["warning1"]
        )
        
        summary = execute_tool._format_execution_summary(
            result, "test_env", "exec_123", True
        )
        
        assert "✅ R代码执行成功" in summary
        assert "test_env" in summary
        assert "0.123秒" in summary
        assert "exec_123" in summary
        assert "1个" in summary  # plots
        assert "警告: 1个" in summary


class TestGetExecutionHistoryTool:
    """Test execution history retrieval tool."""

    @pytest.fixture
    def history_with_data(self):
        """Create history with test data."""
        history = ExecutionHistory()
        
        # Add test entries
        for i in range(5):
            result = ExecutionResult(
                success=i % 2 == 0,  # Alternate success/failure
                output=f"output_{i}",
                error=f"error_{i}" if i % 2 == 1 else None,
                execution_time=0.1 * i
            )
            history.add_entry(f"code_{i}", result, f"env_{i % 2}")
        
        return history

    @pytest.fixture
    def history_tool(self, history_with_data):
        """Create history tool."""
        return GetExecutionHistoryTool(history_with_data)

    def test_tool_properties(self, history_tool):
        """Test tool properties."""
        assert history_tool.name == "get_execution_history"
        assert "历史记录" in history_tool.description
        
        params = {p.name: p for p in history_tool.parameters}
        assert "limit" in params
        assert "entry_id" in params
        assert "environment" in params

    @pytest.mark.asyncio
    async def test_get_recent_history(self, history_tool):
        """Test getting recent history."""
        arguments = {"limit": 3}
        result = await history_tool.execute(arguments)
        
        assert result.success is True
        content = result.content[0]["text"]
        assert "执行历史记录" in content
        assert "共 3 条" in content

    @pytest.mark.asyncio
    async def test_get_specific_entry(self, history_tool, history_with_data):
        """Test getting specific entry by ID."""
        # Get an entry ID
        entry_id = history_with_data.entries[0]["id"]
        
        arguments = {"entry_id": entry_id}
        result = await history_tool.execute(arguments)
        
        assert result.success is True
        content = result.content[0]["text"]
        assert entry_id in content
        assert "执行记录" in content

    @pytest.mark.asyncio
    async def test_get_nonexistent_entry(self, history_tool):
        """Test getting non-existent entry."""
        arguments = {"entry_id": "nonexistent"}
        result = await history_tool.execute(arguments)
        
        assert result.success is True
        content = result.content[0]["text"]
        assert "未找到" in content

    @pytest.mark.asyncio
    async def test_filter_by_environment(self, history_tool):
        """Test filtering by environment."""
        arguments = {"environment": "env_0", "limit": 10}
        result = await history_tool.execute(arguments)
        
        assert result.success is True
        content = result.content[0]["text"]
        # Should contain entries from env_0 (entries 0, 2, 4)
        assert "env_0" in content

    @pytest.mark.asyncio
    async def test_include_code_and_output(self, history_tool):
        """Test including code and output."""
        arguments = {
            "limit": 1,
            "include_code": True,
            "include_output": True
        }
        result = await history_tool.execute(arguments)
        
        assert result.success is True
        content = result.content[0]["text"]
        assert "代码:" in content
        assert "输出:" in content
        assert "```r" in content

    @pytest.mark.asyncio
    async def test_empty_history(self):
        """Test with empty history."""
        empty_history = ExecutionHistory()
        tool = GetExecutionHistoryTool(empty_history)
        
        arguments = {"limit": 10}
        result = await tool.execute(arguments)
        
        assert result.success is True
        content = result.content[0]["text"]
        assert "未找到" in content

    def test_format_history_entry(self, history_tool, history_with_data):
        """Test formatting single history entry."""
        entry = history_with_data.entries[0]
        
        formatted = history_tool._format_history_entry(entry, True, True)
        
        assert entry["id"] in formatted
        assert entry["environment"] in formatted
        assert "代码:" in formatted
        assert "输出:" in formatted

    def test_format_history_list(self, history_tool, history_with_data):
        """Test formatting history list."""
        entries = history_with_data.entries[:3]
        
        formatted = history_tool._format_history_list(entries, False, False)
        
        assert "共 3 条" in formatted
        assert "1." in formatted
        assert "2." in formatted
        assert "3." in formatted


class TestClearExecutionHistoryTool:
    """Test execution history clearing tool."""

    @pytest.fixture
    def history_with_data(self):
        """Create history with test data."""
        history = ExecutionHistory()
        result = ExecutionResult(success=True, output="test")
        
        for i in range(3):
            history.add_entry(f"code_{i}", result)
        
        return history

    @pytest.fixture
    def clear_tool(self, history_with_data):
        """Create clear history tool."""
        return ClearExecutionHistoryTool(history_with_data)

    def test_tool_properties(self, clear_tool):
        """Test tool properties."""
        assert clear_tool.name == "clear_execution_history"
        assert "清除" in clear_tool.description
        
        params = {p.name: p for p in clear_tool.parameters}
        assert "confirm" in params
        assert params["confirm"].required is True

    @pytest.mark.asyncio
    async def test_clear_with_confirmation(self, clear_tool, history_with_data):
        """Test clearing history with confirmation."""
        # Verify history has entries
        assert len(history_with_data.entries) == 3
        
        arguments = {"confirm": True}
        result = await clear_tool.execute(arguments)
        
        assert result.success is True
        content = result.content[0]["text"]
        assert "已清除 3 条" in content
        assert len(history_with_data.entries) == 0

    @pytest.mark.asyncio
    async def test_clear_without_confirmation(self, clear_tool, history_with_data):
        """Test clearing history without confirmation."""
        arguments = {"confirm": False}
        result = await clear_tool.execute(arguments)
        
        assert result.success is False
        assert "confirm=true" in result.error
        # History should remain unchanged
        assert len(history_with_data.entries) == 3

    @pytest.mark.asyncio
    async def test_clear_empty_history(self):
        """Test clearing empty history."""
        empty_history = ExecutionHistory()
        tool = ClearExecutionHistoryTool(empty_history)
        
        arguments = {"confirm": True}
        result = await tool.execute(arguments)
        
        assert result.success is True
        content = result.content[0]["text"]
        assert "已清除 0 条" in content


@pytest.mark.asyncio
async def test_integration_execute_and_history():
    """Integration test for execute and history tools."""
    # Setup
    mock_api = Mock(spec=RStudioAPIWrapper)
    mock_env_manager = Mock(spec=EnvironmentManager)
    
    # Create tools
    execute_tool = ExecuteRCodeTool(mock_api, mock_env_manager)
    history_tool = GetExecutionHistoryTool(execute_tool.history)
    clear_tool = ClearExecutionHistoryTool(execute_tool.history)
    
    # Mock successful execution
    mock_result = ExecutionResult(
        success=True,
        output="[1] 42",
        execution_time=0.1
    )
    mock_api.execute_r_code.return_value = mock_result
    
    # Execute some code
    result1 = await execute_tool.execute({"code": "6 * 7"})
    assert result1.success is True
    
    # Check history
    history_result = await history_tool.execute({"limit": 1})
    assert history_result.success is True
    assert "6 * 7" in history_result.content[0]["text"]
    
    # Clear history
    clear_result = await clear_tool.execute({"confirm": True})
    assert clear_result.success is True
    
    # Verify history is empty
    empty_history = await history_tool.execute({"limit": 10})
    assert "未找到" in empty_history.content[0]["text"]