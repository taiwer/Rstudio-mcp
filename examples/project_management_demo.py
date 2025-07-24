"""
Demo script showing project management tools usage.

This script demonstrates how to use the RStudio MCP project management tools
to create, manage, and inspect RStudio projects.
"""

import asyncio
import sys
import tempfile
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rstudio_mcp.api_wrapper import RStudioAPIWrapper
from rstudio_mcp.tools.project_management_tools import (
    CreateProjectTool,
    GetProjectInfoTool,
    OpenProjectTool,
)


async def demo_create_default_project():
    """Demonstrate creating a default R project."""
    print("=== Creating Default R Project ===")
    
    api = RStudioAPIWrapper()
    tool = CreateProjectTool(api)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        result = await tool.execute({
            "name": "my_analysis_project",
            "path": temp_dir,
            "type": "default",
            "git": True
        })
        
        if result.success:
            print("✓ Project created successfully!")
            for content in result.content:
                print(f"  {content['text']}")
            
            # Show project structure
            project_path = Path(temp_dir) / "my_analysis_project"
            print(f"\nProject structure in {project_path}:")
            for item in sorted(project_path.rglob("*")):
                if item.is_file():
                    relative_path = item.relative_to(project_path)
                    print(f"  📄 {relative_path}")
                elif item.is_dir() and item != project_path:
                    relative_path = item.relative_to(project_path)
                    print(f"  📁 {relative_path}/")
        else:
            print(f"✗ Failed to create project: {result.error}")


async def demo_create_shiny_project():
    """Demonstrate creating a Shiny application project."""
    print("\n=== Creating Shiny Application Project ===")
    
    api = RStudioAPIWrapper()
    tool = CreateProjectTool(api)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        result = await tool.execute({
            "name": "my_shiny_app",
            "path": temp_dir,
            "type": "shiny",
            "template_options": {
                "app_type": "single_file"
            }
        })
        
        if result.success:
            print("✓ Shiny project created successfully!")
            
            # Show app.R content preview
            project_path = Path(temp_dir) / "my_shiny_app"
            app_file = project_path / "app.R"
            if app_file.exists():
                print(f"\nPreview of {app_file}:")
                content = app_file.read_text()
                lines = content.split('\n')[:15]  # First 15 lines
                for i, line in enumerate(lines, 1):
                    print(f"  {i:2d}: {line}")
                if len(content.split('\n')) > 15:
                    print("     ... (truncated)")
        else:
            print(f"✗ Failed to create Shiny project: {result.error}")


async def demo_create_package_project():
    """Demonstrate creating an R package project."""
    print("\n=== Creating R Package Project ===")
    
    # Note: This would normally call R's usethis package
    # For demo purposes, we'll show what the call would look like
    
    api = RStudioAPIWrapper()
    tool = CreateProjectTool(api)
    
    print("This would create an R package using usethis::create_package()")
    print("Arguments that would be passed:")
    
    arguments = {
        "name": "myawesomepackage",
        "path": "/tmp",
        "type": "package",
        "template_options": {
            "author": "Jane Doe",
            "email": "jane.doe@example.com",
            "license": "MIT"
        }
    }
    
    for key, value in arguments.items():
        print(f"  {key}: {value}")
    
    print("\nR code that would be executed:")
    print("""
    if (!require(usethis, quietly = TRUE)) {
        install.packages("usethis")
    }
    
    setwd("/tmp")
    
    usethis::create_package("myawesomepackage", 
                           fields = list(
                               Author = "Jane Doe",
                               `Authors@R` = 'person("Jane Doe", email = "jane.doe@example.com", role = c("aut", "cre"))',
                               License = "MIT"
                           ),
                           rstudio = TRUE,
                           open = FALSE)
    """)


async def demo_get_project_info():
    """Demonstrate getting project information."""
    print("\n=== Getting Project Information ===")
    
    api = RStudioAPIWrapper()
    create_tool = CreateProjectTool(api)
    info_tool = GetProjectInfoTool(api)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # First create a project
        create_result = await create_tool.execute({
            "name": "info_demo_project",
            "path": temp_dir,
            "type": "default"
        })
        
        if not create_result.success:
            print(f"✗ Failed to create demo project: {create_result.error}")
            return
        
        project_path = Path(temp_dir) / "info_demo_project"
        
        # Add some demo files
        (project_path / "R" / "analysis.R").write_text("""
# Data Analysis Functions

load_data <- function(file_path) {
    read.csv(file_path)
}

clean_data <- function(data) {
    # Remove missing values
    na.omit(data)
}
""")
        
        (project_path / "data" / "sample.csv").write_text("""
name,age,city
Alice,25,New York
Bob,30,San Francisco
Charlie,35,Chicago
""")
        
        # Get project information
        info_result = await info_tool.execute({
            "project_path": str(project_path),
            "include_files": True,
            "max_files": 20
        })
        
        if info_result.success:
            print("✓ Project information retrieved successfully!")
            
            project_info = info_result.metadata
            print(f"\nProject Details:")
            print(f"  Name: {project_info['name']}")
            print(f"  Type: {project_info['type']}")
            print(f"  Path: {project_info['path']}")
            print(f"  Size: {project_info['size']} bytes")
            print(f"  File Count: {project_info['file_count']}")
            print(f"  Git Enabled: {project_info['git_enabled']}")
            print(f"  renv Enabled: {project_info['renv_enabled']}")
            
            if project_info.get('description'):
                print(f"  Description: {project_info['description']}")
            
            print(f"\nFiles in project:")
            for file_info in project_info['files'][:10]:  # Show first 10 files
                size_kb = file_info['size'] / 1024
                print(f"  📄 {file_info['path']} ({size_kb:.1f} KB)")
            
            if len(project_info['files']) > 10:
                print(f"  ... and {len(project_info['files']) - 10} more files")
        else:
            print(f"✗ Failed to get project info: {info_result.error}")


async def demo_project_types():
    """Demonstrate different project types and their structures."""
    print("\n=== Project Types Comparison ===")
    
    api = RStudioAPIWrapper()
    tool = CreateProjectTool(api)
    
    project_types = [
        ("default", "Standard R project with basic structure"),
        ("shiny", "Interactive web application using Shiny"),
        ("website", "R Markdown website with _site.yml"),
        ("bookdown", "Book/document project using bookdown")
    ]
    
    with tempfile.TemporaryDirectory() as temp_dir:
        for project_type, description in project_types:
            print(f"\n{project_type.upper()} Project:")
            print(f"  Description: {description}")
            
            if project_type == "bookdown":
                print("  Note: Requires bookdown package to be installed")
                continue
            
            result = await tool.execute({
                "name": f"demo_{project_type}",
                "path": temp_dir,
                "type": project_type
            })
            
            if result.success:
                project_path = Path(temp_dir) / f"demo_{project_type}"
                print(f"  ✓ Created successfully at {project_path}")
                
                # Show key files for each type
                key_files = []
                if project_type == "default":
                    key_files = ["*.Rproj", "R/", "data/", "README.md"]
                elif project_type == "shiny":
                    key_files = ["*.Rproj", "app.R", "www/"]
                elif project_type == "website":
                    key_files = ["*.Rproj", "_site.yml", "index.Rmd", "about.Rmd"]
                
                print("  Key files/directories:")
                for pattern in key_files:
                    if pattern.endswith("/"):
                        # Directory
                        dir_path = project_path / pattern.rstrip("/")
                        if dir_path.exists():
                            print(f"    📁 {pattern}")
                    elif "*" in pattern:
                        # Glob pattern
                        matches = list(project_path.glob(pattern))
                        for match in matches:
                            print(f"    📄 {match.name}")
                    else:
                        # Specific file
                        file_path = project_path / pattern
                        if file_path.exists():
                            print(f"    📄 {pattern}")
            else:
                print(f"  ✗ Failed to create: {result.error}")


async def demo_open_project():
    """Demonstrate opening a project (simulation)."""
    print("\n=== Opening Project (Simulation) ===")
    
    # Note: This would normally require RStudio API to be available
    print("The open_project tool would:")
    print("1. Check if RStudio API is available")
    print("2. Resolve the project path to find .Rproj file")
    print("3. Call rstudioapi::openProject() with the resolved path")
    print("4. Optionally open in a new session")
    
    print("\nExample usage:")
    print("""
    api = RStudioAPIWrapper()
    tool = OpenProjectTool(api)
    
    result = await tool.execute({
        "project_path": "/path/to/my_project",
        "new_session": True
    })
    """)
    
    print("\nThis would execute R code similar to:")
    print('rstudioapi::openProject("/path/to/my_project/my_project.Rproj", newSession = TRUE)')


async def main():
    """Run all project management demos."""
    print("RStudio MCP Project Management Tools Demo")
    print("=" * 50)
    
    try:
        await demo_create_default_project()
        await demo_create_shiny_project()
        await demo_create_package_project()
        await demo_get_project_info()
        await demo_project_types()
        await demo_open_project()
        
        print("\n" + "=" * 50)
        print("Demo completed successfully!")
        print("\nThese tools provide comprehensive project management capabilities:")
        print("• Create projects of different types (default, Shiny, package, website)")
        print("• Initialize Git repositories and renv package management")
        print("• Open projects in RStudio (when API is available)")
        print("• Get detailed project information including file structure")
        print("• Support for project templates and customization options")
        
    except Exception as e:
        print(f"\n✗ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())