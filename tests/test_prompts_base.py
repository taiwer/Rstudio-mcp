"""Tests for prompt base classes."""

import pytest
from unittest.mock import AsyncMock, Mock

from src.rstudio_mcp.prompts.base import (
    BasePrompt, 
    PromptResult, 
    PromptArgument, 
    PromptMessage,
    PromptValidationError
)


class TestPromptArgument:
    """Test PromptArgument class."""
    
    def test_create_required_argument(self):
        """Test creating a required argument."""
        arg = PromptArgument(
            name="dataset",
            description="Dataset to analyze",
            required=True
        )
        
        assert arg.name == "dataset"
        assert arg.description == "Dataset to analyze"
        assert arg.required is True
        assert arg.default is None
    
    def test_create_optional_argument_with_default(self):
        """Test creating an optional argument with default value."""
        arg = PromptArgument(
            name="analysis_type",
            description="Type of analysis",
            required=False,
            default="exploratory"
        )
        
        assert arg.name == "analysis_type"
        assert arg.description == "Type of analysis"
        assert arg.required is False
        assert arg.default == "exploratory"


class TestPromptMessage:
    """Test PromptMessage class."""
    
    def test_create_system_message(self):
        """Test creating a system message."""
        msg = PromptMessage(
            role="system",
            content="You are a data analysis expert."
        )
        
        assert msg.role == "system"
        assert msg.content == "You are a data analysis expert."
        assert msg.metadata == {}
    
    def test_create_message_with_metadata(self):
        """Test creating a message with metadata."""
        metadata = {"source": "template", "version": "1.0"}
        msg = PromptMessage(
            role="user",
            content="Analyze this dataset",
            metadata=metadata
        )
        
        assert msg.role == "user"
        assert msg.content == "Analyze this dataset"
        assert msg.metadata == metadata


class TestPromptResult:
    """Test PromptResult class."""
    
    def test_create_successful_result(self):
        """Test creating a successful result."""
        messages = [
            PromptMessage(role="system", content="System message"),
            PromptMessage(role="user", content="User message")
        ]
        
        result = PromptResult(
            success=True,
            messages=messages
        )
        
        assert result.success is True
        assert len(result.messages) == 2
        assert result.error is None
        assert result.metadata == {}
    
    def test_create_error_result(self):
        """Test creating an error result."""
        result = PromptResult(
            success=False,
            error="Validation failed"
        )
        
        assert result.success is False
        assert len(result.messages) == 0
        assert result.error == "Validation failed"
    
    def test_add_system_message(self):
        """Test adding a system message."""
        result = PromptResult(success=True)
        result.add_system_message("You are an expert.")
        
        assert len(result.messages) == 1
        assert result.messages[0].role == "system"
        assert result.messages[0].content == "You are an expert."
    
    def test_add_user_message(self):
        """Test adding a user message."""
        result = PromptResult(success=True)
        result.add_user_message("Please help me.")
        
        assert len(result.messages) == 1
        assert result.messages[0].role == "user"
        assert result.messages[0].content == "Please help me."
    
    def test_add_assistant_message(self):
        """Test adding an assistant message."""
        result = PromptResult(success=True)
        result.add_assistant_message("I can help you.")
        
        assert len(result.messages) == 1
        assert result.messages[0].role == "assistant"
        assert result.messages[0].content == "I can help you."
    
    def test_add_message_with_metadata(self):
        """Test adding a message with metadata."""
        result = PromptResult(success=True)
        metadata = {"template": "analysis"}
        result.add_system_message("System prompt", metadata)
        
        assert len(result.messages) == 1
        assert result.messages[0].metadata == metadata


class MockPrompt(BasePrompt):
    """Mock prompt for testing."""
    
    def __init__(self, name="test_prompt", description="Test prompt", arguments=None):
        super().__init__()
        self._name = name
        self._description = description
        self._arguments = arguments or []
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return self._description
    
    @property
    def arguments(self) -> list:
        return self._arguments
    
    async def generate(self, arguments: dict) -> PromptResult:
        result = PromptResult(success=True)
        result.add_system_message("Mock system message")
        result.add_user_message(f"Mock user message with args: {arguments}")
        return result


class TestBasePrompt:
    """Test BasePrompt class."""
    
    def test_prompt_properties(self):
        """Test prompt properties."""
        arguments = [
            PromptArgument(name="arg1", description="First argument", required=True),
            PromptArgument(name="arg2", description="Second argument", required=False, default="default_value")
        ]
        
        prompt = MockPrompt(
            name="test_prompt",
            description="Test prompt description",
            arguments=arguments
        )
        
        assert prompt.name == "test_prompt"
        assert prompt.description == "Test prompt description"
        assert len(prompt.arguments) == 2
        assert prompt.arguments[0].name == "arg1"
        assert prompt.arguments[1].name == "arg2"
    
    def test_validate_arguments_success(self):
        """Test successful argument validation."""
        arguments = [
            PromptArgument(name="required_arg", description="Required", required=True),
            PromptArgument(name="optional_arg", description="Optional", required=False, default="default")
        ]
        
        prompt = MockPrompt(arguments=arguments)
        
        # Test with all arguments provided
        validated = prompt.validate_arguments({
            "required_arg": "value1",
            "optional_arg": "value2"
        })
        
        assert validated["required_arg"] == "value1"
        assert validated["optional_arg"] == "value2"
        
        # Test with only required argument (should apply default)
        validated = prompt.validate_arguments({
            "required_arg": "value1"
        })
        
        assert validated["required_arg"] == "value1"
        assert validated["optional_arg"] == "default"
    
    def test_validate_arguments_missing_required(self):
        """Test validation failure for missing required arguments."""
        arguments = [
            PromptArgument(name="required_arg", description="Required", required=True)
        ]
        
        prompt = MockPrompt(arguments=arguments)
        
        with pytest.raises(PromptValidationError) as exc_info:
            prompt.validate_arguments({})
        
        assert "Missing required arguments" in str(exc_info.value)
        assert "required_arg" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_generate_success(self):
        """Test successful prompt generation."""
        prompt = MockPrompt()
        result = await prompt.generate({"test": "value"})
        
        assert result.success is True
        assert len(result.messages) == 2
        assert result.messages[0].role == "system"
        assert result.messages[1].role == "user"
        assert "Mock user message with args: {'test': 'value'}" in result.messages[1].content
    
    @pytest.mark.asyncio
    async def test_safe_generate_success(self):
        """Test safe generation with successful validation."""
        arguments = [
            PromptArgument(name="test_arg", description="Test", required=True)
        ]
        
        prompt = MockPrompt(arguments=arguments)
        result = await prompt.safe_generate({"test_arg": "value"})
        
        assert result.success is True
        assert len(result.messages) == 2
    
    @pytest.mark.asyncio
    async def test_safe_generate_validation_error(self):
        """Test safe generation with validation error."""
        arguments = [
            PromptArgument(name="required_arg", description="Required", required=True)
        ]
        
        prompt = MockPrompt(arguments=arguments)
        result = await prompt.safe_generate({})  # Missing required argument
        
        assert result.success is False
        assert "Argument validation failed" in result.error
        assert len(result.messages) == 0
    
    @pytest.mark.asyncio
    async def test_safe_generate_unexpected_error(self):
        """Test safe generation with unexpected error."""
        prompt = MockPrompt()
        
        # Mock the generate method to raise an exception
        async def failing_generate(arguments):
            raise ValueError("Unexpected error")
        
        prompt.generate = failing_generate
        
        result = await prompt.safe_generate({})
        
        assert result.success is False
        assert "Unexpected error during prompt generation" in result.error
        assert len(result.messages) == 0
    
    def test_to_mcp_prompt(self):
        """Test conversion to MCP prompt format."""
        arguments = [
            PromptArgument(name="arg1", description="First argument", required=True),
            PromptArgument(name="arg2", description="Second argument", required=False)
        ]
        
        prompt = MockPrompt(
            name="test_prompt",
            description="Test description",
            arguments=arguments
        )
        
        mcp_prompt = prompt.to_mcp_prompt()
        
        assert mcp_prompt["name"] == "test_prompt"
        assert mcp_prompt["description"] == "Test description"
        assert len(mcp_prompt["arguments"]) == 2
        assert mcp_prompt["arguments"][0]["name"] == "arg1"
        assert mcp_prompt["arguments"][0]["required"] is True
        assert mcp_prompt["arguments"][1]["name"] == "arg2"
        assert mcp_prompt["arguments"][1]["required"] is False
    
    def test_create_success_result(self):
        """Test creating a success result."""
        prompt = MockPrompt()
        messages = [PromptMessage(role="system", content="Test")]
        metadata = {"key": "value"}
        
        result = prompt.create_success_result(messages, metadata)
        
        assert result.success is True
        assert result.messages == messages
        assert result.metadata == metadata
        assert result.error is None
    
    def test_create_error_result(self):
        """Test creating an error result."""
        prompt = MockPrompt()
        
        result = prompt.create_error_result("Test error")
        
        assert result.success is False
        assert result.error == "Test error"
        assert len(result.messages) == 0