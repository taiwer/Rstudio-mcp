"""Demo script for plot management tools."""

import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.rstudio_mcp.api_wrapper import ExecutionResult, RStudioAPIWrapper
from src.rstudio_mcp.tools.plot_management_tools import (
    CapturePlotTool,
    ListPlotsTool,
    ExportPlotTool,
    PlotManager,
)


def create_sample_plot_file(temp_dir: str, filename: str = "demo_plot.png") -> str:
    """Create a sample plot file for demonstration."""
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


async def demo_plot_management():
    """Demonstrate plot management functionality."""
    print("=== RStudio MCP Plot Management Demo ===\n")
    
    # Create temporary directories
    temp_dir = tempfile.mkdtemp(prefix="plot_demo_")
    storage_dir = tempfile.mkdtemp(prefix="plot_storage_")
    
    try:
        # Initialize components
        print("1. Initializing plot management components...")
        
        # Create mock API wrapper
        mock_api = Mock(spec=RStudioAPIWrapper)
        mock_api.execute_r_code = AsyncMock()
        
        # Create plot manager
        plot_manager = PlotManager(storage_dir=storage_dir)
        
        # Create tools
        capture_tool = CapturePlotTool(mock_api, plot_manager)
        list_tool = ListPlotsTool(plot_manager)
        export_tool = ExportPlotTool(plot_manager)
        
        print(f"   - Plot storage directory: {storage_dir}")
        print(f"   - Temporary directory: {temp_dir}")
        print("   - Tools initialized successfully\n")
        
        # Demo 1: Capture plots
        print("2. Demonstrating plot capture...")
        
        # Mock successful R execution
        mock_api.execute_r_code.return_value = ExecutionResult(
            success=True,
            output="Plot device created successfully",
        )
        
        # Create sample plot files for different scenarios
        sample_plots = [
            ("scatter_plot.png", "plot(mtcars$wt, mtcars$mpg, main='Weight vs MPG')", "Scatter Plot", "Weight vs MPG relationship"),
            ("histogram.png", "hist(rnorm(1000), main='Normal Distribution')", "Histogram", "Distribution of random normal values"),
            ("boxplot.png", "boxplot(mpg ~ cyl, data=mtcars, main='MPG by Cylinders')", "Box Plot", "MPG distribution by cylinder count"),
        ]
        
        captured_plots = []
        
        for filename, code, title, description in sample_plots:
            # Create actual plot file
            plot_file = create_sample_plot_file(temp_dir, filename)
            
            # Store plot directly using plot manager (simulating successful capture)
            plot_id = plot_manager.store_plot(plot_file, code, title, description)
            captured_plots.append(plot_id)
            
            print(f"   - Captured plot: {title} (ID: {plot_id})")
        
        print(f"   - Total plots captured: {len(captured_plots)}\n")
        
        # Demo 2: List plots
        print("3. Demonstrating plot listing...")
        
        # List all plots
        list_result = await list_tool.execute({})
        print("   All plots:")
        print(f"   {list_result.content[0]['text']}\n")
        
        # List with limit
        list_result = await list_tool.execute({"limit": 2})
        print("   Limited to 2 plots:")
        print(f"   {list_result.content[0]['text']}\n")
        
        # List with search
        list_result = await list_tool.execute({"search": "scatter"})
        print("   Search for 'scatter':")
        print(f"   {list_result.content[0]['text']}\n")
        
        # List with format filter
        list_result = await list_tool.execute({"format": "png"})
        print("   Filter by PNG format:")
        print(f"   {list_result.content[0]['text']}\n")
        
        # Demo 3: Export plots
        print("4. Demonstrating plot export...")
        
        if captured_plots:
            plot_id = captured_plots[0]
            export_path = Path(temp_dir) / "exported_scatter_plot.png"
            
            export_result = await export_tool.execute({
                "plot_id": plot_id,
                "output_path": str(export_path)
            })
            
            print("   Export result:")
            print(f"   {export_result.content[0]['text']}")
            
            if export_path.exists():
                print(f"   - Exported file exists: {export_path}")
                print(f"   - File size: {export_path.stat().st_size} bytes\n")
        
        # Demo 4: Plot metadata
        print("5. Demonstrating plot metadata access...")
        
        if captured_plots:
            plot_id = captured_plots[0]
            metadata = plot_manager.get_plot_metadata(plot_id)
            
            if metadata:
                print(f"   Plot ID: {metadata.plot_id}")
                print(f"   Title: {metadata.title}")
                print(f"   Description: {metadata.description}")
                print(f"   Format: {metadata.format}")
                print(f"   Size: {metadata.size} bytes")
                print(f"   Created: {metadata.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"   Code preview: {metadata.code[:50]}...")
                if metadata.width and metadata.height:
                    print(f"   Dimensions: {metadata.width}x{metadata.height}")
                print()
        
        # Demo 5: Error handling
        print("6. Demonstrating error handling...")
        
        # Try to export non-existent plot
        export_result = await export_tool.execute({
            "plot_id": "nonexistent_plot",
            "output_path": "/tmp/nonexistent.png"
        })
        
        print("   Export non-existent plot:")
        print(f"   Success: {export_result.success}")
        print(f"   Error: {export_result.error}\n")
        
        # Try to list with invalid format
        list_result = await list_tool.execute({"format": "invalid_format"})
        print("   List with invalid format:")
        print(f"   {list_result.content[0]['text']}\n")
        
        # Demo 6: Plot cleanup
        print("7. Demonstrating plot cleanup...")
        
        initial_count = len(plot_manager.list_plots())
        print(f"   Initial plot count: {initial_count}")
        
        # Delete a plot
        if captured_plots:
            plot_id = captured_plots[0]
            success = plot_manager.delete_plot(plot_id)
            print(f"   Deleted plot {plot_id}: {success}")
            
            remaining_count = len(plot_manager.list_plots())
            print(f"   Remaining plot count: {remaining_count}")
        
        # Cleanup old plots (simulate old plots by setting max_age_days to 0)
        deleted_count = plot_manager.cleanup_old_plots(max_age_days=0)
        print(f"   Cleaned up {deleted_count} old plots")
        
        final_count = len(plot_manager.list_plots())
        print(f"   Final plot count: {final_count}\n")
        
        print("=== Demo completed successfully! ===")
        
    except Exception as e:
        print(f"Demo failed with error: {e}")
        raise
    
    finally:
        # Cleanup temporary directories
        shutil.rmtree(temp_dir, ignore_errors=True)
        shutil.rmtree(storage_dir, ignore_errors=True)
        print(f"Cleaned up temporary directories")


async def demo_capture_tool_integration():
    """Demonstrate capture tool with mocked R execution."""
    print("\n=== Plot Capture Tool Integration Demo ===\n")
    
    temp_dir = tempfile.mkdtemp(prefix="capture_demo_")
    storage_dir = tempfile.mkdtemp(prefix="capture_storage_")
    
    try:
        # Setup
        mock_api = Mock(spec=RStudioAPIWrapper)
        mock_api.execute_r_code = AsyncMock()
        
        plot_manager = PlotManager(storage_dir=storage_dir)
        capture_tool = CapturePlotTool(mock_api, plot_manager)
        
        print("1. Testing plot capture with different formats...")
        
        formats = ["png", "pdf", "svg", "jpeg"]
        
        for fmt in formats:
            print(f"\n   Testing {fmt.upper()} format:")
            
            # Mock successful R execution
            mock_api.execute_r_code.return_value = ExecutionResult(
                success=True,
                output=f"{fmt.upper()} plot created successfully",
            )
            
            # Create a sample plot file that would be created by R
            sample_plot = create_sample_plot_file(temp_dir, f"test_plot.{fmt}")
            
            # Mock the file operations for capture
            from unittest.mock import patch, mock_open
            
            with patch('tempfile.mkdtemp') as mock_mkdtemp, \
                 patch('os.path.exists') as mock_exists, \
                 patch('builtins.open', create=True) as mock_file_open, \
                 patch('shutil.rmtree'):
                
                # Setup mocks
                plot_temp_dir = f"/tmp/mock_plot_{fmt}"
                mock_mkdtemp.return_value = plot_temp_dir
                mock_exists.return_value = True
                
                # Read actual plot data
                with open(sample_plot, 'rb') as f:
                    plot_data = f.read()
                
                mock_file_open.return_value.__enter__.return_value.read.return_value = plot_data
                
                # Mock plot manager store_plot to use actual file
                original_store_plot = plot_manager.store_plot
                
                def mock_store_plot(source_path, code, title=None, description=None):
                    return original_store_plot(sample_plot, code, title, description)
                
                with patch.object(plot_manager, 'store_plot', side_effect=mock_store_plot):
                    # Execute capture
                    arguments = {
                        "code": f"plot(1:10, main='{fmt.upper()} Test Plot')",
                        "title": f"{fmt.upper()} Test Plot",
                        "description": f"A test plot in {fmt.upper()} format",
                        "format": fmt,
                        "width": 800,
                        "height": 600,
                    }
                    
                    result = await capture_tool.execute(arguments)
                    
                    print(f"     Success: {result.success}")
                    if result.success:
                        print(f"     Plot ID: {result.metadata.get('plot_id', 'N/A')}")
                        print(f"     Content items: {len(result.content)}")
                        print(f"     Format: {result.metadata.get('format', 'N/A')}")
                    else:
                        print(f"     Error: {result.error}")
        
        print("\n2. Testing error scenarios...")
        
        # Test R execution failure
        mock_api.execute_r_code.return_value = ExecutionResult(
            success=False,
            error="R syntax error: unexpected symbol",
        )
        
        result = await capture_tool.execute({
            "code": "invalid R syntax !!!",
            "title": "Failed Plot"
        })
        
        print(f"   R execution failure:")
        print(f"     Success: {result.success}")
        print(f"     Error: {result.error}")
        
        print("\n=== Capture Tool Demo completed! ===")
        
    except Exception as e:
        print(f"Capture demo failed: {e}")
        raise
    
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        shutil.rmtree(storage_dir, ignore_errors=True)


async def main():
    """Run all demos."""
    try:
        await demo_plot_management()
        await demo_capture_tool_integration()
    except Exception as e:
        print(f"Demo failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))