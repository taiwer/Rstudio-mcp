"""Plot resource handler for RStudio MCP Server."""

import base64
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from ..tools.plot_management_tools import PlotManager, PlotMetadata
from .base import BaseResource, ResourceInfo, ResourceResult


class PlotResource(BaseResource):
    """Resource handler for plot files and metadata."""
    
    def __init__(self, plot_manager: Optional[PlotManager] = None):
        """Initialize the plot resource handler.
        
        Args:
            plot_manager: PlotManager instance to use for plot operations
        """
        super().__init__()
        self.plot_manager = plot_manager or PlotManager()
    
    @property
    def scheme(self) -> str:
        """URI scheme handled by this resource."""
        return "rstudio-plot"
    
    @property
    def description(self) -> str:
        """Resource handler description."""
        return "Access to RStudio plot files and metadata"
    
    async def list_resources(self, uri_prefix: Optional[str] = None) -> List[ResourceInfo]:
        """List available plot resources.
        
        Args:
            uri_prefix: Optional URI prefix to filter resources
            
        Returns:
            List of available plot resources
        """
        try:
            resources = []
            
            # Parse filter parameters from URI prefix if provided
            format_filter = None
            search_term = None
            limit = None
            
            if uri_prefix:
                parsed = urlparse(uri_prefix)
                if parsed.query:
                    query_params = parse_qs(parsed.query)
                    format_filter = query_params.get('format', [None])[0]
                    search_term = query_params.get('search', [None])[0]
                    limit_str = query_params.get('limit', [None])[0]
                    if limit_str:
                        try:
                            limit = int(limit_str)
                        except ValueError:
                            pass
            
            # Get plots from plot manager (without limit first)
            plots = self.plot_manager.list_plots(
                limit=None,  # Don't limit plots yet
                format_filter=format_filter,
                search_term=search_term
            )
            
            # Create resource info for each plot
            for plot in plots:
                # Main plot resource (binary data)
                plot_uri = f"rstudio-plot://{plot.plot_id}"
                plot_resource = ResourceInfo(
                    uri=plot_uri,
                    name=f"Plot: {plot.title or plot.plot_id}",
                    description=plot.description or f"Plot generated on {plot.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
                    mime_type=self._get_mime_type(plot.format),
                    size=plot.size,
                    modified=plot.created_at.isoformat(),
                    metadata={
                        "plot_id": plot.plot_id,
                        "format": plot.format,
                        "width": plot.width,
                        "height": plot.height,
                        "code_preview": plot.code[:100] + "..." if len(plot.code) > 100 else plot.code
                    }
                )
                resources.append(plot_resource)
                
                # Metadata resource (JSON)
                metadata_uri = f"rstudio-plot://{plot.plot_id}/metadata"
                metadata_resource = ResourceInfo(
                    uri=metadata_uri,
                    name=f"Plot Metadata: {plot.title or plot.plot_id}",
                    description=f"Metadata for plot {plot.plot_id}",
                    mime_type="application/json",
                    size=None,  # Will be calculated when accessed
                    modified=plot.created_at.isoformat(),
                    metadata={
                        "plot_id": plot.plot_id,
                        "type": "metadata"
                    }
                )
                resources.append(metadata_resource)
                
                # Code resource (text)
                code_uri = f"rstudio-plot://{plot.plot_id}/code"
                code_resource = ResourceInfo(
                    uri=code_uri,
                    name=f"Plot Code: {plot.title or plot.plot_id}",
                    description=f"R code that generated plot {plot.plot_id}",
                    mime_type="text/x-r",
                    size=len(plot.code.encode('utf-8')),
                    modified=plot.created_at.isoformat(),
                    metadata={
                        "plot_id": plot.plot_id,
                        "type": "code"
                    }
                )
                resources.append(code_resource)
            
            # Apply limit after creating all resources
            if limit is not None and limit > 0:
                resources = resources[:limit]
            
            self.logger.info(f"Listed {len(resources)} plot resources")
            return resources
            
        except Exception as e:
            self.logger.error(f"Error listing plot resources: {e}")
            return []
    
    async def read_resource(self, uri: str) -> ResourceResult:
        """Read plot resource content.
        
        Args:
            uri: Resource URI (e.g., rstudio-plot://plot_id, rstudio-plot://plot_id/metadata)
            
        Returns:
            Resource content and metadata
        """
        try:
            parsed = urlparse(uri)
            
            # Handle both netloc and path cases for plot ID
            # rstudio-plot://plot_id -> netloc = plot_id, path = ""
            # rstudio-plot:///plot_id -> netloc = "", path = "/plot_id"
            if parsed.netloc:
                # Case: rstudio-plot://plot_id or rstudio-plot://plot_id/resource_type
                plot_id = parsed.netloc
                path_parts = parsed.path.strip('/').split('/') if parsed.path.strip('/') else []
                resource_type = path_parts[0] if path_parts and path_parts[0] else "data"
            else:
                # Case: rstudio-plot:///plot_id/resource_type
                path_parts = parsed.path.strip('/').split('/')
                if not path_parts or not path_parts[0]:
                    return self.create_error_result("Invalid plot URI: missing plot ID")
                plot_id = path_parts[0]
                resource_type = path_parts[1] if len(path_parts) > 1 else "data"
            
            # Get plot metadata
            plot_metadata = self.plot_manager.get_plot_metadata(plot_id)
            if not plot_metadata:
                return self.create_error_result(f"Plot not found: {plot_id}")
            
            # Handle different resource types
            if resource_type == "data" or resource_type == "":
                return await self._read_plot_data(plot_metadata)
            elif resource_type == "metadata":
                return await self._read_plot_metadata(plot_metadata)
            elif resource_type == "code":
                return await self._read_plot_code(plot_metadata)
            elif resource_type == "thumbnail":
                return await self._read_plot_thumbnail(plot_metadata)
            else:
                return self.create_error_result(f"Unknown resource type: {resource_type}")
                
        except Exception as e:
            self.logger.error(f"Error reading plot resource {uri}: {e}")
            return self.create_error_result(f"Failed to read plot resource: {str(e)}")
    
    async def _read_plot_data(self, plot_metadata: PlotMetadata) -> ResourceResult:
        """Read plot binary data.
        
        Args:
            plot_metadata: Plot metadata
            
        Returns:
            ResourceResult with plot binary data
        """
        try:
            plot_file = Path(plot_metadata.file_path)
            if not plot_file.exists():
                return self.create_error_result(f"Plot file not found: {plot_metadata.file_path}")
            
            # Read binary data
            with open(plot_file, 'rb') as f:
                plot_data = f.read()
            
            mime_type = self._get_mime_type(plot_metadata.format)
            
            metadata = {
                "plot_id": plot_metadata.plot_id,
                "format": plot_metadata.format,
                "size": len(plot_data),
                "created_at": plot_metadata.created_at.isoformat(),
                "title": plot_metadata.title,
                "description": plot_metadata.description,
                "width": plot_metadata.width,
                "height": plot_metadata.height,
                "encoding": "base64"  # Indicate that binary data is base64 encoded
            }
            
            return self.create_binary_result(plot_data, mime_type, metadata)
            
        except Exception as e:
            return self.create_error_result(f"Failed to read plot data: {str(e)}")
    
    async def _read_plot_metadata(self, plot_metadata: PlotMetadata) -> ResourceResult:
        """Read plot metadata as JSON.
        
        Args:
            plot_metadata: Plot metadata
            
        Returns:
            ResourceResult with plot metadata as JSON
        """
        try:
            metadata_dict = plot_metadata.to_dict()
            
            # Add additional computed fields
            metadata_dict.update({
                "uri": f"rstudio-plot://{plot_metadata.plot_id}",
                "data_uri": f"rstudio-plot://{plot_metadata.plot_id}/data",
                "code_uri": f"rstudio-plot://{plot_metadata.plot_id}/code",
                "thumbnail_uri": f"rstudio-plot://{plot_metadata.plot_id}/thumbnail",
                "file_exists": os.path.exists(plot_metadata.file_path),
                "age_seconds": (datetime.now() - plot_metadata.created_at).total_seconds()
            })
            
            return self.create_json_result(metadata_dict)
            
        except Exception as e:
            return self.create_error_result(f"Failed to read plot metadata: {str(e)}")
    
    async def _read_plot_code(self, plot_metadata: PlotMetadata) -> ResourceResult:
        """Read plot R code.
        
        Args:
            plot_metadata: Plot metadata
            
        Returns:
            ResourceResult with R code as text
        """
        try:
            metadata = {
                "plot_id": plot_metadata.plot_id,
                "title": plot_metadata.title,
                "created_at": plot_metadata.created_at.isoformat(),
                "code_length": len(plot_metadata.code),
                "language": "r"
            }
            
            return self.create_text_result(plot_metadata.code, "text/x-r", metadata)
            
        except Exception as e:
            return self.create_error_result(f"Failed to read plot code: {str(e)}")
    
    async def _read_plot_thumbnail(self, plot_metadata: PlotMetadata) -> ResourceResult:
        """Read plot thumbnail (scaled down version).
        
        Args:
            plot_metadata: Plot metadata
            
        Returns:
            ResourceResult with thumbnail data
        """
        try:
            # For now, return the original plot data
            # In a full implementation, you might generate actual thumbnails
            return await self._read_plot_data(plot_metadata)
            
        except Exception as e:
            return self.create_error_result(f"Failed to read plot thumbnail: {str(e)}")
    
    def _get_mime_type(self, format_ext: str) -> str:
        """Get MIME type for plot format.
        
        Args:
            format_ext: File format extension
            
        Returns:
            MIME type string
        """
        mime_types = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "svg": "image/svg+xml",
            "pdf": "application/pdf",
            "eps": "application/postscript",
            "ps": "application/postscript",
            "tiff": "image/tiff",
            "tif": "image/tiff",
            "bmp": "image/bmp"
        }
        
        return mime_types.get(format_ext.lower(), "application/octet-stream")
    
    async def create_plot_collection_resource(self) -> ResourceInfo:
        """Create a resource representing the entire plot collection.
        
        Returns:
            ResourceInfo for the plot collection
        """
        plots = self.plot_manager.list_plots()
        
        return ResourceInfo(
            uri="rstudio-plot://collection",
            name="Plot Collection",
            description=f"Collection of {len(plots)} plots",
            mime_type="application/json",
            metadata={
                "type": "collection",
                "plot_count": len(plots),
                "formats": list(set(p.format for p in plots)),
                "total_size": sum(p.size for p in plots),
                "date_range": {
                    "earliest": min(p.created_at for p in plots).isoformat() if plots else None,
                    "latest": max(p.created_at for p in plots).isoformat() if plots else None
                }
            }
        )
    
    async def read_plot_collection(self) -> ResourceResult:
        """Read the entire plot collection as JSON.
        
        Returns:
            ResourceResult with plot collection data
        """
        try:
            plots = self.plot_manager.list_plots()
            
            collection_data = {
                "type": "plot_collection",
                "count": len(plots),
                "plots": [plot.to_dict() for plot in plots],
                "summary": {
                    "formats": {},
                    "total_size": 0,
                    "date_range": {
                        "earliest": None,
                        "latest": None
                    }
                }
            }
            
            # Calculate summary statistics
            if plots:
                # Format distribution
                for plot in plots:
                    fmt = plot.format
                    collection_data["summary"]["formats"][fmt] = collection_data["summary"]["formats"].get(fmt, 0) + 1
                
                # Total size
                collection_data["summary"]["total_size"] = sum(p.size for p in plots)
                
                # Date range
                dates = [p.created_at for p in plots]
                collection_data["summary"]["date_range"]["earliest"] = min(dates).isoformat()
                collection_data["summary"]["date_range"]["latest"] = max(dates).isoformat()
            
            return self.create_json_result(collection_data)
            
        except Exception as e:
            return self.create_error_result(f"Failed to read plot collection: {str(e)}")
    
    async def search_plots(self, query: str, format_filter: Optional[str] = None, 
                          limit: Optional[int] = None) -> List[ResourceInfo]:
        """Search plots and return matching resources.
        
        Args:
            query: Search query
            format_filter: Optional format filter
            limit: Optional result limit
            
        Returns:
            List of matching plot resources
        """
        try:
            plots = self.plot_manager.list_plots(
                limit=limit,
                format_filter=format_filter,
                search_term=query
            )
            
            resources = []
            for plot in plots:
                plot_uri = f"rstudio-plot://{plot.plot_id}"
                resource = ResourceInfo(
                    uri=plot_uri,
                    name=f"Plot: {plot.title or plot.plot_id}",
                    description=plot.description or f"Plot generated on {plot.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
                    mime_type=self._get_mime_type(plot.format),
                    size=plot.size,
                    modified=plot.created_at.isoformat(),
                    metadata={
                        "plot_id": plot.plot_id,
                        "format": plot.format,
                        "match_score": self._calculate_match_score(plot, query)
                    }
                )
                resources.append(resource)
            
            return resources
            
        except Exception as e:
            self.logger.error(f"Error searching plots: {e}")
            return []
    
    def _calculate_match_score(self, plot: PlotMetadata, query: str) -> float:
        """Calculate relevance score for search query.
        
        Args:
            plot: Plot metadata
            query: Search query
            
        Returns:
            Match score between 0.0 and 1.0
        """
        query_lower = query.lower()
        score = 0.0
        
        # Title match (highest weight)
        if plot.title and query_lower in plot.title.lower():
            score += 0.4
        
        # Description match
        if plot.description and query_lower in plot.description.lower():
            score += 0.3
        
        # Code match
        if query_lower in plot.code.lower():
            score += 0.2
        
        # Format match
        if query_lower == plot.format.lower():
            score += 0.1
        
        return min(score, 1.0)
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        # The plot manager handles its own cleanup
        self.logger.info("Plot resource handler cleaned up")