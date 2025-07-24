"""Tests for workspace management tools."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.rstudio_mcp.api_wrapper import ExecutionResult, RStudioAPIWrapper
from src.rstudio_mcp.tools.workspace_management_tools import (
    CleanWorkspaceTool,
    ListWorkspaceObjectsTool,
    LoadWorkspaceTool,
    SaveWorkspaceTool,
)


@pytest.fixture
def mock_api_wrapper():
    """Create a mock API wrapper for testing."""
    api = Mock(spec=RStudioAPIWrapper)
    api.execute_r_code = AsyncMock()
    return api


@pytest.fixture
def temp_workspace_file():
    """Create a temporary workspace file for testing."""
    with tempfile.NamedTemporaryFile(suffix='.RData', delete=False) as f:
        temp_path = f.name
    yield temp_path
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


class TestSaveWorkspaceTool:
    """Tests for SaveWorkspaceTool."""
    
    @pytest.fixture
    def save_tool(self, mock_api_wrapper):
        """Create SaveWorkspaceTool instance."""
        return SaveWorkspaceTool(mock_api_wrapper)
    
    def test_tool_properties(self, save_tool):
        """Test tool properties."""
        assert save_tool.name == "save_workspace"
        assert "保存当前工作空间状态" in save_tool.description
        
        params = {p.name: p for p in save_tool.parameters}
        assert "file_path" in params
        assert params["file_path"].required is True
        assert "include_hidden" in params
        assert "compress" in params
        assert "overwrite" in params
    
    @pytest.mark.asyncio
    async def test_save_workspace_success(self, save_tool, temp_workspace_file):
        """Test successful workspace save."""
        # Setup mock
        save_tool.api.execute_r_code.return_value = ExecutionResult(
            success=True,
            output="Workspace saved successfully\nObjects saved: 5\nFile size: 1024 bytes\n"
        )
        
        # Execute tool
        result = await save_tool.execute({
            "file_path": temp_workspace_file,
            "include_hidden": False,
            "compress": True,
            "overwrite": True
        })
        
        # Verify result
        assert result.success is True
        assert temp_workspace_file in result.content[0]["text"]
        assert "成功保存" in result.content[0]["text"]
        
        # Verify API call
        save_tool.api.execute_r_code.assert_called()
        # Check the first call (save operation)
        first_call_args = save_tool.api.execute_r_code.call_args_list[0][0]
        assert temp_workspace_file in first_call_args[0]
        assert "save(" in first_call_args[0]
    
    @pytest.mark.asyncio
    async def test_save_workspace_with_hidden_objects(self, save_tool, temp_workspace_file):
        """Test saving workspace with hidden objects."""
        save_tool.api.execute_r_code.return_value = ExecutionResult(
            success=True,
            output="Workspace saved successfully\n"
        )
        
        result = await save_tool.execute({
            "file_path": temp_workspace_file,
            "include_hidden": True,
            "overwrite": True  # Add overwrite to handle existing temp file
        })
        
        assert result.success is True
        
        # Check that hidden objects are included in R code
        call_args = save_tool.api.execute_r_code.call_args[0]
        assert "ls(all.names = TRUE)" in call_args[0]
    
    @pytest.mark.asyncio
    async def test_save_workspace_file_exists_no_overwrite(self, save_tool):
        """Test save when file exists and overwrite is False."""
        # Create existing file
        with tempfile.NamedTemporaryFile(suffix='.RData', delete=False) as f:
            existing_file = f.name
        
        try:
            result = await save_tool.execute({
                "file_path": existing_file,
                "overwrite": False
            })
            
            assert result.success is False
            assert "已存在" in result.error
        finally:
            Path(existing_file).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_save_workspace_r_error(self, save_tool):
        """Test save workspace with R execution error."""
        save_tool.api.execute_r_code.return_value = ExecutionResult(
            success=False,
            error="R error occurred"
        )
        
        # Use a non-existing file path to avoid file existence check
        result = await save_tool.execute({
            "file_path": "/tmp/nonexistent_dir/test_workspace.RData",
            "overwrite": True
        })
        
        assert result.success is False
        assert "保存工作空间失败" in result.error
    
    @pytest.mark.asyncio
    async def test_save_workspace_auto_extension(self, save_tool):
        """Test automatic .RData extension addition."""
        save_tool.api.execute_r_code.return_value = ExecutionResult(
            success=True,
            output="Workspace saved successfully\n"
        )
        
        result = await save_tool.execute({
            "file_path": "/tmp/test_workspace",  # No extension
            "overwrite": True
        })
        
        # Should succeed and add .RData extension
        call_args = save_tool.api.execute_r_code.call_args[0]
        assert "/tmp/test_workspace.RData" in call_args[0]


class TestLoadWorkspaceTool:
    """Tests for LoadWorkspaceTool."""
    
    @pytest.fixture
    def load_tool(self, mock_api_wrapper):
        """Create LoadWorkspaceTool instance."""
        return LoadWorkspaceTool(mock_api_wrapper)
    
    def test_tool_properties(self, load_tool):
        """Test tool properties."""
        assert load_tool.name == "load_workspace"
        assert "从文件恢复工作空间状态" in load_tool.description
        
        params = {p.name: p for p in load_tool.parameters}
        assert "file_path" in params
        assert params["file_path"].required is True
        assert "clear_current" in params
        assert "verbose" in params
    
    @pytest.mark.asyncio
    async def test_load_workspace_success(self, load_tool):
        """Test successful workspace load."""
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix='.RData', delete=False) as f:
            temp_file = f.name
        
        try:
            # Setup mocks
            load_tool.api.execute_r_code.side_effect = [
                # Current objects query
                ExecutionResult(success=True, output="obj1 obj2"),
                # Load workspace
                ExecutionResult(
                    success=True,
                    output="Workspace loaded successfully\nObjects loaded: 3\nObject names: x, y, z\n"
                ),
                # Object info query
                ExecutionResult(
                    success=True,
                    output='{"x": {"name": "x", "class": "numeric", "type": "double", "size": 56}}'
                )
            ]
            
            result = await load_tool.execute({
                "file_path": temp_file,
                "clear_current": False,
                "verbose": True
            })
            
            assert result.success is True
            assert "成功从文件加载" in result.content[0]["text"]
            assert temp_file in result.content[0]["text"]
            
        finally:
            Path(temp_file).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_load_workspace_file_not_exists(self, load_tool):
        """Test load workspace when file doesn't exist."""
        result = await load_tool.execute({
            "file_path": "/nonexistent/file.RData"
        })
        
        assert result.success is False
        assert "文件不存在" in result.error
    
    @pytest.mark.asyncio
    async def test_load_workspace_with_clear_current(self, load_tool):
        """Test loading workspace with clearing current workspace."""
        with tempfile.NamedTemporaryFile(suffix='.RData', delete=False) as f:
            temp_file = f.name
        
        try:
            load_tool.api.execute_r_code.side_effect = [
                ExecutionResult(success=True, output=""),  # Current objects
                ExecutionResult(success=True, output="Workspace loaded successfully\n"),  # Load
                ExecutionResult(success=True, output='{}')  # Object info
            ]
            
            result = await load_tool.execute({
                "file_path": temp_file,
                "clear_current": True
            })
            
            assert result.success is True
            
            # Check that clear command is in R code
            call_args = load_tool.api.execute_r_code.call_args_list[1][0]
            assert "rm(list = ls())" in call_args[0]
            
        finally:
            Path(temp_file).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_load_workspace_r_error(self, load_tool):
        """Test load workspace with R execution error."""
        with tempfile.NamedTemporaryFile(suffix='.RData', delete=False) as f:
            temp_file = f.name
        
        try:
            load_tool.api.execute_r_code.side_effect = [
                ExecutionResult(success=True, output=""),  # Current objects
                ExecutionResult(success=False, error="Load failed")  # Load error
            ]
            
            result = await load_tool.execute({
                "file_path": temp_file
            })
            
            assert result.success is False
            assert "加载工作空间失败" in result.error
            
        finally:
            Path(temp_file).unlink(missing_ok=True)


class TestListWorkspaceObjectsTool:
    """Tests for ListWorkspaceObjectsTool."""
    
    @pytest.fixture
    def list_tool(self, mock_api_wrapper):
        """Create ListWorkspaceObjectsTool instance."""
        return ListWorkspaceObjectsTool(mock_api_wrapper)
    
    def test_tool_properties(self, list_tool):
        """Test tool properties."""
        assert list_tool.name == "list_workspace_objects"
        assert "显示当前工作空间中的所有对象" in list_tool.description
        
        params = {p.name: p for p in list_tool.parameters}
        assert "include_hidden" in params
        assert "sort_by" in params
        assert "include_details" in params
        assert "filter_class" in params
        
        # Check enum values for sort_by
        sort_param = params["sort_by"]
        assert "name" in sort_param.enum
        assert "size" in sort_param.enum
    
    @pytest.mark.asyncio
    async def test_list_objects_with_details(self, list_tool):
        """Test listing objects with detailed information."""
        mock_output = '''工作空间对象总数: 2

对象列表:
  x: numeric [100] (0.001 MB)
  y: data.frame [10 x 3] (0.002 MB)

{"x": {"name": "x", "class": "numeric", "type": "double", "size": 800}, "y": {"name": "y", "class": "data.frame", "type": "list", "size": 2048}}'''
        
        list_tool.api.execute_r_code.return_value = ExecutionResult(
            success=True,
            output=mock_output
        )
        
        result = await list_tool.execute({
            "include_details": True,
            "sort_by": "name"
        })
        
        assert result.success is True
        assert "工作空间对象列表" in result.content[0]["text"]
        assert "工作空间对象总数: 2" in result.content[1]["text"]
        
        # Check metadata
        assert "objects" in result.metadata
        assert result.metadata["object_count"] == 2
    
    @pytest.mark.asyncio
    async def test_list_objects_empty_workspace(self, list_tool):
        """Test listing objects in empty workspace."""
        list_tool.api.execute_r_code.return_value = ExecutionResult(
            success=True,
            output="工作空间为空\n{}"
        )
        
        result = await list_tool.execute({})
        
        assert result.success is True
        assert "工作空间为空" in result.content[1]["text"]
    
    @pytest.mark.asyncio
    async def test_list_objects_with_hidden(self, list_tool):
        """Test listing objects including hidden ones."""
        list_tool.api.execute_r_code.return_value = ExecutionResult(
            success=True,
            output="工作空间对象总数: 1\n{}"
        )
        
        result = await list_tool.execute({
            "include_hidden": True
        })
        
        assert result.success is True
        
        # Check that hidden objects are included in R code
        call_args = list_tool.api.execute_r_code.call_args[0]
        assert "ls(all.names = TRUE)" in call_args[0]
    
    @pytest.mark.asyncio
    async def test_list_objects_with_filter(self, list_tool):
        """Test listing objects with class filter."""
        list_tool.api.execute_r_code.return_value = ExecutionResult(
            success=True,
            output="工作空间对象总数: 1\n{}"
        )
        
        result = await list_tool.execute({
            "filter_class": "data.frame"
        })
        
        assert result.success is True
        
        # Check that filter is applied in R code
        call_args = list_tool.api.execute_r_code.call_args[0]
        assert 'x$class == "data.frame"' in call_args[0]
    
    @pytest.mark.asyncio
    async def test_list_objects_sort_by_size(self, list_tool):
        """Test listing objects sorted by size."""
        list_tool.api.execute_r_code.return_value = ExecutionResult(
            success=True,
            output="工作空间对象总数: 2\n{}"
        )
        
        result = await list_tool.execute({
            "sort_by": "size"
        })
        
        assert result.success is True
        
        # Check that sorting is applied in R code
        call_args = list_tool.api.execute_r_code.call_args[0]
        assert 'sort_key <- "size"' in call_args[0]
        assert "decreasing = TRUE" in call_args[0]
    
    @pytest.mark.asyncio
    async def test_list_objects_r_error(self, list_tool):
        """Test list objects with R execution error."""
        list_tool.api.execute_r_code.return_value = ExecutionResult(
            success=False,
            error="R error occurred"
        )
        
        result = await list_tool.execute({})
        
        assert result.success is False
        assert "列出工作空间对象失败" in result.error


class TestCleanWorkspaceTool:
    """Tests for CleanWorkspaceTool."""
    
    @pytest.fixture
    def clean_tool(self, mock_api_wrapper):
        """Create CleanWorkspaceTool instance."""
        return CleanWorkspaceTool(mock_api_wrapper)
    
    def test_tool_properties(self, clean_tool):
        """Test tool properties."""
        assert clean_tool.name == "clean_workspace"
        assert "清理和优化工作空间" in clean_tool.description
        
        params = {p.name: p for p in clean_tool.parameters}
        assert "action" in params
        assert params["action"].required is True
        
        # Check enum values for action
        action_param = params["action"]
        expected_actions = ["remove_objects", "garbage_collect", "clear_all", "remove_large", "remove_by_class"]
        for action in expected_actions:
            assert action in action_param.enum
    
    @pytest.mark.asyncio
    async def test_garbage_collect(self, clean_tool):
        """Test garbage collection action."""
        clean_tool.api.execute_r_code.return_value = ExecutionResult(
            success=True,
            output="垃圾回收完成\n回收前内存使用:\n  used (Mb) gc trigger\n回收后内存使用:\n  used (Mb) gc trigger\n"
        )
        
        result = await clean_tool.execute({
            "action": "garbage_collect"
        })
        
        assert result.success is True
        assert "垃圾回收完成" in result.content[1]["text"]
        
        # Check R code contains gc()
        call_args = clean_tool.api.execute_r_code.call_args[0]
        assert "gc()" in call_args[0]
    
    @pytest.mark.asyncio
    async def test_clear_all_without_confirm(self, clean_tool):
        """Test clear all action without confirmation."""
        result = await clean_tool.execute({
            "action": "clear_all",
            "confirm": False
        })
        
        assert result.success is False
        assert "confirm=true" in result.error
    
    @pytest.mark.asyncio
    async def test_clear_all_with_confirm(self, clean_tool):
        """Test clear all action with confirmation."""
        clean_tool.api.execute_r_code.return_value = ExecutionResult(
            success=True,
            output="已清空所有工作空间对象\n删除对象数量: 5\n"
        )
        
        result = await clean_tool.execute({
            "action": "clear_all",
            "confirm": True
        })
        
        assert result.success is True
        assert "清理操作 'clear_all' 完成" in result.content[0]["text"]
        
        # Check R code contains rm(list = ls())
        call_args = clean_tool.api.execute_r_code.call_args[0]
        assert "rm(list = ls())" in call_args[0]
    
    @pytest.mark.asyncio
    async def test_remove_objects(self, clean_tool):
        """Test remove specific objects action."""
        clean_tool.api.execute_r_code.return_value = ExecutionResult(
            success=True,
            output="已删除对象: obj1, obj2\n"
        )
        
        result = await clean_tool.execute({
            "action": "remove_objects",
            "object_names": ["obj1", "obj2"],
            "confirm": True
        })
        
        assert result.success is True
        assert "已删除对象: obj1, obj2" in result.content[1]["text"]
        
        # Check R code contains object names
        call_args = clean_tool.api.execute_r_code.call_args[0]
        assert '"obj1"' in call_args[0]
        assert '"obj2"' in call_args[0]
    
    @pytest.mark.asyncio
    async def test_remove_objects_missing_names(self, clean_tool):
        """Test remove objects without specifying names."""
        result = await clean_tool.execute({
            "action": "remove_objects",
            "confirm": True
        })
        
        assert result.success is False
        assert "需要指定object_names参数" in result.error
    
    @pytest.mark.asyncio
    async def test_remove_large_objects(self, clean_tool):
        """Test remove large objects action."""
        clean_tool.api.execute_r_code.return_value = ExecutionResult(
            success=True,
            output="已删除大对象 (>10MB):\n  large_obj: 15.5MB\n"
        )
        
        result = await clean_tool.execute({
            "action": "remove_large",
            "size_threshold_mb": 10.0,
            "confirm": True
        })
        
        assert result.success is True
        assert "已删除大对象" in result.content[1]["text"]
        
        # Check R code contains size threshold
        call_args = clean_tool.api.execute_r_code.call_args[0]
        assert "10.0 * 1024 * 1024" in call_args[0]
    
    @pytest.mark.asyncio
    async def test_remove_by_class(self, clean_tool):
        """Test remove objects by class action."""
        clean_tool.api.execute_r_code.return_value = ExecutionResult(
            success=True,
            output="已删除类型为 'data.frame' 的对象:\n  df1, df2\n"
        )
        
        result = await clean_tool.execute({
            "action": "remove_by_class",
            "object_class": "data.frame",
            "confirm": True
        })
        
        assert result.success is True
        assert "已删除类型为 'data.frame' 的对象" in result.content[1]["text"]
        
        # Check R code contains class filter
        call_args = clean_tool.api.execute_r_code.call_args[0]
        assert 'class(obj)[1] == "data.frame"' in call_args[0]
    
    @pytest.mark.asyncio
    async def test_remove_by_class_missing_class(self, clean_tool):
        """Test remove by class without specifying class."""
        result = await clean_tool.execute({
            "action": "remove_by_class",
            "confirm": True
        })
        
        assert result.success is False
        assert "需要指定object_class参数" in result.error
    
    @pytest.mark.asyncio
    async def test_unknown_action(self, clean_tool):
        """Test unknown cleaning action."""
        result = await clean_tool.execute({
            "action": "unknown_action",
            "confirm": True
        })
        
        assert result.success is False
        assert "未知的清理操作" in result.error
    
    @pytest.mark.asyncio
    async def test_clean_workspace_r_error(self, clean_tool):
        """Test clean workspace with R execution error."""
        clean_tool.api.execute_r_code.return_value = ExecutionResult(
            success=False,
            error="R error occurred"
        )
        
        result = await clean_tool.execute({
            "action": "garbage_collect"
        })
        
        assert result.success is False
        assert "工作空间清理失败" in result.error


@pytest.mark.asyncio
async def test_tool_integration():
    """Test integration between workspace management tools."""
    # This test demonstrates how the tools work together
    api = Mock(spec=RStudioAPIWrapper)
    api.execute_r_code = AsyncMock()
    
    # Create tools
    save_tool = SaveWorkspaceTool(api)
    load_tool = LoadWorkspaceTool(api)
    list_tool = ListWorkspaceObjectsTool(api)
    clean_tool = CleanWorkspaceTool(api)
    
    # Test workflow: list -> save -> clean -> load -> list
    
    # 1. List initial objects
    api.execute_r_code.return_value = ExecutionResult(
        success=True,
        output="工作空间对象总数: 2\n{}"
    )
    
    list_result = await list_tool.execute({})
    assert list_result.success is True
    
    # 2. Save workspace
    with tempfile.NamedTemporaryFile(suffix='.RData', delete=False) as f:
        temp_file = f.name
    
    try:
        api.execute_r_code.return_value = ExecutionResult(
            success=True,
            output="Workspace saved successfully\n"
        )
        
        save_result = await save_tool.execute({
            "file_path": temp_file,
            "overwrite": True
        })
        assert save_result.success is True
        
        # 3. Clean workspace
        api.execute_r_code.return_value = ExecutionResult(
            success=True,
            output="已清空所有工作空间对象\n"
        )
        
        clean_result = await clean_tool.execute({
            "action": "clear_all",
            "confirm": True
        })
        assert clean_result.success is True
        
        # 4. Load workspace back
        api.execute_r_code.side_effect = [
            ExecutionResult(success=True, output=""),  # Current objects
            ExecutionResult(success=True, output="Workspace loaded successfully\n"),  # Load
            ExecutionResult(success=True, output='{}')  # Object info
        ]
        
        load_result = await load_tool.execute({
            "file_path": temp_file
        })
        assert load_result.success is True
        
    finally:
        Path(temp_file).unlink(missing_ok=True)