"""Tests for data analysis prompt templates."""

import pytest

from src.rstudio_mcp.prompts.data_analysis_prompts import DataAnalysisPrompt, StatisticalTestPrompt


class TestDataAnalysisPrompt:
    """Test DataAnalysisPrompt class."""
    
    def test_prompt_properties(self):
        """Test prompt basic properties."""
        prompt = DataAnalysisPrompt()
        
        assert prompt.name == "analyze_data"
        assert "data analysis" in prompt.description.lower()
        assert len(prompt.arguments) == 4
        
        # Check required arguments
        arg_names = [arg.name for arg in prompt.arguments]
        assert "dataset" in arg_names
        assert "analysis_type" in arg_names
        assert "variables" in arg_names
        assert "research_question" in arg_names
        
        # Check required status
        required_args = [arg.name for arg in prompt.arguments if arg.required]
        assert "dataset" in required_args
        assert len(required_args) == 1  # Only dataset is required
    
    @pytest.mark.asyncio
    async def test_generate_descriptive_analysis(self):
        """Test generating descriptive analysis prompt."""
        prompt = DataAnalysisPrompt()
        
        arguments = {
            "dataset": "sales_data.csv",
            "analysis_type": "descriptive",
            "variables": "revenue, quantity, region"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        assert len(result.messages) == 3  # system, user, assistant
        assert result.messages[0].role == "system"
        assert result.messages[1].role == "user"
        assert result.messages[2].role == "assistant"
        
        # Check content
        system_msg = result.messages[0].content
        assert "descriptive statistics" in system_msg.lower()
        
        user_msg = result.messages[1].content
        assert "sales_data.csv" in user_msg
        assert "descriptive" in user_msg
        assert "revenue, quantity, region" in user_msg
        assert "summary statistics" in user_msg.lower()
    
    @pytest.mark.asyncio
    async def test_generate_exploratory_analysis(self):
        """Test generating exploratory analysis prompt."""
        prompt = DataAnalysisPrompt()
        
        arguments = {
            "dataset": "customer_data.csv",
            "analysis_type": "exploratory",
            "research_question": "What factors influence customer satisfaction?"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        assert len(result.messages) == 3
        
        system_msg = result.messages[0].content
        assert "exploratory data analysis" in system_msg.lower()
        assert "patterns" in system_msg.lower()
        
        user_msg = result.messages[1].content
        assert "customer_data.csv" in user_msg
        assert "exploratory" in user_msg
        assert "What factors influence customer satisfaction?" in user_msg
        assert "correlation analysis" in user_msg.lower()
    
    @pytest.mark.asyncio
    async def test_generate_statistical_analysis(self):
        """Test generating statistical analysis prompt."""
        prompt = DataAnalysisPrompt()
        
        arguments = {
            "dataset": "experiment_data.csv",
            "analysis_type": "statistical",
            "variables": "treatment, outcome",
            "research_question": "Does treatment A significantly improve outcomes?"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        system_msg = result.messages[0].content
        assert "statistical inference" in system_msg.lower()
        assert "hypothesis testing" in system_msg.lower()
        
        user_msg = result.messages[1].content
        assert "statistical" in user_msg
        assert "hypothesis testing" in user_msg.lower()
        assert "statistical tests" in user_msg.lower()
    
    @pytest.mark.asyncio
    async def test_generate_predictive_analysis(self):
        """Test generating predictive analysis prompt."""
        prompt = DataAnalysisPrompt()
        
        arguments = {
            "dataset": "housing_data.csv",
            "analysis_type": "predictive"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        system_msg = result.messages[0].content
        assert "predictive modeling" in system_msg.lower()
        assert "machine learning" in system_msg.lower()
        
        user_msg = result.messages[1].content
        assert "predictive" in user_msg
        assert "feature selection" in user_msg.lower()
        assert "model selection" in user_msg.lower()
    
    @pytest.mark.asyncio
    async def test_generate_with_defaults(self):
        """Test generating prompt with default values."""
        prompt = DataAnalysisPrompt()
        
        arguments = {
            "dataset": "test_data.csv"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        # Should default to exploratory analysis
        system_msg = result.messages[0].content
        assert "exploratory" in system_msg.lower()
    
    def test_to_mcp_prompt(self):
        """Test conversion to MCP prompt format."""
        prompt = DataAnalysisPrompt()
        
        mcp_prompt = prompt.to_mcp_prompt()
        
        assert mcp_prompt["name"] == "analyze_data"
        assert "data analysis" in mcp_prompt["description"].lower()
        assert len(mcp_prompt["arguments"]) == 4
        
        # Check argument structure
        dataset_arg = next(arg for arg in mcp_prompt["arguments"] if arg["name"] == "dataset")
        assert dataset_arg["required"] is True
        
        analysis_type_arg = next(arg for arg in mcp_prompt["arguments"] if arg["name"] == "analysis_type")
        assert analysis_type_arg["required"] is False


class TestStatisticalTestPrompt:
    """Test StatisticalTestPrompt class."""
    
    def test_prompt_properties(self):
        """Test prompt basic properties."""
        prompt = StatisticalTestPrompt()
        
        assert prompt.name == "statistical_test"
        assert "statistical test" in prompt.description.lower()
        assert len(prompt.arguments) == 4
        
        # Check required arguments
        required_args = [arg.name for arg in prompt.arguments if arg.required]
        assert "data_description" in required_args
        assert "research_question" in required_args
        assert len(required_args) == 2
    
    @pytest.mark.asyncio
    async def test_generate_statistical_test_prompt(self):
        """Test generating statistical test selection prompt."""
        prompt = StatisticalTestPrompt()
        
        arguments = {
            "data_description": "Two groups of patients, continuous outcome variable",
            "research_question": "Is there a significant difference in recovery time between treatments?",
            "variable_types": "Treatment (categorical), Recovery time (continuous)",
            "sample_size": "n1=30, n2=32"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        assert len(result.messages) == 3
        
        system_msg = result.messages[0].content
        assert "statistician" in system_msg.lower()
        assert "statistical test selection" in system_msg.lower()
        
        user_msg = result.messages[1].content
        assert "Two groups of patients" in user_msg
        assert "significant difference in recovery time" in user_msg
        assert "Treatment (categorical)" in user_msg
        assert "n1=30, n2=32" in user_msg
        assert "appropriate statistical test" in user_msg.lower()
        
        assistant_msg = result.messages[2].content
        assert "statistical test" in assistant_msg.lower()
        assert "str(your_data)" in assistant_msg
    
    @pytest.mark.asyncio
    async def test_generate_minimal_arguments(self):
        """Test generating prompt with minimal required arguments."""
        prompt = StatisticalTestPrompt()
        
        arguments = {
            "data_description": "Survey responses on 5-point Likert scale",
            "research_question": "Do responses differ by demographic group?"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        user_msg = result.messages[1].content
        assert "Survey responses on 5-point Likert scale" in user_msg
        assert "Do responses differ by demographic group?" in user_msg
        # Should not include optional fields that weren't provided
        assert "Variable Types:" not in user_msg
        assert "Sample Size:" not in user_msg
    
    def test_to_mcp_prompt(self):
        """Test conversion to MCP prompt format."""
        prompt = StatisticalTestPrompt()
        
        mcp_prompt = prompt.to_mcp_prompt()
        
        assert mcp_prompt["name"] == "statistical_test"
        assert len(mcp_prompt["arguments"]) == 4
        
        # Check required arguments
        required_args = [arg["name"] for arg in mcp_prompt["arguments"] if arg["required"]]
        assert "data_description" in required_args
        assert "research_question" in required_args
        assert len(required_args) == 2