"""Project resource handler for RStudio MCP Server."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..api_wrapper import RStudioAPIWrapper
from .base import BaseResource, ResourceInfo, ResourceResult


class ProjectResource(BaseResource):
    """Resource handler for RStudio projects."""
    
    def __init__(self, api_wrapper: Optional[RStudioAPIWrapper] = None):
        """Initialize the project resource handler.
        
        Args:
            api_wrapper: Optional RStudio API wrapper instance
        """
        super().__init__()
        self.api_wrapper = api_wrapper
    
    @property
    def scheme(self) -> str:
        """URI scheme handled by this resource."""
        return "rstudio-project"
    
    @property
    def description(self) -> str:
        """Resource handler description."""
        return "RStudio project files and configuration access"
    
    async def list_resources(self, uri_prefix: Optional[str] = None) -> List[ResourceInfo]:
        """List available project resources.
        
        Args:
            uri_prefix: Optional URI prefix to filter resources
            
        Returns:
            List of available project resources
        """
        resources = []
        
        try:
            # Get active project if API wrapper is available
            active_project = None
            if self.api_wrapper:
                active_project = await self.api_wrapper.get_active_project()
            
            if active_project and os.path.exists(active_project):
                project_path = Path(active_project)
                project_name = project_path.name
                
                # Main project resource
                resources.append(ResourceInfo(
                    uri=f"rstudio-project://{active_project}",
                    name=f"Project: {project_name}",
                    description=f"RStudio project configuration and information",
                    mime_type="application/json",
                    metadata={
                        "project_path": active_project,
                        "project_name": project_name
                    }
                ))
                
                # Project files
                try:
                    for file_path in self._get_project_files(project_path):
                        relative_path = file_path.relative_to(project_path)
                        file_uri = f"rstudio-project://{active_project}/files/{relative_path}"
                        
                        # Determine MIME type based on file extension
                        mime_type = self._get_mime_type(file_path)
                        
                        resources.append(ResourceInfo(
                            uri=file_uri,
                            name=f"File: {relative_path}",
                            description=f"Project file: {relative_path}",
                            mime_type=mime_type,
                            size=file_path.stat().st_size if file_path.exists() else None,
                            metadata={
                                "project_path": active_project,
                                "file_path": str(file_path),
                                "relative_path": str(relative_path)
                            }
                        ))
                except Exception as e:
                    self.logger.warning(f"Failed to list project files: {e}")
            
            # If no active project, try to find common project locations
            if not resources:
                resources.extend(await self._discover_projects())
        
        except Exception as e:
            self.logger.error(f"Error listing project resources: {e}")
        
        return resources
    
    async def read_resource(self, uri: str) -> ResourceResult:
        """Read project resource content.
        
        Args:
            uri: Resource URI
            
        Returns:
            Resource content and metadata
        """
        try:
            uri_parts = self.parse_uri(uri)
            full_path = uri_parts["path"]
            
            if not full_path:
                return self.create_error_result("Invalid project URI: missing project path")
            
            # Check if this is a file resource (contains /files/)
            if "/files/" in full_path:
                # Split at /files/ to separate project path from file path
                parts = full_path.split("/files/", 1)
                if len(parts) == 2:
                    project_path = parts[0]
                    file_path = parts[1]
                    return await self._read_project_file(project_path, file_path)
                else:
                    return self.create_error_result(f"Invalid file URI format: {uri}")
            else:
                # Main project resource - return project information
                project_path = full_path
                return await self._read_project_info(project_path)
        
        except Exception as e:
            return self.create_error_result(f"Error reading project resource: {str(e)}")
    
    async def _read_project_info(self, project_path: str) -> ResourceResult:
        """Read project information.
        
        Args:
            project_path: Path to the project
            
        Returns:
            Project information as JSON
        """
        try:
            if not os.path.exists(project_path):
                return self.create_error_result(f"Project path does not exist: {project_path}")
            
            project_path_obj = Path(project_path)
            project_info = {
                "name": project_path_obj.name,
                "path": project_path,
                "type": "unknown",
                "files": [],
                "git_enabled": False,
                "r_version": "unknown"
            }
            
            # Check for project type indicators
            if (project_path_obj / "DESCRIPTION").exists():
                project_info["type"] = "package"
            elif (project_path_obj / "app.R").exists() or (project_path_obj / "ui.R").exists():
                project_info["type"] = "shiny"
            elif (project_path_obj / f"{project_path_obj.name}.Rproj").exists():
                project_info["type"] = "default"
            
            # Check for Git
            if (project_path_obj / ".git").exists():
                project_info["git_enabled"] = True
            
            # Get file list
            try:
                project_files = []
                for file_path in self._get_project_files(project_path_obj, max_files=50):
                    relative_path = file_path.relative_to(project_path_obj)
                    project_files.append({
                        "path": str(relative_path),
                        "size": file_path.stat().st_size if file_path.exists() else 0,
                        "type": "file" if file_path.is_file() else "directory"
                    })
                project_info["files"] = project_files
            except Exception as e:
                self.logger.warning(f"Failed to get project files: {e}")
            
            # Get R version if API wrapper is available
            if self.api_wrapper:
                try:
                    project_info["r_version"] = await self.api_wrapper.get_r_version()
                except Exception as e:
                    self.logger.warning(f"Failed to get R version: {e}")
            
            return self.create_json_result(project_info)
        
        except Exception as e:
            return self.create_error_result(f"Error reading project info: {str(e)}")
    
    async def _read_project_file(self, project_path: str, file_path: str) -> ResourceResult:
        """Read a project file.
        
        Args:
            project_path: Path to the project
            file_path: Relative path to the file within the project
            
        Returns:
            File content
        """
        try:
            full_file_path = Path(project_path) / file_path
            
            # Check if file is within project directory (security check)
            # Do this before checking existence to prevent path traversal attacks
            try:
                full_file_path.resolve().relative_to(Path(project_path).resolve())
            except ValueError:
                return self.create_error_result(f"File is outside project directory: {file_path}")
            
            if not full_file_path.exists():
                return self.create_error_result(f"File does not exist: {file_path}")
            
            if not full_file_path.is_file():
                return self.create_error_result(f"Path is not a file: {file_path}")
            
            # Determine MIME type
            mime_type = self._get_mime_type(full_file_path)
            
            # Read file content
            if mime_type.startswith("text/") or mime_type == "application/json":
                # Read as text
                try:
                    with open(full_file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    return self.create_text_result(content, mime_type)
                except UnicodeDecodeError:
                    # Fallback to binary if text reading fails
                    with open(full_file_path, 'rb') as f:
                        content = f.read()
                    return self.create_binary_result(content, "application/octet-stream")
            else:
                # Read as binary
                with open(full_file_path, 'rb') as f:
                    content = f.read()
                return self.create_binary_result(content, mime_type)
        
        except Exception as e:
            return self.create_error_result(f"Error reading project file: {str(e)}")
    
    def _get_project_files(self, project_path: Path, max_files: int = 100) -> List[Path]:
        """Get list of files in the project.
        
        Args:
            project_path: Path to the project
            max_files: Maximum number of files to return
            
        Returns:
            List of file paths
        """
        files = []
        
        # Common file patterns to include
        include_patterns = [
            "*.R", "*.Rmd", "*.r", "*.rmd",
            "*.py", "*.sql", "*.yaml", "*.yml", "*.json",
            "*.txt", "*.md", "*.csv", "*.tsv",
            "DESCRIPTION", "NAMESPACE", "*.Rproj"
        ]
        
        # Directories to exclude
        exclude_dirs = {
            ".git", ".Rproj.user", "__pycache__", ".pytest_cache",
            "node_modules", ".venv", "venv", "env"
        }
        
        try:
            for root, dirs, filenames in os.walk(project_path):
                # Filter out excluded directories
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                
                root_path = Path(root)
                
                for filename in filenames:
                    file_path = root_path / filename
                    
                    # Check if file matches include patterns
                    if any(file_path.match(pattern) for pattern in include_patterns):
                        files.append(file_path)
                        
                        if len(files) >= max_files:
                            break
                
                if len(files) >= max_files:
                    break
        
        except Exception as e:
            self.logger.warning(f"Error walking project directory: {e}")
        
        return files
    
    def _get_mime_type(self, file_path: Path) -> str:
        """Get MIME type for a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            MIME type string
        """
        suffix = file_path.suffix.lower()
        
        mime_types = {
            ".r": "text/x-r",
            ".rmd": "text/x-r-markdown",
            ".py": "text/x-python",
            ".sql": "text/x-sql",
            ".json": "application/json",
            ".yaml": "text/x-yaml",
            ".yml": "text/x-yaml",
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".csv": "text/csv",
            ".tsv": "text/tab-separated-values",
            ".html": "text/html",
            ".xml": "text/xml",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".pdf": "application/pdf"
        }
        
        return mime_types.get(suffix, "text/plain")
    
    async def _discover_projects(self) -> List[ResourceInfo]:
        """Discover RStudio projects in common locations.
        
        Returns:
            List of discovered project resources
        """
        resources = []
        
        # Common project locations
        search_paths = [
            Path.home() / "Documents",
            Path.home() / "Projects",
            Path.home() / "RStudio",
            Path.cwd()
        ]
        
        for search_path in search_paths:
            if search_path.exists() and search_path.is_dir():
                try:
                    for item in search_path.iterdir():
                        if item.is_dir() and self._is_rstudio_project(item):
                            resources.append(ResourceInfo(
                                uri=f"rstudio-project://{item}",
                                name=f"Project: {item.name}",
                                description=f"RStudio project at {item}",
                                mime_type="application/json",
                                metadata={
                                    "project_path": str(item),
                                    "project_name": item.name,
                                    "discovered": True
                                }
                            ))
                except Exception as e:
                    self.logger.warning(f"Error searching for projects in {search_path}: {e}")
        
        return resources
    
    def _is_rstudio_project(self, path: Path) -> bool:
        """Check if a directory is an RStudio project.
        
        Args:
            path: Directory path to check
            
        Returns:
            True if directory appears to be an RStudio project
        """
        # Check for .Rproj file
        for item in path.glob("*.Rproj"):
            if item.is_file():
                return True
        
        # Check for common R project indicators
        indicators = ["DESCRIPTION", "app.R", "ui.R", "server.R"]
        for indicator in indicators:
            if (path / indicator).exists():
                return True
        
        # Check for R files
        r_files = list(path.glob("*.R")) + list(path.glob("*.r"))
        if len(r_files) > 0:
            return True
        
        return False