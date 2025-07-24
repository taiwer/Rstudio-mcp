"""Visualization prompt templates for RStudio MCP Server."""

from typing import Any, Dict, List

from .base import BasePrompt, PromptResult, PromptArgument


class CreateVisualizationPrompt(BasePrompt):
    """Prompt template for creating data visualizations."""
    
    @property
    def name(self) -> str:
        return "create_visualization"
    
    @property
    def description(self) -> str:
        return "Generate prompts for creating data visualizations with different chart types"
    
    @property
    def arguments(self) -> List[PromptArgument]:
        return [
            PromptArgument(
                name="data_source",
                description="Name or description of the data source",
                required=True
            ),
            PromptArgument(
                name="chart_type",
                description="Type of chart (scatter, bar, line, histogram, boxplot, heatmap, violin, density)",
                required=True
            ),
            PromptArgument(
                name="variables",
                description="Variables to visualize (x, y, color, facet, etc.)",
                required=True
            ),
            PromptArgument(
                name="purpose",
                description="Purpose of the visualization (exploration, presentation, comparison, etc.)",
                required=False,
                default="exploration"
            ),
            PromptArgument(
                name="style",
                description="Visualization style (minimal, publication, interactive, dashboard)",
                required=False,
                default="minimal"
            )
        ]
    
    async def generate(self, arguments: Dict[str, Any]) -> PromptResult:
        """Generate visualization creation prompt."""
        data_source = arguments["data_source"]
        chart_type = arguments["chart_type"]
        variables = arguments["variables"]
        purpose = arguments.get("purpose", "exploration")
        style = arguments.get("style", "minimal")
        
        result = PromptResult(success=True)
        
        # System message based on chart type and purpose
        system_msg = self._get_system_message(chart_type, purpose)
        result.add_system_message(system_msg)
        
        # User message with specific visualization request
        user_msg = self._build_user_message(data_source, chart_type, variables, purpose, style)
        result.add_user_message(user_msg)
        
        # Example response to guide visualization creation
        example_msg = self._get_example_response(chart_type, style)
        result.add_assistant_message(example_msg)
        
        return result
    
    def _get_system_message(self, chart_type: str, purpose: str) -> str:
        """Get system message based on chart type and purpose."""
        base_msg = """You are an expert data visualization specialist with deep knowledge of ggplot2, plotly, and other R visualization libraries."""
        
        purpose_guidance = {
            "exploration": "Focus on creating clear, informative visualizations that reveal patterns and insights in the data.",
            "presentation": "Create polished, publication-ready visualizations with proper titles, labels, and formatting.",
            "comparison": "Design visualizations that effectively highlight differences and similarities between groups or conditions.",
            "dashboard": "Build interactive, dashboard-style visualizations that allow for exploration and filtering."
        }
        
        chart_guidance = {
            "scatter": "Specialize in scatter plots for showing relationships between continuous variables.",
            "bar": "Expert in bar charts for comparing categories and showing distributions.",
            "line": "Focus on line charts for time series and trend visualization.",
            "histogram": "Specialize in histograms for showing data distributions.",
            "boxplot": "Expert in box plots for comparing distributions across groups.",
            "heatmap": "Focus on heatmaps for showing correlation matrices and 2D data patterns.",
            "violin": "Specialize in violin plots for detailed distribution comparisons.",
            "density": "Expert in density plots for smooth distribution visualization."
        }
        
        return f"""{base_msg}

{purpose_guidance.get(purpose, purpose_guidance["exploration"])}

{chart_guidance.get(chart_type, "Create effective visualizations that clearly communicate the data story.")}

Always provide:
1. Clean, well-commented R code
2. Appropriate color schemes and aesthetics
3. Clear titles, labels, and legends
4. Suggestions for improving the visualization
5. Alternative visualization approaches when relevant"""
    
    def _build_user_message(self, data_source: str, chart_type: str, variables: str, 
                           purpose: str, style: str) -> str:
        """Build user message for visualization request."""
        msg_parts = [
            f"Please create a {chart_type} visualization using data from: {data_source}",
            f"Variables to visualize: {variables}",
            f"Purpose: {purpose}",
            f"Style preference: {style}"
        ]
        
        # Add chart-specific requirements
        chart_requirements = {
            "scatter": [
                "Show the relationship between variables clearly",
                "Add trend lines if appropriate",
                "Handle overplotting if necessary",
                "Consider color coding by groups"
            ],
            "bar": [
                "Ensure bars are properly ordered",
                "Add value labels if helpful",
                "Consider horizontal vs vertical orientation",
                "Use appropriate color scheme"
            ],
            "line": [
                "Ensure time/sequence is on x-axis",
                "Add appropriate smoothing if needed",
                "Handle multiple series clearly",
                "Include confidence intervals if relevant"
            ],
            "histogram": [
                "Choose appropriate bin width",
                "Show distribution shape clearly",
                "Add density curve if helpful",
                "Consider faceting by groups"
            ],
            "boxplot": [
                "Show all distribution statistics",
                "Handle outliers appropriately",
                "Consider violin plots for more detail",
                "Add sample size information"
            ],
            "heatmap": [
                "Use appropriate color scale",
                "Ensure readability of labels",
                "Consider clustering if appropriate",
                "Add correlation values if relevant"
            ]
        }
        
        requirements = chart_requirements.get(chart_type, [
            "Create clear, informative visualization",
            "Use appropriate aesthetics and colors",
            "Ensure all elements are properly labeled"
        ])
        
        msg_parts.append("\nSpecific requirements:")
        for req in requirements:
            msg_parts.append(f"- {req}")
        
        # Add style-specific requirements
        style_requirements = {
            "minimal": "Use clean, minimal design with focus on data",
            "publication": "Create publication-ready plot with proper formatting and high DPI",
            "interactive": "Make the plot interactive using plotly or similar",
            "dashboard": "Design for dashboard integration with filtering capabilities"
        }
        
        if style in style_requirements:
            msg_parts.append(f"\nStyle requirements: {style_requirements[style]}")
        
        msg_parts.append("\nPlease provide complete R code with explanations and suggestions for improvements.")
        
        return "\n".join(msg_parts)
    
    def _get_example_response(self, chart_type: str, style: str) -> str:
        """Get example response based on chart type and style."""
        examples = {
            "scatter": """I'll create a scatter plot for you. Let me start with the basic structure and then enhance it:

```r
library(ggplot2)
library(dplyr)

# Basic scatter plot
p <- ggplot(data, aes(x = variable_x, y = variable_y)) +
  geom_point(alpha = 0.7) +
  labs(title = "Relationship between X and Y",
       x = "X Variable",
       y = "Y Variable") +
  theme_minimal()

# Add trend line
p + geom_smooth(method = "lm", se = TRUE, color = "blue")
```

This creates a clean scatter plot with a trend line to show the relationship.""",
            
            "bar": """I'll create an effective bar chart for your data:

```r
library(ggplot2)
library(dplyr)

# Create bar chart with proper ordering
data_summary <- data %>%
  group_by(category) %>%
  summarise(value = mean(variable, na.rm = TRUE)) %>%
  arrange(desc(value))

ggplot(data_summary, aes(x = reorder(category, value), y = value)) +
  geom_col(fill = "steelblue", alpha = 0.8) +
  coord_flip() +
  labs(title = "Average Values by Category",
       x = "Category",
       y = "Average Value") +
  theme_minimal()
```

This creates a horizontal bar chart with categories ordered by value.""",
            
            "line": """I'll create a line chart perfect for showing trends over time:

```r
library(ggplot2)
library(dplyr)

# Line chart with proper formatting
ggplot(data, aes(x = time_variable, y = value_variable)) +
  geom_line(size = 1.2, color = "darkblue") +
  geom_point(size = 2, color = "darkblue") +
  labs(title = "Trend Over Time",
       x = "Time",
       y = "Value") +
  theme_minimal() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1))
```

This shows the trend clearly with both lines and points."""
        }
        
        return examples.get(chart_type, examples["scatter"])


class DashboardPrompt(BasePrompt):
    """Prompt template for creating interactive dashboards."""
    
    @property
    def name(self) -> str:
        return "create_dashboard"
    
    @property
    def description(self) -> str:
        return "Generate prompts for creating interactive dashboards and reports"
    
    @property
    def arguments(self) -> List[PromptArgument]:
        return [
            PromptArgument(
                name="data_sources",
                description="Description of data sources to include",
                required=True
            ),
            PromptArgument(
                name="dashboard_type",
                description="Type of dashboard (executive, analytical, operational, exploratory)",
                required=False,
                default="analytical"
            ),
            PromptArgument(
                name="key_metrics",
                description="Key metrics and KPIs to display",
                required=True
            ),
            PromptArgument(
                name="interactivity",
                description="Required interactive features (filters, drill-down, real-time updates)",
                required=False
            ),
            PromptArgument(
                name="audience",
                description="Target audience (executives, analysts, general users)",
                required=False,
                default="analysts"
            )
        ]
    
    async def generate(self, arguments: Dict[str, Any]) -> PromptResult:
        """Generate dashboard creation prompt."""
        data_sources = arguments["data_sources"]
        dashboard_type = arguments.get("dashboard_type", "analytical")
        key_metrics = arguments["key_metrics"]
        interactivity = arguments.get("interactivity", "")
        audience = arguments.get("audience", "analysts")
        
        result = PromptResult(success=True)
        
        system_msg = f"""You are an expert dashboard designer and R Shiny developer specializing in creating interactive data dashboards.

Your expertise includes:
1. R Shiny application development
2. Interactive visualization with plotly and DT
3. Dashboard layout and UX design
4. Performance optimization for large datasets
5. Responsive design for different screen sizes

Focus on creating dashboards that are:
- User-friendly and intuitive for {audience}
- Performant and responsive
- Visually appealing and professional
- Functionally complete with proper error handling"""
        
        result.add_system_message(system_msg)
        
        user_msg = f"""Please help me create an interactive {dashboard_type} dashboard with the following specifications:

Data Sources: {data_sources}

Key Metrics to Display: {key_metrics}

Target Audience: {audience}"""
        
        if interactivity:
            user_msg += f"\n\nRequired Interactive Features: {interactivity}"
        
        dashboard_requirements = {
            "executive": [
                "High-level KPI summary cards",
                "Executive-friendly visualizations",
                "Minimal clutter and clear messaging",
                "Export capabilities for reports"
            ],
            "analytical": [
                "Detailed charts and tables",
                "Drill-down capabilities",
                "Statistical summaries",
                "Data export and filtering options"
            ],
            "operational": [
                "Real-time or near real-time updates",
                "Alert systems for thresholds",
                "Operational metrics tracking",
                "Quick action buttons"
            ],
            "exploratory": [
                "Flexible filtering and grouping",
                "Multiple visualization options",
                "Data discovery tools",
                "Interactive parameter adjustment"
            ]
        }
        
        requirements = dashboard_requirements.get(dashboard_type, dashboard_requirements["analytical"])
        
        user_msg += f"\n\nDashboard Requirements:"
        for req in requirements:
            user_msg += f"\n- {req}"
        
        user_msg += """

Please provide:
1. Complete R Shiny application code (ui.R and server.R)
2. Required libraries and dependencies
3. Data preprocessing steps
4. Layout and styling recommendations
5. Deployment considerations"""
        
        result.add_user_message(user_msg)
        
        example_msg = """I'll help you create a comprehensive interactive dashboard. Let me start with the basic Shiny structure:

```r
# Load required libraries
library(shiny)
library(shinydashboard)
library(plotly)
library(DT)
library(dplyr)

# UI
ui <- dashboardPage(
  dashboardHeader(title = "Data Dashboard"),
  dashboardSidebar(
    sidebarMenu(
      menuItem("Overview", tabName = "overview"),
      menuItem("Detailed Analysis", tabName = "analysis")
    )
  ),
  dashboardBody(
    tabItems(
      tabItem(tabName = "overview",
        fluidRow(
          valueBoxOutput("kpi1"),
          valueBoxOutput("kpi2"),
          valueBoxOutput("kpi3")
        ),
        fluidRow(
          box(plotlyOutput("main_chart"), width = 12)
        )
      )
    )
  )
)

# Server logic will include reactive data processing and chart generation
```

This provides a solid foundation for your dashboard with KPI boxes and interactive charts."""
        
        result.add_assistant_message(example_msg)
        
        return result