#!/usr/bin/env python3
"""
Demo script for RStudio MCP code execution tools.

This script demonstrates the code execution functionality including:
- Executing R code with result capture
- Plot generation and capture
- Execution history management
- Error handling and timeout management
- Environment switching
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rstudio_mcp.api_wrapper import ExecutionResult, RStudioAPIWrapper
from rstudio_mcp.environment_manager import Environment, EnvironmentManager
from rstudio_mcp.tools.code_execution_tools import (
    ClearExecutionHistoryTool,
    ExecuteRCodeTool,
    ExecutionHistory,
    GetExecutionHistoryTool,
)


def setup_logging():
    """Setup logging for the demo."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def create_mock_api_wrapper():
    """Create a mock API wrapper for demonstration."""
    api = Mock(spec=RStudioAPIWrapper)
    
    # Mock different types of execution results
    def mock_execute_r_code(code, **kwargs):
        """Mock R code execution with realistic responses."""
        if "error" in code.lower():
            return ExecutionResult(
                success=False,
                error="object 'nonexistent_var' not found",
                execution_time=0.05
            )
        elif "plot" in code.lower():
            # Create a temporary plot file for demo
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(b"fake_plot_data_for_demo")
                plot_path = f.name
            
            return ExecutionResult(
                success=True,
                output="Plot created successfully",
                plots=[plot_path],
                execution_time=0.3
            )
        elif "sleep" in code.lower():
            # Simulate long-running code
            return ExecutionResult(
                success=True,
                output="Completed after delay",
                execution_time=2.0
            )
        elif "warning" in code.lower():
            return ExecutionResult(
                success=True,
                output="[1] 42",
                warnings=["Warning: This is a demo warning"],
                execution_time=0.1
            )
        else:
            # Default successful execution
            return ExecutionResult(
                success=True,
                output=f"[1] Result of: {code}",
                execution_time=0.1
            )
    
    api.execute_r_code = AsyncMock(side_effect=mock_execute_r_code)
    return api


def create_mock_env_manager():
    """Create a mock environment manager for demonstration."""
    env_manager = Mock(spec=EnvironmentManager)
    
    # Create some demo environments
    demo_envs = {
        "data_analysis": Environment(
            name="data_analysis",
            r_version="4.3.0",
            path="/tmp/data_analysis",
            packages=["dplyr", "ggplot2", "tidyr"]
        ),
        "machine_learning": Environment(
            name="machine_learning",
            r_version="4.3.0",
            path="/tmp/machine_learning",
            packages=["caret", "randomForest", "e1071"]
        )
    }
    
    env_manager.get_environment = AsyncMock(
        side_effect=lambda name: demo_envs.get(name)
    )
    env_manager.switch_environment = AsyncMock(return_value=True)
    
    return env_manager


async def demo_basic_execution(execute_tool):
    """Demonstrate basic R code execution."""
    print("\n" + "="*60)
    print("🚀 DEMO: Basic R Code Execution")
    print("="*60)
    
    # Simple arithmetic
    print("\n📝 Executing: 2 + 3 * 4")
    result = await execute_tool.execute({
        "code": "2 + 3 * 4",
        "save_to_history": True
    })
    
    print(f"✅ Success: {result.success}")
    if result.content:
        print(f"📄 Output:\n{result.content[0]['text']}")
        if len(result.content) > 1:
            print(f"📊 Result:\n{result.content[1]['text']}")
    
    # Data manipulation
    print("\n📝 Executing: Data frame creation")
    result = await execute_tool.execute({
        "code": """
        df <- data.frame(
            x = 1:5,
            y = c(2, 4, 6, 8, 10),
            category = c('A', 'B', 'A', 'B', 'A')
        )
        summary(df)
        """,
        "save_to_history": True
    })
    
    print(f"✅ Success: {result.success}")
    if result.content and len(result.content) > 1:
        print(f"📊 Result:\n{result.content[1]['text']}")


async def demo_plot_generation(execute_tool):
    """Demonstrate plot generation and capture."""
    print("\n" + "="*60)
    print("📊 DEMO: Plot Generation and Capture")
    print("="*60)
    
    print("\n📝 Executing: plot(1:10, (1:10)^2)")
    result = await execute_tool.execute({
        "code": "plot(1:10, (1:10)^2, main='Quadratic Function', xlab='x', ylab='x²')",
        "capture_plots": True,
        "save_to_history": True
    })
    
    print(f"✅ Success: {result.success}")
    if result.content:
        print(f"📄 Summary:\n{result.content[0]['text']}")
        
        # Check for image content
        image_count = sum(1 for content in result.content if content.get("type") == "image")
        if image_count > 0:
            print(f"🖼️  Generated {image_count} plot(s)")
        
        # Show metadata
        if result.metadata:
            print(f"📈 Metadata: {result.metadata}")


async def demo_error_handling(execute_tool):
    """Demonstrate error handling."""
    print("\n" + "="*60)
    print("❌ DEMO: Error Handling")
    print("="*60)
    
    print("\n📝 Executing: print(nonexistent_error_var)")
    result = await execute_tool.execute({
        "code": "print(nonexistent_error_var)",
        "save_to_history": True
    })
    
    print(f"❌ Success: {result.success}")
    print(f"🚨 Error: {result.error}")
    if result.content:
        print(f"📄 Details:\n{result.content[0]['text']}")


async def demo_warnings(execute_tool):
    """Demonstrate warning handling."""
    print("\n" + "="*60)
    print("⚠️  DEMO: Warning Handling")
    print("="*60)
    
    print("\n📝 Executing: Code with warning")
    result = await execute_tool.execute({
        "code": "result_with_warning <- 42",
        "save_to_history": True
    })
    
    print(f"✅ Success: {result.success}")
    if result.content:
        for i, content in enumerate(result.content):
            print(f"📄 Content {i+1}:\n{content['text']}")


async def demo_environment_switching(execute_tool):
    """Demonstrate environment switching."""
    print("\n" + "="*60)
    print("🔄 DEMO: Environment Switching")
    print("="*60)
    
    print("\n📝 Executing in 'data_analysis' environment")
    result = await execute_tool.execute({
        "code": "library(dplyr); data.frame(x=1:3) %>% summarise(mean_x = mean(x))",
        "environment": "data_analysis",
        "save_to_history": True
    })
    
    print(f"✅ Success: {result.success}")
    if result.content:
        print(f"📄 Summary:\n{result.content[0]['text']}")
    
    print("\n📝 Executing in 'machine_learning' environment")
    result = await execute_tool.execute({
        "code": "library(caret); data(iris); nrow(iris)",
        "environment": "machine_learning",
        "save_to_history": True
    })
    
    print(f"✅ Success: {result.success}")
    if result.content:
        print(f"📄 Summary:\n{result.content[0]['text']}")


async def demo_execution_history(history_tool):
    """Demonstrate execution history retrieval."""
    print("\n" + "="*60)
    print("📚 DEMO: Execution History")
    print("="*60)
    
    print("\n📖 Getting recent execution history (limit: 3)")
    result = await history_tool.execute({
        "limit": 3,
        "include_code": True,
        "include_output": False
    })
    
    print(f"✅ Success: {result.success}")
    if result.content:
        print(f"📄 History:\n{result.content[0]['text']}")
    
    print("\n📖 Getting detailed history with output")
    result = await history_tool.execute({
        "limit": 2,
        "include_code": True,
        "include_output": True
    })
    
    print(f"✅ Success: {result.success}")
    if result.content:
        print(f"📄 Detailed History:\n{result.content[0]['text']}")


async def demo_history_management(clear_tool, history_tool):
    """Demonstrate history management."""
    print("\n" + "="*60)
    print("🗑️  DEMO: History Management")
    print("="*60)
    
    # Show current history count
    print("\n📊 Current history status")
    result = await history_tool.execute({"limit": 100})
    if result.content:
        content = result.content[0]['text']
        if "共" in content:
            print(f"📈 {content.split('共')[1].split('条')[0].strip()} entries in history")
        else:
            print("📈 History appears to be empty")
    
    # Clear history
    print("\n🗑️  Clearing execution history")
    result = await clear_tool.execute({"confirm": True})
    
    print(f"✅ Success: {result.success}")
    if result.content:
        print(f"📄 Result:\n{result.content[0]['text']}")
    
    # Verify history is cleared
    print("\n📊 Verifying history is cleared")
    result = await history_tool.execute({"limit": 10})
    if result.content:
        print(f"📄 Status:\n{result.content[0]['text']}")


async def demo_advanced_features(execute_tool):
    """Demonstrate advanced features."""
    print("\n" + "="*60)
    print("🔬 DEMO: Advanced Features")
    print("="*60)
    
    # Custom timeout
    print("\n⏱️  Executing with custom timeout")
    result = await execute_tool.execute({
        "code": "Sys.sleep(0.1); print('Quick execution')",
        "timeout": 5,
        "save_to_history": True
    })
    
    print(f"✅ Success: {result.success}")
    if result.metadata:
        print(f"📊 Execution time: {result.metadata.get('execution_time', 'N/A')}s")
    
    # Disable output capture
    print("\n🔇 Executing without output capture")
    result = await execute_tool.execute({
        "code": "invisible(print('This output should not be captured'))",
        "capture_output": False,
        "save_to_history": True
    })
    
    print(f"✅ Success: {result.success}")
    print(f"📄 Output captured: {bool(result.content and len(result.content) > 1)}")
    
    # Disable history saving
    print("\n📝 Executing without saving to history")
    initial_count = len(execute_tool.history.entries)
    
    result = await execute_tool.execute({
        "code": "temp_var <- 'not saved to history'",
        "save_to_history": False
    })
    
    final_count = len(execute_tool.history.entries)
    print(f"✅ Success: {result.success}")
    print(f"📊 History entries before: {initial_count}, after: {final_count}")


async def main():
    """Main demo function."""
    setup_logging()
    
    print("🎯 RStudio MCP Code Execution Tools Demo")
    print("=" * 60)
    print("This demo showcases the code execution functionality of the RStudio MCP server.")
    print("Note: This uses mock implementations for demonstration purposes.")
    
    # Create mock dependencies
    api_wrapper = create_mock_api_wrapper()
    env_manager = create_mock_env_manager()
    
    # Create shared execution history
    execution_history = ExecutionHistory()
    
    # Create tools
    execute_tool = ExecuteRCodeTool(api_wrapper, env_manager)
    execute_tool.history = execution_history  # Share history
    
    history_tool = GetExecutionHistoryTool(execution_history)
    clear_tool = ClearExecutionHistoryTool(execution_history)
    
    try:
        # Run demos
        await demo_basic_execution(execute_tool)
        await demo_plot_generation(execute_tool)
        await demo_error_handling(execute_tool)
        await demo_warnings(execute_tool)
        await demo_environment_switching(execute_tool)
        await demo_execution_history(history_tool)
        await demo_advanced_features(execute_tool)
        await demo_history_management(clear_tool, history_tool)
        
        print("\n" + "="*60)
        print("🎉 Demo completed successfully!")
        print("="*60)
        print("\nKey features demonstrated:")
        print("✅ Basic R code execution with output capture")
        print("✅ Plot generation and image capture")
        print("✅ Error handling and reporting")
        print("✅ Warning detection and display")
        print("✅ Environment switching")
        print("✅ Execution history tracking")
        print("✅ History retrieval and filtering")
        print("✅ History management (clearing)")
        print("✅ Advanced execution options (timeout, capture settings)")
        print("✅ Metadata tracking (execution time, plot count, etc.)")
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup any temporary files
        print("\n🧹 Cleaning up temporary files...")
        # Note: In a real implementation, we'd clean up plot files here


if __name__ == "__main__":
    asyncio.run(main())