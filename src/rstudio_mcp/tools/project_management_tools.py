"""Project management tools for RStudio MCP Server."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..api_wrapper import RStudioAPIWrapper
from ..exceptions import ProjectError
from .base import BaseTool, ToolParameter, ToolResult


class CreateProjectTool(BaseTool):
    """Tool for creating new RStudio projects."""
    
    def __init__(self, api_wrapper: Optional[RStudioAPIWrapper] = None):
        """Initialize the create project tool.
        
        Args:
            api_wrapper: RStudio API wrapper instance
        """
        super().__init__()
        self.api = api_wrapper or RStudioAPIWrapper()
    
    @property
    def name(self) -> str:
        return "create_project"
    
    @property
    def description(self) -> str:
        return "创建新的RStudio项目，支持不同类型的项目模板"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="name",
                type="string",
                description="项目名称",
                required=True
            ),
            ToolParameter(
                name="path",
                type="string", 
                description="项目创建路径（父目录）",
                required=True
            ),
            ToolParameter(
                name="type",
                type="string",
                description="项目类型",
                required=False,
                default="default",
                enum=["default", "package", "shiny", "bookdown", "website"]
            ),
            ToolParameter(
                name="git",
                type="boolean",
                description="是否初始化Git仓库",
                required=False,
                default=False
            ),
            ToolParameter(
                name="renv",
                type="boolean", 
                description="是否使用renv进行包管理",
                required=False,
                default=False
            ),
            ToolParameter(
                name="template_options",
                type="object",
                description="项目模板的额外选项",
                required=False,
                default={}
            )
        ]
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the create project tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        try:
            name = arguments["name"]
            parent_path = arguments["path"]
            project_type = arguments.get("type", "default")
            use_git = arguments.get("git", False)
            use_renv = arguments.get("renv", False)
            template_options = arguments.get("template_options", {})
            
            # Validate project name
            if not name or not name.replace("_", "").replace("-", "").replace(".", "").isalnum():
                return ToolResult(
                    success=False,
                    error="项目名称只能包含字母、数字、下划线、连字符和点"
                )
            
            # Create full project path
            project_path = Path(parent_path) / name
            
            # Check if path already exists
            if project_path.exists():
                return ToolResult(
                    success=False,
                    error=f"路径 {project_path} 已存在"
                )
            
            # Create project directory
            project_path.mkdir(parents=True, exist_ok=False)
            
            # Create project based on type
            success = await self._create_project_by_type(
                project_path, project_type, template_options
            )
            
            if not success:
                # Clean up on failure
                if project_path.exists():
                    import shutil
                    shutil.rmtree(project_path)
                return ToolResult(
                    success=False,
                    error=f"创建 {project_type} 类型项目失败"
                )
            
            # Initialize Git if requested
            if use_git:
                await self._initialize_git(project_path)
            
            # Initialize renv if requested
            if use_renv:
                await self._initialize_renv(project_path)
            
            result = ToolResult(success=True)
            result.add_text_content(f"成功创建项目 '{name}' 在路径: {project_path}")
            result.add_text_content(f"项目类型: {project_type}")
            
            if use_git:
                result.add_text_content("已初始化Git仓库")
            if use_renv:
                result.add_text_content("已初始化renv包管理")
            
            # Add project info to metadata
            result.metadata = {
                "project_name": name,
                "project_path": str(project_path),
                "project_type": project_type,
                "git_enabled": use_git,
                "renv_enabled": use_renv
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to create project: {e}")
            return ToolResult(
                success=False,
                error=f"创建项目失败: {str(e)}"
            )
    
    async def _create_project_by_type(
        self, 
        project_path: Path, 
        project_type: str,
        template_options: Dict[str, Any]
    ) -> bool:
        """Create project files based on project type.
        
        Args:
            project_path: Path to the project directory
            project_type: Type of project to create
            template_options: Additional template options
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if project_type == "default":
                return await self._create_default_project(project_path)
            elif project_type == "package":
                return await self._create_package_project(project_path, template_options)
            elif project_type == "shiny":
                return await self._create_shiny_project(project_path, template_options)
            elif project_type == "bookdown":
                return await self._create_bookdown_project(project_path)
            elif project_type == "website":
                return await self._create_website_project(project_path)
            else:
                self.logger.error(f"Unknown project type: {project_type}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to create {project_type} project: {e}")
            return False
    
    async def _create_default_project(self, project_path: Path) -> bool:
        """Create a default R project.
        
        Args:
            project_path: Path to the project directory
            
        Returns:
            True if successful
        """
        # Create .Rproj file
        rproj_content = """Version: 1.0

RestoreWorkspace: Default
SaveWorkspace: Default
AlwaysSaveHistory: Default

EnableCodeIndexing: Yes
UseSpacesForTab: Yes
NumSpacesForTab: 2
Encoding: UTF-8

RnwWeave: Sweave
LaTeX: pdfLaTeX
"""
        
        rproj_file = project_path / f"{project_path.name}.Rproj"
        rproj_file.write_text(rproj_content)
        
        # Create basic directory structure
        (project_path / "R").mkdir(exist_ok=True)
        (project_path / "data").mkdir(exist_ok=True)
        (project_path / "output").mkdir(exist_ok=True)
        
        # Create README
        readme_content = f"""# {project_path.name}

这是一个R项目。

## 目录结构

- `R/`: R脚本文件
- `data/`: 数据文件
- `output/`: 输出文件

## 使用方法

1. 在RStudio中打开项目文件 `{project_path.name}.Rproj`
2. 在 `R/` 目录中编写R脚本
3. 将数据文件放在 `data/` 目录中
4. 输出结果保存在 `output/` 目录中
"""
        
        (project_path / "README.md").write_text(readme_content)
        
        return True
    
    async def _create_package_project(self, project_path: Path, options: Dict[str, Any]) -> bool:
        """Create an R package project.
        
        Args:
            project_path: Path to the project directory
            options: Package creation options
            
        Returns:
            True if successful
        """
        package_name = project_path.name
        author = options.get("author", "Your Name")
        email = options.get("email", "your.email@example.com")
        license = options.get("license", "MIT")
        
        # Use R to create package structure
        r_code = f"""
        # Create package structure
        if (!require(usethis, quietly = TRUE)) {{
            install.packages("usethis")
        }}
        
        # Set working directory
        setwd("{project_path.parent}")
        
        # Create package
        usethis::create_package("{package_name}", 
                               fields = list(
                                   Author = "{author}",
                                   `Authors@R` = 'person("{author}", email = "{email}", role = c("aut", "cre"))',
                                   License = "{license}"
                               ),
                               rstudio = TRUE,
                               open = FALSE)
        """
        
        result = await self.api.execute_r_code(r_code, capture_plots=False)
        return result.success
    
    async def _create_shiny_project(self, project_path: Path, options: Dict[str, Any]) -> bool:
        """Create a Shiny application project.
        
        Args:
            project_path: Path to the project directory
            options: Shiny app options
            
        Returns:
            True if successful
        """
        app_type = options.get("app_type", "single_file")  # single_file or multi_file
        
        # Create .Rproj file
        rproj_content = """Version: 1.0

RestoreWorkspace: Default
SaveWorkspace: Default
AlwaysSaveHistory: Default

EnableCodeIndexing: Yes
UseSpacesForTab: Yes
NumSpacesForTab: 2
Encoding: UTF-8

RnwWeave: Sweave
LaTeX: pdfLaTeX

AutoAppendNewline: Yes
StripTrailingWhitespace: Yes
"""
        
        rproj_file = project_path / f"{project_path.name}.Rproj"
        rproj_file.write_text(rproj_content)
        
        if app_type == "single_file":
            # Create single-file Shiny app
            app_content = '''library(shiny)

# Define UI
ui <- fluidPage(
    titlePanel("Hello Shiny!"),
    
    sidebarLayout(
        sidebarPanel(
            sliderInput("obs", 
                       "Number of observations:",
                       min = 1, 
                       max = 1000, 
                       value = 500)
        ),
        
        mainPanel(
            plotOutput("distPlot")
        )
    )
)

# Define server logic
server <- function(input, output) {
    output$distPlot <- renderPlot({
        hist(rnorm(input$obs), 
             col = 'darkgray', 
             border = 'white',
             main = "Histogram of Random Normal Values")
    })
}

# Run the application
shinyApp(ui = ui, server = server)
'''
            (project_path / "app.R").write_text(app_content)
        
        else:  # multi_file
            # Create UI file
            ui_content = '''library(shiny)

# Define UI for application
fluidPage(
    titlePanel("Hello Shiny!"),
    
    sidebarLayout(
        sidebarPanel(
            sliderInput("obs", 
                       "Number of observations:",
                       min = 1, 
                       max = 1000, 
                       value = 500)
        ),
        
        mainPanel(
            plotOutput("distPlot")
        )
    )
)
'''
            (project_path / "ui.R").write_text(ui_content)
            
            # Create server file
            server_content = '''library(shiny)

# Define server logic
function(input, output) {
    output$distPlot <- renderPlot({
        hist(rnorm(input$obs), 
             col = 'darkgray', 
             border = 'white',
             main = "Histogram of Random Normal Values")
    })
}
'''
            (project_path / "server.R").write_text(server_content)
        
        # Create www directory for static files
        (project_path / "www").mkdir(exist_ok=True)
        
        return True
    
    async def _create_bookdown_project(self, project_path: Path) -> bool:
        """Create a bookdown project.
        
        Args:
            project_path: Path to the project directory
            
        Returns:
            True if successful
        """
        # Use R to create bookdown project
        r_code = f"""
        if (!require(bookdown, quietly = TRUE)) {{
            install.packages("bookdown")
        }}
        
        # Set working directory
        setwd("{project_path}")
        
        # Create bookdown files
        bookdown:::bookdown_skeleton(".")
        """
        
        result = await self.api.execute_r_code(r_code, capture_plots=False)
        return result.success
    
    async def _create_website_project(self, project_path: Path) -> bool:
        """Create a website project.
        
        Args:
            project_path: Path to the project directory
            
        Returns:
            True if successful
        """
        # Create basic website structure
        rproj_content = """Version: 1.0

RestoreWorkspace: No
SaveWorkspace: No
AlwaysSaveHistory: Default

EnableCodeIndexing: Yes
UseSpacesForTab: Yes
NumSpacesForTab: 2
Encoding: UTF-8

RnwWeave: Sweave
LaTeX: pdfLaTeX

BuildType: Website
"""
        
        rproj_file = project_path / f"{project_path.name}.Rproj"
        rproj_file.write_text(rproj_content)
        
        # Create _site.yml
        site_yml = f"""name: "{project_path.name}"
navbar:
  title: "{project_path.name}"
  left:
    - text: "Home"
      href: index.html
    - text: "About"
      href: about.html
output_dir: "_site"
"""
        (project_path / "_site.yml").write_text(site_yml)
        
        # Create index.Rmd
        index_content = f"""---
title: "{project_path.name}"
---

# Welcome to {project_path.name}

This is the homepage of your website.

```{{r setup, include=FALSE}}
knitr::opts_chunk$set(echo = TRUE)
```

## Getting Started

Edit this file to customize your homepage.
"""
        (project_path / "index.Rmd").write_text(index_content)
        
        # Create about.Rmd
        about_content = """---
title: "About"
---

## About This Site

This website was created using R Markdown and RStudio.
"""
        (project_path / "about.Rmd").write_text(about_content)
        
        return True
    
    async def _initialize_git(self, project_path: Path) -> bool:
        """Initialize Git repository in the project.
        
        Args:
            project_path: Path to the project directory
            
        Returns:
            True if successful
        """
        try:
            import subprocess
            
            # Initialize git repository
            subprocess.run(
                ["git", "init"], 
                cwd=project_path, 
                check=True, 
                capture_output=True
            )
            
            # Create .gitignore
            gitignore_content = """.Rproj.user
.Rhistory
.RData
.Ruserdata
*.Rproj
.DS_Store
Thumbs.db
"""
            (project_path / ".gitignore").write_text(gitignore_content)
            
            return True
            
        except Exception as e:
            self.logger.warning(f"Failed to initialize Git: {e}")
            return False
    
    async def _initialize_renv(self, project_path: Path) -> bool:
        """Initialize renv for the project.
        
        Args:
            project_path: Path to the project directory
            
        Returns:
            True if successful
        """
        try:
            r_code = f"""
            if (!require(renv, quietly = TRUE)) {{
                install.packages("renv")
            }}
            
            setwd("{project_path}")
            renv::init()
            """
            
            result = await self.api.execute_r_code(r_code, capture_plots=False)
            return result.success
            
        except Exception as e:
            self.logger.warning(f"Failed to initialize renv: {e}")
            return False


class OpenProjectTool(BaseTool):
    """Tool for opening RStudio projects."""
    
    def __init__(self, api_wrapper: Optional[RStudioAPIWrapper] = None):
        """Initialize the open project tool.
        
        Args:
            api_wrapper: RStudio API wrapper instance
        """
        super().__init__()
        self.api = api_wrapper or RStudioAPIWrapper()
    
    @property
    def name(self) -> str:
        return "open_project"
    
    @property
    def description(self) -> str:
        return "在RStudio中打开指定的项目"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="project_path",
                type="string",
                description="项目路径（.Rproj文件路径或项目目录路径）",
                required=True
            ),
            ToolParameter(
                name="new_session",
                type="boolean",
                description="是否在新会话中打开项目",
                required=False,
                default=False
            )
        ]
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the open project tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        try:
            project_path = arguments["project_path"]
            new_session = arguments.get("new_session", False)
            
            # Check if RStudio API is available
            if not await self.api.check_rstudio_available():
                return ToolResult(
                    success=False,
                    error="RStudio API不可用，请确保在RStudio环境中运行"
                )
            
            # Resolve project path
            resolved_path = await self._resolve_project_path(project_path)
            if not resolved_path:
                return ToolResult(
                    success=False,
                    error=f"找不到项目文件: {project_path}"
                )
            
            # Open project using RStudio API
            if new_session:
                r_code = f'rstudioapi::openProject("{resolved_path}", newSession = TRUE)'
            else:
                r_code = f'rstudioapi::openProject("{resolved_path}")'
            
            result = await self.api.execute_r_code(r_code, capture_plots=False)
            
            if result.success:
                tool_result = ToolResult(success=True)
                tool_result.add_text_content(f"成功打开项目: {resolved_path}")
                if new_session:
                    tool_result.add_text_content("项目在新会话中打开")
                
                tool_result.metadata = {
                    "project_path": resolved_path,
                    "new_session": new_session
                }
                
                return tool_result
            else:
                return ToolResult(
                    success=False,
                    error=f"打开项目失败: {result.error}"
                )
                
        except Exception as e:
            self.logger.error(f"Failed to open project: {e}")
            return ToolResult(
                success=False,
                error=f"打开项目失败: {str(e)}"
            )
    
    async def _resolve_project_path(self, project_path: str) -> Optional[str]:
        """Resolve project path to .Rproj file.
        
        Args:
            project_path: Input project path
            
        Returns:
            Resolved .Rproj file path or None if not found
        """
        path = Path(project_path)
        
        # If it's already a .Rproj file
        if path.suffix == ".Rproj" and path.exists():
            return str(path)
        
        # If it's a directory, look for .Rproj file
        if path.is_dir():
            rproj_files = list(path.glob("*.Rproj"))
            if rproj_files:
                return str(rproj_files[0])
        
        return None


class GetProjectInfoTool(BaseTool):
    """Tool for getting detailed project information."""
    
    def __init__(self, api_wrapper: Optional[RStudioAPIWrapper] = None):
        """Initialize the get project info tool.
        
        Args:
            api_wrapper: RStudio API wrapper instance
        """
        super().__init__()
        self.api = api_wrapper or RStudioAPIWrapper()
    
    @property
    def name(self) -> str:
        return "get_project_info"
    
    @property
    def description(self) -> str:
        return "获取RStudio项目的详细信息，包括文件结构、配置等"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="project_path",
                type="string",
                description="项目路径（可选，默认使用当前活动项目）",
                required=False
            ),
            ToolParameter(
                name="include_files",
                type="boolean",
                description="是否包含文件列表",
                required=False,
                default=True
            ),
            ToolParameter(
                name="include_git_info",
                type="boolean",
                description="是否包含Git信息",
                required=False,
                default=True
            ),
            ToolParameter(
                name="max_files",
                type="integer",
                description="最大文件数量限制",
                required=False,
                default=100
            )
        ]
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the get project info tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        try:
            project_path = arguments.get("project_path")
            include_files = arguments.get("include_files", True)
            include_git_info = arguments.get("include_git_info", True)
            max_files = arguments.get("max_files", 100)
            
            # Get project path
            if not project_path:
                project_path = await self.api.get_active_project()
                if not project_path:
                    return ToolResult(
                        success=False,
                        error="没有活动项目，请指定项目路径"
                    )
            
            # Validate project path
            project_dir = Path(project_path)
            if not project_dir.exists():
                return ToolResult(
                    success=False,
                    error=f"项目路径不存在: {project_path}"
                )
            
            # Collect project information
            project_info = await self._collect_project_info(
                project_dir, include_files, include_git_info, max_files
            )
            
            result = ToolResult(success=True)
            result.add_text_content("项目信息:")
            result.add_text_content(json.dumps(project_info, indent=2, ensure_ascii=False))
            
            result.metadata = project_info
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to get project info: {e}")
            return ToolResult(
                success=False,
                error=f"获取项目信息失败: {str(e)}"
            )
    
    async def _collect_project_info(
        self, 
        project_dir: Path, 
        include_files: bool,
        include_git_info: bool,
        max_files: int
    ) -> Dict[str, Any]:
        """Collect comprehensive project information.
        
        Args:
            project_dir: Project directory path
            include_files: Whether to include file listing
            include_git_info: Whether to include Git information
            max_files: Maximum number of files to list
            
        Returns:
            Project information dictionary
        """
        info = {
            "name": project_dir.name,
            "path": str(project_dir),
            "type": "unknown",
            "created": None,
            "modified": None,
            "size": 0,
            "rproj_file": None,
            "git_enabled": False,
            "renv_enabled": False,
            "description": None
        }
        
        try:
            # Find .Rproj file
            rproj_files = list(project_dir.glob("*.Rproj"))
            if rproj_files:
                rproj_file = rproj_files[0]
                info["rproj_file"] = str(rproj_file)
                info["created"] = rproj_file.stat().st_ctime
                info["modified"] = rproj_file.stat().st_mtime
                
                # Determine project type from .Rproj content
                info["type"] = await self._determine_project_type(rproj_file, project_dir)
            
            # Check for Git
            if (project_dir / ".git").exists():
                info["git_enabled"] = True
                if include_git_info:
                    info["git_info"] = await self._get_git_info(project_dir)
            
            # Check for renv
            if (project_dir / "renv.lock").exists():
                info["renv_enabled"] = True
                info["renv_info"] = await self._get_renv_info(project_dir)
            
            # Get project description
            readme_files = list(project_dir.glob("README*"))
            if readme_files:
                try:
                    content = readme_files[0].read_text(encoding='utf-8')
                    # Extract first paragraph as description
                    lines = content.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            info["description"] = line[:200]
                            break
                except Exception:
                    pass
            
            # Calculate total size
            total_size = 0
            file_count = 0
            
            if include_files:
                files = []
                for file_path in project_dir.rglob("*"):
                    if file_count >= max_files:
                        break
                    
                    if file_path.is_file():
                        try:
                            stat = file_path.stat()
                            relative_path = file_path.relative_to(project_dir)
                            
                            files.append({
                                "path": str(relative_path),
                                "size": stat.st_size,
                                "modified": stat.st_mtime,
                                "type": file_path.suffix or "file"
                            })
                            
                            total_size += stat.st_size
                            file_count += 1
                            
                        except Exception:
                            continue
                
                info["files"] = files
                info["file_count"] = file_count
                if file_count >= max_files:
                    info["files_truncated"] = True
            
            info["size"] = total_size
            
        except Exception as e:
            self.logger.warning(f"Error collecting project info: {e}")
        
        return info
    
    async def _determine_project_type(self, rproj_file: Path, project_dir: Path) -> str:
        """Determine project type from .Rproj file and directory structure.
        
        Args:
            rproj_file: Path to .Rproj file
            project_dir: Project directory path
            
        Returns:
            Project type string
        """
        try:
            # Read .Rproj file content
            content = rproj_file.read_text()
            
            # Check for specific build types
            if "BuildType: Package" in content:
                return "package"
            elif "BuildType: Website" in content:
                return "website"
            elif "BuildType: Makefile" in content:
                return "makefile"
            
            # Check directory structure for clues
            if (project_dir / "DESCRIPTION").exists():
                return "package"
            elif (project_dir / "app.R").exists() or (project_dir / "ui.R").exists():
                return "shiny"
            elif (project_dir / "_bookdown.yml").exists():
                return "bookdown"
            elif (project_dir / "_site.yml").exists():
                return "website"
            else:
                return "default"
                
        except Exception:
            return "unknown"
    
    async def _get_git_info(self, project_dir: Path) -> Dict[str, Any]:
        """Get Git repository information.
        
        Args:
            project_dir: Project directory path
            
        Returns:
            Git information dictionary
        """
        git_info = {}
        
        try:
            import subprocess
            
            # Get current branch
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=project_dir,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                git_info["current_branch"] = result.stdout.strip()
            
            # Get remote URL
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=project_dir,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                git_info["remote_url"] = result.stdout.strip()
            
            # Get status
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_dir,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                git_info["has_changes"] = bool(result.stdout.strip())
            
        except Exception as e:
            self.logger.warning(f"Failed to get Git info: {e}")
        
        return git_info
    
    async def _get_renv_info(self, project_dir: Path) -> Dict[str, Any]:
        """Get renv information.
        
        Args:
            project_dir: Project directory path
            
        Returns:
            renv information dictionary
        """
        renv_info = {}
        
        try:
            renv_lock = project_dir / "renv.lock"
            if renv_lock.exists():
                import json
                lock_data = json.loads(renv_lock.read_text())
                
                renv_info["renv_version"] = lock_data.get("renv", {}).get("Version")
                renv_info["r_version"] = lock_data.get("R", {}).get("Version")
                
                packages = lock_data.get("Packages", {})
                renv_info["package_count"] = len(packages)
                renv_info["packages"] = list(packages.keys())[:20]  # First 20 packages
                
        except Exception as e:
            self.logger.warning(f"Failed to get renv info: {e}")
        
        return renv_info