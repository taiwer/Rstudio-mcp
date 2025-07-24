"""Tool system for RStudio MCP Server."""

from .base import BaseTool, ToolResult
from .manager import ToolManager
from .environment_tools import (
    CreateEnvironmentTool,
    ListEnvironmentsTool,
    SwitchEnvironmentTool,
    DeleteEnvironmentTool
)
from .code_execution_tools import (
    ExecuteRCodeTool,
    GetExecutionHistoryTool,
    ClearExecutionHistoryTool,
    ExecutionHistory
)
from .project_management_tools import (
    CreateProjectTool,
    OpenProjectTool,
    GetProjectInfoTool
)
from .workspace_management_tools import (
    SaveWorkspaceTool,
    LoadWorkspaceTool,
    ListWorkspaceObjectsTool,
    CleanWorkspaceTool
)
from .plot_management_tools import (
    CapturePlotTool,
    ListPlotsTool,
    ExportPlotTool,
    PlotManager,
    PlotMetadata
)

__all__ = [
    "BaseTool", 
    "ToolResult", 
    "ToolManager",
    "CreateEnvironmentTool",
    "ListEnvironmentsTool", 
    "SwitchEnvironmentTool",
    "DeleteEnvironmentTool",
    "ExecuteRCodeTool",
    "GetExecutionHistoryTool",
    "ClearExecutionHistoryTool",
    "ExecutionHistory",
    "CreateProjectTool",
    "OpenProjectTool",
    "GetProjectInfoTool",
    "SaveWorkspaceTool",
    "LoadWorkspaceTool",
    "ListWorkspaceObjectsTool",
    "CleanWorkspaceTool",
    "CapturePlotTool",
    "ListPlotsTool",
    "ExportPlotTool",
    "PlotManager",
    "PlotMetadata"
]