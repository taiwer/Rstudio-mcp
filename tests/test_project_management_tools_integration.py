"""Integration tests for project management tools."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.rstudio_mcp.api_wrapper import ExecutionResult, RStudioAPIWrapper
from src.rstudio_mcp.tools.manager import ToolManager
from src.rstudio_mcp.tools.project_management_tools import (
    CreateProjectTool,
    GetProjectInfoTool,
    OpenProjectTool,
)


@pytest.fixture
def mock_api_wrapper():
    """Create a mock API wrapper for integration tests."""
    api = Mock(spec=RStudioAPIWrapper)
    api.execute_r_code = AsyncMock()
    api.check_rstudio_available = AsyncMock(return_value=True)
    api.get_active_project = AsyncMock(return_value=None)
    return api


@pytest.fixture
def tool_manager(mock_api_wrapper):
    """Create a tool manager with project management tools."""
    manager = ToolManager()
    
    # Register project management tools
    manager.register_tool(CreateProjectTool(mock_api_wrapper))
    manager.register_tool(OpenProjectTool(mock_api_wrapper))
    manager.register_tool(GetProjectInfoTool(mock_api_wrapper))
    
    return manager


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for integration testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


class TestProjectManagementIntegration:
    """Integration tests for project management workflow."""
    
    @pytest.mark.asyncio
    async def test_complete_project_workflow(self, tool_manager, temp_workspace, mock_api_wrapper):
        """Test complete project creation and management workflow."""
        # Step 1: Create a new project
        create_result = await tool_manager.execute_tool("create_project", {
            "name": "test_integration_project",
            "path": str(temp_workspace),
            "type": "default",
            "git": True
        })
        
        assert create_result.success
        assert "成功创建项目" in create_result.content[0]["text"]
        
        project_path = temp_workspace / "test_integration_project"
        assert project_path.exists()
        assert (project_path / "test_integration_project.Rproj").exists()
        
        # Step 2: Get project information
        info_result = await tool_manager.execute_tool("get_project_info", {
            "project_path": str(project_path)
        })
        
        assert info_result.success
        project_info = info_result.metadata
        assert project_info["name"] == "test_integration_project"
        assert project_info["type"] == "default"
        assert project_info["git_enabled"] is True
        
        # Step 3: Open the project (mock RStudio API call)
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=True, output="Project opened successfully"
        )
        
        open_result = await tool_manager.execute_tool("open_project", {
            "project_path": str(project_path)
        })
        
        assert open_result.success
        assert "成功打开项目" in open_result.content[0]["text"]
        mock_api_wrapper.execute_r_code.assert_called()
    
    @pytest.mark.asyncio
    async def test_shiny_project_workflow(self, tool_manager, temp_workspace):
        """Test Shiny project creation and inspection workflow."""
        # Create a Shiny project
        create_result = await tool_manager.execute_tool("create_project", {
            "name": "shiny_app_test",
            "path": str(temp_workspace),
            "type": "shiny",
            "template_options": {"app_type": "single_file"}
        })
        
        assert create_result.success
        
        project_path = temp_workspace / "shiny_app_test"
        assert (project_path / "app.R").exists()
        assert (project_path / "www").exists()
        
        # Get project info to verify Shiny detection
        info_result = await tool_manager.execute_tool("get_project_info", {
            "project_path": str(project_path)
        })
        
        assert info_result.success
        project_info = info_result.metadata
        
        # Should detect as Shiny project based on app.R presence
        assert project_info["type"] == "shiny"
        
        # Check that app.R is in the file list
        app_r_files = [f for f in project_info["files"] if f["path"] == "app.R"]
        assert len(app_r_files) == 1
    
    @pytest.mark.asyncio
    async def test_package_project_workflow(self, tool_manager, temp_workspace, mock_api_wrapper):
        """Test R package project creation workflow."""
        # Mock successful package creation
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=True, output="Package created successfully"
        )
        
        create_result = await tool_manager.execute_tool("create_project", {
            "name": "mypackage",
            "path": str(temp_workspace),
            "type": "package",
            "template_options": {
                "author": "Test Author",
                "email": "test@example.com",
                "license": "MIT"
            }
        })
        
        assert create_result.success
        
        # Verify R code was called for package creation
        mock_api_wrapper.execute_r_code.assert_called()
        call_args = mock_api_wrapper.execute_r_code.call_args[0][0]
        assert "usethis::create_package" in call_args
        assert "Test Author" in call_args
        assert "test@example.com" in call_args
    
    @pytest.mark.asyncio
    async def test_website_project_workflow(self, tool_manager, temp_workspace):
        """Test website project creation and structure."""
        create_result = await tool_manager.execute_tool("create_project", {
            "name": "my_website",
            "path": str(temp_workspace),
            "type": "website"
        })
        
        assert create_result.success
        
        project_path = temp_workspace / "my_website"
        
        # Check website-specific files
        assert (project_path / "_site.yml").exists()
        assert (project_path / "index.Rmd").exists()
        assert (project_path / "about.Rmd").exists()
        
        # Check .Rproj file has correct build type
        rproj_content = (project_path / "my_website.Rproj").read_text()
        assert "BuildType: Website" in rproj_content
        
        # Get project info to verify website detection
        info_result = await tool_manager.execute_tool("get_project_info", {
            "project_path": str(project_path)
        })
        
        assert info_result.success
        project_info = info_result.metadata
        assert project_info["type"] == "website"
    
    @pytest.mark.asyncio
    async def test_tool_manager_integration(self, tool_manager):
        """Test tool manager integration with project tools."""
        # Check that all project tools are registered
        tool_names = tool_manager.list_tools()
        assert "create_project" in tool_names
        assert "open_project" in tool_names
        assert "get_project_info" in tool_names
        
        # Check tool definitions
        definitions = tool_manager.get_tool_definitions()
        project_tools = [d for d in definitions if d["name"].endswith("_project") or d["name"] == "get_project_info"]
        assert len(project_tools) == 3
        
        # Verify each tool has proper schema
        for tool_def in project_tools:
            assert "name" in tool_def
            assert "description" in tool_def
            assert "inputSchema" in tool_def
            assert "properties" in tool_def["inputSchema"]
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, tool_manager, temp_workspace):
        """Test error handling in integrated workflow."""
        # Try to create project with invalid name
        result = await tool_manager.execute_tool("create_project", {
            "name": "invalid name!",
            "path": str(temp_workspace),
            "type": "default"
        })
        
        assert not result.success
        assert "项目名称只能包含" in result.error
        
        # Try to get info for non-existent project
        result = await tool_manager.execute_tool("get_project_info", {
            "project_path": "/nonexistent/project"
        })
        
        assert not result.success
        assert "项目路径不存在" in result.error
        
        # Try to open non-existent project
        result = await tool_manager.execute_tool("open_project", {
            "project_path": "/nonexistent/project.Rproj"
        })
        
        assert not result.success
        assert "找不到项目文件" in result.error
    
    @pytest.mark.asyncio
    async def test_project_with_renv_integration(self, tool_manager, temp_workspace, mock_api_wrapper):
        """Test project creation with renv integration."""
        # Mock successful renv initialization
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=True, output="renv initialized successfully"
        )
        
        create_result = await tool_manager.execute_tool("create_project", {
            "name": "renv_project",
            "path": str(temp_workspace),
            "type": "default",
            "renv": True
        })
        
        assert create_result.success
        
        # Verify renv initialization was called
        mock_api_wrapper.execute_r_code.assert_called()
        call_args = mock_api_wrapper.execute_r_code.call_args[0][0]
        assert "renv::init()" in call_args
        
        # Check that renv message is in content
        content_texts = [item["text"] for item in create_result.content]
        assert any("已初始化renv包管理" in text for text in content_texts)
    
    @pytest.mark.asyncio
    async def test_project_info_with_git_integration(self, tool_manager, temp_workspace):
        """Test project info retrieval with Git integration."""
        # Create project with Git
        create_result = await tool_manager.execute_tool("create_project", {
            "name": "git_project",
            "path": str(temp_workspace),
            "type": "default",
            "git": True
        })
        
        assert create_result.success
        
        project_path = temp_workspace / "git_project"
        
        # Mock Git commands for project info
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout="main"),  # current branch
                Mock(returncode=0, stdout="https://github.com/user/repo.git"),  # remote URL
                Mock(returncode=0, stdout="")  # status (clean)
            ]
            
            info_result = await tool_manager.execute_tool("get_project_info", {
                "project_path": str(project_path),
                "include_git_info": True
            })
        
        assert info_result.success
        project_info = info_result.metadata
        assert project_info["git_enabled"] is True
        assert "git_info" in project_info
        assert project_info["git_info"]["current_branch"] == "main"
    
    @pytest.mark.asyncio
    async def test_multi_file_shiny_integration(self, tool_manager, temp_workspace):
        """Test multi-file Shiny project creation and detection."""
        create_result = await tool_manager.execute_tool("create_project", {
            "name": "multi_shiny",
            "path": str(temp_workspace),
            "type": "shiny",
            "template_options": {"app_type": "multi_file"}
        })
        
        assert create_result.success
        
        project_path = temp_workspace / "multi_shiny"
        
        # Check multi-file structure
        assert (project_path / "ui.R").exists()
        assert (project_path / "server.R").exists()
        assert not (project_path / "app.R").exists()
        
        # Verify content of files
        ui_content = (project_path / "ui.R").read_text()
        server_content = (project_path / "server.R").read_text()
        
        assert "library(shiny)" in ui_content
        assert "fluidPage" in ui_content
        assert "library(shiny)" in server_content
        assert "function(input, output)" in server_content
        
        # Get project info should still detect as Shiny
        info_result = await tool_manager.execute_tool("get_project_info", {
            "project_path": str(project_path)
        })
        
        assert info_result.success
        project_info = info_result.metadata
        assert project_info["type"] == "shiny"
    
    @pytest.mark.asyncio
    async def test_project_validation_integration(self, tool_manager):
        """Test argument validation integration."""
        # Test missing required arguments
        result = await tool_manager.execute_tool("create_project", {
            "path": "/some/path"
            # Missing required "name" argument
        })
        
        assert not result.success
        assert "Missing required parameters" in result.error
        
        # Test invalid enum value
        result = await tool_manager.execute_tool("create_project", {
            "name": "test",
            "path": "/some/path",
            "type": "invalid_type"
        })
        
        assert not result.success
        assert "must be one of" in result.error
    
    @pytest.mark.asyncio
    async def test_tool_schema_integration(self, tool_manager):
        """Test tool schema integration."""
        # Get schema for create_project tool
        schema = tool_manager.get_tool_schema("create_project")
        
        assert schema is not None
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "name" in schema["properties"]
        assert "path" in schema["properties"]
        assert "type" in schema["properties"]
        
        # Check enum values for type parameter
        type_property = schema["properties"]["type"]
        assert "enum" in type_property
        assert "default" in type_property
        assert "shiny" in type_property["enum"]
        assert "package" in type_property["enum"]
        
        # Check required fields
        assert "required" in schema
        assert "name" in schema["required"]
        assert "path" in schema["required"]