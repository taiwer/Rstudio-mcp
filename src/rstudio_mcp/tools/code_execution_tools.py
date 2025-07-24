"""Code execution tools for RStudio MCP Server."""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..api_wrapper import RStudioAPIWrapper, ExecutionResult
from ..environment_manager import EnvironmentManager
from ..exceptions import ExecutionError, EnvironmentError
from .base import BaseTool, ToolParameter, ToolResult


class ExecutionHistory:
    """Manages code execution history."""
    
    def __init__(self, max_entries: int = 1000):
        """Initialize execution history.
        
        Args:
            max_entries: Maximum number of history entries to keep
        """
        self.max_entries = max_entries
        self.entries: List[Dict[str, Any]] = []
        self.logger = logging.getLogger(__name__)
    
    def add_entry(self, code: str, result: ExecutionResult, environment: str = "default") -> str:
        """Add execution entry to history.
        
        Args:
            code: Executed R code
            result: Execution result
            environment: Environment name
            
        Returns:
            Entry ID
        """
        entry_id = f"exec_{int(time.time() * 1000)}"
        
        entry = {
            "id": entry_id,
            "timestamp": datetime.now().isoformat(),
            "code": code,
            "environment": environment,
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "execution_time": result.execution_time,
            "plots": result.plots,
            "warnings": result.warnings
        }
        
        self.entries.append(entry)
        
        # Trim history if needed
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]
        
        return entry_id
    
    def get_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """Get execution entry by ID.
        
        Args:
            entry_id: Entry ID
            
        Returns:
            Entry data or None if not found
        """
        for entry in self.entries:
            if entry["id"] == entry_id:
                return entry
        return None
    
    def get_recent_entries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent execution entries.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of recent entries
        """
        return self.entries[-limit:] if self.entries else []
    
    def clear_history(self) -> int:
        """Clear execution history.
        
        Returns:
            Number of entries cleared
        """
        count = len(self.entries)
        self.entries.clear()
        return count


class ExecuteRCodeTool(BaseTool):
    """Tool for executing R code in specified environments."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "execute_r_code"

    @property
    def description(self) -> str:
        """Tool description."""
        return "在指定R环境中执行R代码，支持结果捕获和格式化"

    @property
    def parameters(self) -> List[ToolParameter]:
        """Tool parameters."""
        return [
            ToolParameter(
                name="code",
                type="string",
                description="要执行的R代码",
                required=True
            ),
            ToolParameter(
                name="environment",
                type="string",
                description="目标环境名称（可选，默认使用当前活动环境）",
                required=False
            ),
            ToolParameter(
                name="capture_output",
                type="boolean",
                description="是否捕获输出",
                required=False,
                default=True
            ),
            ToolParameter(
                name="capture_plots",
                type="boolean",
                description="是否捕获生成的图表",
                required=False,
                default=True
            ),
            ToolParameter(
                name="timeout",
                type="number",
                description="执行超时时间（秒）",
                required=False,
                default=300
            ),
            ToolParameter(
                name="save_to_history",
                type="boolean",
                description="是否保存到执行历史",
                required=False,
                default=True
            ),
            ToolParameter(
                name="format_output",
                type="boolean",
                description="是否格式化输出结果",
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
        self.history = ExecutionHistory()

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        try:
            code = arguments["code"]
            environment = arguments.get("environment")
            capture_output = arguments.get("capture_output", True)
            capture_plots = arguments.get("capture_plots", True)
            timeout = arguments.get("timeout", 300)
            save_to_history = arguments.get("save_to_history", True)
            format_output = arguments.get("format_output", True)

            # Validate code
            if not code or not code.strip():
                return ToolResult(
                    success=False,
                    error="代码不能为空"
                )

            # Switch to target environment if specified
            if environment:
                env_exists = await self.env_manager.get_environment(environment)
                if not env_exists:
                    return ToolResult(
                        success=False,
                        error=f"环境 '{environment}' 不存在"
                    )
                
                # Switch to the environment
                switch_success = await self.env_manager.switch_environment(environment)
                if not switch_success:
                    return ToolResult(
                        success=False,
                        error=f"无法切换到环境 '{environment}'"
                    )

            # Execute R code
            self.logger.info(f"Executing R code in environment '{environment or 'current'}'")
            
            execution_result = await self.api.execute_r_code(
                code=code,
                capture_output=capture_output,
                capture_plots=capture_plots,
                timeout=timeout
            )

            # Save to history if requested
            entry_id = None
            if save_to_history:
                entry_id = self.history.add_entry(
                    code=code,
                    result=execution_result,
                    environment=environment or "current"
                )

            # Format result
            result = ToolResult(success=execution_result.success)
            
            if execution_result.success:
                # Add execution summary
                summary = self._format_execution_summary(
                    execution_result, environment, entry_id, format_output
                )
                result.add_text_content(summary)
                
                # Add output if available
                if execution_result.output and format_output:
                    formatted_output = self._format_output(execution_result.output)
                    result.add_text_content(f"输出:\n{formatted_output}")
                elif execution_result.output:
                    result.add_text_content(f"输出:\n{execution_result.output}")
                
                # Add plots if available
                if execution_result.plots:
                    for plot_path in execution_result.plots:
                        try:
                            with open(plot_path, 'rb') as f:
                                plot_data = f.read()
                            result.add_image_content(plot_data, "image/png")
                            result.add_text_content(f"生成图表: {Path(plot_path).name}")
                        except Exception as e:
                            self.logger.warning(f"Failed to read plot file {plot_path}: {e}")
                
                # Add warnings if any
                if execution_result.warnings:
                    warnings_text = "\n".join(execution_result.warnings)
                    result.add_text_content(f"警告:\n{warnings_text}")
                
            else:
                # Handle execution failure
                error_msg = f"代码执行失败: {execution_result.error}"
                result.add_text_content(error_msg)
                result.error = execution_result.error
                
                # Still add partial output if available
                if execution_result.output:
                    result.add_text_content(f"部分输出:\n{execution_result.output}")

            # Add metadata
            result.metadata = {
                "execution_time": execution_result.execution_time,
                "environment": environment or "current",
                "entry_id": entry_id,
                "code_length": len(code),
                "plot_count": len(execution_result.plots),
                "warning_count": len(execution_result.warnings)
            }

            return result

        except EnvironmentError as e:
            return ToolResult(
                success=False,
                error=f"环境错误: {str(e)}"
            )
        except ExecutionError as e:
            return ToolResult(
                success=False,
                error=f"执行错误: {str(e)}"
            )
        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                error=f"代码执行超时（{timeout}秒）"
            )
        except Exception as e:
            self.logger.error("Unexpected error in execute_r_code: %s", e, exc_info=True)
            return ToolResult(
                success=False,
                error=f"执行R代码时发生意外错误: {str(e)}"
            )

    def _format_execution_summary(
        self, 
        result: ExecutionResult, 
        environment: Optional[str], 
        entry_id: Optional[str],
        format_output: bool
    ) -> str:
        """Format execution summary.
        
        Args:
            result: Execution result
            environment: Environment name
            entry_id: History entry ID
            format_output: Whether to format output
            
        Returns:
            Formatted summary string
        """
        summary_parts = [
            "✅ R代码执行成功" if result.success else "❌ R代码执行失败",
            f"环境: {environment or '当前环境'}",
            f"执行时间: {result.execution_time:.3f}秒"
        ]
        
        if entry_id:
            summary_parts.append(f"历史记录ID: {entry_id}")
        
        if result.plots:
            summary_parts.append(f"生成图表: {len(result.plots)}个")
        
        if result.warnings:
            summary_parts.append(f"警告: {len(result.warnings)}个")
        
        return "\n".join(summary_parts)

    def _format_output(self, output: str) -> str:
        """Format R output for better readability.
        
        Args:
            output: Raw R output
            
        Returns:
            Formatted output
        """
        if not output:
            return ""
        
        # Basic formatting - add code block markers
        lines = output.split('\n')
        formatted_lines = []
        
        for line in lines:
            # Clean up common R output patterns
            line = line.strip()
            if line:
                formatted_lines.append(line)
        
        if formatted_lines:
            return "```r\n" + "\n".join(formatted_lines) + "\n```"
        else:
            return output


class GetExecutionHistoryTool(BaseTool):
    """Tool for retrieving code execution history."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "get_execution_history"

    @property
    def description(self) -> str:
        """Tool description."""
        return "获取R代码执行历史记录"

    @property
    def parameters(self) -> List[ToolParameter]:
        """Tool parameters."""
        return [
            ToolParameter(
                name="limit",
                type="number",
                description="返回的历史记录数量限制",
                required=False,
                default=10
            ),
            ToolParameter(
                name="entry_id",
                type="string",
                description="特定历史记录ID（可选）",
                required=False
            ),
            ToolParameter(
                name="environment",
                type="string",
                description="筛选特定环境的历史记录（可选）",
                required=False
            ),
            ToolParameter(
                name="include_code",
                type="boolean",
                description="是否包含代码内容",
                required=False,
                default=True
            ),
            ToolParameter(
                name="include_output",
                type="boolean",
                description="是否包含输出内容",
                required=False,
                default=False
            )
        ]

    def __init__(self, execution_history: ExecutionHistory):
        """Initialize the tool.
        
        Args:
            execution_history: Execution history instance
        """
        super().__init__()
        self.history = execution_history

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        try:
            limit = arguments.get("limit", 10)
            entry_id = arguments.get("entry_id")
            environment = arguments.get("environment")
            include_code = arguments.get("include_code", True)
            include_output = arguments.get("include_output", False)

            result = ToolResult(success=True)

            if entry_id:
                # Get specific entry
                entry = self.history.get_entry(entry_id)
                if entry:
                    formatted_entry = self._format_history_entry(
                        entry, include_code, include_output
                    )
                    result.add_text_content(formatted_entry)
                else:
                    result.add_text_content(f"未找到ID为 '{entry_id}' 的历史记录")
            else:
                # Get recent entries
                entries = self.history.get_recent_entries(limit)
                
                if environment:
                    # Filter by environment
                    entries = [e for e in entries if e.get("environment") == environment]
                
                if not entries:
                    result.add_text_content("未找到执行历史记录")
                else:
                    history_text = self._format_history_list(
                        entries, include_code, include_output
                    )
                    result.add_text_content(history_text)

            return result

        except Exception as e:
            self.logger.error("Unexpected error in get_execution_history: %s", e, exc_info=True)
            return ToolResult(
                success=False,
                error=f"获取执行历史时发生错误: {str(e)}"
            )

    def _format_history_entry(
        self, 
        entry: Dict[str, Any], 
        include_code: bool, 
        include_output: bool
    ) -> str:
        """Format a single history entry.
        
        Args:
            entry: History entry data
            include_code: Whether to include code
            include_output: Whether to include output
            
        Returns:
            Formatted entry string
        """
        lines = [
            f"📝 执行记录 {entry['id']}",
            f"时间: {entry['timestamp']}",
            f"环境: {entry['environment']}",
            f"状态: {'✅ 成功' if entry['success'] else '❌ 失败'}",
            f"执行时间: {entry['execution_time']:.3f}秒"
        ]
        
        if entry.get('plots'):
            lines.append(f"图表: {len(entry['plots'])}个")
        
        if entry.get('warnings'):
            lines.append(f"警告: {len(entry['warnings'])}个")
        
        if include_code and entry.get('code'):
            lines.extend([
                "",
                "代码:",
                "```r",
                entry['code'],
                "```"
            ])
        
        if include_output and entry.get('output'):
            lines.extend([
                "",
                "输出:",
                "```",
                entry['output'],
                "```"
            ])
        
        if not entry['success'] and entry.get('error'):
            lines.extend([
                "",
                f"错误: {entry['error']}"
            ])
        
        return "\n".join(lines)

    def _format_history_list(
        self, 
        entries: List[Dict[str, Any]], 
        include_code: bool, 
        include_output: bool
    ) -> str:
        """Format a list of history entries.
        
        Args:
            entries: List of history entries
            include_code: Whether to include code
            include_output: Whether to include output
            
        Returns:
            Formatted history string
        """
        if not entries:
            return "无执行历史记录"
        
        lines = [f"📚 执行历史记录 (共 {len(entries)} 条)"]
        lines.append("=" * 50)
        
        for i, entry in enumerate(entries, 1):
            lines.append(f"\n{i}. {self._format_history_entry(entry, include_code, include_output)}")
        
        return "\n".join(lines)


class ClearExecutionHistoryTool(BaseTool):
    """Tool for clearing code execution history."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "clear_execution_history"

    @property
    def description(self) -> str:
        """Tool description."""
        return "清除R代码执行历史记录"

    @property
    def parameters(self) -> List[ToolParameter]:
        """Tool parameters."""
        return [
            ToolParameter(
                name="confirm",
                type="boolean",
                description="确认清除历史记录",
                required=True
            )
        ]

    def __init__(self, execution_history: ExecutionHistory):
        """Initialize the tool.
        
        Args:
            execution_history: Execution history instance
        """
        super().__init__()
        self.history = execution_history

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        try:
            confirm = arguments.get("confirm", False)
            
            if not confirm:
                return ToolResult(
                    success=False,
                    error="必须设置 confirm=true 来确认清除历史记录"
                )
            
            cleared_count = self.history.clear_history()
            
            result = ToolResult(success=True)
            result.add_text_content(f"✅ 已清除 {cleared_count} 条执行历史记录")
            
            return result

        except Exception as e:
            self.logger.error("Unexpected error in clear_execution_history: %s", e, exc_info=True)
            return ToolResult(
                success=False,
                error=f"清除执行历史时发生错误: {str(e)}"
            )