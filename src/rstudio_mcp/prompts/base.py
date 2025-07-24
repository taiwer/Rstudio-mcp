"""Base prompt classes and interfaces for RStudio MCP Server."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class PromptValidationError(Exception):
    """Custom validation error for prompt arguments."""
    pass


class PromptArgument(BaseModel):
    """Prompt argument definition."""
    
    name: str = Field(..., description="Argument name")
    description: str = Field(..., description="Argument description")
    required: bool = Field(default=False, description="Whether argument is required")
    default: Optional[Any] = Field(None, description="Default value")


class PromptMessage(BaseModel):
    """A message in a prompt conversation."""
    
    role: str = Field(..., description="Message role (system, user, assistant)")
    content: str = Field(..., description="Message content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class PromptResult(BaseModel):
    """Result of prompt generation."""
    
    success: bool = Field(..., description="Whether the prompt generation was successful")
    messages: List[PromptMessage] = Field(default_factory=list, description="Generated prompt messages")
    error: Optional[str] = Field(None, description="Error message if generation failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    def add_system_message(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a system message to the prompt.
        
        Args:
            content: Message content
            metadata: Optional metadata
        """
        self.messages.append(PromptMessage(
            role="system",
            content=content,
            metadata=metadata or {}
        ))
    
    def add_user_message(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a user message to the prompt.
        
        Args:
            content: Message content
            metadata: Optional metadata
        """
        self.messages.append(PromptMessage(
            role="user",
            content=content,
            metadata=metadata or {}
        ))
    
    def add_assistant_message(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add an assistant message to the prompt.
        
        Args:
            content: Message content
            metadata: Optional metadata
        """
        self.messages.append(PromptMessage(
            role="assistant",
            content=content,
            metadata=metadata or {}
        ))


class BasePrompt(ABC):
    """Abstract base class for all MCP prompts."""
    
    def __init__(self):
        """Initialize the prompt."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Prompt name."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Prompt description."""
        pass
    
    @property
    @abstractmethod
    def arguments(self) -> List[PromptArgument]:
        """Prompt arguments."""
        pass
    
    @abstractmethod
    async def generate(self, arguments: Dict[str, Any]) -> PromptResult:
        """Generate the prompt with given arguments.
        
        Args:
            arguments: Prompt arguments
            
        Returns:
            Generated prompt result
        """
        pass
    
    def validate_arguments(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Validate prompt arguments.
        
        Args:
            arguments: Arguments to validate
            
        Returns:
            Validated arguments with defaults applied
            
        Raises:
            PromptValidationError: If validation fails
        """
        # Apply defaults
        validated_args = arguments.copy()
        for arg in self.arguments:
            if arg.name not in validated_args and arg.default is not None:
                validated_args[arg.name] = arg.default
        
        # Check required arguments
        required_args = [arg.name for arg in self.arguments if arg.required]
        missing_args = [arg for arg in required_args if arg not in validated_args]
        
        if missing_args:
            raise PromptValidationError(f"Missing required arguments: {missing_args}")
        
        return validated_args
    
    async def safe_generate(self, arguments: Dict[str, Any]) -> PromptResult:
        """Safely generate the prompt with error handling.
        
        Args:
            arguments: Prompt arguments
            
        Returns:
            Prompt generation result
        """
        try:
            # Validate arguments
            validated_args = self.validate_arguments(arguments)
            
            # Generate prompt
            self.logger.info(f"Generating prompt '{self.name}' with arguments: {validated_args}")
            result = await self.generate(validated_args)
            
            if result.success:
                self.logger.info(f"Prompt '{self.name}' generated successfully")
            else:
                self.logger.warning(f"Prompt '{self.name}' generation failed: {result.error}")
            
            return result
            
        except PromptValidationError as e:
            error_msg = f"Argument validation failed: {str(e)}"
            self.logger.error(error_msg)
            return PromptResult(
                success=False,
                error=error_msg
            )
        
        except Exception as e:
            error_msg = f"Unexpected error during prompt generation: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return PromptResult(
                success=False,
                error=error_msg
            )
    
    def to_mcp_prompt(self) -> Dict[str, Any]:
        """Convert to MCP prompt format.
        
        Returns:
            MCP prompt definition
        """
        return {
            "name": self.name,
            "description": self.description,
            "arguments": [
                {
                    "name": arg.name,
                    "description": arg.description,
                    "required": arg.required
                }
                for arg in self.arguments
            ]
        }
    
    def create_success_result(self, messages: List[PromptMessage], 
                            metadata: Optional[Dict[str, Any]] = None) -> PromptResult:
        """Create a successful prompt result.
        
        Args:
            messages: Generated messages
            metadata: Optional metadata
            
        Returns:
            PromptResult with success status
        """
        return PromptResult(
            success=True,
            messages=messages,
            metadata=metadata or {}
        )
    
    def create_error_result(self, error: str) -> PromptResult:
        """Create an error prompt result.
        
        Args:
            error: Error message
            
        Returns:
            PromptResult with error
        """
        return PromptResult(
            success=False,
            error=error
        )