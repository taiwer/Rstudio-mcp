"""Tests for plot resource handler."""

import json
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.rstudio_mcp.resources.plot_resource import PlotResource
from src.rstudio_mcp.tools.plot_management_tools import PlotManager, PlotMetadata


class TestPlotResource:
    """Test PlotResource class."""
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory."""
        temp_dir = tempfile.mkdtemp(prefix="test_plot_resource_")
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def plot_manager(self, temp_storage_dir):
        """Create PlotManager instance."""
        return PlotManager(storage_dir=temp_storage_dir)
    
    @pytest.fixture
    def plot_resource(self, plot_manager):
        """Create PlotResource instance."""
        return PlotResource(plot_manager=plot_manager)
    
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
    
    def test_resource_properties(self, plot_resource):
        """Test resource properties."""
        assert plot_resource.scheme == "rstudio-plot"
        assert "plot" in plot_resource.description.lower()
    
    def test_validate_uri(self, plot_resource):
        """Test URI validation."""
        # Valid URIs
        assert plot_resource.validate_uri("rstudio-plot://plot_123")
        assert plot_resource.validate_uri("rstudio-plot://plot_123/metadata")
        assert plot_resource.validate_uri("rstudio-plot://plot_123/code")
        
        # Invalid URIs
        assert not plot_resource.validate_uri("http://example.com")
        assert not plot_resource.validate_uri("invalid-uri")
        assert not plot_resource.validate_uri("rstudio-project://test")
    
    def test_get_mime_type(self, plot_resource):
        """Test MIME type detection."""
        assert plot_resource._get_mime_type("png") == "image/png"
        assert plot_resource._get_mime_type("jpg") == "image/jpeg"
        assert plot_resource._get_mime_type("jpeg") == "image/jpeg"
        assert plot_resource._get_mime_type("svg") == "image/svg+xml"
        assert plot_resource._get_mime_type("pdf") == "application/pdf"
        assert plot_resource._get_mime_type("unknown") == "application/octet-stream"
    
    @pytest.mark.asyncio
    async def test_list_resources_empty(self, plot_resource):
        """Test listing resources when no plots exist."""
        resources = await plot_resource.list_resources()
        assert resources == []
    
    @pytest.mark.asyncio
    async def test_list_resources_with_plots(self, plot_resource, plot_manager, sample_plot_file):
        """Test listing resources with existing plots."""
        # Store some plots
        plot_id1 = plot_manager.store_plot(sample_plot_file, "plot(1:10)", "Test Plot 1", "First test plot")
        plot_id2 = plot_manager.store_plot(sample_plot_file, "hist(rnorm(100))", "Test Plot 2", "Second test plot")
        
        resources = await plot_resource.list_resources()
        
        # Should have 3 resources per plot (data, metadata, code)
        assert len(resources) == 6
        
        # Check resource URIs
        uris = [r.uri for r in resources]
        assert f"rstudio-plot://{plot_id1}" in uris
        assert f"rstudio-plot://{plot_id1}/metadata" in uris
        assert f"rstudio-plot://{plot_id1}/code" in uris
        assert f"rstudio-plot://{plot_id2}" in uris
        assert f"rstudio-plot://{plot_id2}/metadata" in uris
        assert f"rstudio-plot://{plot_id2}/code" in uris
        
        # Check MIME types
        mime_types = [r.mime_type for r in resources]
        assert "image/png" in mime_types
        assert "application/json" in mime_types
        assert "text/x-r" in mime_types
    
    @pytest.mark.asyncio
    async def test_list_resources_with_filters(self, plot_resource, plot_manager, sample_plot_file):
        """Test listing resources with filters."""
        # Store plots with different formats
        plot_id = plot_manager.store_plot(sample_plot_file, "plot(1:10)", "PNG Plot")
        
        # Test format filter (via URI prefix query parameters)
        resources = await plot_resource.list_resources("rstudio-plot://?format=png")
        assert len(resources) == 3  # data, metadata, code
        
        # Test search filter
        resources = await plot_resource.list_resources("rstudio-plot://?search=PNG")
        assert len(resources) == 3
        
        # Test limit filter
        resources = await plot_resource.list_resources("rstudio-plot://?limit=2")
        assert len(resources) == 2
    
    @pytest.mark.asyncio
    async def test_read_plot_data(self, plot_resource, plot_manager, sample_plot_file):
        """Test reading plot binary data."""
        plot_id = plot_manager.store_plot(sample_plot_file, "plot(1:10)", "Test Plot")
        
        result = await plot_resource.read_resource(f"rstudio-plot://{plot_id}")
        
        assert result.success
        assert result.is_binary()
        assert result.mime_type == "image/png"
        assert result.get_binary_content() is not None
        assert len(result.get_binary_content()) > 0
        assert result.metadata["plot_id"] == plot_id
        assert result.metadata["format"] == "png"
        assert "encoding" in result.metadata
    
    @pytest.mark.asyncio
    async def test_read_plot_metadata(self, plot_resource, plot_manager, sample_plot_file):
        """Test reading plot metadata."""
        plot_id = plot_manager.store_plot(sample_plot_file, "plot(1:10)", "Test Plot", "A test plot")
        
        result = await plot_resource.read_resource(f"rstudio-plot://{plot_id}/metadata")
        
        assert result.success
        assert result.is_text()
        assert result.mime_type == "application/json"
        
        # Parse JSON content
        metadata = json.loads(result.get_text_content())
        assert metadata["plot_id"] == plot_id
        assert metadata["title"] == "Test Plot"
        assert metadata["description"] == "A test plot"
        assert metadata["format"] == "png"
        assert "uri" in metadata
        assert "data_uri" in metadata
        assert "code_uri" in metadata
        assert "file_exists" in metadata
        assert "age_seconds" in metadata
    
    @pytest.mark.asyncio
    async def test_read_plot_code(self, plot_resource, plot_manager, sample_plot_file):
        """Test reading plot R code."""
        code = "plot(1:10, main='Test Plot')"
        plot_id = plot_manager.store_plot(sample_plot_file, code, "Test Plot")
        
        result = await plot_resource.read_resource(f"rstudio-plot://{plot_id}/code")
        
        assert result.success
        assert result.is_text()
        assert result.mime_type == "text/x-r"
        assert result.get_text_content() == code
        assert result.metadata["plot_id"] == plot_id
        assert result.metadata["language"] == "r"
        assert result.metadata["code_length"] == len(code)
    
    @pytest.mark.asyncio
    async def test_read_plot_thumbnail(self, plot_resource, plot_manager, sample_plot_file):
        """Test reading plot thumbnail."""
        plot_id = plot_manager.store_plot(sample_plot_file, "plot(1:10)", "Test Plot")
        
        result = await plot_resource.read_resource(f"rstudio-plot://{plot_id}/thumbnail")
        
        assert result.success
        assert result.is_binary()
        assert result.mime_type == "image/png"
        # For now, thumbnail is same as original data
        assert result.get_binary_content() is not None
    
    @pytest.mark.asyncio
    async def test_read_nonexistent_plot(self, plot_resource):
        """Test reading non-existent plot."""
        result = await plot_resource.read_resource("rstudio-plot://nonexistent_plot")
        
        assert not result.success
        assert "not found" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_read_invalid_resource_type(self, plot_resource, plot_manager, sample_plot_file):
        """Test reading invalid resource type."""
        plot_id = plot_manager.store_plot(sample_plot_file, "plot(1:10)", "Test Plot")
        
        result = await plot_resource.read_resource(f"rstudio-plot://{plot_id}/invalid_type")
        
        assert not result.success
        assert "unknown resource type" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_read_invalid_uri(self, plot_resource):
        """Test reading with invalid URI."""
        result = await plot_resource.read_resource("rstudio-plot://")
        
        assert not result.success
        assert "invalid" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_create_plot_collection_resource(self, plot_resource, plot_manager, sample_plot_file):
        """Test creating plot collection resource."""
        # Store some plots
        plot_manager.store_plot(sample_plot_file, "plot(1:10)", "Plot 1")
        plot_manager.store_plot(sample_plot_file, "hist(rnorm(100))", "Plot 2")
        
        resource = await plot_resource.create_plot_collection_resource()
        
        assert resource.uri == "rstudio-plot://collection"
        assert resource.name == "Plot Collection"
        assert "2 plots" in resource.description
        assert resource.mime_type == "application/json"
        assert resource.metadata["type"] == "collection"
        assert resource.metadata["plot_count"] == 2
        assert "png" in resource.metadata["formats"]
    
    @pytest.mark.asyncio
    async def test_read_plot_collection(self, plot_resource, plot_manager, sample_plot_file):
        """Test reading plot collection."""
        # Store some plots
        plot_manager.store_plot(sample_plot_file, "plot(1:10)", "Plot 1")
        plot_manager.store_plot(sample_plot_file, "hist(rnorm(100))", "Plot 2")
        
        result = await plot_resource.read_plot_collection()
        
        assert result.success
        assert result.is_text()
        assert result.mime_type == "application/json"
        
        # Parse JSON content
        collection = json.loads(result.get_text_content())
        assert collection["type"] == "plot_collection"
        assert collection["count"] == 2
        assert len(collection["plots"]) == 2
        assert "summary" in collection
        assert "formats" in collection["summary"]
        assert collection["summary"]["total_size"] > 0
    
    @pytest.mark.asyncio
    async def test_search_plots(self, plot_resource, plot_manager, sample_plot_file):
        """Test searching plots."""
        # Store plots with different titles
        plot_manager.store_plot(sample_plot_file, "plot(1:10)", "Scatter Plot", "A scatter plot")
        plot_manager.store_plot(sample_plot_file, "hist(rnorm(100))", "Histogram", "A histogram plot")
        plot_manager.store_plot(sample_plot_file, "boxplot(data)", "Box Plot", "A box plot")
        
        # Search for "scatter"
        resources = await plot_resource.search_plots("scatter")
        assert len(resources) == 1
        assert "Scatter Plot" in resources[0].name
        
        # Search for "plot"
        resources = await plot_resource.search_plots("plot")
        assert len(resources) == 3  # All plots contain "plot"
        
        # Search with format filter
        resources = await plot_resource.search_plots("plot", format_filter="png")
        assert len(resources) == 3
        
        # Search with limit
        resources = await plot_resource.search_plots("plot", limit=2)
        assert len(resources) == 2
    
    def test_calculate_match_score(self, plot_resource):
        """Test match score calculation."""
        plot = PlotMetadata(
            plot_id="test_plot",
            file_path="/path/to/plot.png",
            format="png",
            created_at=datetime.now(),
            code="plot(mtcars$wt, mtcars$mpg)",
            size=1024,
            title="Scatter Plot",
            description="Weight vs MPG scatter plot"
        )
        
        # Title match should have high score
        score = plot_resource._calculate_match_score(plot, "scatter")
        assert score >= 0.4
        
        # Description match
        score = plot_resource._calculate_match_score(plot, "weight")
        assert score >= 0.3
        
        # Code match
        score = plot_resource._calculate_match_score(plot, "mtcars")
        assert score >= 0.2
        
        # Format match
        score = plot_resource._calculate_match_score(plot, "png")
        assert score >= 0.1
        
        # No match
        score = plot_resource._calculate_match_score(plot, "nonexistent")
        assert score == 0.0
    
    @pytest.mark.asyncio
    async def test_read_plot_missing_file(self, plot_resource, plot_manager, sample_plot_file):
        """Test reading plot when file is missing."""
        plot_id = plot_manager.store_plot(sample_plot_file, "plot(1:10)", "Test Plot")
        
        # Delete the plot file
        metadata = plot_manager.get_plot_metadata(plot_id)
        Path(metadata.file_path).unlink()
        
        result = await plot_resource.read_resource(f"rstudio-plot://{plot_id}")
        
        assert not result.success
        assert "not found" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_different_plot_formats(self, plot_resource, plot_manager, temp_storage_dir):
        """Test handling different plot formats."""
        formats = ["png", "pdf", "svg", "jpeg"]
        
        for fmt in formats:
            # Create sample file for this format
            plot_file = Path(temp_storage_dir) / f"test_plot.{fmt}"
            
            if fmt == "png":
                # PNG data
                data = (
                    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
                    b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13'
                    b'\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc```'
                    b'\x00\x00\x00\x04\x00\x01\xdd\x8d\xb4\x1c\x00\x00\x00\x00IEND\xaeB`\x82'
                )
            elif fmt == "pdf":
                data = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 1\n0000000000 65535 f \ntrailer\n<<\n/Size 1\n/Root 1 0 R\n>>\nstartxref\n9\n%%EOF"
            elif fmt == "svg":
                data = b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="red"/></svg>'
            else:  # jpeg
                data = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x01\x01\x11\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00\xaa\xff\xd9'
            
            with open(plot_file, 'wb') as f:
                f.write(data)
            
            # Store plot
            plot_id = plot_manager.store_plot(str(plot_file), f"plot(1:10, main='{fmt.upper()}')", f"{fmt.upper()} Plot")
            
            # Test reading the plot
            result = await plot_resource.read_resource(f"rstudio-plot://{plot_id}")
            
            assert result.success
            assert result.is_binary()
            
            # Check MIME type
            expected_mime = plot_resource._get_mime_type(fmt)
            assert result.mime_type == expected_mime
            
            # Check metadata
            assert result.metadata["format"] == fmt
            assert result.metadata["plot_id"] == plot_id