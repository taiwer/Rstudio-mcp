#!/usr/bin/env python3
"""
Demo script for RStudio MCP Package Management Tools.

This script demonstrates the usage of package management tools including:
- Installing R packages
- Updating R packages  
- Uninstalling R packages
- Listing installed packages

Note: This is a demonstration script. In a real MCP server, these tools would be
called through the MCP protocol by an AI client.
"""

import asyncio
import logging
from unittest.mock import AsyncMock, Mock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.rstudio_mcp.api_wrapper import RStudioAPIWrapper, ExecutionResult
from src.rstudio_mcp.environment_manager import EnvironmentManager
from src.rstudio_mcp.tools.package_management_tools import (
    InstallPackageTool,
    UpdatePackageTool,
    UninstallPackageTool,
    ListPackagesTool
)


def setup_logging():
    """Set up logging for the demo."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def create_mock_api_wrapper():
    """Create a mock API wrapper for demonstration."""
    api = Mock(spec=RStudioAPIWrapper)
    api.execute_r_code = AsyncMock()
    return api


def create_mock_environment_manager():
    """Create a mock environment manager for demonstration."""
    env_manager = Mock(spec=EnvironmentManager)
    env_manager.get_environment = AsyncMock(return_value=True)
    env_manager.switch_environment = AsyncMock(return_value=True)
    return env_manager


async def demo_install_package():
    """Demonstrate package installation."""
    print("\n" + "="*60)
    print("📦 PACKAGE INSTALLATION DEMO")
    print("="*60)
    
    # Create mock dependencies
    api_wrapper = create_mock_api_wrapper()
    env_manager = create_mock_environment_manager()
    
    # Mock R API responses for package installation
    api_wrapper.execute_r_code.side_effect = [
        ExecutionResult(success=True, output="FALSE"),  # Package not installed
        ExecutionResult(success=True, output="Installing package 'ggplot2'..."),  # Installation
        ExecutionResult(success=True, output="TRUE"),  # Verification
        ExecutionResult(success=True, output='"3.4.0"'),  # Version check
        ExecutionResult(success=True, output='"scales" "gtable" "grid"')  # Dependencies
    ]
    
    # Create and execute tool
    tool = InstallPackageTool(api_wrapper, env_manager)
    
    print("Installing ggplot2 package...")
    result = await tool.execute({
        "package": "ggplot2",
        "dependencies": True
    })
    
    print(f"Success: {result.success}")
    for content in result.content:
        print(f"Output: {content['text']}")
    
    if result.error:
        print(f"Error: {result.error}")


async def demo_update_package():
    """Demonstrate package update."""
    print("\n" + "="*60)
    print("🔄 PACKAGE UPDATE DEMO")
    print("="*60)
    
    # Create mock dependencies
    api_wrapper = create_mock_api_wrapper()
    env_manager = create_mock_environment_manager()
    
    # Mock R API responses for package update
    api_wrapper.execute_r_code.side_effect = [
        ExecutionResult(success=True, output="TRUE"),  # Package installed
        ExecutionResult(success=True, output='"3.4.0"'),  # Current version
        ExecutionResult(success=True, output="Updating package 'ggplot2'..."),  # Update
        ExecutionResult(success=True, output='"3.4.1"')  # New version
    ]
    
    # Create and execute tool
    tool = UpdatePackageTool(api_wrapper, env_manager)
    
    print("Updating ggplot2 package...")
    result = await tool.execute({
        "package": "ggplot2"
    })
    
    print(f"Success: {result.success}")
    for content in result.content:
        print(f"Output: {content['text']}")
    
    if result.error:
        print(f"Error: {result.error}")


async def demo_list_packages():
    """Demonstrate package listing."""
    print("\n" + "="*60)
    print("📋 PACKAGE LISTING DEMO")
    print("="*60)
    
    # Create mock dependencies
    api_wrapper = create_mock_api_wrapper()
    env_manager = create_mock_environment_manager()
    
    # Mock R API response for package listing
    package_json = '''[
        {
            "name": "base",
            "version": "4.3.0",
            "description": "The R Base Package",
            "built": "4.3.0"
        },
        {
            "name": "ggplot2",
            "version": "3.4.1",
            "description": "Create Elegant Data Visualisations Using the Grammar of Graphics",
            "built": "4.3.0"
        },
        {
            "name": "dplyr",
            "version": "1.1.0",
            "description": "A Grammar of Data Manipulation",
            "built": "4.3.0"
        }
    ]'''
    
    api_wrapper.execute_r_code.return_value = ExecutionResult(
        success=True,
        output=package_json
    )
    
    # Create and execute tool
    tool = ListPackagesTool(api_wrapper, env_manager)
    
    print("Listing installed packages...")
    result = await tool.execute({
        "include_description": True,
        "sort_by": "name"
    })
    
    print(f"Success: {result.success}")
    for content in result.content:
        print(f"Output:\n{content['text']}")
    
    if result.error:
        print(f"Error: {result.error}")


async def demo_uninstall_package():
    """Demonstrate package uninstallation."""
    print("\n" + "="*60)
    print("🗑️  PACKAGE UNINSTALLATION DEMO")
    print("="*60)
    
    # Create mock dependencies
    api_wrapper = create_mock_api_wrapper()
    env_manager = create_mock_environment_manager()
    
    # Mock R API responses for package uninstallation
    api_wrapper.execute_r_code.side_effect = [
        ExecutionResult(success=True, output="TRUE"),  # Package installed
        ExecutionResult(success=True, output='"3.4.1"'),  # Package version
        ExecutionResult(success=True, output="character(0)"),  # No dependents
        ExecutionResult(success=True, output="Removing package 'ggplot2'..."),  # Uninstall
        ExecutionResult(success=True, output="FALSE")  # Verification
    ]
    
    # Create and execute tool
    tool = UninstallPackageTool(api_wrapper, env_manager)
    
    print("Uninstalling ggplot2 package...")
    result = await tool.execute({
        "package": "ggplot2"
    })
    
    print(f"Success: {result.success}")
    for content in result.content:
        print(f"Output: {content['text']}")
    
    if result.error:
        print(f"Error: {result.error}")


async def demo_package_with_dependencies():
    """Demonstrate handling package with dependencies."""
    print("\n" + "="*60)
    print("⚠️  PACKAGE WITH DEPENDENCIES DEMO")
    print("="*60)
    
    # Create mock dependencies
    api_wrapper = create_mock_api_wrapper()
    env_manager = create_mock_environment_manager()
    
    # Mock R API responses showing package has dependents
    api_wrapper.execute_r_code.side_effect = [
        ExecutionResult(success=True, output="TRUE"),  # Package installed
        ExecutionResult(success=True, output='"1.2.0"'),  # Package version
        ExecutionResult(success=True, output='"ggplot2" "dplyr"')  # Has dependents
    ]
    
    # Create and execute tool
    tool = UninstallPackageTool(api_wrapper, env_manager)
    
    print("Attempting to uninstall scales package (has dependents)...")
    result = await tool.execute({
        "package": "scales"
    })
    
    print(f"Success: {result.success}")
    if result.content:
        for content in result.content:
            print(f"Output: {content['text']}")
    
    if result.error:
        print(f"Error: {result.error}")
    
    # Now try with force
    print("\nTrying again with force=true...")
    api_wrapper.execute_r_code.side_effect = [
        ExecutionResult(success=True, output="TRUE"),  # Package installed
        ExecutionResult(success=True, output='"1.2.0"'),  # Package version
        ExecutionResult(success=True, output="Force removing package 'scales'..."),  # Force uninstall
        ExecutionResult(success=True, output="FALSE")  # Verification
    ]
    
    result = await tool.execute({
        "package": "scales",
        "force": True
    })
    
    print(f"Success: {result.success}")
    for content in result.content:
        print(f"Output: {content['text']}")


async def demo_environment_switching():
    """Demonstrate package operations with environment switching."""
    print("\n" + "="*60)
    print("🔄 ENVIRONMENT SWITCHING DEMO")
    print("="*60)
    
    # Create mock dependencies
    api_wrapper = create_mock_api_wrapper()
    env_manager = create_mock_environment_manager()
    
    # Mock R API responses for package installation in specific environment
    api_wrapper.execute_r_code.side_effect = [
        ExecutionResult(success=True, output="FALSE"),  # Package not installed
        ExecutionResult(success=True, output="Installing in test_env..."),  # Installation
        ExecutionResult(success=True, output="TRUE"),  # Verification
        ExecutionResult(success=True, output='"1.0.0"'),  # Version check
        ExecutionResult(success=True, output="character(0)")  # Dependencies
    ]
    
    # Create and execute tool
    tool = InstallPackageTool(api_wrapper, env_manager)
    
    print("Installing jsonlite package in 'test_env' environment...")
    result = await tool.execute({
        "package": "jsonlite",
        "environment": "test_env"
    })
    
    print(f"Success: {result.success}")
    for content in result.content:
        print(f"Output: {content['text']}")
    
    # Verify environment operations were called
    print(f"Environment checked: {env_manager.get_environment.called}")
    print(f"Environment switched: {env_manager.switch_environment.called}")


async def main():
    """Run all package management demos."""
    setup_logging()
    
    print("🚀 RStudio MCP Package Management Tools Demo")
    print("This demo shows how the package management tools work.")
    print("Note: This uses mock R API responses for demonstration purposes.")
    
    try:
        await demo_install_package()
        await demo_update_package()
        await demo_list_packages()
        await demo_uninstall_package()
        await demo_package_with_dependencies()
        await demo_environment_switching()
        
        print("\n" + "="*60)
        print("✅ ALL DEMOS COMPLETED SUCCESSFULLY!")
        print("="*60)
        print("\nThe package management tools provide:")
        print("• 📦 install_package - Install R packages with dependency resolution")
        print("• 🔄 update_package - Update packages to latest versions")
        print("• 🗑️  uninstall_package - Safely remove packages with dependency checks")
        print("• 📋 list_packages - List installed packages with detailed information")
        print("\nAll tools support:")
        print("• Environment switching")
        print("• Error handling and validation")
        print("• Detailed logging and feedback")
        print("• Dependency management")
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())