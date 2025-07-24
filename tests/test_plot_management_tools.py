"""Tests for plot management tools."""

import json
import os
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.rstudio_mcp.api_wrapper import ExecutionResult, RStudioAPIWrapper
from src.rstudio_mcp.tools.plot_management_tools import (
    CapturePlotTool,
    ExportPlotTool,
    ListPlotsTool,
    PlotManager,
    PlotMetadata,
)


class TestPlotMetadata:
    """Test PlotMetadata class."""
    
    def test_to_dict(self):
        """Test converting metadata to dictionary."""
        created_at = datetime.now()
        metadata = PlotMetadata(
            plot_id="test_plot_001",
            file_path="/path/to/plot.png",
            format="png",
            created_at=created_at,
            code="plot(1:10)",
            size=1024,
            width=800,
            height=600,
            title="Test Plot",
            description="A test plot",
        )
        
        result = metadata.to_dict()
        
        assert result["plot_id"] == "test_plot_001"
        assert result["file_path"] == "/path/to/plot.png"
        assert result["format"] == "png"
        assert result["created_at"] == created_at.isoformat()
        assert result["code"] == "plot(1:10)"
        assert result["size"] == 1024
        assert result["width"] == 800
        assert result["height"] == 600
        assert result["title"] == "Test Plot"
        assert result["description"] == "A test plot"
    
    def test_from_dict(self):
        """Test creating metadata from dictionary."""
        created_at = datetime.now()
        data = {
            "plot_id": "test_plot_001",
            "file_path": "/path/to/plot.png",
            "format": "png",
            "created_at": created_at.isoformat(),
            "code": "plot(1:10)",
            "size": 1024,
            "width": 800,
            "height": 600,
            "title": "Test Plot",
            "description": "A test plot",
        }
        
        metadata = PlotMetadata.from_dict(data)
        
        assert metadata.plot_id == "test_plot_001"
        assert metadata.file_path == "/path/to/plot.png"
        assert metadata.format == "png"
        assert metadata.created_at == created_at
        assert metadata.code == "plot(1:10)"
        assert metadata.size == 1024
        assert metadata.width == 800
        assert metadata.height == 600
        assert metadata.title == "Test Plot"
        assert metadata.description == "A test plot"


class TestPlotManager:
    """Test PlotManager class."""
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory."""
        temp_dir = tempfile.mkdtemp(prefix="test_plot_storage_")
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def plot_manager(self, temp_storage_dir):
        """Create PlotManager instance."""
        return PlotManager(storage_dir=temp_storage_dir)
    
    @pytest.fixture
    def sample_plot_file(self, temp_storage_dir):
        """Create a sample plot file."""
        plot_file = Path(temp_storage_dir) / "sample_plot.png"
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
    
    def test_initialization(self, temp_storage_dir):
        """Test PlotManager initialization."""
        manager = PlotManager(storage_dir=temp_storage_dir)
        
        assert manager.storage_dir == Path(temp_storage_dir)
        assert manager.storage_dir.exists()
        assert manager.metadata_file == Path(temp_storage_dir) / "plot_metadata.json"
        assert isinstance(manager._metadata_cache, dict)
    
    def test_store_plot(self, plot_manager, sample_plot_file):
        """Test storing a plot."""
        code = "plot(1:10)"
        title = "Test Plot"
        description = "A simple test plot"
        
        plot_id = plot_manager.store_plot(
            sample_plot_file, code, title, description
        )
        
        assert plot_id is not None
        assert plot_id.startswith("plot_")
        
        # Check metadata
        metadata = plot_manager.get_plot_metadata(plot_id)
        assert metadata is not None
        assert metadata.plot_id == plot_id
        assert metadata.code == code
        assert metadata.title == title
        assert metadata.description == description
        assert metadata.format == "png"
        assert metadata.size > 0
        
        # Check file was copied
        stored_file = Path(metadata.file_path)
        assert stored_file.exists()
        assert stored_file.parent == plot_manager.storage_dir
    
    def test_store_plot_file_not_found(self, plot_manager):
        """Test storing a plot with non-existent file."""
        with pytest.raises(FileNotFoundError):
            plot_manager.store_plot("/nonexistent/file.png", "plot(1:10)")
    
    def test_list_plots_empty(self, plot_manager):
        """Test listing plots when none exist."""
        plots = plot_manager.list_plots()
        assert plots == []
    
    def test_list_plots_with_data(self, plot_manager, sample_plot_file):
        """Test listing plots with stored data."""
        # Store multiple plots
        plot_id1 = plot_manager.store_plot(sample_plot_file, "plot(1:10)", "Plot 1")
        plot_id2 = plot_manager.store_plot(sample_plot_file, "hist(rnorm(100))", "Plot 2")
        
        plots = plot_manager.list_plots()
        
        assert len(plots) == 2
        plot_ids = [p.plot_id for p in plots]
        assert plot_id1 in plot_ids
        assert plot_id2 in plot_ids
        
        # Check sorting (newest first)
        assert plots[0].created_at >= plots[1].created_at
    
    def test_list_plots_with_limit(self, plot_manager, sample_plot_file):
        """Test listing plots with limit."""
        # Store multiple plots
        for i in range(5):
            plot_manager.store_plot(sample_plot_file, f"plot({i})", f"Plot {i}")
        
        plots = plot_manager.list_plots(limit=3)
        assert len(plots) == 3
    
    def test_list_plots_with_format_filter(self, plot_manager, sample_plot_file):
        """Test listing plots with format filter."""
        plot_manager.store_plot(sample_plot_file, "plot(1:10)", "PNG Plot")
        
        # Test matching filter
        plots = plot_manager.list_plots(format_filter="png")
        assert len(plots) == 1
        
        # Test non-matching filter
        plots = plot_manager.list_plots(format_filter="pdf")
        assert len(plots) == 0
    
    def test_list_plots_with_search(self, plot_manager, sample_plot_file):
        """Test listing plots with search term."""
        plot_manager.store_plot(sample_plot_file, "plot(1:10)", "Scatter Plot", "A scatter plot")
        plot_manager.store_plot(sample_plot_file, "hist(rnorm(100))", "Histogram", "A histogram")
        
        # Search in title
        plots = plot_manager.list_plots(search_term="scatter")
        assert len(plots) == 1
        assert plots[0].title == "Scatter Plot"
        
        # Search in description
        plots = plot_manager.list_plots(search_term="histogram")
        assert len(plots) == 1
        assert plots[0].title == "Histogram"
        
        # Search in code
        plots = plot_manager.list_plots(search_term="rnorm")
        assert len(plots) == 1
        assert plots[0].title == "Histogram"
    
    def test_delete_plot(self, plot_manager, sample_plot_file):
        """Test deleting a plot."""
        plot_id = plot_manager.store_plot(sample_plot_file, "plot(1:10)")
        
        # Verify plot exists
        metadata = plot_manager.get_plot_metadata(plot_id)
        assert metadata is not None
        stored_file = Path(metadata.file_path)
        assert stored_file.exists()
        
        # Delete plot
        success = plot_manager.delete_plot(plot_id)
        assert success
        
        # Verify plot is deleted
        assert plot_manager.get_plot_metadata(plot_id) is None
        assert not stored_file.exists()
    
    def test_delete_nonexistent_plot(self, plot_manager):
        """Test deleting a non-existent plot."""
        success = plot_manager.delete_plot("nonexistent_plot")
        assert not success
    
    def test_export_plot_same_format(self, plot_manager, sample_plot_file, temp_storage_dir):
        """Test exporting plot in same format."""
        plot_id = plot_manager.store_plot(sample_plot_file, "plot(1:10)")
        output_path = os.path.join(temp_storage_dir, "exported_plot.png")
        
        success = plot_manager.export_plot(plot_id, output_path)
        assert success
        assert os.path.exists(output_path)
    
    def test_export_nonexistent_plot(self, plot_manager, temp_storage_dir):
        """Test exporting non-existent plot."""
        output_path = os.path.join(temp_storage_dir, "exported_plot.png")
        success = plot_manager.export_plot("nonexistent_plot", output_path)
        assert not success
    
    def test_cleanup_old_plots(self, plot_manager, sample_plot_file):
        """Test cleaning up old plots."""
        # Store a plot
        plot_id = plot_manager.store_plot(sample_plot_file, "plot(1:10)")
        
        # Manually set old creation time
        metadata = plot_manager._metadata_cache[plot_id]
        old_time = datetime.now().timestamp() - (40 * 24 * 3600)  # 40 days ago
        metadata.created_at = datetime.fromtimestamp(old_time)
        
        # Run cleanup (30 days max age)
        deleted_count = plot_manager.cleanup_old_plots(max_age_days=30)
        
        assert deleted_count == 1
        assert plot_manager.get_plot_metadata(plot_id) is None
    
    def test_metadata_persistence(self, temp_storage_dir, sample_plot_file):
        """Test that metadata persists across manager instances."""
        # Create first manager and store plot
        manager1 = PlotManager(storage_dir=temp_storage_dir)
        plot_id = manager1.store_plot(sample_plot_file, "plot(1:10)", "Test Plot")
        
        # Create second manager and check plot exists
        manager2 = PlotManager(storage_dir=temp_storage_dir)
        metadata = manager2.get_plot_metadata(plot_id)
        
        assert metadata is not None
        assert metadata.plot_id == plot_id
        assert metadata.title == "Test Plot"


class TestCapturePlotTool:
    """Test CapturePlotTool class."""
    
    @pytest.fixture
    def mock_api_wrapper(self):
        """Create mock API wrapper."""
        mock = Mock(spec=RStudioAPIWrapper)
        mock.execute_r_code = AsyncMock()
        return mock
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory."""
        temp_dir = tempfile.mkdtemp(prefix="test_plot_storage_")
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def plot_manager(self, temp_storage_dir):
        """Create PlotManager instance."""
        return PlotManager(storage_dir=temp_storage_dir)
    
    @pytest.fixture
    def capture_tool(self, mock_api_wrapper, plot_manager):
        """Create CapturePlotTool instance."""
        return CapturePlotTool(mock_api_wrapper, plot_manager)
    
    def test_tool_properties(self, capture_tool):
        """Test tool properties."""
        assert capture_tool.name == "capture_plot"
        assert "捕获" in capture_tool.description
        
        params = capture_tool.parameters
        param_names = [p.name for p in params]
        assert "code" in param_names
        assert "title" in param_names
        assert "description" in param_names
        assert "format" in param_names
        assert "width" in param_names
        assert "height" in param_names
    
    @pytest.mark.asyncio
    async def test_execute_success(self, capture_tool, mock_api_wrapper):
        """Test successful plot capture."""
        # Mock successful R execution
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=True,
            output="Plot created successfully",
        )
        
        # Create a temporary plot file that will be "created" by R
        with patch('tempfile.mkdtemp') as mock_mkdtemp, \
             patch('os.path.exists') as mock_exists, \
             patch('builtins.open', create=True) as mock_open, \
             patch('shutil.rmtree'):
            
            temp_dir = "/tmp/test_plot_dir"
            mock_mkdtemp.return_value = temp_dir
            mock_exists.return_value = True
            
            # Mock file content
            plot_data = b"fake_png_data"
            mock_open.return_value.__enter__.return_value.read.return_value = plot_data
            
            # Mock plot manager store_plot
            with patch.object(capture_tool.plot_manager, 'store_plot') as mock_store, \
                 patch.object(capture_tool.plot_manager, 'get_plot_metadata') as mock_get_meta:
                
                mock_store.return_value = "plot_123"
                mock_meta = Mock()
                mock_meta.created_at = datetime.now()
                mock_get_meta.return_value = mock_meta
                
                arguments = {
                    "code": "plot(1:10)",
                    "title": "Test Plot",
                    "format": "png",
                    "width": 800,
                    "height": 600,
                }
                
                result = await capture_tool.execute(arguments)
                
                assert result.success
                assert len(result.content) == 2  # Text + image content
                assert "plot_123" in result.content[0]["text"]
                assert result.content[1]["type"] == "image"
                assert "plot_id" in result.metadata
    
    @pytest.mark.asyncio
    async def test_execute_r_code_failure(self, capture_tool, mock_api_wrapper):
        """Test plot capture with R code failure."""
        # Mock R execution failure
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=False,
            error="R syntax error",
        )
        
        arguments = {"code": "invalid_r_code()"}
        result = await capture_tool.execute(arguments)
        
        assert not result.success
        assert "Failed to execute plot code" in result.error
    
    @pytest.mark.asyncio
    async def test_execute_no_plot_file(self, capture_tool, mock_api_wrapper):
        """Test plot capture when no plot file is created."""
        # Mock successful R execution but no file created
        mock_api_wrapper.execute_r_code.return_value = ExecutionResult(
            success=True,
            output="No plot generated",
        )
        
        with patch('tempfile.mkdtemp') as mock_mkdtemp, \
             patch('os.path.exists') as mock_exists, \
             patch('shutil.rmtree'):
            
            mock_mkdtemp.return_value = "/tmp/test_plot_dir"
            mock_exists.return_value = False  # No plot file created
            
            arguments = {"code": "# No plot code"}
            result = await capture_tool.execute(arguments)
            
            assert not result.success
            assert "Plot file was not created" in result.error


class TestListPlotsTool:
    """Test ListPlotsTool class."""
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory."""
        temp_dir = tempfile.mkdtemp(prefix="test_plot_storage_")
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def plot_manager(self, temp_storage_dir):
        """Create PlotManager instance."""
        return PlotManager(storage_dir=temp_storage_dir)
    
    @pytest.fixture
    def list_tool(self, plot_manager):
        """Create ListPlotsTool instance."""
        return ListPlotsTool(plot_manager)
    
    def test_tool_properties(self, list_tool):
        """Test tool properties."""
        assert list_tool.name == "list_plots"
        assert "列出" in list_tool.description
        
        params = list_tool.parameters
        param_names = [p.name for p in params]
        assert "limit" in param_names
        assert "format" in param_names
        assert "search" in param_names
    
    @pytest.mark.asyncio
    async def test_execute_empty_list(self, list_tool):
        """Test listing when no plots exist."""
        arguments = {}
        result = await list_tool.execute(arguments)
        
        assert result.success
        assert "没有找到" in result.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_execute_with_plots(self, list_tool, plot_manager):
        """Test listing with existing plots."""
        # Mock some plot metadata
        metadata1 = PlotMetadata(
            plot_id="plot_001",
            file_path="/path/to/plot1.png",
            format="png",
            created_at=datetime.now(),
            code="plot(1:10)",
            size=1024,
            width=800,
            height=600,
            title="Test Plot 1",
        )
        
        metadata2 = PlotMetadata(
            plot_id="plot_002",
            file_path="/path/to/plot2.png",
            format="pdf",
            created_at=datetime.now(),
            code="hist(rnorm(100))",
            size=2048,
            title="Test Plot 2",
        )
        
        plot_manager._metadata_cache = {
            "plot_001": metadata1,
            "plot_002": metadata2,
        }
        
        arguments = {}
        result = await list_tool.execute(arguments)
        
        assert result.success
        assert "找到 2 个图表" in result.content[0]["text"]
        assert "plot_001" in result.content[0]["text"]
        assert "plot_002" in result.content[0]["text"]
        assert result.metadata["total_plots"] == 2
        assert len(result.metadata["plots"]) == 2
    
    @pytest.mark.asyncio
    async def test_execute_with_filters(self, list_tool, plot_manager):
        """Test listing with filters."""
        # Mock plot metadata
        metadata = PlotMetadata(
            plot_id="plot_001",
            file_path="/path/to/plot1.png",
            format="png",
            created_at=datetime.now(),
            code="plot(1:10)",
            size=1024,
            title="Scatter Plot",
        )
        
        plot_manager._metadata_cache = {"plot_001": metadata}
        
        # Test format filter
        arguments = {"format": "png"}
        result = await list_tool.execute(arguments)
        assert result.success
        assert "找到 1 个图表" in result.content[0]["text"]
        
        # Test search filter
        arguments = {"search": "scatter"}
        result = await list_tool.execute(arguments)
        assert result.success
        assert "找到 1 个图表" in result.content[0]["text"]


class TestExportPlotTool:
    """Test ExportPlotTool class."""
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory."""
        temp_dir = tempfile.mkdtemp(prefix="test_plot_storage_")
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def plot_manager(self, temp_storage_dir):
        """Create PlotManager instance."""
        return PlotManager(storage_dir=temp_storage_dir)
    
    @pytest.fixture
    def export_tool(self, plot_manager):
        """Create ExportPlotTool instance."""
        return ExportPlotTool(plot_manager)
    
    def test_tool_properties(self, export_tool):
        """Test tool properties."""
        assert export_tool.name == "export_plot"
        assert "导出" in export_tool.description
        
        params = export_tool.parameters
        param_names = [p.name for p in params]
        assert "plot_id" in param_names
        assert "output_path" in param_names
        assert "format" in param_names
    
    @pytest.mark.asyncio
    async def test_execute_success(self, export_tool, plot_manager):
        """Test successful plot export."""
        # Mock plot metadata
        metadata = PlotMetadata(
            plot_id="plot_001",
            file_path="/path/to/plot1.png",
            format="png",
            created_at=datetime.now(),
            code="plot(1:10)",
            size=1024,
            title="Test Plot",
        )
        
        plot_manager._metadata_cache = {"plot_001": metadata}
        
        with patch.object(plot_manager, 'export_plot') as mock_export:
            mock_export.return_value = True
            
            arguments = {
                "plot_id": "plot_001",
                "output_path": "/tmp/exported_plot.png",
            }
            
            result = await export_tool.execute(arguments)
            
            assert result.success
            assert "已成功导出" in result.content[0]["text"]
            assert result.metadata["plot_id"] == "plot_001"
            assert result.metadata["output_path"] == "/tmp/exported_plot.png"
    
    @pytest.mark.asyncio
    async def test_execute_plot_not_found(self, export_tool):
        """Test export with non-existent plot."""
        arguments = {
            "plot_id": "nonexistent_plot",
            "output_path": "/tmp/exported_plot.png",
        }
        
        result = await export_tool.execute(arguments)
        
        assert not result.success
        assert "not found" in result.error
    
    @pytest.mark.asyncio
    async def test_execute_export_failure(self, export_tool, plot_manager):
        """Test export failure."""
        # Mock plot metadata
        metadata = PlotMetadata(
            plot_id="plot_001",
            file_path="/path/to/plot1.png",
            format="png",
            created_at=datetime.now(),
            code="plot(1:10)",
            size=1024,
        )
        
        plot_manager._metadata_cache = {"plot_001": metadata}
        
        with patch.object(plot_manager, 'export_plot') as mock_export:
            mock_export.return_value = False
            
            arguments = {
                "plot_id": "plot_001",
                "output_path": "/tmp/exported_plot.png",
            }
            
            result = await export_tool.execute(arguments)
            
            assert not result.success
            assert "Failed to export" in result.error