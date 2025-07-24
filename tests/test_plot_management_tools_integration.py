"""Integration tests for plot management tools."""

import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.rstudio_mcp.api_wrapper import ExecutionResult, RStudioAPIWrapper
from src.rstudio_mcp.tools.plot_management_tools import (
    CapturePlotTool,
    ExportPlotTool,
    ListPlotsTool,
    PlotManager,
)


class TestPlotManagementIntegration:
    """Integration tests for plot management functionality."""
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory."""
        temp_dir = tempfile.mkdtemp(prefix="test_plot_integration_")
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def mock_api_wrapper(self):
        """Create mock API wrapper."""
        mock = Mock(spec=RStudioAPIWrapper)
        mock.execute_r_code = AsyncMock()
        return mock
    
    @pytest.fixture
    def plot_manager(self, temp_storage_dir):
        """Create PlotManager instance."""
        return PlotManager(storage_dir=temp_storage_dir)
    
    @pytest.fixture
    def capture_tool(self, mock_api_wrapper, plot_manager):
        """Create CapturePlotTool instance."""
        return CapturePlotTool(mock_api_wrapper, plot_manager)
    
    @pytest.fixture
    def list_tool(self, plot_manager):
        """Create ListPlotsTool instance."""
        return ListPlotsTool(plot_manager)
    
    @pytest.fixture
    def export_tool(self, plot_manager):
        """Create ExportPlotTool instance."""
        return ExportPlotTool(plot_manager)
    
    def create_sample_plot_file(self, temp_dir: str, filename: str = "test_plot.png") -> str:
        """Create a sample plot file for testing."""
        plot_file = Path(temp_dir) / filename
        # Create a minimal PNG file (1x1 pixel)
        png_data = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13'
            b'\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc```'
            b'\x00\x00\x00\x04\x00\x01\xdd\x8d\xb4\x1c\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        with open(plot_file, 'wb') as f:
            f.write(png_data)
        return str(plot_file)
    
    @pytest.mark.asyncio
    async def test_complete_plot_workflow(
        self, 
        capture_tool, 
        list_tool, 
        export_tool, 
        mock_api_wrapper,
        temp_storage_dir
    ):
        """Test complete plot management workflow."""
        # Step 1: Capture a plot
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=True,
            output="Plot created successfully",
        )
        
        with patch('tempfile.mkdtemp') as mock_mkdtemp, \
             patch('os.path.exists') as mock_exists, \
             patch('builtins.open', create=True) as mock_open, \
             patch('shutil.rmtree'):
            
            # Setup mocks for plot capture
            plot_temp_dir = "/tmp/test_plot_capture"
            expected_plot_file = f"{plot_temp_dir}/plot.png"
            mock_mkdtemp.return_value = plot_temp_dir
            mock_exists.return_value = True
            
            # Create actual plot file for testing
            actual_plot_file = self.create_sample_plot_file(temp_storage_dir, "plot.png")
            with open(actual_plot_file, 'rb') as f:
                plot_data = f.read()
            
            mock_open.return_value.__enter__.return_value.read.return_value = plot_data
            
            # Mock the store_plot method to use actual file
            original_store_plot = capture_tool.plot_manager.store_plot
            
            def mock_store_plot(source_path, code, title=None, description=None):
                # Use the actual plot file instead of the mocked path
                return original_store_plot(actual_plot_file, code, title, description)
            
            with patch.object(capture_tool.plot_manager, 'store_plot', side_effect=mock_store_plot):
                capture_args = {
                    "code": "plot(1:10, main='Test Plot')",
                    "title": "Integration Test Plot",
                    "description": "A plot created during integration testing",
                    "format": "png",
                    "width": 800,
                    "height": 600,
                }
                
                capture_result = await capture_tool.execute(capture_args)
                
                assert capture_result.success
                assert len(capture_result.content) == 2
                assert "plot_id" in capture_result.metadata
                
                plot_id = capture_result.metadata["plot_id"]
        
        # Step 2: List plots to verify it was stored
        list_result = await list_tool.execute({})
        
        assert list_result.success
        assert "找到 1 个图表" in list_result.content[0]["text"]
        assert plot_id in list_result.content[0]["text"]
        assert list_result.metadata["total_plots"] == 1
        
        plot_metadata = list_result.metadata["plots"][0]
        assert plot_metadata["plot_id"] == plot_id
        assert plot_metadata["title"] == "Integration Test Plot"
        assert plot_metadata["description"] == "A plot created during integration testing"
        assert plot_metadata["format"] == "png"
        
        # Step 3: Export the plot
        export_path = os.path.join(temp_storage_dir, "exported_plot.png")
        export_args = {
            "plot_id": plot_id,
            "output_path": export_path,
        }
        
        export_result = await export_tool.execute(export_args)
        
        assert export_result.success
        assert "已成功导出" in export_result.content[0]["text"]
        assert export_result.metadata["plot_id"] == plot_id
        assert export_result.metadata["output_path"] == export_path
        
        # Verify exported file exists
        assert os.path.exists(export_path)
        
        # Step 4: List plots with search filter
        search_result = await list_tool.execute({"search": "integration"})
        
        assert search_result.success
        assert "找到 1 个图表" in search_result.content[0]["text"]
        assert plot_id in search_result.content[0]["text"]
        
        # Step 5: List plots with format filter
        format_result = await list_tool.execute({"format": "png"})
        
        assert format_result.success
        assert "找到 1 个图表" in format_result.content[0]["text"]
        
        # Test with non-matching format
        no_match_result = await list_tool.execute({"format": "pdf"})
        assert no_match_result.success
        assert "没有找到" in no_match_result.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_multiple_plots_management(
        self, 
        capture_tool, 
        list_tool, 
        mock_api_wrapper,
        temp_storage_dir
    ):
        """Test managing multiple plots."""
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=True,
            output="Plot created successfully",
        )
        
        plot_ids = []
        
        # Create multiple plots
        for i in range(3):
            with patch('tempfile.mkdtemp') as mock_mkdtemp, \
                 patch('os.path.exists') as mock_exists, \
                 patch('builtins.open', create=True) as mock_open, \
                 patch('shutil.rmtree'):
                
                plot_temp_dir = f"/tmp/test_plot_capture_{i}"
                mock_mkdtemp.return_value = plot_temp_dir
                mock_exists.return_value = True
                
                # Create actual plot file
                actual_plot_file = self.create_sample_plot_file(
                    temp_storage_dir, f"test_plot_{i}.png"
                )
                with open(actual_plot_file, 'rb') as f:
                    plot_data = f.read()
                
                mock_open.return_value.__enter__.return_value.read.return_value = plot_data
                
                # Mock store_plot to use actual file
                original_store_plot = capture_tool.plot_manager.store_plot
                
                def mock_store_plot(source_path, code, title=None, description=None):
                    return original_store_plot(actual_plot_file, code, title, description)
                
                with patch.object(capture_tool.plot_manager, 'store_plot', side_effect=mock_store_plot):
                    capture_args = {
                        "code": f"plot(1:{i+5}, main='Plot {i+1}')",
                        "title": f"Test Plot {i+1}",
                        "format": "png",
                    }
                    
                    result = await capture_tool.execute(capture_args)
                    assert result.success
                    plot_ids.append(result.metadata["plot_id"])
        
        # List all plots
        list_result = await list_tool.execute({})
        assert list_result.success
        assert "找到 3 个图表" in list_result.content[0]["text"]
        assert list_result.metadata["total_plots"] == 3
        
        # Test limit
        limited_result = await list_tool.execute({"limit": 2})
        assert limited_result.success
        assert "找到 2 个图表" in limited_result.content[0]["text"]
        assert limited_result.metadata["total_plots"] == 2
        
        # Verify all plot IDs are present in full list
        all_plot_ids = [p["plot_id"] for p in list_result.metadata["plots"]]
        for plot_id in plot_ids:
            assert plot_id in all_plot_ids
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(
        self, 
        capture_tool, 
        export_tool, 
        mock_api_wrapper
    ):
        """Test error handling in integrated workflow."""
        # Test R code execution failure
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=False,
            error="R syntax error: unexpected symbol",
        )
        
        capture_args = {
            "code": "invalid R code !!!",
            "title": "Failed Plot",
        }
        
        capture_result = await capture_tool.execute(capture_args)
        assert not capture_result.success
        assert "Failed to execute plot code" in capture_result.error
        
        # Test exporting non-existent plot
        export_args = {
            "plot_id": "nonexistent_plot_123",
            "output_path": "/tmp/nonexistent_export.png",
        }
        
        export_result = await export_tool.execute(export_args)
        assert not export_result.success
        assert "not found" in export_result.error
    
    @pytest.mark.asyncio
    async def test_plot_metadata_persistence(
        self, 
        temp_storage_dir, 
        mock_api_wrapper
    ):
        """Test that plot metadata persists across tool instances."""
        # Create first set of tools and capture a plot
        plot_manager1 = PlotManager(storage_dir=temp_storage_dir)
        capture_tool1 = CapturePlotTool(mock_api_wrapper, plot_manager1)
        
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=True,
            output="Plot created successfully",
        )
        
        with patch('tempfile.mkdtemp') as mock_mkdtemp, \
             patch('os.path.exists') as mock_exists, \
             patch('builtins.open', create=True) as mock_open, \
             patch('shutil.rmtree'):
            
            plot_temp_dir = "/tmp/test_plot_persistence"
            mock_mkdtemp.return_value = plot_temp_dir
            mock_exists.return_value = True
            
            # Create actual plot file
            actual_plot_file = self.create_sample_plot_file(temp_storage_dir)
            with open(actual_plot_file, 'rb') as f:
                plot_data = f.read()
            
            mock_open.return_value.__enter__.return_value.read.return_value = plot_data
            
            # Mock store_plot to use actual file
            original_store_plot = plot_manager1.store_plot
            
            def mock_store_plot(source_path, code, title=None, description=None):
                return original_store_plot(actual_plot_file, code, title, description)
            
            with patch.object(plot_manager1, 'store_plot', side_effect=mock_store_plot):
                capture_args = {
                    "code": "plot(1:10)",
                    "title": "Persistent Plot",
                    "description": "A plot to test persistence",
                }
                
                result = await capture_tool1.execute(capture_args)
                assert result.success
                plot_id = result.metadata["plot_id"]
        
        # Create second set of tools with same storage directory
        plot_manager2 = PlotManager(storage_dir=temp_storage_dir)
        list_tool2 = ListPlotsTool(plot_manager2)
        
        # Verify plot is still accessible
        list_result = await list_tool2.execute({})
        assert list_result.success
        assert "找到 1 个图表" in list_result.content[0]["text"]
        assert plot_id in list_result.content[0]["text"]
        
        # Verify metadata is correct
        plot_metadata = list_result.metadata["plots"][0]
        assert plot_metadata["plot_id"] == plot_id
        assert plot_metadata["title"] == "Persistent Plot"
        assert plot_metadata["description"] == "A plot to test persistence"
    
    @pytest.mark.asyncio
    async def test_different_plot_formats(
        self, 
        capture_tool, 
        list_tool, 
        mock_api_wrapper,
        temp_storage_dir
    ):
        """Test handling different plot formats."""
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=True,
            output="Plot created successfully",
        )
        
        formats = ["png", "pdf", "svg", "jpeg"]
        plot_ids = []
        
        for fmt in formats:
            with patch('tempfile.mkdtemp') as mock_mkdtemp, \
                 patch('os.path.exists') as mock_exists, \
                 patch('builtins.open', create=True) as mock_open, \
                 patch('shutil.rmtree'):
                
                plot_temp_dir = f"/tmp/test_plot_{fmt}"
                mock_mkdtemp.return_value = plot_temp_dir
                mock_exists.return_value = True
                
                # Create sample file for this format
                actual_plot_file = self.create_sample_plot_file(
                    temp_storage_dir, f"test_plot.{fmt}"
                )
                
                # For non-PNG formats, create minimal valid content
                if fmt == "pdf":
                    pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 1\n0000000000 65535 f \ntrailer\n<<\n/Size 1\n/Root 1 0 R\n>>\nstartxref\n9\n%%EOF"
                    with open(actual_plot_file, 'wb') as f:
                        f.write(pdf_content)
                elif fmt == "svg":
                    svg_content = b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="red"/></svg>'
                    with open(actual_plot_file, 'wb') as f:
                        f.write(svg_content)
                
                with open(actual_plot_file, 'rb') as f:
                    plot_data = f.read()
                
                mock_open.return_value.__enter__.return_value.read.return_value = plot_data
                
                # Mock store_plot to use actual file
                original_store_plot = capture_tool.plot_manager.store_plot
                
                def mock_store_plot(source_path, code, title=None, description=None):
                    return original_store_plot(actual_plot_file, code, title, description)
                
                with patch.object(capture_tool.plot_manager, 'store_plot', side_effect=mock_store_plot):
                    capture_args = {
                        "code": f"plot(1:10, main='{fmt.upper()} Plot')",
                        "title": f"{fmt.upper()} Test Plot",
                        "format": fmt,
                    }
                    
                    result = await capture_tool.execute(capture_args)
                    assert result.success
                    plot_ids.append(result.metadata["plot_id"])
        
        # List all plots
        list_result = await list_tool.execute({})
        assert list_result.success
        assert f"找到 {len(formats)} 个图表" in list_result.content[0]["text"]
        
        # Test format filtering
        for fmt in formats:
            format_result = await list_tool.execute({"format": fmt})
            assert format_result.success
            assert "找到 1 个图表" in format_result.content[0]["text"]
            
            # Verify the correct format plot is returned
            plot_metadata = format_result.metadata["plots"][0]
            assert plot_metadata["format"] == fmt
            assert fmt.upper() in plot_metadata["title"]