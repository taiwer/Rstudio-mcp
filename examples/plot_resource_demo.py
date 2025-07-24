"""Demo script for plot resource functionality."""

import asyncio
import json
import tempfile
import shutil
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.rstudio_mcp.resources.plot_resource import PlotResource
from src.rstudio_mcp.tools.plot_management_tools import PlotManager


def create_sample_plot_file(temp_dir: str, filename: str = "demo_plot.png", format_type: str = "png") -> str:
    """Create a sample plot file for demonstration."""
    plot_file = Path(temp_dir) / filename
    
    if format_type == "png":
        # Create a minimal PNG file (1x1 pixel)
        data = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13'
            b'\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc```'
            b'\x00\x00\x00\x04\x00\x01\xdd\x8d\xb4\x1c\x00\x00\x00\x00IEND\xaeB`\x82'
        )
    elif format_type == "pdf":
        data = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 1\n0000000000 65535 f \ntrailer\n<<\n/Size 1\n/Root 1 0 R\n>>\nstartxref\n9\n%%EOF"
    elif format_type == "svg":
        data = b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="red"/></svg>'
    else:  # jpeg
        data = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x01\x01\x11\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00\xaa\xff\xd9'
    
    with open(plot_file, 'wb') as f:
        f.write(data)
    return str(plot_file)


async def demo_plot_resources():
    """Demonstrate plot resource functionality."""
    print("=== RStudio MCP Plot Resource Demo ===\n")
    
    # Create temporary directories
    temp_dir = tempfile.mkdtemp(prefix="plot_resource_demo_")
    storage_dir = tempfile.mkdtemp(prefix="plot_resource_storage_")
    
    try:
        # Initialize components
        print("1. Initializing plot resource components...")
        
        plot_manager = PlotManager(storage_dir=storage_dir)
        plot_resource = PlotResource(plot_manager=plot_manager)
        
        print(f"   - Plot storage directory: {storage_dir}")
        print(f"   - Temporary directory: {temp_dir}")
        print(f"   - Resource scheme: {plot_resource.scheme}")
        print(f"   - Resource description: {plot_resource.description}")
        print()
        
        # Demo 1: Store some sample plots
        print("2. Creating sample plots...")
        
        sample_plots = [
            ("scatter_plot.png", "png", "plot(mtcars$wt, mtcars$mpg, main='Weight vs MPG')", "Scatter Plot", "Weight vs MPG relationship"),
            ("histogram.pdf", "pdf", "hist(rnorm(1000), main='Normal Distribution')", "Histogram", "Distribution of random normal values"),
            ("boxplot.svg", "svg", "boxplot(mpg ~ cyl, data=mtcars, main='MPG by Cylinders')", "Box Plot", "MPG distribution by cylinder count"),
            ("barplot.png", "png", "barplot(table(mtcars$cyl), main='Cylinder Count')", "Bar Plot", "Count of cars by cylinder number"),
        ]
        
        plot_ids = []
        
        for filename, format_type, code, title, description in sample_plots:
            # Create sample plot file
            plot_file = create_sample_plot_file(temp_dir, filename, format_type)
            
            # Store plot
            plot_id = plot_manager.store_plot(plot_file, code, title, description)
            plot_ids.append(plot_id)
            
            print(f"   - Created {format_type.upper()} plot: {title} (ID: {plot_id})")
        
        print(f"   - Total plots created: {len(plot_ids)}\n")
        
        # Demo 2: List all resources
        print("3. Listing all plot resources...")
        
        resources = await plot_resource.list_resources()
        
        print(f"   Found {len(resources)} resources:")
        for resource in resources[:6]:  # Show first 6 resources
            print(f"   - {resource.uri}")
            print(f"     Name: {resource.name}")
            print(f"     MIME Type: {resource.mime_type}")
            print(f"     Size: {resource.size} bytes" if resource.size else "     Size: N/A")
            print()
        
        if len(resources) > 6:
            print(f"   ... and {len(resources) - 6} more resources\n")
        
        # Demo 3: Test resource filtering
        print("4. Testing resource filtering...")
        
        # Filter by format
        png_resources = await plot_resource.list_resources("rstudio-plot://?format=png")
        print(f"   PNG format resources: {len(png_resources)}")
        
        # Search by title
        scatter_resources = await plot_resource.list_resources("rstudio-plot://?search=scatter")
        print(f"   Resources matching 'scatter': {len(scatter_resources)}")
        
        # Limit results
        limited_resources = await plot_resource.list_resources("rstudio-plot://?limit=5")
        print(f"   Limited to 5 resources: {len(limited_resources)}")
        print()
        
        # Demo 4: Read different resource types
        print("5. Reading different resource types...")
        
        if plot_ids:
            plot_id = plot_ids[0]
            
            # Read plot binary data
            print(f"   Reading plot data for {plot_id}...")
            data_result = await plot_resource.read_resource(f"rstudio-plot://{plot_id}")
            print(f"   - Success: {data_result.success}")
            print(f"   - MIME Type: {data_result.mime_type}")
            print(f"   - Is Binary: {data_result.is_binary()}")
            if data_result.success:
                binary_data = data_result.get_binary_content()
                print(f"   - Data Size: {len(binary_data)} bytes")
                print(f"   - Metadata: {list(data_result.metadata.keys())}")
            print()
            
            # Read plot metadata
            print(f"   Reading plot metadata for {plot_id}...")
            metadata_result = await plot_resource.read_resource(f"rstudio-plot://{plot_id}/metadata")
            print(f"   - Success: {metadata_result.success}")
            print(f"   - MIME Type: {metadata_result.mime_type}")
            print(f"   - Is Text: {metadata_result.is_text()}")
            if metadata_result.success:
                metadata_json = json.loads(metadata_result.get_text_content())
                print(f"   - Plot ID: {metadata_json.get('plot_id')}")
                print(f"   - Title: {metadata_json.get('title')}")
                print(f"   - Format: {metadata_json.get('format')}")
                print(f"   - File Exists: {metadata_json.get('file_exists')}")
                print(f"   - Age: {metadata_json.get('age_seconds'):.1f} seconds")
            print()
            
            # Read plot code
            print(f"   Reading plot code for {plot_id}...")
            code_result = await plot_resource.read_resource(f"rstudio-plot://{plot_id}/code")
            print(f"   - Success: {code_result.success}")
            print(f"   - MIME Type: {code_result.mime_type}")
            if code_result.success:
                code_content = code_result.get_text_content()
                print(f"   - Code: {code_content}")
                print(f"   - Language: {code_result.metadata.get('language')}")
            print()
            
            # Read plot thumbnail
            print(f"   Reading plot thumbnail for {plot_id}...")
            thumbnail_result = await plot_resource.read_resource(f"rstudio-plot://{plot_id}/thumbnail")
            print(f"   - Success: {thumbnail_result.success}")
            print(f"   - MIME Type: {thumbnail_result.mime_type}")
            if thumbnail_result.success:
                thumbnail_data = thumbnail_result.get_binary_content()
                print(f"   - Thumbnail Size: {len(thumbnail_data)} bytes")
            print()
        
        # Demo 5: Plot collection resource
        print("6. Testing plot collection resource...")
        
        collection_resource = await plot_resource.create_plot_collection_resource()
        print(f"   Collection URI: {collection_resource.uri}")
        print(f"   Collection Name: {collection_resource.name}")
        print(f"   Collection Description: {collection_resource.description}")
        print(f"   Plot Count: {collection_resource.metadata['plot_count']}")
        print(f"   Formats: {collection_resource.metadata['formats']}")
        print(f"   Total Size: {collection_resource.metadata['total_size']} bytes")
        print()
        
        # Read collection data
        collection_result = await plot_resource.read_plot_collection()
        if collection_result.success:
            collection_data = json.loads(collection_result.get_text_content())
            print(f"   Collection Type: {collection_data['type']}")
            print(f"   Plot Count: {collection_data['count']}")
            print(f"   Format Distribution: {collection_data['summary']['formats']}")
            print(f"   Date Range: {collection_data['summary']['date_range']['earliest']} to {collection_data['summary']['date_range']['latest']}")
        print()
        
        # Demo 6: Search functionality
        print("7. Testing search functionality...")
        
        # Search for plots
        search_results = await plot_resource.search_plots("scatter", limit=5)
        print(f"   Search for 'scatter': {len(search_results)} results")
        for result in search_results:
            print(f"   - {result.name} (Score: {result.metadata.get('match_score', 0):.2f})")
        
        # Search with format filter
        png_search_results = await plot_resource.search_plots("plot", format_filter="png", limit=3)
        print(f"   Search for 'plot' in PNG format: {len(png_search_results)} results")
        for result in png_search_results:
            print(f"   - {result.name}")
        print()
        
        # Demo 7: URI validation
        print("8. Testing URI validation...")
        
        valid_uris = [
            "rstudio-plot://plot_123",
            "rstudio-plot://plot_123/metadata",
            "rstudio-plot://plot_123/code",
            "rstudio-plot://plot_123/thumbnail"
        ]
        
        invalid_uris = [
            "http://example.com",
            "rstudio-project://test",
            "invalid-uri",
            "rstudio-plot://"
        ]
        
        print("   Valid URIs:")
        for uri in valid_uris:
            is_valid = plot_resource.validate_uri(uri)
            print(f"   - {uri}: {is_valid}")
        
        print("   Invalid URIs:")
        for uri in invalid_uris:
            is_valid = plot_resource.validate_uri(uri)
            print(f"   - {uri}: {is_valid}")
        print()
        
        # Demo 8: Error handling
        print("9. Testing error handling...")
        
        # Try to read non-existent plot
        error_result = await plot_resource.read_resource("rstudio-plot://nonexistent_plot")
        print(f"   Non-existent plot:")
        print(f"   - Success: {error_result.success}")
        print(f"   - Error: {error_result.error}")
        
        # Try invalid resource type
        if plot_ids:
            invalid_result = await plot_resource.read_resource(f"rstudio-plot://{plot_ids[0]}/invalid_type")
            print(f"   Invalid resource type:")
            print(f"   - Success: {invalid_result.success}")
            print(f"   - Error: {invalid_result.error}")
        
        # Try invalid URI format
        invalid_uri_result = await plot_resource.read_resource("rstudio-plot://")
        print(f"   Invalid URI format:")
        print(f"   - Success: {invalid_uri_result.success}")
        print(f"   - Error: {invalid_uri_result.error}")
        print()
        
        # Demo 9: MIME type detection
        print("10. Testing MIME type detection...")
        
        formats = ["png", "jpg", "jpeg", "svg", "pdf", "gif", "tiff", "bmp", "unknown"]
        for fmt in formats:
            mime_type = plot_resource._get_mime_type(fmt)
            print(f"   - {fmt}: {mime_type}")
        print()
        
        print("=== Plot Resource Demo completed successfully! ===")
        
    except Exception as e:
        print(f"Demo failed with error: {e}")
        raise
    
    finally:
        # Cleanup temporary directories
        shutil.rmtree(temp_dir, ignore_errors=True)
        shutil.rmtree(storage_dir, ignore_errors=True)
        print(f"Cleaned up temporary directories")


async def main():
    """Run the demo."""
    try:
        await demo_plot_resources()
    except Exception as e:
        print(f"Demo failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))