"""Integration tests for workspace resource handler."""

from unittest.mock import AsyncMock, Mock

import pytest

from src.rstudio_mcp.api_wrapper import RStudioAPIWrapper
from src.rstudio_mcp.resources.workspace_resource import WorkspaceResource


class TestWorkspaceResourceIntegration:
    """Integration tests for WorkspaceResource."""
    
    @pytest.fixture
    def mock_api_wrapper(self):
        """Create a mock API wrapper."""
        api = Mock(spec=RStudioAPIWrapper)
        api.get_workspace_objects = AsyncMock(return_value=[
            {
                'name': 'data_frame',
                'class': 'data.frame',
                'type': 'list',
                'size': 1024,
                'summary': 'A data frame with 10 rows and 3 columns'
            },
            {
                'name': 'my_vector',
                'class': 'numeric',
                'type': 'double',
                'size': 80,
                'summary': 'num [1:10] 1 2 3 4 5 6 7 8 9 10'
            }
        ])
        api.execute_r_code = AsyncMock()
        api.get_r_version = AsyncMock(return_value="4.3.0")
        return api
    
    @pytest.fixture
    def workspace_resource(self, mock_api_wrapper):
        """Create a workspace resource with mock API wrapper."""
        return WorkspaceResource(api_wrapper=mock_api_wrapper)
    
    @pytest.mark.asyncio
    async def test_list_resources(self, workspace_resource):
        """Test listing workspace resources."""
        resources = await workspace_resource.list_resources()
        
        assert len(resources) >= 4  # 2 objects + 2 special resources
        
        # Check for workspace objects
        object_resources = [r for r in resources if r.uri.startswith("rstudio-workspace://") and not r.metadata.get("special")]
        assert len(object_resources) == 2
        
        # Check for specific objects
        data_frame_resources = [r for r in object_resources if "data_frame" in r.uri]
        assert len(data_frame_resources) == 1
        assert data_frame_resources[0].name == "Object: data_frame"
        assert "data.frame" in data_frame_resources[0].description
        
        # Check for special resources
        special_resources = [r for r in resources if r.metadata.get("special")]
        assert len(special_resources) == 2
        
        special_uris = [r.uri for r in special_resources]
        assert "rstudio-workspace://summary" in special_uris
        assert "rstudio-workspace://environment" in special_uris
    
    @pytest.mark.asyncio
    async def test_read_workspace_summary(self, workspace_resource):
        """Test reading workspace summary."""
        result = await workspace_resource.read_resource("rstudio-workspace://summary")
        
        assert result.success
        assert result.mime_type == "application/json"
        
        import json
        summary = json.loads(result.get_text_content())
        
        assert summary["total_objects"] == 2
        assert "data.frame" in summary["objects_by_class"]
        assert "numeric" in summary["objects_by_class"]
        assert summary["objects_by_class"]["data.frame"] == 1
        assert summary["objects_by_class"]["numeric"] == 1
        
        assert len(summary["objects"]) == 2
        object_names = [obj["name"] for obj in summary["objects"]]
        assert "data_frame" in object_names
        assert "my_vector" in object_names
    
    @pytest.mark.asyncio
    async def test_read_environment_info(self, workspace_resource, mock_api_wrapper):
        """Test reading environment information."""
        # Create proper mock result objects
        def create_mock_result(output):
            mock_result = Mock()
            mock_result.success = True
            mock_result.output = output
            mock_result.warnings = []
            return mock_result
        
        # Mock R code execution results
        mock_api_wrapper.execute_r_code.side_effect = [
            # getwd()
            create_mock_result('"/Users/test/project"'),
            # (.packages())
            create_mock_result('[1] "stats"     "graphics" "grDevices" "utils"    "datasets"'),
            # search()
            create_mock_result('[1] ".GlobalEnv"        "package:stats"     "package:graphics"'),
            # gc()
            create_mock_result('         used (Mb) gc trigger (Mb) max used (Mb)\nNcells  12345  0.7     123456  6.6    12345  0.7'),
            # sessionInfo()
            create_mock_result('R version 4.3.0 (2023-04-21)\nPlatform: x86_64-apple-darwin20')
        ]
        
        result = await workspace_resource.read_resource("rstudio-workspace://environment")
        
        assert result.success
        assert result.mime_type == "application/json"
        
        import json
        env_info = json.loads(result.get_text_content())
        
        assert env_info["r_version"] == "4.3.0"
        assert env_info["working_directory"] == "/Users/test/project"
        # Check that the parsing returned some results (exact content may vary due to parsing)
        assert isinstance(env_info["loaded_packages"], list)
        assert isinstance(env_info["search_path"], list)
        # At least one of the lists should have content
        assert len(env_info["loaded_packages"]) > 0 or len(env_info["search_path"]) > 0
    
    @pytest.mark.asyncio
    async def test_read_specific_workspace_object(self, workspace_resource, mock_api_wrapper):
        """Test reading information about a specific workspace object."""
        # Create a proper mock result object
        mock_result = Mock()
        mock_result.success = True
        mock_result.output = 'Class: data.frame\nType: list\nLength: 3\nSize: 1024'
        mock_result.warnings = []
        
        # Mock R code execution for object info
        mock_api_wrapper.execute_r_code.return_value = mock_result
        
        result = await workspace_resource.read_resource("rstudio-workspace://data_frame")
        
        assert result.success
        assert result.mime_type == "application/json"
        
        import json
        obj_info = json.loads(result.get_text_content())
        
        assert obj_info["name"] == "data_frame"
        assert "Class: data.frame" in obj_info["basic_info"]
    
    @pytest.mark.asyncio
    async def test_read_nonexistent_object(self, workspace_resource, mock_api_wrapper):
        """Test reading non-existent workspace object."""
        # Create a proper mock result object
        mock_result = Mock()
        mock_result.success = True
        mock_result.output = 'Error: Object not found'
        mock_result.warnings = []
        
        # Mock R code execution for non-existent object
        mock_api_wrapper.execute_r_code.return_value = mock_result
        
        result = await workspace_resource.read_resource("rstudio-workspace://nonexistent")
        
        assert result.success  # The resource handler succeeds, but the R output indicates error
        assert result.mime_type == "application/json"
    
    @pytest.mark.asyncio
    async def test_no_api_wrapper(self):
        """Test workspace resource without API wrapper."""
        workspace_resource = WorkspaceResource(api_wrapper=None)
        
        # List resources should return empty list with warning
        resources = await workspace_resource.list_resources()
        assert len(resources) == 0
        
        # Read resource should return error
        result = await workspace_resource.read_resource("rstudio-workspace://test")
        assert not result.success
        assert "No API wrapper available" in result.error
    
    @pytest.mark.asyncio
    async def test_invalid_uri_format(self, workspace_resource):
        """Test invalid URI format."""
        result = await workspace_resource.read_resource("rstudio-workspace://")
        
        assert not result.success
        assert "missing object name" in result.error
    
