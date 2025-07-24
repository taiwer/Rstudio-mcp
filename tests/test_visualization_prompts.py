"""Tests for visualization prompt templates."""

import pytest

from src.rstudio_mcp.prompts.visualization_prompts import CreateVisualizationPrompt, DashboardPrompt


class TestCreateVisualizationPrompt:
    """Test CreateVisualizationPrompt class."""
    
    def test_prompt_properties(self):
        """Test prompt basic properties."""
        prompt = CreateVisualizationPrompt()
        
        assert prompt.name == "create_visualization"
        assert "visualization" in prompt.description.lower()
        assert len(prompt.arguments) == 5
        
        # Check required arguments
        required_args = [arg.name for arg in prompt.arguments if arg.required]
        assert "data_source" in required_args
        assert "chart_type" in required_args
        assert "variables" in required_args
        assert len(required_args) == 3
        
        # Check optional arguments with defaults
        purpose_arg = next(arg for arg in prompt.arguments if arg.name == "purpose")
        assert purpose_arg.default == "exploration"
        
        style_arg = next(arg for arg in prompt.arguments if arg.name == "style")
        assert style_arg.default == "minimal"
    
    @pytest.mark.asyncio
    async def test_generate_scatter_plot(self):
        """Test generating scatter plot visualization prompt."""
        prompt = CreateVisualizationPrompt()
        
        arguments = {
            "data_source": "sales_data.csv",
            "chart_type": "scatter",
            "variables": "x=price, y=quantity, color=region",
            "purpose": "exploration",
            "style": "minimal"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        assert len(result.messages) == 3
        
        system_msg = result.messages[0].content
        assert "data visualization specialist" in system_msg.lower()
        assert "scatter plots" in system_msg.lower()
        assert "relationships between continuous variables" in system_msg.lower()
        
        user_msg = result.messages[1].content
        assert "scatter visualization" in user_msg
        assert "sales_data.csv" in user_msg
        assert "x=price, y=quantity, color=region" in user_msg
        assert "trend lines" in user_msg.lower()
        assert "overplotting" in user_msg.lower()
        
        assistant_msg = result.messages[2].content
        assert "scatter plot" in assistant_msg.lower()
        assert "ggplot2" in assistant_msg
        assert "geom_point" in assistant_msg
    
    @pytest.mark.asyncio
    async def test_generate_bar_chart(self):
        """Test generating bar chart visualization prompt."""
        prompt = CreateVisualizationPrompt()
        
        arguments = {
            "data_source": "survey_data",
            "chart_type": "bar",
            "variables": "category, count",
            "purpose": "presentation",
            "style": "publication"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        
        system_msg = result.messages[0].content
        assert "bar charts" in system_msg.lower()
        assert "publication-ready" in system_msg.lower()
        
        user_msg = result.messages[1].content
        assert "bar visualization" in user_msg
        assert "properly ordered" in user_msg.lower()
        assert "value labels" in user_msg.lower()
        
        assistant_msg = result.messages[2].content
        assert "bar chart" in assistant_msg.lower()
        assert "geom_col" in assistant_msg
    
    @pytest.mark.asyncio
    async def test_generate_line_chart(self):
        """Test generating line chart visualization prompt."""
        prompt = CreateVisualizationPrompt()
        
        arguments = {
            "data_source": "time_series_data",
            "chart_type": "line",
            "variables": "date, value, series",
            "purpose": "comparison"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        
        system_msg = result.messages[0].content
        assert "line charts" in system_msg.lower()
        assert "time series" in system_msg.lower()
        
        user_msg = result.messages[1].content
        assert "line visualization" in user_msg
        assert "time/sequence is on x-axis" in user_msg.lower()
        assert "multiple series" in user_msg.lower()
        
        assistant_msg = result.messages[2].content
        assert "line chart" in assistant_msg.lower()
        assert "geom_line" in assistant_msg
    
    @pytest.mark.asyncio
    async def test_generate_histogram(self):
        """Test generating histogram visualization prompt."""
        prompt = CreateVisualizationPrompt()
        
        arguments = {
            "data_source": "measurement_data",
            "chart_type": "histogram",
            "variables": "measurement_value"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        
        user_msg = result.messages[1].content
        assert "histogram visualization" in user_msg
        assert "bin width" in user_msg.lower()
        assert "distribution shape" in user_msg.lower()
    
    @pytest.mark.asyncio
    async def test_generate_with_defaults(self):
        """Test generating prompt with default values."""
        prompt = CreateVisualizationPrompt()
        
        arguments = {
            "data_source": "test_data",
            "chart_type": "boxplot",
            "variables": "group, value"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        # Should use default purpose and style
        user_msg = result.messages[1].content
        assert "Purpose: exploration" in user_msg
        assert "Style preference: minimal" in user_msg
    
    def test_to_mcp_prompt(self):
        """Test conversion to MCP prompt format."""
        prompt = CreateVisualizationPrompt()
        
        mcp_prompt = prompt.to_mcp_prompt()
        
        assert mcp_prompt["name"] == "create_visualization"
        assert len(mcp_prompt["arguments"]) == 5
        
        # Check required arguments
        required_args = [arg["name"] for arg in mcp_prompt["arguments"] if arg["required"]]
        assert len(required_args) == 3
        assert "data_source" in required_args
        assert "chart_type" in required_args
        assert "variables" in required_args


class TestDashboardPrompt:
    """Test DashboardPrompt class."""
    
    def test_prompt_properties(self):
        """Test prompt basic properties."""
        prompt = DashboardPrompt()
        
        assert prompt.name == "create_dashboard"
        assert "dashboard" in prompt.description.lower()
        assert len(prompt.arguments) == 5
        
        # Check required arguments
        required_args = [arg.name for arg in prompt.arguments if arg.required]
        assert "data_sources" in required_args
        assert "key_metrics" in required_args
        assert len(required_args) == 2
        
        # Check defaults
        dashboard_type_arg = next(arg for arg in prompt.arguments if arg.name == "dashboard_type")
        assert dashboard_type_arg.default == "analytical"
        
        audience_arg = next(arg for arg in prompt.arguments if arg.name == "audience")
        assert audience_arg.default == "analysts"
    
    @pytest.mark.asyncio
    async def test_generate_analytical_dashboard(self):
        """Test generating analytical dashboard prompt."""
        prompt = DashboardPrompt()
        
        arguments = {
            "data_sources": "Sales database, Customer feedback, Web analytics",
            "dashboard_type": "analytical",
            "key_metrics": "Revenue, Customer satisfaction, Conversion rate",
            "interactivity": "Filters by date range, region, product category",
            "audience": "data analysts"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        assert len(result.messages) == 3
        
        system_msg = result.messages[0].content
        assert "dashboard designer" in system_msg.lower()
        assert "r shiny" in system_msg.lower()
        assert "data analysts" in system_msg
        
        user_msg = result.messages[1].content
        assert "analytical dashboard" in user_msg
        assert "Sales database, Customer feedback, Web analytics" in user_msg
        assert "Revenue, Customer satisfaction, Conversion rate" in user_msg
        assert "Filters by date range, region, product category" in user_msg
        assert "Detailed charts and tables" in user_msg
        assert "Drill-down capabilities" in user_msg
        
        assistant_msg = result.messages[2].content
        assert "shiny" in assistant_msg.lower()
        assert "dashboardPage" in assistant_msg
    
    @pytest.mark.asyncio
    async def test_generate_executive_dashboard(self):
        """Test generating executive dashboard prompt."""
        prompt = DashboardPrompt()
        
        arguments = {
            "data_sources": "Business KPIs",
            "dashboard_type": "executive",
            "key_metrics": "Revenue, Profit margin, Market share",
            "audience": "executives"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        
        user_msg = result.messages[1].content
        assert "executive dashboard" in user_msg
        assert "High-level KPI summary cards" in user_msg
        assert "Executive-friendly visualizations" in user_msg
        assert "Export capabilities" in user_msg
    
    @pytest.mark.asyncio
    async def test_generate_operational_dashboard(self):
        """Test generating operational dashboard prompt."""
        prompt = DashboardPrompt()
        
        arguments = {
            "data_sources": "System metrics, Performance data",
            "dashboard_type": "operational",
            "key_metrics": "System uptime, Response time, Error rate"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        
        user_msg = result.messages[1].content
        assert "operational dashboard" in user_msg
        assert "Real-time or near real-time updates" in user_msg
        assert "Alert systems" in user_msg
        assert "Operational metrics tracking" in user_msg
    
    @pytest.mark.asyncio
    async def test_generate_exploratory_dashboard(self):
        """Test generating exploratory dashboard prompt."""
        prompt = DashboardPrompt()
        
        arguments = {
            "data_sources": "Research data",
            "dashboard_type": "exploratory",
            "key_metrics": "Various research metrics"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        
        user_msg = result.messages[1].content
        assert "exploratory dashboard" in user_msg
        assert "Flexible filtering and grouping" in user_msg
        assert "Multiple visualization options" in user_msg
        assert "Data discovery tools" in user_msg
    
    @pytest.mark.asyncio
    async def test_generate_with_defaults(self):
        """Test generating prompt with default values."""
        prompt = DashboardPrompt()
        
        arguments = {
            "data_sources": "Test data",
            "key_metrics": "Test metrics"
        }
        
        result = await prompt.generate(arguments)
        
        assert result.success is True
        user_msg = result.messages[1].content
        assert "analytical dashboard" in user_msg  # Default type
        assert "analysts" in user_msg  # Default audience
    
    def test_to_mcp_prompt(self):
        """Test conversion to MCP prompt format."""
        prompt = DashboardPrompt()
        
        mcp_prompt = prompt.to_mcp_prompt()
        
        assert mcp_prompt["name"] == "create_dashboard"
        assert len(mcp_prompt["arguments"]) == 5
        
        # Check required arguments
        required_args = [arg["name"] for arg in mcp_prompt["arguments"] if arg["required"]]
        assert len(required_args) == 2
        assert "data_sources" in required_args
        assert "key_metrics" in required_args