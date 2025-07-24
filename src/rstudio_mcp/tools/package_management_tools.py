"""Package management tools for RStudio MCP Server."""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from ..api_wrapper import RStudioAPIWrapper
from ..environment_manager import EnvironmentManager
from ..exceptions import PackageError, EnvironmentError
from .base import BaseTool, ToolParameter, ToolResult


class InstallPackageTool(BaseTool):
    """Tool for installing R packages with dependency resolution."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "install_package"

    @property
    def description(self) -> str:
        """Tool description."""
        return "在指定环境中安装R包，支持依赖解析和版本控制"

    @property
    def parameters(self) -> List[ToolParameter]:
        """Tool parameters."""
        return [
            ToolParameter(
                name="package",
                type="string",
                description="要安装的包名称",
                required=True
            ),
            ToolParameter(
                name="environment",
                type="string",
                description="目标环境名称（可选，默认使用当前活动环境）",
                required=False
            ),
            ToolParameter(
                name="version",
                type="string",
                description="指定包版本（可选）",
                required=False
            ),
            ToolParameter(
                name="repository",
                type="string",
                description="包仓库URL（可选，默认使用CRAN）",
                required=False
            ),
            ToolParameter(
                name="dependencies",
                type="boolean",
                description="是否安装依赖包",
                required=False,
                default=True
            ),
            ToolParameter(
                name="upgrade",
                type="boolean",
                description="是否升级已安装的依赖包",
                required=False,
                default=False
            ),
            ToolParameter(
                name="force_reinstall",
                type="boolean",
                description="强制重新安装（即使已安装）",
                required=False,
                default=False
            )
        ]

    def __init__(self, api_wrapper: RStudioAPIWrapper, environment_manager: EnvironmentManager):
        """Initialize the tool.
        
        Args:
            api_wrapper: RStudio API wrapper instance
            environment_manager: Environment manager instance
        """
        super().__init__()
        self.api = api_wrapper
        self.env_manager = environment_manager

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        try:
            package_name = arguments["package"]
            environment = arguments.get("environment")
            version = arguments.get("version")
            repository = arguments.get("repository")
            dependencies = arguments.get("dependencies", True)
            upgrade = arguments.get("upgrade", False)
            force_reinstall = arguments.get("force_reinstall", False)

            # Validate package name
            if not package_name or not package_name.strip():
                return ToolResult(
                    success=False,
                    error="包名称不能为空"
                )

            # Switch to target environment if specified
            if environment:
                env_exists = await self.env_manager.get_environment(environment)
                if not env_exists:
                    return ToolResult(
                        success=False,
                        error=f"环境 '{environment}' 不存在"
                    )
                
                switch_success = await self.env_manager.switch_environment(environment)
                if not switch_success:
                    return ToolResult(
                        success=False,
                        error=f"无法切换到环境 '{environment}'"
                    )

            # Check if package is already installed (unless force reinstall)
            if not force_reinstall:
                is_installed = await self._check_package_installed(package_name)
                if is_installed:
                    current_version = await self._get_package_version(package_name)
                    if version and current_version != version:
                        self.logger.info(f"Package {package_name} is installed with version {current_version}, but version {version} was requested")
                    else:
                        return ToolResult(
                            success=True,
                            content=[{
                                "type": "text",
                                "text": f"包 '{package_name}' 已安装 (版本: {current_version})"
                            }]
                        )

            # Build installation command
            install_code = self._build_install_command(
                package_name, version, repository, dependencies, upgrade
            )

            self.logger.info(f"Installing package '{package_name}' in environment '{environment or 'current'}'")
            
            # Execute installation
            result = await self.api.execute_r_code(
                code=install_code,
                capture_output=True,
                capture_plots=False,
                timeout=600  # Longer timeout for package installation
            )

            if result.success:
                # Verify installation
                is_installed = await self._check_package_installed(package_name)
                if is_installed:
                    installed_version = await self._get_package_version(package_name)
                    
                    tool_result = ToolResult(success=True)
                    tool_result.add_text_content(
                        f"✅ 成功安装包 '{package_name}'\n"
                        f"版本: {installed_version}\n"
                        f"环境: {environment or '当前环境'}"
                    )
                    
                    if result.output:
                        tool_result.add_text_content(f"安装日志:\n```\n{result.output}\n```")
                    
                    if result.warnings:
                        warnings_text = "\n".join(result.warnings)
                        tool_result.add_text_content(f"警告:\n{warnings_text}")
                    
                    # Get dependency information
                    deps = await self._get_package_dependencies(package_name)
                    if deps:
                        tool_result.add_text_content(f"依赖包: {', '.join(deps)}")
                    
                    return tool_result
                else:
                    return ToolResult(
                        success=False,
                        error=f"包安装命令执行成功，但无法验证包 '{package_name}' 是否正确安装"
                    )
            else:
                error_msg = f"包 '{package_name}' 安装失败"
                if result.error:
                    error_msg += f": {result.error}"
                
                tool_result = ToolResult(success=False, error=error_msg)
                if result.output:
                    tool_result.add_text_content(f"安装日志:\n```\n{result.output}\n```")
                
                return tool_result

        except EnvironmentError as e:
            return ToolResult(
                success=False,
                error=f"环境错误: {str(e)}"
            )
        except PackageError as e:
            return ToolResult(
                success=False,
                error=f"包管理错误: {str(e)}"
            )
        except Exception as e:
            self.logger.error("Unexpected error in install_package: %s", e, exc_info=True)
            return ToolResult(
                success=False,
                error=f"安装包时发生意外错误: {str(e)}"
            )

    def _build_install_command(
        self,
        package_name: str,
        version: Optional[str] = None,
        repository: Optional[str] = None,
        dependencies: bool = True,
        upgrade: bool = False
    ) -> str:
        """Build R package installation command.
        
        Args:
            package_name: Package name
            version: Specific version to install
            repository: Repository URL
            dependencies: Whether to install dependencies
            upgrade: Whether to upgrade dependencies
            
        Returns:
            R installation command
        """
        if version:
            # Install specific version using remotes package
            command = f"""
            if (!require(remotes, quietly = TRUE)) {{
                install.packages("remotes", repos = "https://cran.r-project.org/")
            }}
            remotes::install_version("{package_name}", version = "{version}", 
                                   dependencies = {str(dependencies).upper()}, 
                                   upgrade = "{('always' if upgrade else 'never')}")
            """
        else:
            # Standard installation
            repos = f'"{repository}"' if repository else '"https://cran.r-project.org/"'
            deps_arg = "TRUE" if dependencies else "FALSE"
            
            command = f"""
            install.packages("{package_name}", 
                           repos = {repos}, 
                           dependencies = {deps_arg})
            """
        
        return command.strip()

    async def _check_package_installed(self, package_name: str) -> bool:
        """Check if a package is installed.
        
        Args:
            package_name: Package name to check
            
        Returns:
            True if package is installed, False otherwise
        """
        try:
            code = f'"{package_name}" %in% rownames(installed.packages())'
            result = await self.api.execute_r_code(code, capture_output=True, capture_plots=False)
            
            if result.success and result.output:
                return "TRUE" in result.output.strip()
        except Exception as e:
            self.logger.warning(f"Failed to check if package {package_name} is installed: {e}")
        
        return False

    async def _get_package_version(self, package_name: str) -> str:
        """Get installed package version.
        
        Args:
            package_name: Package name
            
        Returns:
            Package version string
        """
        try:
            code = f'as.character(packageVersion("{package_name}"))'
            result = await self.api.execute_r_code(code, capture_output=True, capture_plots=False)
            
            if result.success and result.output:
                return result.output.strip().strip('"')
        except Exception as e:
            self.logger.warning(f"Failed to get version for package {package_name}: {e}")
        
        return "unknown"

    async def _get_package_dependencies(self, package_name: str) -> List[str]:
        """Get package dependencies.
        
        Args:
            package_name: Package name
            
        Returns:
            List of dependency package names
        """
        try:
            code = f"""
            pkg_info <- installed.packages()["{package_name}", ]
            deps <- pkg_info["Depends"]
            if (!is.na(deps)) {{
                # Parse dependencies (simplified)
                dep_list <- strsplit(deps, ",")[[1]]
                dep_names <- gsub("\\\\s*\\\\([^)]*\\\\)", "", dep_list)
                dep_names <- gsub("^\\\\s+|\\\\s+$", "", dep_names)
                dep_names[dep_names != "R"]
            }} else {{
                character(0)
            }}
            """
            
            result = await self.api.execute_r_code(code, capture_output=True, capture_plots=False)
            
            if result.success and result.output:
                # Parse the output to extract dependency names
                output = result.output.strip()
                if output and output != "character(0)":
                    # Simple parsing - this could be improved
                    deps = [dep.strip().strip('"') for dep in output.split() if dep.strip()]
                    return [dep for dep in deps if dep and dep != "character(0)"]
        except Exception as e:
            self.logger.warning(f"Failed to get dependencies for package {package_name}: {e}")
        
        return []


class UpdatePackageTool(BaseTool):
    """Tool for updating R packages."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "update_package"

    @property
    def description(self) -> str:
        """Tool description."""
        return "更新指定的R包到最新版本"

    @property
    def parameters(self) -> List[ToolParameter]:
        """Tool parameters."""
        return [
            ToolParameter(
                name="package",
                type="string",
                description="要更新的包名称（可选，不指定则更新所有包）",
                required=False
            ),
            ToolParameter(
                name="environment",
                type="string",
                description="目标环境名称（可选，默认使用当前活动环境）",
                required=False
            ),
            ToolParameter(
                name="repository",
                type="string",
                description="包仓库URL（可选，默认使用CRAN）",
                required=False
            ),
            ToolParameter(
                name="check_built",
                type="boolean",
                description="是否检查包是否需要重新构建",
                required=False,
                default=True
            )
        ]

    def __init__(self, api_wrapper: RStudioAPIWrapper, environment_manager: EnvironmentManager):
        """Initialize the tool.
        
        Args:
            api_wrapper: RStudio API wrapper instance
            environment_manager: Environment manager instance
        """
        super().__init__()
        self.api = api_wrapper
        self.env_manager = environment_manager

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        try:
            package_name = arguments.get("package")
            environment = arguments.get("environment")
            repository = arguments.get("repository")
            check_built = arguments.get("check_built", True)

            # Switch to target environment if specified
            if environment:
                env_exists = await self.env_manager.get_environment(environment)
                if not env_exists:
                    return ToolResult(
                        success=False,
                        error=f"环境 '{environment}' 不存在"
                    )
                
                switch_success = await self.env_manager.switch_environment(environment)
                if not switch_success:
                    return ToolResult(
                        success=False,
                        error=f"无法切换到环境 '{environment}'"
                    )

            # Build update command
            if package_name:
                # Update specific package
                if not await self._check_package_installed(package_name):
                    return ToolResult(
                        success=False,
                        error=f"包 '{package_name}' 未安装，无法更新"
                    )
                
                current_version = await self._get_package_version(package_name)
                update_code = self._build_update_command(package_name, repository, check_built)
            else:
                # Update all packages
                current_version = None
                update_code = self._build_update_all_command(repository, check_built)

            self.logger.info(f"Updating package(s) '{package_name or 'all'}' in environment '{environment or 'current'}'")
            
            # Execute update
            result = await self.api.execute_r_code(
                code=update_code,
                capture_output=True,
                capture_plots=False,
                timeout=900  # Longer timeout for package updates
            )

            if result.success:
                tool_result = ToolResult(success=True)
                
                if package_name:
                    # Check if specific package was updated
                    new_version = await self._get_package_version(package_name)
                    if new_version != current_version:
                        tool_result.add_text_content(
                            f"✅ 成功更新包 '{package_name}'\n"
                            f"旧版本: {current_version}\n"
                            f"新版本: {new_version}\n"
                            f"环境: {environment or '当前环境'}"
                        )
                    else:
                        tool_result.add_text_content(
                            f"📦 包 '{package_name}' 已是最新版本 ({current_version})"
                        )
                else:
                    tool_result.add_text_content(
                        f"✅ 包更新操作完成\n"
                        f"环境: {environment or '当前环境'}"
                    )
                
                if result.output:
                    tool_result.add_text_content(f"更新日志:\n```\n{result.output}\n```")
                
                if result.warnings:
                    warnings_text = "\n".join(result.warnings)
                    tool_result.add_text_content(f"警告:\n{warnings_text}")
                
                return tool_result
            else:
                error_msg = f"包更新失败"
                if result.error:
                    error_msg += f": {result.error}"
                
                tool_result = ToolResult(success=False, error=error_msg)
                if result.output:
                    tool_result.add_text_content(f"更新日志:\n```\n{result.output}\n```")
                
                return tool_result

        except EnvironmentError as e:
            return ToolResult(
                success=False,
                error=f"环境错误: {str(e)}"
            )
        except PackageError as e:
            return ToolResult(
                success=False,
                error=f"包管理错误: {str(e)}"
            )
        except Exception as e:
            self.logger.error("Unexpected error in update_package: %s", e, exc_info=True)
            return ToolResult(
                success=False,
                error=f"更新包时发生意外错误: {str(e)}"
            )

    def _build_update_command(
        self,
        package_name: str,
        repository: Optional[str] = None,
        check_built: bool = True
    ) -> str:
        """Build R package update command for specific package.
        
        Args:
            package_name: Package name to update
            repository: Repository URL
            check_built: Whether to check if package needs rebuilding
            
        Returns:
            R update command
        """
        repos = f'"{repository}"' if repository else '"https://cran.r-project.org/"'
        check_arg = "TRUE" if check_built else "FALSE"
        
        return f"""
        update.packages(oldPkgs = "{package_name}", 
                       repos = {repos}, 
                       checkBuilt = {check_arg},
                       ask = FALSE)
        """

    def _build_update_all_command(
        self,
        repository: Optional[str] = None,
        check_built: bool = True
    ) -> str:
        """Build R package update command for all packages.
        
        Args:
            repository: Repository URL
            check_built: Whether to check if packages need rebuilding
            
        Returns:
            R update command
        """
        repos = f'"{repository}"' if repository else '"https://cran.r-project.org/"'
        check_arg = "TRUE" if check_built else "FALSE"
        
        return f"""
        update.packages(repos = {repos}, 
                       checkBuilt = {check_arg},
                       ask = FALSE)
        """

    async def _check_package_installed(self, package_name: str) -> bool:
        """Check if a package is installed.
        
        Args:
            package_name: Package name to check
            
        Returns:
            True if package is installed, False otherwise
        """
        try:
            code = f'"{package_name}" %in% rownames(installed.packages())'
            result = await self.api.execute_r_code(code, capture_output=True, capture_plots=False)
            
            if result.success and result.output:
                return "TRUE" in result.output.strip()
        except Exception as e:
            self.logger.warning(f"Failed to check if package {package_name} is installed: {e}")
        
        return False

    async def _get_package_version(self, package_name: str) -> str:
        """Get installed package version.
        
        Args:
            package_name: Package name
            
        Returns:
            Package version string
        """
        try:
            code = f'as.character(packageVersion("{package_name}"))'
            result = await self.api.execute_r_code(code, capture_output=True, capture_plots=False)
            
            if result.success and result.output:
                return result.output.strip().strip('"')
        except Exception as e:
            self.logger.warning(f"Failed to get version for package {package_name}: {e}")
        
        return "unknown"


class UninstallPackageTool(BaseTool):
    """Tool for safely uninstalling R packages."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "uninstall_package"

    @property
    def description(self) -> str:
        """Tool description."""
        return "安全卸载R包，可选择是否移除未使用的依赖"

    @property
    def parameters(self) -> List[ToolParameter]:
        """Tool parameters."""
        return [
            ToolParameter(
                name="package",
                type="string",
                description="要卸载的包名称",
                required=True
            ),
            ToolParameter(
                name="environment",
                type="string",
                description="目标环境名称（可选，默认使用当前活动环境）",
                required=False
            ),
            ToolParameter(
                name="remove_dependencies",
                type="boolean",
                description="是否移除未使用的依赖包",
                required=False,
                default=False
            ),
            ToolParameter(
                name="force",
                type="boolean",
                description="强制卸载（忽略依赖检查）",
                required=False,
                default=False
            )
        ]

    def __init__(self, api_wrapper: RStudioAPIWrapper, environment_manager: EnvironmentManager):
        """Initialize the tool.
        
        Args:
            api_wrapper: RStudio API wrapper instance
            environment_manager: Environment manager instance
        """
        super().__init__()
        self.api = api_wrapper
        self.env_manager = environment_manager

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        try:
            package_name = arguments["package"]
            environment = arguments.get("environment")
            remove_dependencies = arguments.get("remove_dependencies", False)
            force = arguments.get("force", False)

            # Validate package name
            if not package_name or not package_name.strip():
                return ToolResult(
                    success=False,
                    error="包名称不能为空"
                )

            # Switch to target environment if specified
            if environment:
                env_exists = await self.env_manager.get_environment(environment)
                if not env_exists:
                    return ToolResult(
                        success=False,
                        error=f"环境 '{environment}' 不存在"
                    )
                
                switch_success = await self.env_manager.switch_environment(environment)
                if not switch_success:
                    return ToolResult(
                        success=False,
                        error=f"无法切换到环境 '{environment}'"
                    )

            # Check if package is installed
            if not await self._check_package_installed(package_name):
                return ToolResult(
                    success=False,
                    error=f"包 '{package_name}' 未安装"
                )

            # Get package information before removal
            package_version = await self._get_package_version(package_name)
            
            # Check for dependent packages if not forcing
            if not force:
                dependents = await self._get_dependent_packages(package_name)
                if dependents:
                    return ToolResult(
                        success=False,
                        error=f"无法卸载包 '{package_name}'，以下包依赖于它: {', '.join(dependents)}。使用 force=true 强制卸载"
                    )

            # Build uninstall command
            uninstall_code = self._build_uninstall_command(package_name)

            self.logger.info(f"Uninstalling package '{package_name}' from environment '{environment or 'current'}'")
            
            # Execute uninstall
            result = await self.api.execute_r_code(
                code=uninstall_code,
                capture_output=True,
                capture_plots=False,
                timeout=300
            )

            if result.success:
                # Verify uninstallation
                is_still_installed = await self._check_package_installed(package_name)
                if not is_still_installed:
                    tool_result = ToolResult(success=True)
                    tool_result.add_text_content(
                        f"✅ 成功卸载包 '{package_name}'\n"
                        f"版本: {package_version}\n"
                        f"环境: {environment or '当前环境'}"
                    )
                    
                    # Handle dependency removal if requested
                    if remove_dependencies:
                        removed_deps = await self._remove_unused_dependencies()
                        if removed_deps:
                            tool_result.add_text_content(f"同时移除未使用的依赖包: {', '.join(removed_deps)}")
                    
                    if result.output:
                        tool_result.add_text_content(f"卸载日志:\n```\n{result.output}\n```")
                    
                    return tool_result
                else:
                    return ToolResult(
                        success=False,
                        error=f"卸载命令执行成功，但包 '{package_name}' 仍然存在"
                    )
            else:
                error_msg = f"包 '{package_name}' 卸载失败"
                if result.error:
                    error_msg += f": {result.error}"
                
                tool_result = ToolResult(success=False, error=error_msg)
                if result.output:
                    tool_result.add_text_content(f"卸载日志:\n```\n{result.output}\n```")
                
                return tool_result

        except EnvironmentError as e:
            return ToolResult(
                success=False,
                error=f"环境错误: {str(e)}"
            )
        except PackageError as e:
            return ToolResult(
                success=False,
                error=f"包管理错误: {str(e)}"
            )
        except Exception as e:
            self.logger.error("Unexpected error in uninstall_package: %s", e, exc_info=True)
            return ToolResult(
                success=False,
                error=f"卸载包时发生意外错误: {str(e)}"
            )

    def _build_uninstall_command(self, package_name: str) -> str:
        """Build R package uninstall command.
        
        Args:
            package_name: Package name to uninstall
            
        Returns:
            R uninstall command
        """
        return f'remove.packages("{package_name}")'

    async def _check_package_installed(self, package_name: str) -> bool:
        """Check if a package is installed.
        
        Args:
            package_name: Package name to check
            
        Returns:
            True if package is installed, False otherwise
        """
        try:
            code = f'"{package_name}" %in% rownames(installed.packages())'
            result = await self.api.execute_r_code(code, capture_output=True, capture_plots=False)
            
            if result.success and result.output:
                return "TRUE" in result.output.strip()
        except Exception as e:
            self.logger.warning(f"Failed to check if package {package_name} is installed: {e}")
        
        return False

    async def _get_package_version(self, package_name: str) -> str:
        """Get installed package version.
        
        Args:
            package_name: Package name
            
        Returns:
            Package version string
        """
        try:
            code = f'as.character(packageVersion("{package_name}"))'
            result = await self.api.execute_r_code(code, capture_output=True, capture_plots=False)
            
            if result.success and result.output:
                return result.output.strip().strip('"')
        except Exception as e:
            self.logger.warning(f"Failed to get version for package {package_name}: {e}")
        
        return "unknown"

    async def _get_dependent_packages(self, package_name: str) -> List[str]:
        """Get packages that depend on the specified package.
        
        Args:
            package_name: Package name
            
        Returns:
            List of dependent package names
        """
        try:
            code = f"""
            # Get all installed packages
            installed_pkgs <- installed.packages()
            
            # Find packages that depend on the target package
            dependents <- character(0)
            for (pkg in rownames(installed_pkgs)) {{
                deps <- installed_pkgs[pkg, "Depends"]
                imports <- installed_pkgs[pkg, "Imports"]
                
                if (!is.na(deps) && grepl("{package_name}", deps)) {{
                    dependents <- c(dependents, pkg)
                }}
                if (!is.na(imports) && grepl("{package_name}", imports)) {{
                    dependents <- c(dependents, pkg)
                }}
            }}
            
            unique(dependents)
            """
            
            result = await self.api.execute_r_code(code, capture_output=True, capture_plots=False)
            
            if result.success and result.output:
                output = result.output.strip()
                if output and output != "character(0)":
                    # Parse the output to extract dependent package names
                    dependents = [dep.strip().strip('"') for dep in output.split() if dep.strip()]
                    return [dep for dep in dependents if dep and dep != "character(0)"]
        except Exception as e:
            self.logger.warning(f"Failed to get dependent packages for {package_name}: {e}")
        
        return []

    async def _remove_unused_dependencies(self) -> List[str]:
        """Remove unused dependency packages.
        
        Returns:
            List of removed package names
        """
        try:
            # This is a simplified implementation
            # In practice, this would require more sophisticated dependency analysis
            code = """
            # This is a placeholder for unused dependency removal
            # A real implementation would analyze the dependency graph
            character(0)
            """
            
            result = await self.api.execute_r_code(code, capture_output=True, capture_plots=False)
            
            if result.success and result.output:
                output = result.output.strip()
                if output and output != "character(0)":
                    return [dep.strip().strip('"') for dep in output.split() if dep.strip()]
        except Exception as e:
            self.logger.warning(f"Failed to remove unused dependencies: {e}")
        
        return []


class ListPackagesTool(BaseTool):
    """Tool for listing installed R packages with detailed information."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "list_packages"

    @property
    def description(self) -> str:
        """Tool description."""
        return "显示已安装R包的详细信息，包括版本、描述和依赖关系"

    @property
    def parameters(self) -> List[ToolParameter]:
        """Tool parameters."""
        return [
            ToolParameter(
                name="environment",
                type="string",
                description="目标环境名称（可选，默认使用当前活动环境）",
                required=False
            ),
            ToolParameter(
                name="pattern",
                type="string",
                description="包名称过滤模式（支持正则表达式）",
                required=False
            ),
            ToolParameter(
                name="include_dependencies",
                type="boolean",
                description="是否包含依赖信息",
                required=False,
                default=False
            ),
            ToolParameter(
                name="include_description",
                type="boolean",
                description="是否包含包描述",
                required=False,
                default=True
            ),
            ToolParameter(
                name="sort_by",
                type="string",
                description="排序方式",
                required=False,
                default="name",
                enum=["name", "version", "date"]
            ),
            ToolParameter(
                name="limit",
                type="number",
                description="返回结果数量限制",
                required=False
            )
        ]

    def __init__(self, api_wrapper: RStudioAPIWrapper, environment_manager: EnvironmentManager):
        """Initialize the tool.
        
        Args:
            api_wrapper: RStudio API wrapper instance
            environment_manager: Environment manager instance
        """
        super().__init__()
        self.api = api_wrapper
        self.env_manager = environment_manager

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        try:
            environment = arguments.get("environment")
            pattern = arguments.get("pattern")
            include_dependencies = arguments.get("include_dependencies", False)
            include_description = arguments.get("include_description", True)
            sort_by = arguments.get("sort_by", "name")
            limit = arguments.get("limit")

            # Switch to target environment if specified
            if environment:
                env_exists = await self.env_manager.get_environment(environment)
                if not env_exists:
                    return ToolResult(
                        success=False,
                        error=f"环境 '{environment}' 不存在"
                    )
                
                switch_success = await self.env_manager.switch_environment(environment)
                if not switch_success:
                    return ToolResult(
                        success=False,
                        error=f"无法切换到环境 '{environment}'"
                    )

            # Get package list
            packages = await self._get_package_list(
                pattern, include_dependencies, include_description, sort_by, limit
            )

            if not packages:
                result = ToolResult(success=True)
                result.add_text_content(
                    f"在环境 '{environment or '当前环境'}' 中未找到匹配的包"
                )
                return result

            # Format package list
            formatted_list = self._format_package_list(
                packages, include_dependencies, include_description
            )

            result = ToolResult(success=True)
            result.add_text_content(
                f"📦 环境 '{environment or '当前环境'}' 中的已安装包 (共 {len(packages)} 个):\n\n"
                + formatted_list
            )

            return result

        except EnvironmentError as e:
            return ToolResult(
                success=False,
                error=f"环境错误: {str(e)}"
            )
        except Exception as e:
            self.logger.error("Unexpected error in list_packages: %s", e, exc_info=True)
            return ToolResult(
                success=False,
                error=f"列出包信息时发生意外错误: {str(e)}"
            )

    async def _get_package_list(
        self,
        pattern: Optional[str] = None,
        include_dependencies: bool = False,
        include_description: bool = True,
        sort_by: str = "name",
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get list of installed packages with information.
        
        Args:
            pattern: Package name filter pattern
            include_dependencies: Whether to include dependency info
            include_description: Whether to include description
            sort_by: Sort order
            limit: Result limit
            
        Returns:
            List of package information dictionaries
        """
        try:
            # Build R code to get package information
            code = f"""
            installed_pkgs <- installed.packages()
            
            # Create package info data frame
            pkg_info <- data.frame(
                name = installed_pkgs[, "Package"],
                version = installed_pkgs[, "Version"],
                description = installed_pkgs[, "Title"],
                built = installed_pkgs[, "Built"],
                stringsAsFactors = FALSE
            )
            
            # Apply pattern filter if specified
            {f'pkg_info <- pkg_info[grepl("{pattern}", pkg_info$name, ignore.case = TRUE), ]' if pattern else ''}
            
            # Sort packages
            {self._get_sort_code(sort_by)}
            
            # Apply limit if specified
            {f'pkg_info <- head(pkg_info, {limit})' if limit else ''}
            
            # Convert to JSON
            jsonlite::toJSON(pkg_info, pretty = TRUE)
            """

            result = await self.api.execute_r_code(code, capture_output=True, capture_plots=False)
            
            if result.success and result.output:
                packages = json.loads(result.output)
                
                # Add dependency information if requested
                if include_dependencies:
                    for pkg in packages:
                        pkg["dependencies"] = await self._get_package_dependencies(pkg["name"])
                
                return packages
        except Exception as e:
            self.logger.error(f"Failed to get package list: {e}")
        
        return []

    def _get_sort_code(self, sort_by: str) -> str:
        """Get R code for sorting packages.
        
        Args:
            sort_by: Sort field
            
        Returns:
            R sorting code
        """
        if sort_by == "version":
            return "pkg_info <- pkg_info[order(pkg_info$version), ]"
        elif sort_by == "date":
            return "pkg_info <- pkg_info[order(pkg_info$built, decreasing = TRUE), ]"
        else:  # name
            return "pkg_info <- pkg_info[order(pkg_info$name), ]"

    async def _get_package_dependencies(self, package_name: str) -> List[str]:
        """Get package dependencies.
        
        Args:
            package_name: Package name
            
        Returns:
            List of dependency package names
        """
        try:
            code = f"""
            pkg_info <- installed.packages()["{package_name}", ]
            deps <- pkg_info["Depends"]
            imports <- pkg_info["Imports"]
            
            all_deps <- character(0)
            
            if (!is.na(deps)) {{
                dep_list <- strsplit(deps, ",")[[1]]
                dep_names <- gsub("\\\\s*\\\\([^)]*\\\\)", "", dep_list)
                dep_names <- gsub("^\\\\s+|\\\\s+$", "", dep_names)
                all_deps <- c(all_deps, dep_names[dep_names != "R"])
            }}
            
            if (!is.na(imports)) {{
                import_list <- strsplit(imports, ",")[[1]]
                import_names <- gsub("\\\\s*\\\\([^)]*\\\\)", "", import_list)
                import_names <- gsub("^\\\\s+|\\\\s+$", "", import_names)
                all_deps <- c(all_deps, import_names[import_names != "R"])
            }}
            
            unique(all_deps[all_deps != ""])
            """
            
            result = await self.api.execute_r_code(code, capture_output=True, capture_plots=False)
            
            if result.success and result.output:
                output = result.output.strip()
                if output and output != "character(0)":
                    deps = [dep.strip().strip('"') for dep in output.split() if dep.strip()]
                    return [dep for dep in deps if dep and dep != "character(0)"]
        except Exception as e:
            self.logger.warning(f"Failed to get dependencies for package {package_name}: {e}")
        
        return []

    def _format_package_list(
        self,
        packages: List[Dict[str, Any]],
        include_dependencies: bool,
        include_description: bool
    ) -> str:
        """Format package list for display.
        
        Args:
            packages: List of package information
            include_dependencies: Whether to include dependencies
            include_description: Whether to include description
            
        Returns:
            Formatted package list string
        """
        lines = []
        
        for i, pkg in enumerate(packages, 1):
            name = pkg.get("name", "unknown")
            version = pkg.get("version", "unknown")
            
            line = f"{i:3d}. {name} ({version})"
            
            if include_description and pkg.get("description"):
                line += f"\n     {pkg['description']}"
            
            if include_dependencies and pkg.get("dependencies"):
                deps = pkg["dependencies"]
                if deps:
                    line += f"\n     依赖: {', '.join(deps[:5])}"
                    if len(deps) > 5:
                        line += f" (+{len(deps) - 5} more)"
            
            lines.append(line)
        
        return "\n\n".join(lines)