"""Tests for prompt manager."""

import pytest
from unittest.mock import AsyncMock, Mock

from src.rstudio_mcp.prompts.manager import PromptManager
from src.rstudio_mcp.prompts.base import BasePrompt, PromptResult, PromptArgument, PromptMessage


class MockPrompt(BasePrompt):
    """Mock prompt for testing."""
    
    def __init__(self, name="test_prompt", description="Test prompt", arguments=None, should_fail=False):
        super().__init__()
        self._name = name
        self._description = description
        self._arguments = arguments or []
        self._should_fail = should_fail
    
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
        if self._should_fail:
            return PromptResult(success=False, error="Mock generation failed")
        
        result = PromptResult(success=True)
        result.add_system_message("Mock system message")
        result.add_user_message(f"Mock user message with args: {arguments}")
        return result


class TestPromptManager:
    """Test PromptManager class."""
    
    def test_initialization(self):
        """Test prompt manager initialization."""
        manager = PromptManager()
        
        assert isinstance(manager, PromptManager)
        assert len(manager.list_prompts()) == 7  # 7 default prompts initialized
    
    def test_register_prompt(self):
        """Test registering a prompt."""
        manager = PromptManager()
        prompt = MockPrompt(name="test_prompt", description="Test description")
        
        manager.register_prompt(prompt)
        
        assert "test_prompt" in manager.list_prompts()
        assert manager.get_prompt("test_prompt") is prompt
    
    def test_register_multiple_prompts(self):
        """Test registering multiple prompts."""
        manager = PromptManager()
        initial_count = len(manager.list_prompts())
        prompt1 = MockPrompt(name="prompt1", description="First prompt")
        prompt2 = MockPrompt(name="prompt2", description="Second prompt")
        
        manager.register_prompt(prompt1)
        manager.register_prompt(prompt2)
        
        prompts = manager.list_prompts()
        assert len(prompts) == initial_count + 2
        assert "prompt1" in prompts
        assert "prompt2" in prompts
    
    def test_unregister_prompt(self):
        """Test unregistering a prompt."""
        manager = PromptManager()
        prompt = MockPrompt(name="test_prompt")
        
        manager.register_prompt(prompt)
        assert "test_prompt" in manager.list_prompts()
        
        result = manager.unregister_prompt("test_prompt")
        assert result is True
        assert "test_prompt" not in manager.list_prompts()
    
    def test_unregister_nonexistent_prompt(self):
        """Test unregistering a non-existent prompt."""
        manager = PromptManager()
        
        result = manager.unregister_prompt("nonexistent")
        assert result is False
    
    def test_get_prompt(self):
        """Test getting a prompt by name."""
        manager = PromptManager()
        prompt = MockPrompt(name="test_prompt")
        
        manager.register_prompt(prompt)
        
        retrieved = manager.get_prompt("test_prompt")
        assert retrieved is prompt
        
        # Test non-existent prompt
        assert manager.get_prompt("nonexistent") is None
    
    def test_get_prompt_info(self):
        """Test getting prompt information."""
        manager = PromptManager()
        arguments = [
            PromptArgument(name="arg1", description="First argument", required=True),
            PromptArgument(name="arg2", description="Second argument", required=False, default="default")
        ]
        prompt = MockPrompt(
            name="test_prompt",
            description="Test description",
            arguments=arguments
        )
        
        manager.register_prompt(prompt)
        
        info = manager.get_prompt_info("test_prompt")
        
        assert info is not None
        assert info["name"] == "test_prompt"
        assert info["description"] == "Test description"
        assert len(info["arguments"]) == 2
        assert info["arguments"][0]["name"] == "arg1"
        assert info["arguments"][0]["required"] is True
        assert info["arguments"][1]["name"] == "arg2"
        assert info["arguments"][1]["required"] is False
        assert info["arguments"][1]["default"] == "default"
    
    def test_get_prompt_info_nonexistent(self):
        """Test getting info for non-existent prompt."""
        manager = PromptManager()
        
        info = manager.get_prompt_info("nonexistent")
        assert info is None
    
    @pytest.mark.asyncio
    async def test_generate_prompt_success(self):
        """Test successful prompt generation."""
        manager = PromptManager()
        prompt = MockPrompt(name="test_prompt")
        
        manager.register_prompt(prompt)
        
        result = await manager.generate_prompt("test_prompt", {"key": "value"})
        
        assert result.success is True
        assert len(result.messages) == 2
        assert result.messages[0].role == "system"
        assert result.messages[1].role == "user"
        assert "Mock user message with args: {'key': 'value'}" in result.messages[1].content
    
    @pytest.mark.asyncio
    async def test_generate_prompt_not_found(self):
        """Test generating a non-existent prompt."""
        manager = PromptManager()
        
        result = await manager.generate_prompt("nonexistent", {})
        
        assert result.success is False
        assert "Prompt not found: nonexistent" in result.error
        assert len(result.messages) == 0
    
    @pytest.mark.asyncio
    async def test_generate_prompt_failure(self):
        """Test prompt generation failure."""
        manager = PromptManager()
        prompt = MockPrompt(name="failing_prompt", should_fail=True)
        
        manager.register_prompt(prompt)
        
        result = await manager.generate_prompt("failing_prompt", {})
        
        assert result.success is False
        assert "Mock generation failed" in result.error
    
    def test_get_all_prompt_definitions(self):
        """Test getting all prompt definitions."""
        manager = PromptManager()
        initial_count = len(manager.get_all_prompt_definitions())
        
        arguments1 = [PromptArgument(name="arg1", description="Arg 1", required=True)]
        arguments2 = [PromptArgument(name="arg2", description="Arg 2", required=False)]
        
        prompt1 = MockPrompt(name="prompt1", description="First prompt", arguments=arguments1)
        prompt2 = MockPrompt(name="prompt2", description="Second prompt", arguments=arguments2)
        
        manager.register_prompt(prompt1)
        manager.register_prompt(prompt2)
        
        definitions = manager.get_all_prompt_definitions()
        
        assert len(definitions) == initial_count + 2
        
        # Check first prompt definition
        def1 = next(d for d in definitions if d["name"] == "prompt1")
        assert def1["description"] == "First prompt"
        assert len(def1["arguments"]) == 1
        assert def1["arguments"][0]["name"] == "arg1"
        assert def1["arguments"][0]["required"] is True
        
        # Check second prompt definition
        def2 = next(d for d in definitions if d["name"] == "prompt2")
        assert def2["description"] == "Second prompt"
        assert len(def2["arguments"]) == 1
        assert def2["arguments"][0]["name"] == "arg2"
        assert def2["arguments"][0]["required"] is False
    
    def test_get_all_prompt_definitions_empty(self):
        """Test getting prompt definitions when no prompts are registered."""
        manager = PromptManager()
        
        definitions = manager.get_all_prompt_definitions()
        assert len(definitions) == 7  # 7 default prompts
    
    @pytest.mark.asyncio
    async def test_cleanup(self):
        """Test cleanup functionality."""
        manager = PromptManager()
        prompt = MockPrompt(name="test_prompt")
        
        manager.register_prompt(prompt)
        assert len(manager.list_prompts()) == 8  # 7 default + 1 added
        
        await manager.cleanup()
        assert len(manager.list_prompts()) == 0
    
    def test_list_prompts_empty(self):
        """Test listing prompts when none are registered."""
        manager = PromptManager()
        
        prompts = manager.list_prompts()
        assert len(prompts) == 7  # 7 default prompts
        assert isinstance(prompts, list)
    
    def test_prompt_replacement(self):
        """Test that registering a prompt with the same name replaces the old one."""
        manager = PromptManager()
        
        prompt1 = MockPrompt(name="test_prompt", description="First version")
        prompt2 = MockPrompt(name="test_prompt", description="Second version")
        
        manager.register_prompt(prompt1)
        assert manager.get_prompt("test_prompt").description == "First version"
        
        manager.register_prompt(prompt2)
        assert manager.get_prompt("test_prompt").description == "Second version"
        
        # Should still have 7 default prompts + 1 replaced prompt
        assert len(manager.list_prompts()) == 8