"""Plot management tools for RStudio MCP Server."""

import json
import logging
import os
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..api_wrapper import RStudioAPIWrapper
from .base import BaseTool, ToolParameter, ToolResult


class PlotMetadata:
    """Metadata for a captured plot."""
    
    def __init__(
        self,
        plot_id: str,
        file_path: str,
        format: str,
        created_at: datetime,
        code: str,
        size: int,
        width: Optional[int] = None,
        height: Optional[int] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ):
        self.plot_id = plot_id
        self.file_path = file_path
        self.format = format
        self.created_at = created_at
        self.code = code
        self.size = size
        self.width = width
        self.height = height
        self.title = title
        self.description = description
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "plot_id": self.plot_id,
            "file_path": self.file_path,
            "format": self.format,
            "created_at": self.created_at.isoformat(),
            "code": self.code,
            "size": self.size,
            "width": self.width,
            "height": self.height,
            "title": self.title,
            "description": self.description,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlotMetadata":
        """Create from dictionary representation."""
        return cls(
            plot_id=data["plot_id"],
            file_path=data["file_path"],
            format=data["format"],
            created_at=datetime.fromisoformat(data["created_at"]),
            code=data["code"],
            size=data["size"],
            width=data.get("width"),
            height=data.get("height"),
            title=data.get("title"),
            description=data.get("description"),
        )


class PlotManager:
    """Manager for plot storage and metadata."""
    
    def __init__(self, storage_dir: Optional[str] = None):
        """Initialize plot manager.
        
        Args:
            storage_dir: Directory to store plots and metadata
        """
        self.logger = logging.getLogger(__name__)
        
        if storage_dir is None:
            storage_dir = os.path.join(tempfile.gettempdir(), "rstudio_mcp_plots")
        
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.metadata_file = self.storage_dir / "plot_metadata.json"
        self._metadata_cache: Dict[str, PlotMetadata] = {}
        self._load_metadata()
    
    def _load_metadata(self) -> None:
        """Load plot metadata from file."""
        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for plot_id, plot_data in data.items():
                        self._metadata_cache[plot_id] = PlotMetadata.from_dict(plot_data)
                self.logger.info(f"Loaded metadata for {len(self._metadata_cache)} plots")
        except Exception as e:
            self.logger.warning(f"Failed to load plot metadata: {e}")
            self._metadata_cache = {}
    
    def _save_metadata(self) -> None:
        """Save plot metadata to file."""
        try:
            data = {
                plot_id: metadata.to_dict()
                for plot_id, metadata in self._metadata_cache.items()
            }
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Failed to save plot metadata: {e}")
    
    def store_plot(
        self,
        source_path: str,
        code: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> str:
        """Store a plot file and create metadata.
        
        Args:
            source_path: Path to the source plot file
            code: R code that generated the plot
            title: Optional plot title
            description: Optional plot description
            
        Returns:
            Plot ID for the stored plot
        """
        try:
            source_file = Path(source_path)
            if not source_file.exists():
                raise FileNotFoundError(f"Source plot file not found: {source_path}")
            
            # Generate unique plot ID
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            plot_id = f"plot_{timestamp}_{hash(code) % 10000:04d}"
            
            # Determine format from file extension
            format_ext = source_file.suffix.lower().lstrip('.')
            if not format_ext:
                format_ext = "png"  # Default format
            
            # Create destination path
            dest_filename = f"{plot_id}.{format_ext}"
            dest_path = self.storage_dir / dest_filename
            
            # Copy file to storage
            shutil.copy2(source_path, dest_path)
            
            # Get file size and dimensions if possible
            file_size = dest_path.stat().st_size
            width, height = self._get_image_dimensions(dest_path)
            
            # Create metadata
            metadata = PlotMetadata(
                plot_id=plot_id,
                file_path=str(dest_path),
                format=format_ext,
                created_at=datetime.now(),
                code=code,
                size=file_size,
                width=width,
                height=height,
                title=title,
                description=description,
            )
            
            # Store metadata
            self._metadata_cache[plot_id] = metadata
            self._save_metadata()
            
            self.logger.info(f"Stored plot {plot_id} from {source_path}")
            return plot_id
            
        except Exception as e:
            self.logger.error(f"Failed to store plot: {e}")
            raise
    
    def _get_image_dimensions(self, image_path: Path) -> tuple[Optional[int], Optional[int]]:
        """Get image dimensions if possible.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Tuple of (width, height) or (None, None) if unable to determine
        """
        try:
            # Try to use PIL if available
            from PIL import Image
            with Image.open(image_path) as img:
                return img.size
        except ImportError:
            # PIL not available, skip dimensions
            pass
        except Exception as e:
            self.logger.debug(f"Failed to get image dimensions: {e}")
        
        return None, None
    
    def get_plot_metadata(self, plot_id: str) -> Optional[PlotMetadata]:
        """Get metadata for a specific plot.
        
        Args:
            plot_id: Plot identifier
            
        Returns:
            Plot metadata or None if not found
        """
        return self._metadata_cache.get(plot_id)
    
    def list_plots(
        self,
        limit: Optional[int] = None,
        format_filter: Optional[str] = None,
        search_term: Optional[str] = None,
    ) -> List[PlotMetadata]:
        """List stored plots with optional filtering.
        
        Args:
            limit: Maximum number of plots to return
            format_filter: Filter by plot format (e.g., 'png', 'pdf')
            search_term: Search in title, description, or code
            
        Returns:
            List of plot metadata
        """
        plots = list(self._metadata_cache.values())
        
        # Apply format filter
        if format_filter:
            plots = [p for p in plots if p.format.lower() == format_filter.lower()]
        
        # Apply search filter
        if search_term:
            search_lower = search_term.lower()
            plots = [
                p for p in plots
                if (search_lower in (p.title or "").lower() or
                    search_lower in (p.description or "").lower() or
                    search_lower in p.code.lower())
            ]
        
        # Sort by creation time (newest first)
        plots.sort(key=lambda p: p.created_at, reverse=True)
        
        # Apply limit
        if limit and limit > 0:
            plots = plots[:limit]
        
        return plots
    
    def delete_plot(self, plot_id: str) -> bool:
        """Delete a stored plot and its metadata.
        
        Args:
            plot_id: Plot identifier
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            metadata = self._metadata_cache.get(plot_id)
            if not metadata:
                return False
            
            # Delete file if it exists
            plot_file = Path(metadata.file_path)
            if plot_file.exists():
                plot_file.unlink()
            
            # Remove from metadata
            del self._metadata_cache[plot_id]
            self._save_metadata()
            
            self.logger.info(f"Deleted plot {plot_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete plot {plot_id}: {e}")
            return False
    
    def export_plot(
        self,
        plot_id: str,
        output_path: str,
        target_format: Optional[str] = None,
    ) -> bool:
        """Export a plot to a different location or format.
        
        Args:
            plot_id: Plot identifier
            output_path: Target output path
            target_format: Target format (if different from original)
            
        Returns:
            True if exported successfully, False otherwise
        """
        try:
            metadata = self._metadata_cache.get(plot_id)
            if not metadata:
                return False
            
            source_file = Path(metadata.file_path)
            if not source_file.exists():
                return False
            
            output_file = Path(output_path)
            
            # If no format conversion needed, just copy
            if not target_format or target_format.lower() == metadata.format.lower():
                shutil.copy2(source_file, output_file)
                return True
            
            # Try format conversion if PIL is available
            try:
                from PIL import Image
                with Image.open(source_file) as img:
                    # Convert to RGB if saving as JPEG
                    if target_format.lower() in ['jpg', 'jpeg'] and img.mode in ['RGBA', 'P']:
                        img = img.convert('RGB')
                    
                    img.save(output_file, format=target_format.upper())
                return True
                
            except ImportError:
                self.logger.warning("PIL not available for format conversion")
                return False
            
        except Exception as e:
            self.logger.error(f"Failed to export plot {plot_id}: {e}")
            return False
    
    def cleanup_old_plots(self, max_age_days: int = 30) -> int:
        """Clean up old plots.
        
        Args:
            max_age_days: Maximum age in days for plots to keep
            
        Returns:
            Number of plots deleted
        """
        try:
            cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 3600)
            deleted_count = 0
            
            plots_to_delete = [
                plot_id for plot_id, metadata in self._metadata_cache.items()
                if metadata.created_at.timestamp() < cutoff_time
            ]
            
            for plot_id in plots_to_delete:
                if self.delete_plot(plot_id):
                    deleted_count += 1
            
            self.logger.info(f"Cleaned up {deleted_count} old plots")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup old plots: {e}")
            return 0


class CapturePlotTool(BaseTool):
    """Tool for capturing R-generated plots."""
    
    def __init__(self, api_wrapper: RStudioAPIWrapper, plot_manager: PlotManager):
        super().__init__()
        self.api_wrapper = api_wrapper
        self.plot_manager = plot_manager
    
    @property
    def name(self) -> str:
        return "capture_plot"
    
    @property
    def description(self) -> str:
        return "捕获 R 代码生成的图表并存储"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="code",
                type="string",
                description="生成图表的 R 代码",
                required=True,
            ),
            ToolParameter(
                name="title",
                type="string",
                description="图表标题（可选）",
                required=False,
            ),
            ToolParameter(
                name="description",
                type="string",
                description="图表描述（可选）",
                required=False,
            ),
            ToolParameter(
                name="format",
                type="string",
                description="图表格式",
                required=False,
                default="png",
                enum=["png", "pdf", "svg", "jpeg"],
            ),
            ToolParameter(
                name="width",
                type="number",
                description="图表宽度（像素）",
                required=False,
                default=800,
            ),
            ToolParameter(
                name="height",
                type="number",
                description="图表高度（像素）",
                required=False,
                default=600,
            ),
        ]
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the plot capture tool."""
        try:
            code = arguments["code"]
            title = arguments.get("title")
            description = arguments.get("description")
            format_type = arguments.get("format", "png")
            width = arguments.get("width", 800)
            height = arguments.get("height", 600)
            
            # Create temporary directory for this capture
            temp_dir = tempfile.mkdtemp(prefix="plot_capture_")
            
            try:
                # Set up plot device with specified format and dimensions
                plot_file = os.path.join(temp_dir, f"plot.{format_type}")
                
                if format_type.lower() == "png":
                    device_code = f'png("{plot_file}", width={width}, height={height})'
                elif format_type.lower() == "pdf":
                    device_code = f'pdf("{plot_file}", width={width/72}, height={height/72})'
                elif format_type.lower() == "svg":
                    device_code = f'svg("{plot_file}", width={width/72}, height={height/72})'
                elif format_type.lower() == "jpeg":
                    device_code = f'jpeg("{plot_file}", width={width}, height={height})'
                else:
                    raise ValueError(f"Unsupported format: {format_type}")
                
                # Execute plot code with device setup
                full_code = f"""
                {device_code}
                {code}
                dev.off()
                """
                
                result = await self.api_wrapper.execute_r_code(
                    full_code, capture_plots=False
                )
                
                if not result.success:
                    return ToolResult(
                        success=False,
                        error=f"Failed to execute plot code: {result.error}",
                    )
                
                # Check if plot file was created
                if not os.path.exists(plot_file):
                    return ToolResult(
                        success=False,
                        error="Plot file was not created",
                    )
                
                # Store the plot
                plot_id = self.plot_manager.store_plot(
                    plot_file, code, title, description
                )
                
                # Read plot file for response
                with open(plot_file, 'rb') as f:
                    plot_data = f.read()
                
                # Create result
                result = ToolResult(success=True)
                result.add_text_content(f"图表已成功捕获，ID: {plot_id}")
                
                # Add plot as image content
                mime_type = f"image/{format_type}"
                if format_type == "svg":
                    mime_type = "image/svg+xml"
                elif format_type == "pdf":
                    mime_type = "application/pdf"
                
                result.add_image_content(plot_data, mime_type)
                
                # Add metadata
                metadata = self.plot_manager.get_plot_metadata(plot_id)
                if metadata:
                    result.metadata = {
                        "plot_id": plot_id,
                        "format": format_type,
                        "size": len(plot_data),
                        "width": width,
                        "height": height,
                        "created_at": metadata.created_at.isoformat(),
                    }
                
                return result
                
            finally:
                # Clean up temporary directory
                shutil.rmtree(temp_dir, ignore_errors=True)
                
        except Exception as e:
            self.logger.error(f"Error capturing plot: {e}")
            return ToolResult(
                success=False,
                error=f"Failed to capture plot: {str(e)}",
            )


class ListPlotsTool(BaseTool):
    """Tool for listing captured plots."""
    
    def __init__(self, plot_manager: PlotManager):
        super().__init__()
        self.plot_manager = plot_manager
    
    @property
    def name(self) -> str:
        return "list_plots"
    
    @property
    def description(self) -> str:
        return "列出已捕获的图表历史"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="limit",
                type="number",
                description="返回的最大图表数量",
                required=False,
                default=20,
            ),
            ToolParameter(
                name="format",
                type="string",
                description="按格式筛选图表",
                required=False,
                enum=["png", "pdf", "svg", "jpeg"],
            ),
            ToolParameter(
                name="search",
                type="string",
                description="搜索关键词（在标题、描述或代码中搜索）",
                required=False,
            ),
        ]
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the list plots tool."""
        try:
            limit = arguments.get("limit", 20)
            format_filter = arguments.get("format")
            search_term = arguments.get("search")
            
            plots = self.plot_manager.list_plots(
                limit=limit,
                format_filter=format_filter,
                search_term=search_term,
            )
            
            if not plots:
                result = ToolResult(success=True)
                result.add_text_content("没有找到匹配的图表")
                return result
            
            # Create summary
            result = ToolResult(success=True)
            
            summary_lines = [f"找到 {len(plots)} 个图表:"]
            
            for plot in plots:
                plot_info = [
                    f"ID: {plot.plot_id}",
                    f"格式: {plot.format}",
                    f"创建时间: {plot.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
                    f"大小: {plot.size} 字节",
                ]
                
                if plot.width and plot.height:
                    plot_info.append(f"尺寸: {plot.width}x{plot.height}")
                
                if plot.title:
                    plot_info.append(f"标题: {plot.title}")
                
                if plot.description:
                    plot_info.append(f"描述: {plot.description}")
                
                # Show first line of code
                code_preview = plot.code.split('\n')[0]
                if len(code_preview) > 50:
                    code_preview = code_preview[:47] + "..."
                plot_info.append(f"代码: {code_preview}")
                
                summary_lines.append("  " + " | ".join(plot_info))
            
            result.add_text_content("\n".join(summary_lines))
            
            # Add detailed metadata
            result.metadata = {
                "total_plots": len(plots),
                "plots": [plot.to_dict() for plot in plots],
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error listing plots: {e}")
            return ToolResult(
                success=False,
                error=f"Failed to list plots: {str(e)}",
            )


class ExportPlotTool(BaseTool):
    """Tool for exporting plots to different formats or locations."""
    
    def __init__(self, plot_manager: PlotManager):
        super().__init__()
        self.plot_manager = plot_manager
    
    @property
    def name(self) -> str:
        return "export_plot"
    
    @property
    def description(self) -> str:
        return "导出图表到指定位置或格式"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="plot_id",
                type="string",
                description="要导出的图表 ID",
                required=True,
            ),
            ToolParameter(
                name="output_path",
                type="string",
                description="输出文件路径",
                required=True,
            ),
            ToolParameter(
                name="format",
                type="string",
                description="目标格式（如果与原格式不同）",
                required=False,
                enum=["png", "pdf", "svg", "jpeg"],
            ),
        ]
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the export plot tool."""
        try:
            plot_id = arguments["plot_id"]
            output_path = arguments["output_path"]
            target_format = arguments.get("format")
            
            # Get plot metadata
            metadata = self.plot_manager.get_plot_metadata(plot_id)
            if not metadata:
                return ToolResult(
                    success=False,
                    error=f"Plot with ID '{plot_id}' not found",
                )
            
            # Export the plot
            success = self.plot_manager.export_plot(
                plot_id, output_path, target_format
            )
            
            if not success:
                return ToolResult(
                    success=False,
                    error=f"Failed to export plot '{plot_id}' to '{output_path}'",
                )
            
            result = ToolResult(success=True)
            
            export_info = [
                f"图表 '{plot_id}' 已成功导出到: {output_path}",
                f"原格式: {metadata.format}",
            ]
            
            if target_format:
                export_info.append(f"目标格式: {target_format}")
            
            if metadata.title:
                export_info.append(f"标题: {metadata.title}")
            
            result.add_text_content("\n".join(export_info))
            
            # Add metadata
            result.metadata = {
                "plot_id": plot_id,
                "output_path": output_path,
                "original_format": metadata.format,
                "target_format": target_format or metadata.format,
                "exported_at": datetime.now().isoformat(),
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error exporting plot: {e}")
            return ToolResult(
                success=False,
                error=f"Failed to export plot: {str(e)}",
            )