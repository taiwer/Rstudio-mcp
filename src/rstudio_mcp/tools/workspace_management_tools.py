"""Workspace management tools for RStudio MCP Server."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..api_wrapper import RStudioAPIWrapper
from ..exceptions import ExecutionError
from .base import BaseTool, ToolParameter, ToolResult


class SaveWorkspaceTool(BaseTool):
    """Tool for saving the current workspace state."""
    
    def __init__(self, api_wrapper: Optional[RStudioAPIWrapper] = None):
        """Initialize the save workspace tool.
        
        Args:
            api_wrapper: RStudio API wrapper instance
        """
        super().__init__()
        self.api = api_wrapper or RStudioAPIWrapper()
    
    @property
    def name(self) -> str:
        return "save_workspace"
    
    @property
    def description(self) -> str:
        return "保存当前工作空间状态到文件，包括所有变量和对象"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="file_path",
                type="string",
                description="保存工作空间的文件路径（.RData文件）",
                required=True
            ),
            ToolParameter(
                name="include_hidden",
                type="boolean",
                description="是否包含隐藏对象（以.开头的对象）",
                required=False,
                default=False
            ),
            ToolParameter(
                name="compress",
                type="boolean",
                description="是否压缩保存的文件",
                required=False,
                default=True
            ),
            ToolParameter(
                name="overwrite",
                type="boolean",
                description="如果文件已存在是否覆盖",
                required=False,
                default=False
            )
        ]
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the save workspace tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        try:
            file_path = arguments["file_path"]
            include_hidden = arguments.get("include_hidden", False)
            compress = arguments.get("compress", True)
            overwrite = arguments.get("overwrite", False)
            
            # Validate file path
            if not file_path.endswith('.RData'):
                file_path += '.RData'
            
            file_path_obj = Path(file_path)
            
            # Check if file exists and overwrite is not allowed
            if file_path_obj.exists() and not overwrite:
                return ToolResult(
                    success=False,
                    error=f"文件 {file_path} 已存在，请设置 overwrite=true 或选择其他路径"
                )
            
            # Create directory if it doesn't exist
            file_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            # Build R code for saving workspace
            if include_hidden:
                objects_code = "ls(all.names = TRUE)"
            else:
                objects_code = "ls()"
            
            save_code = f"""
            # Get list of objects to save
            objects_to_save <- {objects_code}
            
            # Save workspace
            save(list = objects_to_save, 
                 file = "{file_path}", 
                 compress = {str(compress).upper()})
            
            # Get information about saved objects
            saved_info <- list(
                file_path = "{file_path}",
                object_count = length(objects_to_save),
                object_names = objects_to_save,
                file_size = file.info("{file_path}")$size,
                compressed = {str(compress).upper()}
            )
            
            cat("Workspace saved successfully\\n")
            cat("Objects saved:", length(objects_to_save), "\\n")
            cat("File size:", file.info("{file_path}")$size, "bytes\\n")
            """
            
            result = await self.api.execute_r_code(save_code, capture_plots=False)
            
            if result.success:
                # Get workspace info for metadata
                info_code = f"""
                load_info <- list(
                    file_path = "{file_path}",
                    file_exists = file.exists("{file_path}"),
                    file_size = file.info("{file_path}")$size,
                    objects_saved = length({objects_code})
                )
                jsonlite::toJSON(load_info, pretty = TRUE)
                """
                
                info_result = await self.api.execute_r_code(info_code, capture_plots=False)
                
                tool_result = ToolResult(success=True)
                tool_result.add_text_content(f"工作空间已成功保存到: {file_path}")
                tool_result.add_text_content(result.output)
                
                # Add metadata
                try:
                    if info_result.success and info_result.output:
                        metadata = json.loads(info_result.output)
                        tool_result.metadata = metadata
                except Exception:
                    pass
                
                tool_result.metadata.update({
                    "file_path": file_path,
                    "include_hidden": include_hidden,
                    "compressed": compress
                })
                
                return tool_result
            else:
                return ToolResult(
                    success=False,
                    error=f"保存工作空间失败: {result.error}"
                )
                
        except Exception as e:
            self.logger.error(f"Failed to save workspace: {e}")
            return ToolResult(
                success=False,
                error=f"保存工作空间失败: {str(e)}"
            )


class LoadWorkspaceTool(BaseTool):
    """Tool for loading workspace from a file."""
    
    def __init__(self, api_wrapper: Optional[RStudioAPIWrapper] = None):
        """Initialize the load workspace tool.
        
        Args:
            api_wrapper: RStudio API wrapper instance
        """
        super().__init__()
        self.api = api_wrapper or RStudioAPIWrapper()
    
    @property
    def name(self) -> str:
        return "load_workspace"
    
    @property
    def description(self) -> str:
        return "从文件恢复工作空间状态，加载所有保存的变量和对象"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="file_path",
                type="string",
                description="要加载的工作空间文件路径（.RData文件）",
                required=True
            ),
            ToolParameter(
                name="clear_current",
                type="boolean",
                description="是否在加载前清空当前工作空间",
                required=False,
                default=False
            ),
            ToolParameter(
                name="verbose",
                type="boolean",
                description="是否显示详细的加载信息",
                required=False,
                default=True
            )
        ]
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the load workspace tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        try:
            file_path = arguments["file_path"]
            clear_current = arguments.get("clear_current", False)
            verbose = arguments.get("verbose", True)
            
            # Validate file path
            if not file_path.endswith('.RData'):
                file_path += '.RData'
            
            file_path_obj = Path(file_path)
            
            # Check if file exists
            if not file_path_obj.exists():
                return ToolResult(
                    success=False,
                    error=f"工作空间文件不存在: {file_path}"
                )
            
            # Get current workspace info before loading
            current_objects = []
            if verbose:
                current_result = await self.api.execute_r_code("ls()", capture_plots=False)
                if current_result.success:
                    current_objects = current_result.output.strip().split()
            
            # Build R code for loading workspace
            load_code = f"""
            # Clear current workspace if requested
            {f'rm(list = ls())' if clear_current else ''}
            
            # Load workspace
            load("{file_path}")
            
            # Get information about loaded objects
            loaded_objects <- ls()
            
            cat("Workspace loaded successfully\\n")
            cat("Objects loaded:", length(loaded_objects), "\\n")
            if (length(loaded_objects) > 0) {{
                cat("Object names:", paste(loaded_objects, collapse = ", "), "\\n")
            }}
            """
            
            result = await self.api.execute_r_code(load_code, capture_plots=False)
            
            if result.success:
                # Get detailed info about loaded objects
                info_code = """
                loaded_objects <- ls()
                if (length(loaded_objects) > 0) {
                    obj_info <- lapply(loaded_objects, function(name) {
                        obj <- get(name)
                        list(
                            name = name,
                            class = class(obj)[1],
                            type = typeof(obj),
                            size = as.numeric(object.size(obj))
                        )
                    })
                    names(obj_info) <- loaded_objects
                    jsonlite::toJSON(obj_info, pretty = TRUE)
                } else {
                    jsonlite::toJSON(list(), pretty = TRUE)
                }
                """
                
                info_result = await self.api.execute_r_code(info_code, capture_plots=False)
                
                tool_result = ToolResult(success=True)
                tool_result.add_text_content(f"工作空间已成功从文件加载: {file_path}")
                tool_result.add_text_content(result.output)
                
                # Add detailed object information
                if info_result.success and info_result.output:
                    try:
                        loaded_objects_info = json.loads(info_result.output)
                        if loaded_objects_info:
                            tool_result.add_text_content("\n加载的对象详情:")
                            for obj_name, obj_info in loaded_objects_info.items():
                                tool_result.add_text_content(
                                    f"  {obj_name}: {obj_info['class']} "
                                    f"({obj_info['size']} bytes)"
                                )
                        
                        tool_result.metadata = {
                            "file_path": file_path,
                            "clear_current": clear_current,
                            "loaded_objects": loaded_objects_info,
                            "object_count": len(loaded_objects_info),
                            "current_objects_before": current_objects
                        }
                    except Exception as e:
                        self.logger.warning(f"Failed to parse object info: {e}")
                
                return tool_result
            else:
                return ToolResult(
                    success=False,
                    error=f"加载工作空间失败: {result.error}"
                )
                
        except Exception as e:
            self.logger.error(f"Failed to load workspace: {e}")
            return ToolResult(
                success=False,
                error=f"加载工作空间失败: {str(e)}"
            )


class ListWorkspaceObjectsTool(BaseTool):
    """Tool for listing objects in the current workspace."""
    
    def __init__(self, api_wrapper: Optional[RStudioAPIWrapper] = None):
        """Initialize the list workspace objects tool.
        
        Args:
            api_wrapper: RStudio API wrapper instance
        """
        super().__init__()
        self.api = api_wrapper or RStudioAPIWrapper()
    
    @property
    def name(self) -> str:
        return "list_workspace_objects"
    
    @property
    def description(self) -> str:
        return "显示当前工作空间中的所有对象，包括详细信息"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="include_hidden",
                type="boolean",
                description="是否包含隐藏对象（以.开头的对象）",
                required=False,
                default=False
            ),
            ToolParameter(
                name="sort_by",
                type="string",
                description="排序方式",
                required=False,
                default="name",
                enum=["name", "size", "class", "type"]
            ),
            ToolParameter(
                name="include_details",
                type="boolean",
                description="是否包含对象的详细信息",
                required=False,
                default=True
            ),
            ToolParameter(
                name="filter_class",
                type="string",
                description="按对象类型过滤（可选）",
                required=False
            )
        ]
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the list workspace objects tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        try:
            include_hidden = arguments.get("include_hidden", False)
            sort_by = arguments.get("sort_by", "name")
            include_details = arguments.get("include_details", True)
            filter_class = arguments.get("filter_class")
            
            # Build R code for listing objects
            if include_hidden:
                objects_code = "ls(all.names = TRUE)"
            else:
                objects_code = "ls()"
            
            if include_details:
                list_code = f"""
                object_names <- {objects_code}
                
                if (length(object_names) == 0) {{
                    cat("工作空间为空\\n")
                    jsonlite::toJSON(list(), pretty = TRUE)
                }} else {{
                    # Get detailed information for each object
                    obj_info <- lapply(object_names, function(name) {{
                        obj <- get(name, envir = .GlobalEnv)
                        obj_class <- class(obj)[1]
                        obj_type <- typeof(obj)
                        obj_size <- as.numeric(object.size(obj))
                        
                        # Get dimensions if applicable
                        obj_dims <- NULL
                        if (is.matrix(obj) || is.data.frame(obj) || is.array(obj)) {{
                            obj_dims <- dim(obj)
                        }} else if (is.vector(obj)) {{
                            obj_dims <- length(obj)
                        }}
                        
                        # Get summary
                        obj_summary <- tryCatch({{
                            capture.output(str(obj, max.level = 1))[1]
                        }}, error = function(e) "")
                        
                        list(
                            name = name,
                            class = obj_class,
                            type = obj_type,
                            size = obj_size,
                            dimensions = obj_dims,
                            summary = obj_summary
                        )
                    }})
                    
                    names(obj_info) <- object_names
                    
                    # Filter by class if specified
                    {f'''
                    if (length(obj_info) > 0) {{
                        class_matches <- sapply(obj_info, function(x) x$class == "{filter_class}")
                        obj_info <- obj_info[class_matches]
                        object_names <- names(obj_info)
                    }}
                    ''' if filter_class else ''}
                    
                    # Sort objects
                    if (length(obj_info) > 0) {{
                        sort_key <- "{sort_by}"
                        if (sort_key == "name") {{
                            sort_order <- order(names(obj_info))
                        }} else if (sort_key == "size") {{
                            sort_order <- order(sapply(obj_info, function(x) x$size), decreasing = TRUE)
                        }} else if (sort_key == "class") {{
                            sort_order <- order(sapply(obj_info, function(x) x$class))
                        }} else if (sort_key == "type") {{
                            sort_order <- order(sapply(obj_info, function(x) x$type))
                        }} else {{
                            sort_order <- seq_along(obj_info)
                        }}
                        obj_info <- obj_info[sort_order]
                    }}
                    
                    # Output summary
                    cat("工作空间对象总数:", length(obj_info), "\\n")
                    if (length(obj_info) > 0) {{
                        cat("\\n对象列表:\\n")
                        for (i in seq_along(obj_info)) {{
                            info <- obj_info[[i]]
                            size_mb <- round(info$size / 1024 / 1024, 3)
                            dims_str <- if (!is.null(info$dimensions)) {{
                                if (length(info$dimensions) == 1) {{
                                    paste0("[", info$dimensions, "]")
                                }} else {{
                                    paste0("[", paste(info$dimensions, collapse = " x "), "]")
                                }}
                            }} else {{
                                ""
                            }}
                            cat(sprintf("  %s: %s %s (%.3f MB)\\n", 
                                       info$name, info$class, dims_str, size_mb))
                        }}
                    }}
                    
                    jsonlite::toJSON(obj_info, pretty = TRUE)
                }}
                """
            else:
                # Simple listing without details
                list_code = f"""
                object_names <- {objects_code}
                
                if (length(object_names) == 0) {{
                    cat("工作空间为空\\n")
                    jsonlite::toJSON(list(), pretty = TRUE)
                }} else {{
                    cat("工作空间对象:", length(object_names), "\\n")
                    cat(paste(object_names, collapse = ", "), "\\n")
                    
                    # Simple object info
                    obj_info <- setNames(lapply(object_names, function(name) {{
                        list(name = name, class = class(get(name))[1])
                    }}), object_names)
                    
                    jsonlite::toJSON(obj_info, pretty = TRUE)
                }}
                """
            
            result = await self.api.execute_r_code(list_code, capture_plots=False)
            
            if result.success:
                tool_result = ToolResult(success=True)
                tool_result.add_text_content("工作空间对象列表:")
                tool_result.add_text_content(result.output)
                
                # Parse and add metadata
                try:
                    # Extract JSON from output
                    output_lines = result.output.split('\n')
                    json_start = -1
                    for i, line in enumerate(output_lines):
                        if line.strip().startswith('{') or line.strip().startswith('['):
                            json_start = i
                            break
                    
                    if json_start >= 0:
                        json_content = '\n'.join(output_lines[json_start:])
                        objects_info = json.loads(json_content)
                        
                        tool_result.metadata = {
                            "objects": objects_info,
                            "object_count": len(objects_info) if objects_info else 0,
                            "include_hidden": include_hidden,
                            "sort_by": sort_by,
                            "filter_class": filter_class
                        }
                except Exception as e:
                    self.logger.warning(f"Failed to parse object info: {e}")
                
                return tool_result
            else:
                return ToolResult(
                    success=False,
                    error=f"列出工作空间对象失败: {result.error}"
                )
                
        except Exception as e:
            self.logger.error(f"Failed to list workspace objects: {e}")
            return ToolResult(
                success=False,
                error=f"列出工作空间对象失败: {str(e)}"
            )


class CleanWorkspaceTool(BaseTool):
    """Tool for cleaning and optimizing the workspace."""
    
    def __init__(self, api_wrapper: Optional[RStudioAPIWrapper] = None):
        """Initialize the clean workspace tool.
        
        Args:
            api_wrapper: RStudio API wrapper instance
        """
        super().__init__()
        self.api = api_wrapper or RStudioAPIWrapper()
    
    @property
    def name(self) -> str:
        return "clean_workspace"
    
    @property
    def description(self) -> str:
        return "清理和优化工作空间，包括删除指定对象、垃圾回收等"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="清理操作类型",
                required=True,
                enum=["remove_objects", "garbage_collect", "clear_all", "remove_large", "remove_by_class"]
            ),
            ToolParameter(
                name="object_names",
                type="array",
                description="要删除的对象名称列表（用于remove_objects操作）",
                required=False,
                items={"type": "string"}
            ),
            ToolParameter(
                name="size_threshold_mb",
                type="number",
                description="大小阈值（MB），用于remove_large操作",
                required=False,
                default=10.0
            ),
            ToolParameter(
                name="object_class",
                type="string",
                description="要删除的对象类型（用于remove_by_class操作）",
                required=False
            ),
            ToolParameter(
                name="confirm",
                type="boolean",
                description="是否确认执行清理操作",
                required=False,
                default=False
            )
        ]
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the clean workspace tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        try:
            action = arguments["action"]
            object_names = arguments.get("object_names", [])
            size_threshold_mb = arguments.get("size_threshold_mb", 10.0)
            object_class = arguments.get("object_class")
            confirm = arguments.get("confirm", False)
            
            if not confirm and action in ["clear_all", "remove_objects", "remove_large", "remove_by_class"]:
                return ToolResult(
                    success=False,
                    error="此操作可能删除工作空间对象，请设置 confirm=true 确认执行"
                )
            
            # Build R code based on action
            if action == "garbage_collect":
                clean_code = """
                # Perform garbage collection
                before_gc <- gc()
                gc_result <- gc()
                
                cat("垃圾回收完成\\n")
                cat("回收前内存使用:\\n")
                print(before_gc)
                cat("\\n回收后内存使用:\\n")
                print(gc_result)
                
                list(
                    action = "garbage_collect",
                    memory_before = before_gc,
                    memory_after = gc_result
                )
                """
                
            elif action == "clear_all":
                clean_code = """
                # Get current objects before clearing
                objects_before <- ls()
                object_count_before <- length(objects_before)
                
                # Clear all objects
                rm(list = ls())
                
                # Perform garbage collection
                gc_result <- gc()
                
                cat("已清空所有工作空间对象\\n")
                cat("删除对象数量:", object_count_before, "\\n")
                cat("垃圾回收结果:\\n")
                print(gc_result)
                
                list(
                    action = "clear_all",
                    objects_removed = objects_before,
                    count_removed = object_count_before,
                    memory_after_gc = gc_result
                )
                """
                
            elif action == "remove_objects":
                if not object_names:
                    return ToolResult(
                        success=False,
                        error="remove_objects操作需要指定object_names参数"
                    )
                
                objects_str = ', '.join(f'"{name}"' for name in object_names)
                clean_code = f"""
                # Check which objects exist
                objects_to_remove <- c({objects_str})
                existing_objects <- objects_to_remove[objects_to_remove %in% ls()]
                missing_objects <- objects_to_remove[!objects_to_remove %in% ls()]
                
                # Remove existing objects
                if (length(existing_objects) > 0) {{
                    rm(list = existing_objects)
                    cat("已删除对象:", paste(existing_objects, collapse = ", "), "\\n")
                }} else {{
                    cat("没有找到要删除的对象\\n")
                }}
                
                if (length(missing_objects) > 0) {{
                    cat("未找到的对象:", paste(missing_objects, collapse = ", "), "\\n")
                }}
                
                # Garbage collection
                gc_result <- gc()
                
                list(
                    action = "remove_objects",
                    objects_removed = existing_objects,
                    objects_not_found = missing_objects,
                    memory_after_gc = gc_result
                )
                """
                
            elif action == "remove_large":
                clean_code = f"""
                # Find large objects
                all_objects <- ls()
                size_threshold <- {size_threshold_mb} * 1024 * 1024  # Convert MB to bytes
                
                large_objects <- character(0)
                object_sizes <- numeric(0)
                
                if (length(all_objects) > 0) {{
                    for (obj_name in all_objects) {{
                        obj_size <- as.numeric(object.size(get(obj_name)))
                        if (obj_size > size_threshold) {{
                            large_objects <- c(large_objects, obj_name)
                            object_sizes <- c(object_sizes, obj_size)
                        }}
                    }}
                }}
                
                # Remove large objects
                if (length(large_objects) > 0) {{
                    rm(list = large_objects)
                    cat("已删除大对象 (>{size_threshold_mb}MB):\\n")
                    for (i in seq_along(large_objects)) {{
                        size_mb <- round(object_sizes[i] / 1024 / 1024, 2)
                        cat("  ", large_objects[i], ": ", size_mb, "MB\\n")
                    }}
                }} else {{
                    cat("没有找到大于 {size_threshold_mb}MB 的对象\\n")
                }}
                
                # Garbage collection
                gc_result <- gc()
                
                list(
                    action = "remove_large",
                    threshold_mb = {size_threshold_mb},
                    objects_removed = large_objects,
                    sizes_mb = round(object_sizes / 1024 / 1024, 2),
                    memory_after_gc = gc_result
                )
                """
                
            elif action == "remove_by_class":
                if not object_class:
                    return ToolResult(
                        success=False,
                        error="remove_by_class操作需要指定object_class参数"
                    )
                
                clean_code = f"""
                # Find objects of specified class
                all_objects <- ls()
                objects_to_remove <- character(0)
                
                if (length(all_objects) > 0) {{
                    for (obj_name in all_objects) {{
                        obj <- get(obj_name)
                        if (class(obj)[1] == "{object_class}") {{
                            objects_to_remove <- c(objects_to_remove, obj_name)
                        }}
                    }}
                }}
                
                # Remove objects of specified class
                if (length(objects_to_remove) > 0) {{
                    rm(list = objects_to_remove)
                    cat("已删除类型为 '{object_class}' 的对象:\\n")
                    cat("  ", paste(objects_to_remove, collapse = ", "), "\\n")
                }} else {{
                    cat("没有找到类型为 '{object_class}' 的对象\\n")
                }}
                
                # Garbage collection
                gc_result <- gc()
                
                list(
                    action = "remove_by_class",
                    object_class = "{object_class}",
                    objects_removed = objects_to_remove,
                    memory_after_gc = gc_result
                )
                """
            else:
                return ToolResult(
                    success=False,
                    error=f"未知的清理操作: {action}"
                )
            
            # Execute the cleaning code
            result = await self.api.execute_r_code(clean_code, capture_plots=False)
            
            if result.success:
                tool_result = ToolResult(success=True)
                tool_result.add_text_content(f"工作空间清理操作 '{action}' 完成:")
                tool_result.add_text_content(result.output)
                
                # Try to extract metadata from R output
                try:
                    # Look for JSON-like output in the result
                    output_lines = result.output.split('\n')
                    for line in output_lines:
                        if 'list(' in line:
                            # This is a simple approach - in practice you might want more robust parsing
                            break
                    
                    tool_result.metadata = {
                        "action": action,
                        "parameters": {
                            "object_names": object_names,
                            "size_threshold_mb": size_threshold_mb,
                            "object_class": object_class
                        }
                    }
                except Exception as e:
                    self.logger.warning(f"Failed to parse cleanup result: {e}")
                
                return tool_result
            else:
                return ToolResult(
                    success=False,
                    error=f"工作空间清理失败: {result.error}"
                )
                
        except Exception as e:
            self.logger.error(f"Failed to clean workspace: {e}")
            return ToolResult(
                success=False,
                error=f"工作空间清理失败: {str(e)}"
            )