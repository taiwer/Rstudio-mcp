#!/usr/bin/env python3
"""
Demo script for RStudio MCP Workspace Management Tools.

This script demonstrates the workspace management capabilities including:
- Saving and loading workspace states
- Listing workspace objects with detailed information
- Cleaning and optimizing workspace
- Managing workspace objects by various criteria

Usage:
    python examples/workspace_management_demo.py
"""

import asyncio
import json
import tempfile
from pathlib import Path

from src.rstudio_mcp.api_wrapper import RStudioAPIWrapper
from src.rstudio_mcp.tools.workspace_management_tools import (
    CleanWorkspaceTool,
    ListWorkspaceObjectsTool,
    LoadWorkspaceTool,
    SaveWorkspaceTool,
)


async def demo_workspace_management():
    """Demonstrate workspace management tools."""
    print("🔧 RStudio MCP Workspace Management Tools Demo")
    print("=" * 50)
    
    # Initialize API wrapper and tools
    try:
        api = RStudioAPIWrapper()
        
        save_tool = SaveWorkspaceTool(api)
        load_tool = LoadWorkspaceTool(api)
        list_tool = ListWorkspaceObjectsTool(api)
        clean_tool = CleanWorkspaceTool(api)
        
        print("✅ Tools initialized successfully")
        
    except Exception as e:
        print(f"❌ Failed to initialize tools: {e}")
        print("Note: This demo requires R and rpy2 to be properly installed")
        return
    
    # Demo 1: Create some sample data in R workspace
    print("\n📊 Demo 1: Creating Sample Data")
    print("-" * 30)
    
    sample_data_code = """
    # Create various types of objects for demonstration
    x <- 1:100
    y <- rnorm(1000)
    df <- data.frame(
        id = 1:50,
        value = runif(50),
        category = sample(c("A", "B", "C"), 50, replace = TRUE)
    )
    large_matrix <- matrix(rnorm(10000), nrow = 100, ncol = 100)
    text_data <- c("hello", "world", "R", "programming")
    
    cat("Sample data created successfully\\n")
    """
    
    try:
        result = await api.execute_r_code(sample_data_code, capture_plots=False)
        if result.success:
            print("✅ Sample data created in R workspace")
            print(f"   Output: {result.output.strip()}")
        else:
            print(f"❌ Failed to create sample data: {result.error}")
            return
    except Exception as e:
        print(f"❌ Error creating sample data: {e}")
        return
    
    # Demo 2: List workspace objects
    print("\n📋 Demo 2: Listing Workspace Objects")
    print("-" * 35)
    
    try:
        list_result = await list_tool.execute({
            "include_details": True,
            "sort_by": "size",
            "include_hidden": False
        })
        
        if list_result.success:
            print("✅ Workspace objects listed successfully")
            for content in list_result.content:
                if content["type"] == "text":
                    print(f"   {content['text']}")
            
            if list_result.metadata:
                print(f"\n📊 Metadata: {list_result.metadata['object_count']} objects found")
        else:
            print(f"❌ Failed to list objects: {list_result.error}")
    
    except Exception as e:
        print(f"❌ Error listing objects: {e}")
    
    # Demo 3: Save workspace
    print("\n💾 Demo 3: Saving Workspace")
    print("-" * 25)
    
    with tempfile.NamedTemporaryFile(suffix='.RData', delete=False) as f:
        workspace_file = f.name
    
    try:
        save_result = await save_tool.execute({
            "file_path": workspace_file,
            "include_hidden": False,
            "compress": True,
            "overwrite": True
        })
        
        if save_result.success:
            print("✅ Workspace saved successfully")
            for content in save_result.content:
                if content["type"] == "text":
                    print(f"   {content['text']}")
            
            print(f"   📁 Saved to: {workspace_file}")
        else:
            print(f"❌ Failed to save workspace: {save_result.error}")
    
    except Exception as e:
        print(f"❌ Error saving workspace: {e}")
    
    # Demo 4: Clean workspace (remove large objects)
    print("\n🧹 Demo 4: Cleaning Workspace (Remove Large Objects)")
    print("-" * 50)
    
    try:
        clean_result = await clean_tool.execute({
            "action": "remove_large",
            "size_threshold_mb": 0.5,  # Remove objects larger than 0.5MB
            "confirm": True
        })
        
        if clean_result.success:
            print("✅ Large objects removed successfully")
            for content in clean_result.content:
                if content["type"] == "text":
                    print(f"   {content['text']}")
        else:
            print(f"❌ Failed to clean workspace: {clean_result.error}")
    
    except Exception as e:
        print(f"❌ Error cleaning workspace: {e}")
    
    # Demo 5: List objects after cleaning
    print("\n📋 Demo 5: Workspace After Cleaning")
    print("-" * 32)
    
    try:
        list_after_clean = await list_tool.execute({
            "include_details": True,
            "sort_by": "name"
        })
        
        if list_after_clean.success:
            print("✅ Workspace objects after cleaning:")
            for content in list_after_clean.content:
                if content["type"] == "text":
                    print(f"   {content['text']}")
        else:
            print(f"❌ Failed to list objects: {list_after_clean.error}")
    
    except Exception as e:
        print(f"❌ Error listing objects: {e}")
    
    # Demo 6: Clear entire workspace
    print("\n🗑️  Demo 6: Clearing Entire Workspace")
    print("-" * 33)
    
    try:
        clear_result = await clean_tool.execute({
            "action": "clear_all",
            "confirm": True
        })
        
        if clear_result.success:
            print("✅ Workspace cleared successfully")
            for content in clear_result.content:
                if content["type"] == "text":
                    print(f"   {content['text']}")
        else:
            print(f"❌ Failed to clear workspace: {clear_result.error}")
    
    except Exception as e:
        print(f"❌ Error clearing workspace: {e}")
    
    # Demo 7: Verify workspace is empty
    print("\n🔍 Demo 7: Verifying Empty Workspace")
    print("-" * 32)
    
    try:
        empty_list = await list_tool.execute({})
        
        if empty_list.success:
            print("✅ Workspace status verified:")
            for content in empty_list.content:
                if content["type"] == "text":
                    print(f"   {content['text']}")
        else:
            print(f"❌ Failed to verify workspace: {empty_list.error}")
    
    except Exception as e:
        print(f"❌ Error verifying workspace: {e}")
    
    # Demo 8: Load workspace from file
    print("\n📂 Demo 8: Loading Workspace from File")
    print("-" * 35)
    
    try:
        load_result = await load_tool.execute({
            "file_path": workspace_file,
            "clear_current": False,
            "verbose": True
        })
        
        if load_result.success:
            print("✅ Workspace loaded successfully")
            for content in load_result.content:
                if content["type"] == "text":
                    print(f"   {content['text']}")
        else:
            print(f"❌ Failed to load workspace: {load_result.error}")
    
    except Exception as e:
        print(f"❌ Error loading workspace: {e}")
    
    # Demo 9: Final workspace listing
    print("\n📋 Demo 9: Final Workspace State")
    print("-" * 30)
    
    try:
        final_list = await list_tool.execute({
            "include_details": True,
            "sort_by": "class"
        })
        
        if final_list.success:
            print("✅ Final workspace state:")
            for content in final_list.content:
                if content["type"] == "text":
                    print(f"   {content['text']}")
            
            if final_list.metadata:
                print(f"\n📊 Summary: {final_list.metadata['object_count']} objects restored")
        else:
            print(f"❌ Failed to list final state: {final_list.error}")
    
    except Exception as e:
        print(f"❌ Error listing final state: {e}")
    
    # Demo 10: Garbage collection
    print("\n♻️  Demo 10: Garbage Collection")
    print("-" * 28)
    
    try:
        gc_result = await clean_tool.execute({
            "action": "garbage_collect"
        })
        
        if gc_result.success:
            print("✅ Garbage collection completed")
            for content in gc_result.content:
                if content["type"] == "text":
                    print(f"   {content['text']}")
        else:
            print(f"❌ Failed to run garbage collection: {gc_result.error}")
    
    except Exception as e:
        print(f"❌ Error running garbage collection: {e}")
    
    # Cleanup
    print("\n🧹 Cleanup")
    print("-" * 10)
    
    try:
        Path(workspace_file).unlink(missing_ok=True)
        print(f"✅ Temporary workspace file removed: {workspace_file}")
    except Exception as e:
        print(f"⚠️  Could not remove temporary file: {e}")
    
    print("\n🎉 Demo completed successfully!")
    print("\nWorkspace Management Tools Features Demonstrated:")
    print("  ✓ Creating and managing R workspace objects")
    print("  ✓ Listing objects with detailed information and sorting")
    print("  ✓ Saving workspace state to files")
    print("  ✓ Loading workspace state from files")
    print("  ✓ Selective object removal by size and criteria")
    print("  ✓ Complete workspace clearing")
    print("  ✓ Garbage collection and memory management")
    print("  ✓ Error handling and validation")


async def demo_advanced_filtering():
    """Demonstrate advanced filtering and sorting capabilities."""
    print("\n🔍 Advanced Filtering and Sorting Demo")
    print("=" * 40)
    
    try:
        api = RStudioAPIWrapper()
        list_tool = ListWorkspaceObjectsTool(api)
        clean_tool = CleanWorkspaceTool(api)
        
        # Create diverse objects for filtering demo
        diverse_data_code = """
        # Create objects of different types and sizes
        small_vector <- 1:10
        medium_vector <- 1:1000
        large_vector <- 1:100000
        
        small_df <- data.frame(x = 1:5, y = letters[1:5])
        large_df <- data.frame(
            id = 1:10000,
            value = rnorm(10000),
            category = sample(LETTERS[1:5], 10000, replace = TRUE)
        )
        
        char_data <- c("apple", "banana", "cherry")
        list_data <- list(a = 1:10, b = letters[1:5], c = matrix(1:20, 4, 5))
        
        # Some hidden objects (starting with .)
        .hidden_var <- "secret"
        .hidden_list <- list(x = 1, y = 2)
        
        cat("Diverse objects created for filtering demo\\n")
        """
        
        result = await api.execute_r_code(diverse_data_code, capture_plots=False)
        if result.success:
            print("✅ Diverse objects created")
        else:
            print(f"❌ Failed to create objects: {result.error}")
            return
        
        # Demo filtering by class
        print("\n📊 Filter by Class: data.frame")
        df_filter = await list_tool.execute({
            "filter_class": "data.frame",
            "include_details": True,
            "sort_by": "size"
        })
        
        if df_filter.success:
            for content in df_filter.content:
                if content["type"] == "text":
                    print(f"   {content['text']}")
        
        # Demo sorting by size
        print("\n📏 Sort by Size (Largest First)")
        size_sort = await list_tool.execute({
            "sort_by": "size",
            "include_details": True
        })
        
        if size_sort.success:
            for content in size_sort.content:
                if content["type"] == "text" and "对象列表" in content["text"]:
                    print(f"   {content['text']}")
        
        # Demo including hidden objects
        print("\n🔍 Include Hidden Objects")
        hidden_include = await list_tool.execute({
            "include_hidden": True,
            "sort_by": "name"
        })
        
        if hidden_include.success:
            for content in hidden_include.content:
                if content["type"] == "text" and ("hidden" in content["text"] or "总数" in content["text"]):
                    print(f"   {content['text']}")
        
        # Demo selective removal by class
        print("\n🗑️  Remove All data.frame Objects")
        remove_df = await clean_tool.execute({
            "action": "remove_by_class",
            "object_class": "data.frame",
            "confirm": True
        })
        
        if remove_df.success:
            for content in remove_df.content:
                if content["type"] == "text":
                    print(f"   {content['text']}")
        
        # Final state
        print("\n📋 Final State After Selective Removal")
        final_state = await list_tool.execute({
            "include_details": True,
            "sort_by": "class"
        })
        
        if final_state.success:
            for content in final_state.content:
                if content["type"] == "text":
                    print(f"   {content['text']}")
        
        print("\n✅ Advanced filtering demo completed!")
        
    except Exception as e:
        print(f"❌ Error in advanced filtering demo: {e}")


async def demo_error_scenarios():
    """Demonstrate error handling scenarios."""
    print("\n⚠️  Error Handling Demo")
    print("=" * 25)
    
    try:
        api = RStudioAPIWrapper()
        save_tool = SaveWorkspaceTool(api)
        load_tool = LoadWorkspaceTool(api)
        clean_tool = CleanWorkspaceTool(api)
        
        # 1. Try to load non-existent file
        print("1. Loading non-existent workspace file:")
        load_error = await load_tool.execute({
            "file_path": "/nonexistent/path/workspace.RData"
        })
        print(f"   ❌ Expected error: {load_error.error}")
        
        # 2. Try to save without overwrite permission
        print("\n2. Saving to existing file without overwrite:")
        with tempfile.NamedTemporaryFile(suffix='.RData', delete=False) as f:
            existing_file = f.name
        
        try:
            save_error = await save_tool.execute({
                "file_path": existing_file,
                "overwrite": False
            })
            print(f"   ❌ Expected error: {save_error.error}")
        finally:
            Path(existing_file).unlink(missing_ok=True)
        
        # 3. Try destructive operation without confirmation
        print("\n3. Destructive operation without confirmation:")
        confirm_error = await clean_tool.execute({
            "action": "clear_all",
            "confirm": False
        })
        print(f"   ❌ Expected error: {confirm_error.error}")
        
        # 4. Try to remove objects without specifying names
        print("\n4. Remove objects without specifying names:")
        names_error = await clean_tool.execute({
            "action": "remove_objects",
            "confirm": True
        })
        print(f"   ❌ Expected error: {names_error.error}")
        
        # 5. Try unknown cleaning action
        print("\n5. Unknown cleaning action:")
        unknown_error = await clean_tool.execute({
            "action": "unknown_action",
            "confirm": True
        })
        print(f"   ❌ Expected error: {unknown_error.error}")
        
        print("\n✅ Error handling demo completed - all errors handled gracefully!")
        
    except Exception as e:
        print(f"❌ Unexpected error in error handling demo: {e}")


async def main():
    """Run all demos."""
    print("🚀 Starting RStudio MCP Workspace Management Tools Demo")
    print("=" * 60)
    
    await demo_workspace_management()
    await demo_advanced_filtering()
    await demo_error_scenarios()
    
    print("\n" + "=" * 60)
    print("🎯 All demos completed!")
    print("\nThe workspace management tools provide comprehensive functionality for:")
    print("  • Managing R workspace objects and their lifecycle")
    print("  • Saving and loading workspace states for reproducibility")
    print("  • Advanced filtering and sorting of workspace contents")
    print("  • Memory optimization through selective cleaning")
    print("  • Robust error handling and user safety")
    print("\nThese tools integrate seamlessly with the RStudio MCP server")
    print("to provide AI assistants with powerful workspace management capabilities.")


if __name__ == "__main__":
    asyncio.run(main())