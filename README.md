# RStudio MCP Server

A Model Context Protocol (MCP) server that provides AI assistants with deep RStudio integration capabilities, including environment management, code execution, project management, and more.

## Features

- **Environment Management**: Create, switch, and manage R environments
- **Code Execution**: Execute R code in specified environments with result capture
- **Project Management**: Create and manage RStudio projects
- **Package Management**: Install, update, and manage R packages
- **Version Control**: Git integration for RStudio projects
- **Visualization**: Capture and manage R plots and visualizations
- **MCP Compliance**: Full compliance with MCP 2025-06-18 specification

## Installation

### Prerequisites

- Python 3.8 or higher
- R 4.0 or higher
- RStudio (optional, but recommended)

### Install from Source

```bash
git clone https://github.com/rstudio/rstudio-mcp.git
cd rstudio-mcp
pip install -e .
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

## Quick Start

### 1. Initialize Configuration

```bash
rstudio-mcp --init-config
```

This creates a default configuration file at `~/.rstudio-mcp/config.yaml`.

### 2. Edit Configuration (Optional)

Edit the configuration file to customize settings:

```bash
nano ~/.rstudio-mcp/config.yaml
```

### 3. Run the Server

```bash
# Run with default configuration
rstudio-mcp

# Run with custom configuration
rstudio-mcp --config /path/to/config.yaml

# Run in debug mode
rstudio-mcp --debug
```

## Configuration

The server uses YAML configuration files. Here's an example configuration:

```yaml
# Server settings
name: "rstudio-mcp"
version: "1.0.0"
debug: false

# Logging configuration
logging:
  level: "INFO"
  file: "~/.rstudio-mcp/logs/server.log"
  max_size: "10MB"
  backup_count: 5

# RStudio configuration
rstudio:
  installation_path: null  # Auto-detect
  default_r_version: "4.3.0"

# Environment management
environments:
  default_location: "~/.rstudio-mcp/environments"
  auto_cleanup: true
  max_environments: 10

# Security settings
security:
  allowed_packages:
    - "base"
    - "utils"
    - "stats"
    - "graphics"
  blocked_functions:
    - "system"
    - "shell"
  execution_timeout: 300
```

## MCP Tools

The server provides the following MCP tools:

### Environment Management
- `create_environment`: Create a new R environment
- `list_environments`: List all available environments
- `switch_environment`: Switch to a different environment
- `delete_environment`: Delete an environment

### Code Execution
- `execute_r_code`: Execute R code in a specified environment
- `get_execution_history`: Get history of executed code

### Project Management
- `create_project`: Create a new RStudio project
- `open_project`: Open an existing project
- `get_project_info`: Get project information

### Package Management
- `install_package`: Install R packages
- `update_package`: Update packages
- `list_packages`: List installed packages

## MCP Resources

The server exposes the following resources:

- `rstudio-project://`: Access to project files and configuration
- `rstudio-workspace://`: Access to workspace objects and variables
- `rstudio-environment://`: Access to environment information
- `rstudio-plot://`: Access to generated plots and visualizations

## MCP Prompts

Pre-built prompts for common R development tasks:

- `analyze_data`: Data analysis guidance
- `create_visualization`: Visualization creation help
- `debug_r_code`: R code debugging assistance
- `optimize_performance`: Performance optimization suggestions

## Development

### Project Structure

```
rstudio-mcp/
├── src/rstudio_mcp/          # Main package
│   ├── __init__.py
│   ├── server.py             # MCP server implementation
│   ├── config.py             # Configuration management
│   ├── cli.py                # Command-line interface
│   ├── exceptions.py         # Exception classes
│   ├── logging_config.py     # Logging setup
│   └── config/
│       └── default.yaml      # Default configuration
├── tests/                    # Test suite
├── docs/                     # Documentation
├── pyproject.toml           # Project configuration
└── README.md
```

### Running Tests

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=src/rstudio_mcp

# Run specific test file
python -m pytest tests/test_server.py -v
```

### Code Quality

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Type checking
mypy src/

# Linting
flake8 src/ tests/
```

## Architecture

The RStudio MCP Server follows a modular architecture:

1. **MCP Server Core**: Handles MCP protocol communication
2. **Tool Manager**: Manages available tools and their execution
3. **Resource Manager**: Handles resource access and URI schemes
4. **Prompt Manager**: Manages prompt templates
5. **RStudio API Wrapper**: Interfaces with RStudio and R
6. **Configuration System**: Manages server configuration
7. **Logging System**: Handles logging and error reporting

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- Documentation: [docs/](docs/)
- Issues: [GitHub Issues](https://github.com/rstudio/rstudio-mcp/issues)
- Discussions: [GitHub Discussions](https://github.com/rstudio/rstudio-mcp/discussions)

## Roadmap

- [x] Basic MCP server framework
- [ ] RStudio API integration
- [ ] Environment management tools
- [ ] Code execution capabilities
- [ ] Project management features
- [ ] Package management tools
- [ ] Version control integration
- [ ] Visualization handling
- [ ] Advanced security features
- [ ] Performance optimizations