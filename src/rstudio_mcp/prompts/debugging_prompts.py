"""Debugging and performance optimization prompt templates for RStudio MCP Server."""

from typing import Any, Dict, List

from .base import BasePrompt, PromptResult, PromptArgument


class DebugRCodePrompt(BasePrompt):
    """Prompt template for debugging R code issues."""
    
    @property
    def name(self) -> str:
        return "debug_r_code"
    
    @property
    def description(self) -> str:
        return "Generate prompts for debugging R code errors and issues"
    
    @property
    def arguments(self) -> List[PromptArgument]:
        return [
            PromptArgument(
                name="code",
                description="The R code that has issues or errors",
                required=True
            ),
            PromptArgument(
                name="error_message",
                description="The error message or unexpected behavior description",
                required=False
            ),
            PromptArgument(
                name="expected_behavior",
                description="What the code should do or expected output",
                required=False
            ),
            PromptArgument(
                name="context",
                description="Additional context about the data or environment",
                required=False
            ),
            PromptArgument(
                name="r_version",
                description="R version and relevant package versions",
                required=False
            )
        ]
    
    async def generate(self, arguments: Dict[str, Any]) -> PromptResult:
        """Generate debugging prompt."""
        code = arguments["code"]
        error_message = arguments.get("error_message", "")
        expected_behavior = arguments.get("expected_behavior", "")
        context = arguments.get("context", "")
        r_version = arguments.get("r_version", "")
        
        result = PromptResult(success=True)
        
        system_msg = """You are an expert R programmer and debugging specialist with extensive experience in:

1. R error diagnosis and resolution
2. Package compatibility issues
3. Data type and structure problems
4. Memory and performance issues
5. Statistical computation errors

Your debugging approach:
- Systematically analyze the error
- Identify root causes
- Provide step-by-step solutions
- Suggest best practices to prevent similar issues
- Offer alternative approaches when needed

Always provide working code examples and clear explanations."""
        
        result.add_system_message(system_msg)
        
        user_msg = f"""I need help debugging this R code issue:

**Problematic Code:**
```r
{code}
```"""
        
        if error_message:
            user_msg += f"\n\n**Error Message:**\n{error_message}"
        
        if expected_behavior:
            user_msg += f"\n\n**Expected Behavior:**\n{expected_behavior}"
        
        if context:
            user_msg += f"\n\n**Additional Context:**\n{context}"
        
        if r_version:
            user_msg += f"\n\n**Environment:**\n{r_version}"
        
        user_msg += """

Please help me:
1. Identify the root cause of the issue
2. Provide a corrected version of the code
3. Explain why the error occurred
4. Suggest best practices to avoid similar issues
5. Offer alternative approaches if applicable"""
        
        result.add_user_message(user_msg)
        
        example_msg = """I'll help you debug this R code systematically. Let me start by analyzing the error:

```r
# First, let's examine the structure of your data
str(your_data)
class(your_data)

# Check for common issues
summary(your_data)
any(is.na(your_data))
```

Based on the error message and code, I'll identify the specific issue and provide a corrected solution with explanations."""
        
        result.add_assistant_message(example_msg)
        
        return result


class PerformanceOptimizationPrompt(BasePrompt):
    """Prompt template for R code performance optimization."""
    
    @property
    def name(self) -> str:
        return "optimize_performance"
    
    @property
    def description(self) -> str:
        return "Generate prompts for optimizing R code performance and efficiency"
    
    @property
    def arguments(self) -> List[PromptArgument]:
        return [
            PromptArgument(
                name="code",
                description="The R code that needs performance optimization",
                required=True
            ),
            PromptArgument(
                name="performance_issue",
                description="Description of the performance problem (slow execution, memory usage, etc.)",
                required=False
            ),
            PromptArgument(
                name="data_size",
                description="Information about data size and complexity",
                required=False
            ),
            PromptArgument(
                name="constraints",
                description="Any constraints or requirements (memory limits, time limits, etc.)",
                required=False
            ),
            PromptArgument(
                name="current_runtime",
                description="Current execution time or performance metrics",
                required=False
            )
        ]
    
    async def generate(self, arguments: Dict[str, Any]) -> PromptResult:
        """Generate performance optimization prompt."""
        code = arguments["code"]
        performance_issue = arguments.get("performance_issue", "")
        data_size = arguments.get("data_size", "")
        constraints = arguments.get("constraints", "")
        current_runtime = arguments.get("current_runtime", "")
        
        result = PromptResult(success=True)
        
        system_msg = """You are an expert R performance optimization specialist with deep knowledge of:

1. R memory management and garbage collection
2. Vectorization and efficient data operations
3. Parallel processing with foreach, parallel, and future packages
4. Data.table and dplyr optimization techniques
5. Rcpp integration for computationally intensive tasks
6. Profiling tools (profvis, Rprof, microbenchmark)

Your optimization approach:
- Profile code to identify bottlenecks
- Apply vectorization where possible
- Optimize data structures and algorithms
- Leverage parallel processing when appropriate
- Consider memory-efficient alternatives
- Provide benchmarking comparisons

Always balance performance gains with code readability and maintainability."""
        
        result.add_system_message(system_msg)
        
        user_msg = f"""I need help optimizing the performance of this R code:

**Current Code:**
```r
{code}
```"""
        
        if performance_issue:
            user_msg += f"\n\n**Performance Issue:**\n{performance_issue}"
        
        if data_size:
            user_msg += f"\n\n**Data Size:**\n{data_size}"
        
        if constraints:
            user_msg += f"\n\n**Constraints:**\n{constraints}"
        
        if current_runtime:
            user_msg += f"\n\n**Current Performance:**\n{current_runtime}"
        
        user_msg += """

Please help me:
1. Identify performance bottlenecks in the code
2. Provide optimized version(s) of the code
3. Explain the optimization techniques used
4. Show performance comparisons with benchmarks
5. Suggest additional optimization strategies
6. Recommend profiling tools for ongoing monitoring"""
        
        result.add_user_message(user_msg)
        
        example_msg = """I'll help you optimize this R code for better performance. Let me start by profiling the current code:

```r
# Load profiling libraries
library(microbenchmark)
library(profvis)

# Profile the current code
profvis({
  # Your current code here
})

# Benchmark current performance
microbenchmark(
  current_version = {
    # Your current code
  },
  times = 10
)
```

Based on the profiling results, I'll identify bottlenecks and provide optimized solutions with performance comparisons."""
        
        result.add_assistant_message(example_msg)
        
        return result


class CodeReviewPrompt(BasePrompt):
    """Prompt template for R code review and best practices."""
    
    @property
    def name(self) -> str:
        return "review_r_code"
    
    @property
    def description(self) -> str:
        return "Generate prompts for reviewing R code quality and suggesting improvements"
    
    @property
    def arguments(self) -> List[PromptArgument]:
        return [
            PromptArgument(
                name="code",
                description="The R code to review",
                required=True
            ),
            PromptArgument(
                name="review_focus",
                description="Specific aspects to focus on (style, performance, correctness, maintainability)",
                required=False,
                default="all"
            ),
            PromptArgument(
                name="code_purpose",
                description="Purpose and context of the code",
                required=False
            ),
            PromptArgument(
                name="team_standards",
                description="Team coding standards or style guide requirements",
                required=False
            )
        ]
    
    async def generate(self, arguments: Dict[str, Any]) -> PromptResult:
        """Generate code review prompt."""
        code = arguments["code"]
        review_focus = arguments.get("review_focus", "all")
        code_purpose = arguments.get("code_purpose", "")
        team_standards = arguments.get("team_standards", "")
        
        result = PromptResult(success=True)
        
        system_msg = """You are an expert R code reviewer with extensive experience in:

1. R coding best practices and style guidelines
2. Code maintainability and readability
3. Performance optimization techniques
4. Statistical correctness and methodology
5. Package development standards
6. Reproducible research practices

Your review approach:
- Assess code quality systematically
- Identify potential issues and improvements
- Suggest specific, actionable changes
- Explain the reasoning behind recommendations
- Consider both technical and practical aspects
- Maintain a constructive and educational tone

Focus on creating code that is correct, efficient, readable, and maintainable."""
        
        result.add_system_message(system_msg)
        
        user_msg = f"""Please review this R code and provide feedback:

**Code to Review:**
```r
{code}
```

**Review Focus:** {review_focus}"""
        
        if code_purpose:
            user_msg += f"\n\n**Code Purpose:**\n{code_purpose}"
        
        if team_standards:
            user_msg += f"\n\n**Team Standards:**\n{team_standards}"
        
        review_areas = {
            "style": [
                "Code formatting and consistency",
                "Variable and function naming conventions",
                "Comment quality and documentation",
                "Code organization and structure"
            ],
            "performance": [
                "Efficiency of algorithms and operations",
                "Memory usage optimization",
                "Vectorization opportunities",
                "Potential bottlenecks"
            ],
            "correctness": [
                "Logic errors and edge cases",
                "Statistical methodology accuracy",
                "Data handling and validation",
                "Error handling and robustness"
            ],
            "maintainability": [
                "Code modularity and reusability",
                "Function design and interfaces",
                "Dependency management",
                "Testing and validation"
            ],
            "all": [
                "Overall code quality assessment",
                "Style and formatting issues",
                "Performance optimization opportunities",
                "Correctness and robustness",
                "Maintainability improvements"
            ]
        }
        
        areas = review_areas.get(review_focus, review_areas["all"])
        
        user_msg += f"\n\nPlease evaluate the following aspects:"
        for area in areas:
            user_msg += f"\n- {area}"
        
        user_msg += """

Please provide:
1. Overall assessment of code quality
2. Specific issues identified with line references
3. Suggested improvements with corrected code examples
4. Best practice recommendations
5. Priority ranking of suggested changes"""
        
        result.add_user_message(user_msg)
        
        example_msg = """I'll provide a comprehensive review of your R code. Let me analyze it systematically:

**Overall Assessment:**
I'll evaluate your code for style, performance, correctness, and maintainability.

**Specific Issues Found:**
```r
# Example of improved code with explanations
# Original: problematic_function()
# Improved: optimized_function()
# Reason: Better performance and readability
```

I'll provide detailed feedback with specific examples and actionable recommendations for improvement."""
        
        result.add_assistant_message(example_msg)
        
        return result