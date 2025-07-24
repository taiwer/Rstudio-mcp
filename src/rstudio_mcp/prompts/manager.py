"""Prompt manager for RStudio MCP Server."""

import logging
from typing import Any, Dict, List, Optional

from .base import BasePrompt, PromptResult


class PromptManager:
    """Manager for MCP prompts."""
    
    def __init__(self):
        """Initialize the prompt manager."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._prompts: Dict[str, BasePrompt] = {}
        self._initialize_default_prompts()
    
    def _initialize_default_prompts(self) -> None:
        """Initialize default prompts."""
        from .data_analysis_prompts import DataAnalysisPrompt, StatisticalTestPrompt
        from .visualization_prompts import CreateVisualizationPrompt, DashboardPrompt
        from .debugging_prompts import DebugRCodePrompt, PerformanceOptimizationPrompt, CodeReviewPrompt
        
        # Register data analysis prompts
        self.register_prompt(DataAnalysisPrompt())
        self.register_prompt(StatisticalTestPrompt())
        
        # Register visualization prompts
        self.register_prompt(CreateVisualizationPrompt())
        self.register_prompt(DashboardPrompt())
        
        # Register debugging and optimization prompts
        self.register_prompt(DebugRCodePrompt())
        self.register_prompt(PerformanceOptimizationPrompt())
        self.register_prompt(CodeReviewPrompt())
        
        self.logger.info(f"Prompt manager initialized with {len(self._prompts)} default prompts")
    
    def register_prompt(self, prompt: BasePrompt) -> None:
        """Register a new prompt.
        
        Args:
            prompt: Prompt to register
        """
        self._prompts[prompt.name] = prompt
        self.logger.info(f"Registered prompt: {prompt.name}")
    
    def unregister_prompt(self, name: str) -> bool:
        """Unregister a prompt.
        
        Args:
            name: Name of prompt to unregister
            
        Returns:
            True if prompt was unregistered, False if not found
        """
        if name in self._prompts:
            del self._prompts[name]
            self.logger.info(f"Unregistered prompt: {name}")
            return True
        return False
    
    def list_prompts(self) -> List[str]:
        """List all registered prompt names.
        
        Returns:
            List of prompt names
        """
        return list(self._prompts.keys())
    
    def get_prompt(self, name: str) -> Optional[BasePrompt]:
        """Get a prompt by name.
        
        Args:
            name: Prompt name
            
        Returns:
            Prompt instance or None if not found
        """
        return self._prompts.get(name)
    
    def get_prompt_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get information about a prompt.
        
        Args:
            name: Prompt name
            
        Returns:
            Prompt information or None if not found
        """
        prompt = self.get_prompt(name)
        if prompt is None:
            return None
        
        return {
            "name": prompt.name,
            "description": prompt.description,
            "arguments": [
                {
                    "name": arg.name,
                    "description": arg.description,
                    "required": arg.required,
                    "default": arg.default
                }
                for arg in prompt.arguments
            ]
        }
    
    async def generate_prompt(self, name: str, arguments: Dict[str, Any]) -> PromptResult:
        """Generate a prompt by name.
        
        Args:
            name: Prompt name
            arguments: Prompt arguments
            
        Returns:
            Generated prompt result
        """
        prompt = self.get_prompt(name)
        if prompt is None:
            return PromptResult(
                success=False,
                error=f"Prompt not found: {name}"
            )
        
        return await prompt.safe_generate(arguments)
    
    def get_all_prompt_definitions(self) -> List[Dict[str, Any]]:
        """Get MCP definitions for all prompts.
        
        Returns:
            List of MCP prompt definitions
        """
        return [prompt.to_mcp_prompt() for prompt in self._prompts.values()]
    
    async def cleanup(self) -> None:
        """Cleanup resources."""
        self.logger.info("Cleaning up prompt manager")
        self._prompts.clear()