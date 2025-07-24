"""Integration tests for project resource handler."""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from src.rstudio_mcp.api_wrapper import RStudioAPIWrapper
from src.rstudio_mcp.resources.project_resource import ProjectResource


class TestProjectResourceIntegration:
    """Integration tests for ProjectResource."""
    
    @pytest.fixture
    def mock_api_wrapper(self):
        """Create a mock API wrapper."""
        api = Mock(spec=RStudioAPIWrapper)
        api.get_active_project = AsyncMock()
        api.get_r_version = AsyncMock(return_value="4.3.0")
        return api
    
    @pytest.fixture
    def temp_project_dir(self):
        """Create a temporary project directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "test_project"
            project_path.mkdir()
            
            # Create some test files
            (project_path / "test.R").write_text("# Test R file\nprint('Hello, World!')")
            (project_path / "data.csv").write_text("name,value\ntest,123")
            (project_path / "README.md").write_text("# Test Project\nThis is a test project.")
            (project_path / "test_project.Rproj").write_text("Version: 1.0\nProjectTemplate: default")
            
            # Create a subdirectory with files
            (project_path / "scripts").mkdir()
            (project_path / "scripts" / "analysis.R").write_text("# Analysis script")
            
            yield str(project_path)
    
    @pytest.fixture
    def project_resource(self, mock_api_wrapper):
        """Create a project resource with mock API wrapper."""
        return ProjectResource(api_wrapper=mock_api_wrapper)
    
    @pytest.mark.asyncio
    async def test_list_resources_with_active_project(self, project_resource, mock_api_wrapper, temp_project_dir):
        """Test listing resources with an active project."""
        mock_api_wrapper.get_active_project.return_value = temp_project_dir
        
        resources = await project_resource.list_resources()
        
        assert len(resources) > 0
        
        # Check main project resource
        project_resources = [r for r in resources if r.uri == f"rstudio-project://{temp_project_dir}"]
        assert len(project_resources) == 1
        assert project_resources[0].name.startswith("Project:")
        assert project_resources[0].mime_type == "application/json"
        
        # Check file resources
        file_resources = [r for r in resources if "/files/" in r.uri]
        assert len(file_resources) > 0
        
        # Check for specific files
        r_file_resources = [r for r in file_resources if r.uri.endswith("test.R")]
        assert len(r_file_resources) == 1
        assert r_file_resources[0].mime_type == "text/x-r"
    
    @pytest.mark.asyncio
    async def test_list_resources_no_active_project(self, project_resource, mock_api_wrapper):
        """Test listing resources with no active project."""
        mock_api_wrapper.get_active_project.return_value = None
        
        resources = await project_resource.list_resources()
        
        # Should still return some resources (discovered projects)
        # The exact number depends on the test environment
        assert isinstance(resources, list)
    
    @pytest.mark.asyncio
    async def test_read_project_info(self, project_resource, mock_api_wrapper, temp_project_dir):
        """Test reading project information."""
        mock_api_wrapper.get_active_project.return_value = temp_project_dir
        
        result = await project_resource.read_resource(f"rstudio-project://{temp_project_dir}")
        
        assert result.success
        assert result.mime_type == "application/json"
        
        import json
        project_info = json.loads(result.get_text_content())
        
        assert project_info["name"] == "test_project"
        assert project_info["path"] == temp_project_dir
        assert project_info["type"] == "default"  # Has .Rproj file
        assert project_info["r_version"] == "4.3.0"
        assert len(project_info["files"]) > 0
        
        # Check for specific files
        file_paths = [f["path"] for f in project_info["files"]]
        assert "test.R" in file_paths
        assert "README.md" in file_paths
    
    @pytest.mark.asyncio
    async def test_read_project_file_r_script(self, project_resource, temp_project_dir):
        """Test reading an R script file."""
        result = await project_resource.read_resource(f"rstudio-project://{temp_project_dir}/files/test.R")
        
        assert result.success
        assert result.mime_type == "text/x-r"
        
        content = result.get_text_content()
        assert "# Test R file" in content
        assert "print('Hello, World!')" in content
    
    @pytest.mark.asyncio
    async def test_read_project_file_csv(self, project_resource, temp_project_dir):
        """Test reading a CSV file."""
        result = await project_resource.read_resource(f"rstudio-project://{temp_project_dir}/files/data.csv")
        
        assert result.success
        assert result.mime_type == "text/csv"
        
        content = result.get_text_content()
        assert "name,value" in content
        assert "test,123" in content
    
    @pytest.mark.asyncio
    async def test_read_project_file_markdown(self, project_resource, temp_project_dir):
        """Test reading a Markdown file."""
        result = await project_resource.read_resource(f"rstudio-project://{temp_project_dir}/files/README.md")
        
        assert result.success
        assert result.mime_type == "text/markdown"
        
        content = result.get_text_content()
        assert "# Test Project" in content
        assert "This is a test project." in content
    
    @pytest.mark.asyncio
    async def test_read_project_file_subdirectory(self, project_resource, temp_project_dir):
        """Test reading a file from a subdirectory."""
        result = await project_resource.read_resource(f"rstudio-project://{temp_project_dir}/files/scripts/analysis.R")
        
        assert result.success
        assert result.mime_type == "text/x-r"
        
        content = result.get_text_content()
        assert "# Analysis script" in content
    
    @pytest.mark.asyncio
    async def test_read_nonexistent_project(self, project_resource):
        """Test reading non-existent project."""
        result = await project_resource.read_resource("rstudio-project:///nonexistent/project")
        
        assert not result.success
        assert "does not exist" in result.error
    
    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, project_resource, temp_project_dir):
        """Test reading non-existent file."""
        result = await project_resource.read_resource(f"rstudio-project://{temp_project_dir}/files/nonexistent.R")
        
        assert not result.success
        assert "does not exist" in result.error
    
    @pytest.mark.asyncio
    async def test_read_file_outside_project(self, project_resource, temp_project_dir):
        """Test reading file outside project directory (security check)."""
        result = await project_resource.read_resource(f"rstudio-project://{temp_project_dir}/files/../../../etc/passwd")
        
        assert not result.success
        assert "outside project directory" in result.error
    
    @pytest.mark.asyncio
    async def test_invalid_uri_format(self, project_resource):
        """Test invalid URI format."""
        result = await project_resource.read_resource("rstudio-project://")
        
        assert not result.success
        assert "missing project path" in result.error
    
    def test_mime_type_detection(self, project_resource):
        """Test MIME type detection for various file types."""
        test_cases = [
            ("test.R", "text/x-r"),
            ("test.r", "text/x-r"),
            ("test.Rmd", "text/x-r-markdown"),
            ("test.py", "text/x-python"),
            ("test.sql", "text/x-sql"),
            ("test.json", "application/json"),
            ("test.yaml", "text/x-yaml"),
            ("test.yml", "text/x-yaml"),
            ("test.txt", "text/plain"),
            ("test.md", "text/markdown"),
            ("test.csv", "text/csv"),
            ("test.png", "image/png"),
            ("test.jpg", "image/jpeg"),
            ("test.pdf", "application/pdf"),
            ("unknown.xyz", "text/plain")  # Default fallback
        ]
        
        for filename, expected_mime_type in test_cases:
            file_path = Path(filename)
            actual_mime_type = project_resource._get_mime_type(file_path)
            assert actual_mime_type == expected_mime_type, f"Failed for {filename}"
    
    def test_is_rstudio_project_detection(self, project_resource):
        """Test RStudio project detection."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test with .Rproj file
            project_dir = Path(temp_dir) / "with_rproj"
            project_dir.mkdir()
            (project_dir / "test.Rproj").write_text("Version: 1.0")
            assert project_resource._is_rstudio_project(project_dir)
            
            # Test with DESCRIPTION file (R package)
            package_dir = Path(temp_dir) / "with_description"
            package_dir.mkdir()
            (package_dir / "DESCRIPTION").write_text("Package: test")
            assert project_resource._is_rstudio_project(package_dir)
            
            # Test with Shiny files
            shiny_dir = Path(temp_dir) / "with_shiny"
            shiny_dir.mkdir()
            (shiny_dir / "app.R").write_text("# Shiny app")
            assert project_resource._is_rstudio_project(shiny_dir)
            
            # Test with R files
            r_dir = Path(temp_dir) / "with_r_files"
            r_dir.mkdir()
            (r_dir / "script.R").write_text("# R script")
            assert project_resource._is_rstudio_project(r_dir)
            
            # Test empty directory
            empty_dir = Path(temp_dir) / "empty"
            empty_dir.mkdir()
            assert not project_resource._is_rstudio_project(empty_dir)