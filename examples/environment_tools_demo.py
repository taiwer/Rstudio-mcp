#!/usr/bin/env python3
"""
Demonstration of RStudio MCP Environment Management Tools

This script shows how to use the environment management tools:
- CreateEnvironmentTool
- ListEnvironmentsTool  
- SwitchEnvironmentTool
- DeleteEnvironmentTool
"""

import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, Mock

# Add the src directory to the path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import the tools and dependencies
from rstudio_mcp.tools.environment_tools import (
    CreateEnvironmentTool,
    ListEnvironmentsTool,
    SwitchEnvironmentTool,
    DeleteEnvironmentTool
)
from rstudio_mcp.environment_manager import EnvironmentManager
from rstudio_mcp.api_wrapper import RStudioAPIWrapper, ExecutionResult


async def demo_environment_tools():
    """Demonstrate the environment management tools."""
    print("🔧 RStudio MCP Environment Management Tools Demo")
    print("=" * 50)
    
    # Create temporary directory for demo
    temp_dir = tempfile.mkdtemp()
    print(f"📁 Using temporary directory: {temp_dir}")
    
    try:
        # Create mock API wrapper
        api_wrapper = Mock(spec=RStudioAPIWrapper)
        api_wrapper.get_r_version = AsyncMock(return_value="4.3.0")
        api_wrapper.execute_r_code = AsyncMock(return_value=ExecutionResult(
            success=True,
            output="Package installed successfully",
            error=None,
            plots=[],
            execution_time=1.0
        ))
        
        # Create environment manager
        env_manager = EnvironmentManager(api_wrapper, temp_dir)
        
        # Create tools
        create_tool = CreateEnvironmentTool(env_manager)
        list_tool = ListEnvironmentsTool(env_manager)
        switch_tool = SwitchEnvironmentTool(env_manager)
        delete_tool = DeleteEnvironmentTool(env_manager)
        
        print("\n1️⃣ Creating environments...")
        
        # Create first environment
        result = await create_tool.execute({
            "name": "data_analysis",
            "r_version": "4.3.0",
            "description": "Environment for data analysis projects",
            "packages": ["ggplot2", "dplyr", "tidyr"]
        })
        
        if result.success:
            print("✅ Created 'data_analysis' environment")
            print(f"   {result.content[0]['text']}")
        else:
            print(f"❌ Failed to create environment: {result.error}")
        
        # Create second environment
        result = await create_tool.execute({
            "name": "machine_learning",
            "r_version": "4.3.0", 
            "description": "Environment for ML projects",
            "packages": ["caret", "randomForest"]
        })
        
        if result.success:
            print("✅ Created 'machine_learning' environment")
        else:
            print(f"❌ Failed to create environment: {result.error}")
        
        print("\n2️⃣ Listing environments...")
        
        result = await list_tool.execute({"include_status": True})
        if result.success:
            print("📋 Available environments:")
            print(result.content[0]['text'])
        else:
            print(f"❌ Failed to list environments: {result.error}")
        
        print("\n3️⃣ Switching environments...")
        
        # Switch to data_analysis environment
        result = await switch_tool.execute({"name": "data_analysis"})
        if result.success:
            print("✅ Switched to 'data_analysis' environment")
            print(f"   {result.content[0]['text']}")
        else:
            print(f"❌ Failed to switch environment: {result.error}")
        
        # List environments again to show active status
        result = await list_tool.execute({"include_status": True})
        if result.success:
            print("\n📋 Environments after switching:")
            print(result.content[0]['text'])
        
        print("\n4️⃣ Attempting to delete active environment (should fail)...")
        
        result = await delete_tool.execute({
            "name": "data_analysis",
            "force": False
        })
        
        if result.success:
            print("❌ Unexpected: deletion should have failed")
        else:
            print(f"✅ Correctly prevented deletion: {result.error}")
        
        print("\n5️⃣ Switching to another environment and deleting...")
        
        # Switch to machine_learning environment
        await switch_tool.execute({"name": "machine_learning"})
        print("✅ Switched to 'machine_learning' environment")
        
        # Now delete the data_analysis environment
        result = await delete_tool.execute({"name": "data_analysis"})
        if result.success:
            print("✅ Successfully deleted 'data_analysis' environment")
            print(f"   {result.content[0]['text']}")
        else:
            print(f"❌ Failed to delete environment: {result.error}")
        
        print("\n6️⃣ Final environment list...")
        
        result = await list_tool.execute({})
        if result.success:
            print("📋 Remaining environments:")
            print(result.content[0]['text'])
        
        print("\n7️⃣ Force deleting remaining environment...")
        
        result = await delete_tool.execute({
            "name": "machine_learning",
            "force": True
        })
        
        if result.success:
            print("✅ Force deleted 'machine_learning' environment")
        else:
            print(f"❌ Failed to force delete: {result.error}")
        
        # Final check
        result = await list_tool.execute({})
        if result.success:
            print("\n📋 Final check - environments remaining:")
            print(result.content[0]['text'])
        
        print("\n🎉 Demo completed successfully!")
        
    finally:
        # Cleanup temporary directory
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"🧹 Cleaned up temporary directory: {temp_dir}")


def demo_tool_properties():
    """Demonstrate tool properties and MCP format."""
    print("\n🔍 Tool Properties and MCP Format Demo")
    print("=" * 40)
    
    # Create mock environment manager for tool initialization
    mock_env_manager = Mock()
    
    tools = [
        CreateEnvironmentTool(mock_env_manager),
        ListEnvironmentsTool(mock_env_manager),
        SwitchEnvironmentTool(mock_env_manager),
        DeleteEnvironmentTool(mock_env_manager)
    ]
    
    for tool in tools:
        print(f"\n🛠️  Tool: {tool.name}")
        print(f"   Description: {tool.description}")
        print(f"   Parameters: {len(tool.parameters)}")
        
        # Show required parameters
        required = [p.name for p in tool.parameters if p.required]
        if required:
            print(f"   Required: {', '.join(required)}")
        
        # Show optional parameters
        optional = [p.name for p in tool.parameters if not p.required]
        if optional:
            print(f"   Optional: {', '.join(optional)}")
        
        # Show MCP format
        mcp_tool = tool.to_mcp_tool()
        print(f"   MCP Name: {mcp_tool['name']}")
        print(f"   Schema Properties: {len(mcp_tool['inputSchema']['properties'])}")


if __name__ == "__main__":
    print("🚀 Starting RStudio MCP Environment Tools Demo")
    
    # Run the main demo
    asyncio.run(demo_environment_tools())
    
    # Show tool properties
    demo_tool_properties()
    
    print("\n✨ All demos completed!")