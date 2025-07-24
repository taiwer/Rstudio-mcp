"""Prompt management system for RStudio MCP Server."""

from .base import BasePrompt, PromptResult, PromptArgument, PromptMessage
from .manager import PromptManager
from .data_analysis_prompts import DataAnalysisPrompt, StatisticalTestPrompt
from .visualization_prompts import CreateVisualizationPrompt, DashboardPrompt
from .debugging_prompts import DebugRCodePrompt, PerformanceOptimizationPrompt, CodeReviewPrompt

__all__ = [
    "BasePrompt", 
    "PromptResult", 
    "PromptArgument", 
    "PromptMessage",
    "PromptManager",
    "DataAnalysisPrompt",
    "StatisticalTestPrompt", 
    "CreateVisualizationPrompt",
    "DashboardPrompt",
    "DebugRCodePrompt",
    "PerformanceOptimizationPrompt",
    "CodeReviewPrompt"
]