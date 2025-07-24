"""Tests for debugging and optimization prompt templates."""

import pytest

from src.rstudio_mcp.prompts.debugging_prompts import (
    DebugRCodePrompt, 
    PerformanceOptimizationPrompt, 
    CodeReviewPrompt
)


class TestDebugRCodePrompt:
    """Test DebugRCodePrompt class."""
    
    def test_prompt_properties(self):
        """Test prompt basic properties."""
        prompt = DebugRCodePrompt()
        
        assert prompt.name == "debug_r_code"
        assert "debugging" in prompt.description.lower()
        assert len(prompt.arguments) == 5
        
        # Check required arguments
        required_args = [arg.name for arg in prompt.arguments if arg.required]
        assert "code" in required_args
        assert len(required_args) == 1  # Only code is required
    
    @pytest.mark.asyncio
    async def test_generate_debug_prompt_full(self):
        """Test generating debug prompt with all arguments."""
        prompt = DebugRCodePrompt()
        
        arguments = {
            "code": "data %>% filter(value > mean(value, na.rm = TRUE))",
            "error_message": "Error: object 'data' not found",
            "expected_behavior": "Should filter rows where value is above average",
            "context": "Working with sales data, trying to find high-value transactions",
            "r_version": "R version 4.3.0, dplyr 1.1.0"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        assert len(result.messages) == 3
        
        system_msg = result.messages[0].content
        assert "expert r programmer" in system_msg.lower()
        assert "debugging specialist" in system_msg.lower()
        assert "error diagnosis" in system_msg.lower()
        
        user_msg = result.messages[1].content
        assert "data %>% filter(value > mean(value, na.rm = TRUE))" in user_msg
        assert "Error: object 'data' not found" in user_msg
        assert "Should filter rows where value is above average" in user_msg
        assert "Working with sales data" in user_msg
        assert "R version 4.3.0, dplyr 1.1.0" in user_msg
        assert "root cause" in user_msg.lower()
        assert "corrected version" in user_msg.lower()
        
        assistant_msg = result.messages[2].content
        assert "debug this r code" in assistant_msg.lower()
        assert "str(your_data)" in assistant_msg
        assert "class(your_data)" in assistant_msg
    
    @pytest.mark.asyncio
    async def test_generate_debug_prompt_minimal(self):
        """Test generating debug prompt with minimal arguments."""
        prompt = DebugRCodePrompt()
        
        arguments = {
            "code": "plot(x, y)"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        
        user_msg = result.messages[1].content
        assert "plot(x, y)" in user_msg
        # Should not include sections for missing optional arguments
        assert "**Error Message:**" not in user_msg
        assert "**Expected Behavior:**" not in user_msg
        assert "**Additional Context:**" not in user_msg
        assert "**Environment:**" not in user_msg
    
    def test_to_mcp_prompt(self):
        """Test conversion to MCP prompt format."""
        prompt = DebugRCodePrompt()
        
        mcp_prompt = prompt.to_mcp_prompt()
        
        assert mcp_prompt["name"] == "debug_r_code"
        assert len(mcp_prompt["arguments"]) == 5
        
        # Check required arguments
        required_args = [arg["name"] for arg in mcp_prompt["arguments"] if arg["required"]]
        assert "code" in required_args
        assert len(required_args) == 1


class TestPerformanceOptimizationPrompt:
    """Test PerformanceOptimizationPrompt class."""
    
    def test_prompt_properties(self):
        """Test prompt basic properties."""
        prompt = PerformanceOptimizationPrompt()
        
        assert prompt.name == "optimize_performance"
        assert "performance" in prompt.description.lower()
        assert "optimizing" in prompt.description.lower()
        assert len(prompt.arguments) == 5
        
        # Check required arguments
        required_args = [arg.name for arg in prompt.arguments if arg.required]
        assert "code" in required_args
        assert len(required_args) == 1
    
    @pytest.mark.asyncio
    async def test_generate_optimization_prompt_full(self):
        """Test generating optimization prompt with all arguments."""
        prompt = PerformanceOptimizationPrompt()
        
        arguments = {
            "code": "for(i in 1:nrow(df)) { df$result[i] <- expensive_function(df$input[i]) }",
            "performance_issue": "Loop takes too long to execute",
            "data_size": "DataFrame with 100,000 rows",
            "constraints": "Must complete within 30 seconds",
            "current_runtime": "5 minutes average execution time"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        assert len(result.messages) == 3
        
        system_msg = result.messages[0].content
        assert "performance optimization specialist" in system_msg.lower()
        assert "vectorization" in system_msg.lower()
        assert "parallel processing" in system_msg.lower()
        assert "memory management" in system_msg.lower()
        
        user_msg = result.messages[1].content
        assert "for(i in 1:nrow(df))" in user_msg
        assert "Loop takes too long to execute" in user_msg
        assert "DataFrame with 100,000 rows" in user_msg
        assert "Must complete within 30 seconds" in user_msg
        assert "5 minutes average execution time" in user_msg
        assert "performance bottlenecks" in user_msg.lower()
        assert "optimized version" in user_msg.lower()
        
        assistant_msg = result.messages[2].content
        assert "optimize this r code" in assistant_msg.lower()
        assert "microbenchmark" in assistant_msg
        assert "profvis" in assistant_msg
    
    @pytest.mark.asyncio
    async def test_generate_optimization_prompt_minimal(self):
        """Test generating optimization prompt with minimal arguments."""
        prompt = PerformanceOptimizationPrompt()
        
        arguments = {
            "code": "apply(matrix, 1, sum)"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        
        user_msg = result.messages[1].content
        assert "apply(matrix, 1, sum)" in user_msg
        # Should not include sections for missing optional arguments
        assert "**Performance Issue:**" not in user_msg
        assert "**Data Size:**" not in user_msg
        assert "**Constraints:**" not in user_msg
        assert "**Current Performance:**" not in user_msg
    
    def test_to_mcp_prompt(self):
        """Test conversion to MCP prompt format."""
        prompt = PerformanceOptimizationPrompt()
        
        mcp_prompt = prompt.to_mcp_prompt()
        
        assert mcp_prompt["name"] == "optimize_performance"
        assert len(mcp_prompt["arguments"]) == 5


class TestCodeReviewPrompt:
    """Test CodeReviewPrompt class."""
    
    def test_prompt_properties(self):
        """Test prompt basic properties."""
        prompt = CodeReviewPrompt()
        
        assert prompt.name == "review_r_code"
        assert "reviewing" in prompt.description.lower()
        assert len(prompt.arguments) == 4
        
        # Check required arguments
        required_args = [arg.name for arg in prompt.arguments if arg.required]
        assert "code" in required_args
        assert len(required_args) == 1
        
        # Check default values
        review_focus_arg = next(arg for arg in prompt.arguments if arg.name == "review_focus")
        assert review_focus_arg.default == "all"
    
    @pytest.mark.asyncio
    async def test_generate_review_prompt_full(self):
        """Test generating code review prompt with all arguments."""
        prompt = CodeReviewPrompt()
        
        arguments = {
            "code": "function(x) { return(x + 1) }",
            "review_focus": "style",
            "code_purpose": "Simple increment function for data processing",
            "team_standards": "Follow tidyverse style guide"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        assert len(result.messages) == 3
        
        system_msg = result.messages[0].content
        assert "expert r code reviewer" in system_msg.lower()
        assert "coding best practices" in system_msg.lower()
        assert "maintainability" in system_msg.lower()
        
        user_msg = result.messages[1].content
        assert "function(x) { return(x + 1) }" in user_msg
        assert "**Review Focus:** style" in user_msg
        assert "Simple increment function for data processing" in user_msg
        assert "Follow tidyverse style guide" in user_msg
        assert "Code formatting and consistency" in user_msg
        assert "Variable and function naming conventions" in user_msg
        
        assistant_msg = result.messages[2].content
        assert "comprehensive review" in assistant_msg.lower()
        assert "your r code" in assistant_msg.lower()
    
    @pytest.mark.asyncio
    async def test_generate_review_prompt_performance_focus(self):
        """Test generating code review prompt focused on performance."""
        prompt = CodeReviewPrompt()
        
        arguments = {
            "code": "lapply(data_list, function(x) sum(x))",
            "review_focus": "performance"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        
        user_msg = result.messages[1].content
        assert "**Review Focus:** performance" in user_msg
        assert "Efficiency of algorithms and operations" in user_msg
        assert "Memory usage optimization" in user_msg
        assert "Vectorization opportunities" in user_msg
    
    @pytest.mark.asyncio
    async def test_generate_review_prompt_correctness_focus(self):
        """Test generating code review prompt focused on correctness."""
        prompt = CodeReviewPrompt()
        
        arguments = {
            "code": "mean(data$value, na.rm = TRUE)",
            "review_focus": "correctness"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        
        user_msg = result.messages[1].content
        assert "**Review Focus:** correctness" in user_msg
        assert "Logic errors and edge cases" in user_msg
        assert "Statistical methodology accuracy" in user_msg
        assert "Data handling and validation" in user_msg
    
    @pytest.mark.asyncio
    async def test_generate_review_prompt_maintainability_focus(self):
        """Test generating code review prompt focused on maintainability."""
        prompt = CodeReviewPrompt()
        
        arguments = {
            "code": "complex_analysis_function <- function() { ... }",
            "review_focus": "maintainability"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        
        user_msg = result.messages[1].content
        assert "**Review Focus:** maintainability" in user_msg
        assert "Code modularity and reusability" in user_msg
        assert "Function design and interfaces" in user_msg
        assert "Testing and validation" in user_msg
    
    @pytest.mark.asyncio
    async def test_generate_review_prompt_all_focus(self):
        """Test generating code review prompt with comprehensive focus."""
        prompt = CodeReviewPrompt()
        
        arguments = {
            "code": "data %>% filter(!is.na(value)) %>% summarise(mean = mean(value))",
            "review_focus": "all"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        
        user_msg = result.messages[1].content
        assert "**Review Focus:** all" in user_msg
        assert "Overall code quality assessment" in user_msg
        assert "Style and formatting issues" in user_msg
        assert "Performance optimization opportunities" in user_msg
        assert "Correctness and robustness" in user_msg
        assert "Maintainability improvements" in user_msg
    
    @pytest.mark.asyncio
    async def test_generate_review_prompt_minimal(self):
        """Test generating code review prompt with minimal arguments."""
        prompt = CodeReviewPrompt()
        
        arguments = {
            "code": "x <- 1:10"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        
        user_msg = result.messages[1].content
        assert "x <- 1:10" in user_msg
        assert "**Review Focus:** all" in user_msg  # Default value
        # Should not include sections for missing optional arguments
        assert "**Code Purpose:**" not in user_msg
        assert "**Team Standards:**" not in user_msg
    
    def test_to_mcp_prompt(self):
        """Test conversion to MCP prompt format."""
        prompt = CodeReviewPrompt()
        
        mcp_prompt = prompt.to_mcp_prompt()
        
        assert mcp_prompt["name"] == "review_r_code"
        assert len(mcp_prompt["arguments"]) == 4
        
        # Check required arguments
        required_args = [arg["name"] for arg in mcp_prompt["arguments"] if arg["required"]]
        assert "code" in required_args
        assert len(required_args) == 1