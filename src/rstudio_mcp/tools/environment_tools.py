"""Environment management tools for RStudio MCP Server."""

import logging
from typing import Any, Dict, List

from ..environment_manager import EnvironmentManager, EnvironmentConfig
from ..exceptions import EnvironmentError
from .base import BaseTool, ToolParameter, ToolResult


class CreateEnvironmentTool(BaseTool):
    """Tool for creating new R environments."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "create_environment"

    @property
    def description(self) -> str:
        """Tool description."""
        return "在RStudio中创建新的R环境"

    @property
    def parameters(self) -> List[ToolParameter]:
        """Tool parameters."""
        return [
            ToolParameter(
                name="name",
                type="string",
                description="环境名称",
                required=True
            ),
            ToolParameter(
                name="r_version",
                type="string",
                description="R版本，如4.3.0",
                required=False
            ),
            ToolParameter(
                name="description",
                type="string",
                description="环境描述",
                required=False
            ),
            ToolParameter(
                name="packages",
                type="array",
                description="预安装包列表",
                required=False,
                items={"type": "string"}
            ),
            ToolParameter(
                name="copy_from",
                type="string",
                description="从现有环境复制",
                required=False
            )
        ]

    def __init__(self, environment_manager: EnvironmentManager):
        """Initialize the tool.
        
        Args:
            environment_manager: Environment manager instance
        """
        super().__init__()
        self.env_manager = environment_manager

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        try:
            # Create environment configuration
            config = EnvironmentConfig(
                name=arguments["name"],
                r_version=arguments.get("r_version"),
                description=arguments.get("description"),
                packages=arguments.get("packages", []),
                copy_from=arguments.get("copy_from")
            )

            # Create environment
            environment = await self.env_manager.create_environment(config)

            result = ToolResult(success=True)
            result.add_text_content(
                f"成功创建环境 '{environment.name}'\n"
                f"R版本: {environment.r_version}\n"
                f"路径: {environment.path}\n"
                f"创建时间: {environment.created_at.isoformat()}"
            )

            if environment.packages:
                result.add_text_content(f"已安装包: {', '.join(environment.packages)}")

            return result

        except EnvironmentError as e:
            return ToolResult(
                success=False,
                error=f"环境创建失败: {str(e)}"
            )
        except Exception as e:
            self.logger.error("Unexpected error in create_environment: %s", e, exc_info=True)
            return ToolResult(
                success=False,
                error=f"创建环境时发生意外错误: {str(e)}"
            )


class ListEnvironmentsTool(BaseTool):
    """Tool for listing available R environments."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "list_environments"

    @property
    def description(self) -> str:
        """Tool description."""
        return "列出所有可用的R环境"

    @property
    def parameters(self) -> List[ToolParameter]:
        """Tool parameters."""
        return [
            ToolParameter(
                name="include_status",
                type="boolean",
                description="是否包含环境状态信息",
                required=False,
                default=True
            )
        ]

    def __init__(self, environment_manager: EnvironmentManager):
        """Initialize the tool.
        
        Args:
            environment_manager: Environment manager instance
        """
        super().__init__()
        self.env_manager = environment_manager

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        try:
            environments = await self.env_manager.list_environments()
            include_status = arguments.get("include_status", True)

            if not environments:
                result = ToolResult(success=True)
                result.add_text_content("未找到任何R环境")
                return result

            result = ToolResult(success=True)
            
            # Create environment list text
            env_list = []
            for env in environments:
                status_indicator = "●" if env.is_active else "○"
                env_info = f"{status_indicator} {env.name} (R {env.r_version})"
                
                if include_status:
                    status = await self.env_manager.get_environment_status(env.name)
                    if status:
                        env_info += f" - {status.package_count} 个包, 状态: {status.health_status}"
                
                if env.description:
                    env_info += f"\n  描述: {env.description}"
                
                env_list.append(env_info)

            result.add_text_content(
                f"找到 {len(environments)} 个R环境:\n\n" + 
                "\n".join(env_list) +
                "\n\n● = 活动环境, ○ = 非活动环境"
            )

            return result

        except Exception as e:
            self.logger.error("Unexpected error in list_environments: %s", e, exc_info=True)
            return ToolResult(
                success=False,
                error=f"列出环境时发生错误: {str(e)}"
            )


class SwitchEnvironmentTool(BaseTool):
    """Tool for switching between R environments."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "switch_environment"

    @property
    def description(self) -> str:
        """Tool description."""
        return "切换到指定的R环境"

    @property
    def parameters(self) -> List[ToolParameter]:
        """Tool parameters."""
        return [
            ToolParameter(
                name="name",
                type="string",
                description="要切换到的环境名称",
                required=True
            )
        ]

    def __init__(self, environment_manager: EnvironmentManager):
        """Initialize the tool.
        
        Args:
            environment_manager: Environment manager instance
        """
        super().__init__()
        self.env_manager = environment_manager

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        try:
            env_name = arguments["name"]
            
            # Check if environment exists
            environment = await self.env_manager.get_environment(env_name)
            if not environment:
                return ToolResult(
                    success=False,
                    error=f"环境 '{env_name}' 不存在"
                )

            # Switch to environment
            success = await self.env_manager.switch_environment(env_name)
            
            if success:
                result = ToolResult(success=True)
                result.add_text_content(
                    f"成功切换到环境 '{env_name}'\n"
                    f"R版本: {environment.r_version}\n"
                    f"路径: {environment.path}"
                )
                
                if environment.packages:
                    result.add_text_content(f"可用包: {', '.join(environment.packages)}")
                
                return result
            else:
                return ToolResult(
                    success=False,
                    error=f"切换到环境 '{env_name}' 失败"
                )

        except EnvironmentError as e:
            return ToolResult(
                success=False,
                error=f"环境切换失败: {str(e)}"
            )
        except Exception as e:
            self.logger.error("Unexpected error in switch_environment: %s", e, exc_info=True)
            return ToolResult(
                success=False,
                error=f"切换环境时发生意外错误: {str(e)}"
            )


class DeleteEnvironmentTool(BaseTool):
    """Tool for safely deleting R environments."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "delete_environment"

    @property
    def description(self) -> str:
        """Tool description."""
        return "安全删除指定的R环境"

    @property
    def parameters(self) -> List[ToolParameter]:
        """Tool parameters."""
        return [
            ToolParameter(
                name="name",
                type="string",
                description="要删除的环境名称",
                required=True
            ),
            ToolParameter(
                name="force",
                type="boolean",
                description="强制删除（即使环境处于活动状态）",
                required=False,
                default=False
            )
        ]

    def __init__(self, environment_manager: EnvironmentManager):
        """Initialize the tool.
        
        Args:
            environment_manager: Environment manager instance
        """
        super().__init__()
        self.env_manager = environment_manager

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        try:
            env_name = arguments["name"]
            force = arguments.get("force", False)
            
            # Check if environment exists
            environment = await self.env_manager.get_environment(env_name)
            if not environment:
                return ToolResult(
                    success=False,
                    error=f"环境 '{env_name}' 不存在"
                )

            # Warn if trying to delete active environment without force
            if environment.is_active and not force:
                return ToolResult(
                    success=False,
                    error=f"无法删除活动环境 '{env_name}'。请先切换到其他环境或使用 force=true 强制删除"
                )

            # Delete environment
            success = await self.env_manager.delete_environment(env_name, force=force)
            
            if success:
                result = ToolResult(success=True)
                result.add_text_content(
                    f"成功删除环境 '{env_name}'\n"
                    f"已删除路径: {environment.path}"
                )
                return result
            else:
                return ToolResult(
                    success=False,
                    error=f"删除环境 '{env_name}' 失败"
                )

        except EnvironmentError as e:
            return ToolResult(
                success=False,
                error=f"环境删除失败: {str(e)}"
            )
        except Exception as e:
            self.logger.error("Unexpected error in delete_environment: %s", e, exc_info=True)
            return ToolResult(
                success=False,
                error=f"删除环境时发生意外错误: {str(e)}"
            )