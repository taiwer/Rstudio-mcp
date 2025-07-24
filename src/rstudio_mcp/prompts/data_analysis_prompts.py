"""Data analysis prompt templates for RStudio MCP Server."""

from typing import Any, Dict, List

from .base import BasePrompt, PromptResult, PromptArgument, PromptMessage


class DataAnalysisPrompt(BasePrompt):
    """Prompt template for data analysis tasks."""
    
    @property
    def name(self) -> str:
        return "analyze_data"
    
    @property
    def description(self) -> str:
        return "Generate prompts for data analysis tasks with different analysis types"
    
    @property
    def arguments(self) -> List[PromptArgument]:
        return [
            PromptArgument(
                name="dataset",
                description="Name or path of the dataset to analyze",
                required=True
            ),
            PromptArgument(
                name="analysis_type",
                description="Type of analysis (descriptive, exploratory, statistical, predictive)",
                required=False,
                default="exploratory"
            ),
            PromptArgument(
                name="variables",
                description="Specific variables to focus on (comma-separated)",
                required=False
            ),
            PromptArgument(
                name="research_question",
                description="Specific research question or hypothesis to investigate",
                required=False
            )
        ]
    
    async def generate(self, arguments: Dict[str, Any]) -> PromptResult:
        """Generate data analysis prompt."""
        dataset = arguments["dataset"]
        analysis_type = arguments.get("analysis_type", "exploratory")
        variables = arguments.get("variables")
        research_question = arguments.get("research_question")
        
        result = PromptResult(success=True)
        
        # System message based on analysis type
        system_messages = {
            "descriptive": self._get_descriptive_system_message(),
            "exploratory": self._get_exploratory_system_message(),
            "statistical": self._get_statistical_system_message(),
            "predictive": self._get_predictive_system_message()
        }
        
        system_msg = system_messages.get(analysis_type, system_messages["exploratory"])
        result.add_system_message(system_msg)
        
        # User message with specific instructions
        user_msg = self._build_user_message(dataset, analysis_type, variables, research_question)
        result.add_user_message(user_msg)
        
        # Add example assistant response to guide the analysis
        example_msg = self._get_example_response(analysis_type)
        result.add_assistant_message(example_msg)
        
        return result
    
    def _get_descriptive_system_message(self) -> str:
        """Get system message for descriptive analysis."""
        return """You are an expert data analyst specializing in descriptive statistics and data summarization. 
Your role is to help users understand the basic characteristics of their data through:

1. Summary statistics (mean, median, mode, standard deviation, etc.)
2. Data distribution analysis
3. Missing value assessment
4. Data quality evaluation
5. Basic visualizations (histograms, box plots, scatter plots)

Always provide clear, actionable R code and explain the insights in plain language."""
    
    def _get_exploratory_system_message(self) -> str:
        """Get system message for exploratory analysis."""
        return """You are an expert data analyst specializing in exploratory data analysis (EDA). 
Your role is to help users discover patterns, relationships, and insights in their data through:

1. Comprehensive data exploration and profiling
2. Correlation analysis and relationship discovery
3. Pattern identification and anomaly detection
4. Feature engineering suggestions
5. Interactive visualizations and dashboards

Focus on uncovering hidden insights and generating hypotheses for further investigation."""
    
    def _get_statistical_system_message(self) -> str:
        """Get system message for statistical analysis."""
        return """You are an expert statistician and data analyst specializing in statistical inference and hypothesis testing.
Your role is to help users conduct rigorous statistical analysis including:

1. Hypothesis formulation and testing
2. Statistical significance testing
3. Confidence intervals and effect sizes
4. Regression analysis and model building
5. ANOVA, t-tests, chi-square tests, and other statistical tests

Always validate assumptions, interpret results correctly, and provide statistical context."""
    
    def _get_predictive_system_message(self) -> str:
        """Get system message for predictive analysis."""
        return """You are an expert data scientist specializing in predictive modeling and machine learning.
Your role is to help users build and evaluate predictive models including:

1. Feature selection and engineering
2. Model selection and comparison
3. Cross-validation and performance evaluation
4. Overfitting prevention and regularization
5. Model interpretation and deployment considerations

Focus on building robust, interpretable models with good generalization performance."""
    
    def _build_user_message(self, dataset: str, analysis_type: str, variables: str = None, 
                           research_question: str = None) -> str:
        """Build the user message with specific analysis request."""
        msg_parts = [
            f"Please perform a {analysis_type} analysis on the dataset: {dataset}"
        ]
        
        if variables:
            msg_parts.append(f"Focus specifically on these variables: {variables}")
        
        if research_question:
            msg_parts.append(f"Research question: {research_question}")
        
        # Add analysis-specific instructions
        if analysis_type == "descriptive":
            msg_parts.append("""
Please provide:
1. Basic summary statistics for all numeric variables
2. Frequency tables for categorical variables
3. Missing value analysis
4. Data distribution visualizations
5. Key insights about the data structure and quality""")
        
        elif analysis_type == "exploratory":
            msg_parts.append("""
Please provide:
1. Comprehensive data profiling
2. Correlation analysis and heatmaps
3. Relationship exploration between variables
4. Outlier detection and analysis
5. Pattern discovery and hypothesis generation""")
        
        elif analysis_type == "statistical":
            msg_parts.append("""
Please provide:
1. Appropriate statistical tests based on the data
2. Hypothesis testing with clear null and alternative hypotheses
3. Assumption checking and validation
4. Effect size calculations and confidence intervals
5. Statistical interpretation and conclusions""")
        
        elif analysis_type == "predictive":
            msg_parts.append("""
Please provide:
1. Target variable identification and feature selection
2. Data preprocessing and feature engineering
3. Model selection and training
4. Cross-validation and performance evaluation
5. Model interpretation and deployment recommendations""")
        
        msg_parts.append("""
Please provide complete, executable R code with detailed comments and clear explanations of the results.""")
        
        return "\n\n".join(msg_parts)
    
    def _get_example_response(self, analysis_type: str) -> str:
        """Get example response to guide the analysis."""
        examples = {
            "descriptive": """I'll help you perform a descriptive analysis. Let me start by loading and examining the data structure:

```r
# Load necessary libraries
library(dplyr)
library(ggplot2)
library(summary)

# Load and examine the dataset
data <- read.csv("your_dataset.csv")
str(data)
summary(data)
```

This approach will give us a comprehensive overview of your data's basic characteristics.""",
            
            "exploratory": """I'll conduct a thorough exploratory data analysis. Let me start with data profiling and then explore relationships:

```r
# Load libraries for EDA
library(dplyr)
library(ggplot2)
library(corrplot)
library(DataExplorer)

# Create comprehensive EDA report
create_report(data)

# Correlation analysis
numeric_vars <- select_if(data, is.numeric)
cor_matrix <- cor(numeric_vars, use = "complete.obs")
corrplot(cor_matrix, method = "color")
```

This will reveal patterns and relationships in your data.""",
            
            "statistical": """I'll help you conduct rigorous statistical analysis. Let me start by examining the data and formulating appropriate hypotheses:

```r
# Load statistical libraries
library(dplyr)
library(broom)
library(car)

# Examine data structure and distributions
summary(data)
hist(data$variable_of_interest)

# Check assumptions and perform appropriate tests
shapiro.test(data$variable_of_interest)  # Normality test
```

I'll ensure all statistical assumptions are met before proceeding with tests.""",
            
            "predictive": """I'll help you build a predictive model. Let me start with data preparation and feature engineering:

```r
# Load machine learning libraries
library(caret)
library(randomForest)
library(glmnet)

# Data preprocessing
set.seed(123)
trainIndex <- createDataPartition(data$target, p = 0.8, list = FALSE)
train_data <- data[trainIndex, ]
test_data <- data[-trainIndex, ]

# Feature engineering and model building
```

I'll guide you through the entire modeling pipeline with proper validation."""
        }
        
        return examples.get(analysis_type, examples["exploratory"])


class StatisticalTestPrompt(BasePrompt):
    """Prompt template for statistical test selection and execution."""
    
    @property
    def name(self) -> str:
        return "statistical_test"
    
    @property
    def description(self) -> str:
        return "Generate prompts for selecting and performing appropriate statistical tests"
    
    @property
    def arguments(self) -> List[PromptArgument]:
        return [
            PromptArgument(
                name="data_description",
                description="Description of the data and variables involved",
                required=True
            ),
            PromptArgument(
                name="research_question",
                description="The research question or hypothesis to test",
                required=True
            ),
            PromptArgument(
                name="variable_types",
                description="Types of variables (continuous, categorical, ordinal)",
                required=False
            ),
            PromptArgument(
                name="sample_size",
                description="Sample size information",
                required=False
            )
        ]
    
    async def generate(self, arguments: Dict[str, Any]) -> PromptResult:
        """Generate statistical test selection prompt."""
        data_description = arguments["data_description"]
        research_question = arguments["research_question"]
        variable_types = arguments.get("variable_types", "")
        sample_size = arguments.get("sample_size", "")
        
        result = PromptResult(success=True)
        
        system_msg = """You are an expert statistician specializing in statistical test selection and execution.
Your role is to help users choose the most appropriate statistical test based on:

1. Research question and hypothesis type
2. Data characteristics and variable types
3. Sample size and distribution assumptions
4. Study design and data collection method

Always explain the rationale for test selection, check assumptions, and provide clear interpretation of results."""
        
        result.add_system_message(system_msg)
        
        user_msg = f"""I need help selecting and performing the appropriate statistical test for my analysis.

Data Description: {data_description}

Research Question: {research_question}"""
        
        if variable_types:
            user_msg += f"\n\nVariable Types: {variable_types}"
        
        if sample_size:
            user_msg += f"\n\nSample Size: {sample_size}"
        
        user_msg += """

Please help me:
1. Identify the most appropriate statistical test(s)
2. Check and validate all necessary assumptions
3. Provide complete R code for the analysis
4. Interpret the results in the context of my research question
5. Suggest follow-up analyses if appropriate"""
        
        result.add_user_message(user_msg)
        
        example_msg = """I'll help you select the appropriate statistical test. Let me start by analyzing your research question and data characteristics:

```r
# First, let's examine the data structure
str(your_data)
summary(your_data)

# Check distributions and assumptions
hist(your_data$variable1)
shapiro.test(your_data$variable1)  # Test for normality
```

Based on your research question and data type, I'll recommend the most suitable test and walk you through the analysis step by step."""
        
        result.add_assistant_message(example_msg)
        
        return result