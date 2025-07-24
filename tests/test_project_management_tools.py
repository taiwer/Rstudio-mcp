"""Tests for project management tools."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.rstudio_mcp.api_wrapper import ExecutionResult, RStudioAPIWrapper
from src.rstudio_mcp.tools.project_management_tools import (
    CreateProjectTool,
    GetProjectInfoTool,
    OpenProjectTool,
)


@pytest.fixture
def mock_api_wrapper():
    """Create a mock API wrapper."""
    api = Mock(spec=RStudioAPIWrapper)
    api.execute_r_code = AsyncMock()
    api.check_rstudio_available = AsyncMock(return_value=True)
    api.get_active_project = AsyncMock(return_value=None)
    return api


@pytest.fixture
def temp_project_dir():
    """Create a temporary directory for project testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


class TestCreateProjectTool:
    """Tests for CreateProjectTool."""
    
    @pytest.fixture
    def create_tool(self, mock_api_wrapper):
        """Create a CreateProjectTool instance."""
        return CreateProjectTool(mock_api_wrapper)
    
    def test_tool_properties(self, create_tool):
        """Test tool properties."""
        assert create_tool.name == "create_project"
        assert "创建新的RStudio项目" in create_tool.description
        
        # Check parameters
        param_names = [p.name for p in create_tool.parameters]
        assert "name" in param_names
        assert "path" in param_names
        assert "type" in param_names
        assert "git" in param_names
        assert "renv" in param_names
    
    @pytest.mark.asyncio
    async def test_create_default_project(self, create_tool, temp_project_dir):
        """Test creating a default project."""
        arguments = {
            "name": "test_project",
            "path": str(temp_project_dir),
            "type": "default"
        }
        
        result = await create_tool.execute(arguments)
        
        assert result.success
        assert "成功创建项目" in result.content[0]["text"]
        
        # Check project structure
        project_path = temp_project_dir / "test_project"
        assert project_path.exists()
        assert (project_path / "test_project.Rproj").exists()
        assert (project_path / "R").exists()
        assert (project_path / "data").exists()
        assert (project_path / "output").exists()
        assert (project_path / "README.md").exists()
    
    @pytest.mark.asyncio
    async def test_create_project_with_git(self, create_tool, temp_project_dir):
        """Test creating a project with Git initialization."""
        arguments = {
            "name": "git_project",
            "path": str(temp_project_dir),
            "type": "default",
            "git": True
        }
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = await create_tool.execute(arguments)
        
        assert result.success
        # Check that Git initialization message is in one of the content items
        content_texts = [item["text"] for item in result.content]
        assert any("已初始化Git仓库" in text for text in content_texts)
        
        # Check .gitignore exists
        project_path = temp_project_dir / "git_project"
        assert (project_path / ".gitignore").exists()
    
    @pytest.mark.asyncio
    async def test_create_shiny_project_single_file(self, create_tool, temp_project_dir):
        """Test creating a single-file Shiny project."""
        arguments = {
            "name": "shiny_app",
            "path": str(temp_project_dir),
            "type": "shiny",
            "template_options": {"app_type": "single_file"}
        }
        
        result = await create_tool.execute(arguments)
        
        assert result.success
        
        # Check Shiny structure
        project_path = temp_project_dir / "shiny_app"
        assert project_path.exists()
        assert (project_path / "app.R").exists()
        assert (project_path / "www").exists()
        
        # Check app.R content
        app_content = (project_path / "app.R").read_text()
        assert "library(shiny)" in app_content
        assert "shinyApp(ui = ui, server = server)" in app_content
    
    @pytest.mark.asyncio
    async def test_create_shiny_project_multi_file(self, create_tool, temp_project_dir):
        """Test creating a multi-file Shiny project."""
        arguments = {
            "name": "shiny_multi",
            "path": str(temp_project_dir),
            "type": "shiny",
            "template_options": {"app_type": "multi_file"}
        }
        
        result = await create_tool.execute(arguments)
        
        assert result.success
        
        # Check multi-file Shiny structure
        project_path = temp_project_dir / "shiny_multi"
        assert (project_path / "ui.R").exists()
        assert (project_path / "server.R").exists()
        assert not (project_path / "app.R").exists()
    
    @pytest.mark.asyncio
    async def test_create_package_project(self, create_tool, temp_project_dir, mock_api_wrapper):
        """Test creating an R package project."""
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=True, output="Package created successfully"
        )
        
        arguments = {
            "name": "mypackage",
            "path": str(temp_project_dir),
            "type": "package",
            "template_options": {
                "author": "Test Author",
                "email": "test@example.com",
                "license": "MIT"
            }
        }
        
        result = await create_tool.execute(arguments)
        
        assert result.success
        mock_api_wrapper.execute_r_code.assert_called_once()
        
        # Check that usethis::create_package was called
        call_args = mock_api_wrapper.execute_r_code.call_args[0][0]
        assert "usethis::create_package" in call_args
        assert "Test Author" in call_args
    
    @pytest.mark.asyncio
    async def test_create_website_project(self, create_tool, temp_project_dir):
        """Test creating a website project."""
        arguments = {
            "name": "my_website",
            "path": str(temp_project_dir),
            "type": "website"
        }
        
        result = await create_tool.execute(arguments)
        
        assert result.success
        
        # Check website structure
        project_path = temp_project_dir / "my_website"
        assert (project_path / "_site.yml").exists()
        assert (project_path / "index.Rmd").exists()
        assert (project_path / "about.Rmd").exists()
        
        # Check .Rproj file has website build type
        rproj_content = (project_path / "my_website.Rproj").read_text()
        assert "BuildType: Website" in rproj_content
    
    @pytest.mark.asyncio
    async def test_create_project_invalid_name(self, create_tool, temp_project_dir):
        """Test creating a project with invalid name."""
        arguments = {
            "name": "invalid name!",
            "path": str(temp_project_dir),
            "type": "default"
        }
        
        result = await create_tool.execute(arguments)
        
        assert not result.success
        assert "项目名称只能包含" in result.error
    
    @pytest.mark.asyncio
    async def test_create_project_existing_path(self, create_tool, temp_project_dir):
        """Test creating a project in existing path."""
        # Create existing directory
        existing_path = temp_project_dir / "existing"
        existing_path.mkdir()
        
        arguments = {
            "name": "existing",
            "path": str(temp_project_dir),
            "type": "default"
        }
        
        result = await create_tool.execute(arguments)
        
        assert not result.success
        assert "已存在" in result.error
    
    @pytest.mark.asyncio
    async def test_create_project_with_renv(self, create_tool, temp_project_dir, mock_api_wrapper):
        """Test creating a project with renv initialization."""
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=True, output="renv initialized"
        )
        
        arguments = {
            "name": "renv_project",
            "path": str(temp_project_dir),
            "type": "default",
            "renv": True
        }
        
        result = await create_tool.execute(arguments)
        
        assert result.success
        # Check that renv initialization message is in one of the content items
        content_texts = [item["text"] for item in result.content]
        assert any("已初始化renv包管理" in text for text in content_texts)


class TestOpenProjectTool:
    """Tests for OpenProjectTool."""
    
    @pytest.fixture
    def open_tool(self, mock_api_wrapper):
        """Create an OpenProjectTool instance."""
        return OpenProjectTool(mock_api_wrapper)
    
    def test_tool_properties(self, open_tool):
        """Test tool properties."""
        assert open_tool.name == "open_project"
        assert "在RStudio中打开" in open_tool.description
        
        # Check parameters
        param_names = [p.name for p in open_tool.parameters]
        assert "project_path" in param_names
        assert "new_session" in param_names
    
    @pytest.mark.asyncio
    async def test_open_project_success(self, open_tool, mock_api_wrapper, temp_project_dir):
        """Test successfully opening a project."""
        # Create a mock .Rproj file
        project_path = temp_project_dir / "test.Rproj"
        project_path.write_text("Version: 1.0")
        
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=True, output="Project opened"
        )
        
        arguments = {
            "project_path": str(project_path),
            "new_session": False
        }
        
        result = await open_tool.execute(arguments)
        
        assert result.success
        assert "成功打开项目" in result.content[0]["text"]
        mock_api_wrapper.execute_r_code.assert_called_once()
        
        # Check R code
        call_args = mock_api_wrapper.execute_r_code.call_args[0][0]
        assert "rstudioapi::openProject" in call_args
        assert "newSession = TRUE" not in call_args
    
    @pytest.mark.asyncio
    async def test_open_project_new_session(self, open_tool, mock_api_wrapper, temp_project_dir):
        """Test opening a project in new session."""
        project_path = temp_project_dir / "test.Rproj"
        project_path.write_text("Version: 1.0")
        
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=True, output="Project opened"
        )
        
        arguments = {
            "project_path": str(project_path),
            "new_session": True
        }
        
        result = await open_tool.execute(arguments)
        
        assert result.success
        assert "项目在新会话中打开" in result.content[1]["text"]
        
        # Check R code includes new session
        call_args = mock_api_wrapper.execute_r_code.call_args[0][0]
        assert "newSession = TRUE" in call_args
    
    @pytest.mark.asyncio
    async def test_open_project_directory(self, open_tool, mock_api_wrapper, temp_project_dir):
        """Test opening a project by directory path."""
        # Create project directory with .Rproj file
        project_dir = temp_project_dir / "myproject"
        project_dir.mkdir()
        rproj_file = project_dir / "myproject.Rproj"
        rproj_file.write_text("Version: 1.0")
        
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=True, output="Project opened"
        )
        
        arguments = {
            "project_path": str(project_dir)
        }
        
        result = await open_tool.execute(arguments)
        
        assert result.success
        
        # Should have resolved to .Rproj file
        call_args = mock_api_wrapper.execute_r_code.call_args[0][0]
        assert str(rproj_file) in call_args
    
    @pytest.mark.asyncio
    async def test_open_project_not_found(self, open_tool, mock_api_wrapper):
        """Test opening non-existent project."""
        arguments = {
            "project_path": "/nonexistent/project.Rproj"
        }
        
        result = await open_tool.execute(arguments)
        
        assert not result.success
        assert "找不到项目文件" in result.error
    
    @pytest.mark.asyncio
    async def test_open_project_rstudio_unavailable(self, open_tool, mock_api_wrapper):
        """Test opening project when RStudio API is unavailable."""
        mock_api_wrapper.check_rstudio_available.return_value = False
        
        arguments = {
            "project_path": "/some/project.Rproj"
        }
        
        result = await open_tool.execute(arguments)
        
        assert not result.success
        assert "RStudio API不可用" in result.error


class TestGetProjectInfoTool:
    """Tests for GetProjectInfoTool."""
    
    @pytest.fixture
    def info_tool(self, mock_api_wrapper):
        """Create a GetProjectInfoTool instance."""
        return GetProjectInfoTool(mock_api_wrapper)
    
    def test_tool_properties(self, info_tool):
        """Test tool properties."""
        assert info_tool.name == "get_project_info"
        assert "获取RStudio项目的详细信息" in info_tool.description
        
        # Check parameters
        param_names = [p.name for p in info_tool.parameters]
        assert "project_path" in param_names
        assert "include_files" in param_names
        assert "include_git_info" in param_names
        assert "max_files" in param_names
    
    @pytest.mark.asyncio
    async def test_get_project_info_default_project(self, info_tool, mock_api_wrapper, temp_project_dir):
        """Test getting info for default project."""
        # Create a simple project
        project_dir = temp_project_dir / "test_project"
        project_dir.mkdir()
        
        # Create .Rproj file
        rproj_file = project_dir / "test_project.Rproj"
        rproj_content = """Version: 1.0
RestoreWorkspace: Default
SaveWorkspace: Default
"""
        rproj_file.write_text(rproj_content)
        
        # Create some files
        (project_dir / "R").mkdir()
        (project_dir / "R" / "functions.R").write_text("# R functions")
        (project_dir / "README.md").write_text("# Test Project\n\nThis is a test project.")
        
        arguments = {
            "project_path": str(project_dir),
            "include_files": True,
            "include_git_info": False
        }
        
        result = await info_tool.execute(arguments)
        
        assert result.success
        assert "项目信息:" in result.content[0]["text"]
        
        # Check metadata
        project_info = result.metadata
        assert project_info["name"] == "test_project"
        assert project_info["type"] == "default"
        assert project_info["rproj_file"] == str(rproj_file)
        assert project_info["description"] == "This is a test project."
        assert "files" in project_info
        assert project_info["file_count"] >= 2
    
    @pytest.mark.asyncio
    async def test_get_project_info_package_project(self, info_tool, mock_api_wrapper, temp_project_dir):
        """Test getting info for package project."""
        # Create a package project
        project_dir = temp_project_dir / "mypackage"
        project_dir.mkdir()
        
        # Create .Rproj file with package build type
        rproj_file = project_dir / "mypackage.Rproj"
        rproj_content = """Version: 1.0
BuildType: Package
"""
        rproj_file.write_text(rproj_content)
        
        # Create DESCRIPTION file
        description_file = project_dir / "DESCRIPTION"
        description_file.write_text("""Package: mypackage
Title: My Test Package
Version: 0.1.0
""")
        
        arguments = {
            "project_path": str(project_dir)
        }
        
        result = await info_tool.execute(arguments)
        
        assert result.success
        
        project_info = result.metadata
        assert project_info["type"] == "package"
    
    @pytest.mark.asyncio
    async def test_get_project_info_with_git(self, info_tool, mock_api_wrapper, temp_project_dir):
        """Test getting project info with Git information."""
        # Create project with Git
        project_dir = temp_project_dir / "git_project"
        project_dir.mkdir()
        
        rproj_file = project_dir / "git_project.Rproj"
        rproj_file.write_text("Version: 1.0")
        
        # Create .git directory
        git_dir = project_dir / ".git"
        git_dir.mkdir()
        
        with patch("subprocess.run") as mock_run:
            # Mock git commands
            mock_run.side_effect = [
                Mock(returncode=0, stdout="main"),  # current branch
                Mock(returncode=0, stdout="https://github.com/user/repo.git"),  # remote URL
                Mock(returncode=0, stdout="")  # status (clean)
            ]
            
            arguments = {
                "project_path": str(project_dir),
                "include_git_info": True
            }
            
            result = await info_tool.execute(arguments)
        
        assert result.success
        
        project_info = result.metadata
        assert project_info["git_enabled"] is True
        assert "git_info" in project_info
        assert project_info["git_info"]["current_branch"] == "main"
        assert "github.com" in project_info["git_info"]["remote_url"]
    
    @pytest.mark.asyncio
    async def test_get_project_info_with_renv(self, info_tool, mock_api_wrapper, temp_project_dir):
        """Test getting project info with renv information."""
        # Create project with renv
        project_dir = temp_project_dir / "renv_project"
        project_dir.mkdir()
        
        rproj_file = project_dir / "renv_project.Rproj"
        rproj_file.write_text("Version: 1.0")
        
        # Create renv.lock file
        renv_lock = project_dir / "renv.lock"
        lock_data = {
            "renv": {"Version": "0.15.5"},
            "R": {"Version": "4.3.0"},
            "Packages": {
                "base": {"Version": "4.3.0"},
                "utils": {"Version": "4.3.0"}
            }
        }
        renv_lock.write_text(json.dumps(lock_data))
        
        arguments = {
            "project_path": str(project_dir)
        }
        
        result = await info_tool.execute(arguments)
        
        assert result.success
        
        project_info = result.metadata
        assert project_info["renv_enabled"] is True
        assert "renv_info" in project_info
        assert project_info["renv_info"]["renv_version"] == "0.15.5"
        assert project_info["renv_info"]["r_version"] == "4.3.0"
        assert project_info["renv_info"]["package_count"] == 2
    
    @pytest.mark.asyncio
    async def test_get_project_info_active_project(self, info_tool, mock_api_wrapper, temp_project_dir):
        """Test getting info for active project."""
        # Setup active project
        project_dir = temp_project_dir / "active_project"
        project_dir.mkdir()
        rproj_file = project_dir / "active_project.Rproj"
        rproj_file.write_text("Version: 1.0")
        
        mock_api_wrapper.get_active_project.return_value = str(project_dir)
        
        arguments = {}  # No project_path specified
        
        result = await info_tool.execute(arguments)
        
        assert result.success
        mock_api_wrapper.get_active_project.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_project_info_no_active_project(self, info_tool, mock_api_wrapper):
        """Test getting info when no active project."""
        mock_api_wrapper.get_active_project.return_value = None
        
        arguments = {}
        
        result = await info_tool.execute(arguments)
        
        assert not result.success
        assert "没有活动项目" in result.error
    
    @pytest.mark.asyncio
    async def test_get_project_info_nonexistent_path(self, info_tool, mock_api_wrapper):
        """Test getting info for nonexistent project path."""
        arguments = {
            "project_path": "/nonexistent/project"
        }
        
        result = await info_tool.execute(arguments)
        
        assert not result.success
        assert "项目路径不存在" in result.error
    
    @pytest.mark.asyncio
    async def test_get_project_info_file_limit(self, info_tool, mock_api_wrapper, temp_project_dir):
        """Test file listing with limit."""
        # Create project with many files
        project_dir = temp_project_dir / "big_project"
        project_dir.mkdir()
        
        rproj_file = project_dir / "big_project.Rproj"
        rproj_file.write_text("Version: 1.0")
        
        # Create more files than the limit
        for i in range(15):
            (project_dir / f"file_{i}.R").write_text(f"# File {i}")
        
        arguments = {
            "project_path": str(project_dir),
            "max_files": 10
        }
        
        result = await info_tool.execute(arguments)
        
        assert result.success
        
        project_info = result.metadata
        assert len(project_info["files"]) == 10
        assert project_info.get("files_truncated") is True