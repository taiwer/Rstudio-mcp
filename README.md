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

#### stdio Mode (Default)

The default mode uses standard input/output for MCP communication, suitable for local integration with AI assistants:

```bash
# Run with default configuration
rstudio-mcp

# Run with custom configuration
rstudio-mcp --config /path/to/config.yaml

# Run in debug mode
rstudio-mcp --debug
```

#### SSE Mode (Server-Sent Events)

SSE mode runs the server as an HTTP service, enabling remote connections and web-based integrations:

```bash
# Run in SSE mode (default port 3000)
rstudio-mcp --mode sse

# Run in SSE mode with custom host and port
rstudio-mcp --mode sse --host 0.0.0.0 --port 8080

# Run in SSE mode with debug logging
rstudio-mcp --mode sse --debug

# Combine with custom configuration
rstudio-mcp --mode sse --config /path/to/config.yaml --port 8080
```

**SSE Endpoints:**
- `http://localhost:3000/sse` - MCP communication endpoint
- `http://localhost:3000/health` - Health check endpoint
- `http://localhost:3000/status` - Server status and connection info
- `http://localhost:3000/connections` - Active connection details

## Configuration

The server uses YAML configuration files. Here's an example configuration:

```yaml
# Server settings
name: "rstudio-mcp"
version: "1.0.0"
debug: false
host: "localhost"  # SSE server host
port: 3000         # SSE server port

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

**Configuration Options:**
- `host`: Server host address (default: "localhost") - used in SSE mode
- `port`: Server port number (default: 3000) - used in SSE mode
- `debug`: Enable debug mode with verbose logging
- `logging.level`: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

See `examples/sse-config.yaml` for an SSE-specific configuration example.

## Integration with AI Coding Assistants

This MCP server is designed to work seamlessly with popular AI coding assistants in RStudio's terminal environment. The server supports the Model Context Protocol (MCP) specification and can be integrated with various AI clients.

### Supported AI Clients

Based on the [MCP client compatibility matrix](llms-full.txt), the following AI coding assistants support MCP integration:

- **Claude Code** - Supports prompts and tools
- **VS Code GitHub Copilot** - Full MCP support with dynamic tool discovery
- **Continue** - Supports tools, prompts, and resources
- **Cursor** - Supports tools via Composer
- **Cline** - Supports tools and resources
- **JetBrains AI Assistant** - Supports tools for all JetBrains IDEs

### Configuration for AI Assistants

#### 1. Claude Code Integration

Claude Code can connect to this MCP server to enhance R development workflows:

```json
{
  "mcpServers": {
    "rstudio-mcp": {
      "command": "rstudio-mcp",
      "args": ["--config", "~/.rstudio-mcp/config.yaml"],
      "env": {
        "RSTUDIO_MCP_DEBUG": "false"
      }
    }
  }
}
```

#### 2. VS Code GitHub Copilot

Configure in VS Code settings or workspace settings:

```json
{
  "github.copilot.chat.mcp.servers": {
    "rstudio-mcp": {
      "command": "rstudio-mcp",
      "args": ["--stdio"],
      "env": {
        "RSTUDIO_MCP_CONFIG": "~/.rstudio-mcp/config.yaml"
      }
    }
  }
}
```

#### 3. Continue Extension

Add to your Continue configuration (`~/.continue/config.json`):

```json
{
  "mcpServers": [
    {
      "name": "rstudio-mcp",
      "command": "rstudio-mcp",
      "args": ["--stdio"],
      "env": {
        "RSTUDIO_MCP_CONFIG": "~/.rstudio-mcp/config.yaml"
      }
    }
  ]
}
```

#### 4. RStudio Terminal Integration

To use with AI assistants directly in RStudio's terminal:

1. **Start the MCP server in the background:**

   ```bash
   # In RStudio Terminal
   rstudio-mcp --daemon --port 3000
   ```

2. **Configure your AI assistant to connect via SSE:**

   ```bash
   # Server endpoint for SSE connections
   http://localhost:3000/sse
   ```

3. **Available tools in RStudio context:**
   - `create_environment` - Create R environments
   - `execute_r_code` - Run R code with result capture
   - `create_project` - Create RStudio projects
   - `install_package` - Manage R packages
   - `get_project_info` - Access project metadata

### Environment Variables

Set these environment variables for optimal integration:

```bash
# RStudio MCP Configuration
export RSTUDIO_MCP_CONFIG="~/.rstudio-mcp/config.yaml"
export RSTUDIO_MCP_LOG_LEVEL="INFO"
export RSTUDIO_MCP_PORT="3000"

# R Environment
export R_HOME="/usr/local/lib/R"
export R_LIBS_USER="~/.rstudio-mcp/libraries"
```

### Usage Examples

#### With Claude Code in RStudio Terminal

```bash
# Start MCP server
rstudio-mcp --daemon

# Claude Code can now:
# - Create R environments: "Create a new R environment for data analysis"
# - Execute R code: "Run this statistical analysis and show results"
# - Manage projects: "Set up a new RStudio project for machine learning"
```

#### With GitHub Copilot in VS Code

```bash
# In VS Code terminal connected to RStudio server
# Copilot can access:
# - R workspace objects via rstudio-workspace:// resources
# - Project files via rstudio-project:// resources
# - Environment info via rstudio-environment:// resources
# - Generated plots via rstudio-plot:// resources
```

### Troubleshooting

1. **Connection Issues:**

   ```bash
   # Check if MCP server is running
   rstudio-mcp --status

   # Test connection
   curl http://localhost:3000/health
   ```

2. **Permission Issues:**

   ```bash
   # Ensure proper permissions
   chmod +x $(which rstudio-mcp)
   chown -R $USER ~/.rstudio-mcp/
   ```

3. **R Environment Issues:**

   ```bash
   # Verify R installation
   rstudio-mcp --check-r

   # Reset environments
   rstudio-mcp --reset-environments
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

```text
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