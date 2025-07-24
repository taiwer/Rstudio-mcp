"""Resource manager for RStudio MCP Server."""

import logging
from typing import Any, Dict, List, Optional, Type
from urllib.parse import urlparse

from .base import BaseResource, ResourceInfo, ResourceResult


class ResourceManager:
    """Manager for MCP resources."""
    
    def __init__(self):
        """Initialize the resource manager."""
        self.logger = logging.getLogger(__name__)
        self._resources: Dict[str, BaseResource] = {}
        self._resource_classes: Dict[str, Type[BaseResource]] = {}
        self._cache: Dict[str, Any] = {}
        self._cache_enabled = True
        self._cache_ttl = 300  # 5 minutes default TTL
    
    def register_resource(self, resource: BaseResource) -> None:
        """Register a resource handler instance.
        
        Args:
            resource: Resource handler instance to register
            
        Raises:
            ValueError: If resource scheme already exists
        """
        if resource.scheme in self._resources:
            raise ValueError(f"Resource scheme '{resource.scheme}' is already registered")
        
        self._resources[resource.scheme] = resource
        self.logger.info("Registered resource handler: %s", resource.scheme)
    
    def register_resource_class(self, resource_class: Type[BaseResource], 
                              scheme: Optional[str] = None) -> None:
        """Register a resource class for lazy instantiation.
        
        Args:
            resource_class: Resource class to register
            scheme: Optional scheme override (uses class scheme if not provided)
            
        Raises:
            ValueError: If resource scheme already exists
        """
        # Get scheme from class if not provided
        if scheme is None:
            # Create temporary instance to get scheme
            temp_instance = resource_class()
            scheme = temp_instance.scheme
        
        if scheme in self._resource_classes or scheme in self._resources:
            raise ValueError(f"Resource scheme '{scheme}' is already registered")
        
        self._resource_classes[scheme] = resource_class
        self.logger.info("Registered resource class: %s", scheme)
    
    def unregister_resource(self, scheme: str) -> bool:
        """Unregister a resource handler.
        
        Args:
            scheme: Resource scheme to unregister
            
        Returns:
            True if resource was unregistered, False if not found
        """
        removed = False
        
        if scheme in self._resources:
            del self._resources[scheme]
            removed = True
        
        if scheme in self._resource_classes:
            del self._resource_classes[scheme]
            removed = True
        
        # Clear cache entries for this scheme
        cache_keys_to_remove = [key for key in self._cache.keys() if key.startswith(f"{scheme}:")]
        for key in cache_keys_to_remove:
            del self._cache[key]
        
        if removed:
            self.logger.info("Unregistered resource handler: %s", scheme)
        
        return removed
    
    def get_resource_handler(self, scheme: str) -> Optional[BaseResource]:
        """Get a resource handler by scheme.
        
        Args:
            scheme: Resource scheme
            
        Returns:
            Resource handler instance or None if not found
        """
        # Check if already instantiated
        if scheme in self._resources:
            return self._resources[scheme]
        
        # Check if we have a class to instantiate
        if scheme in self._resource_classes:
            try:
                resource_class = self._resource_classes[scheme]
                resource_instance = resource_class()
                
                # Move from class registry to instance registry
                self._resources[scheme] = resource_instance
                del self._resource_classes[scheme]
                
                self.logger.debug("Instantiated resource handler: %s", scheme)
                return resource_instance
                
            except Exception as e:
                self.logger.error("Failed to instantiate resource handler '%s': %s", scheme, e)
                return None
        
        return None
    
    def list_schemes(self) -> List[str]:
        """List all available resource schemes.
        
        Returns:
            List of resource schemes
        """
        return list(set(self._resources.keys()) | set(self._resource_classes.keys()))
    
    async def list_all_resources(self, uri_prefix: Optional[str] = None) -> List[ResourceInfo]:
        """List all available resources from all handlers.
        
        Args:
            uri_prefix: Optional URI prefix to filter resources
            
        Returns:
            List of all available resources
        """
        all_resources = []
        
        # Determine which schemes to query
        schemes_to_query = self.list_schemes()
        
        if uri_prefix:
            try:
                parsed = urlparse(uri_prefix)
                if parsed.scheme:
                    # Filter to specific scheme if URI prefix has one
                    schemes_to_query = [parsed.scheme] if parsed.scheme in schemes_to_query else []
            except Exception:
                pass
        
        # Query each scheme
        for scheme in schemes_to_query:
            handler = self.get_resource_handler(scheme)
            if handler:
                try:
                    # Check cache first
                    cache_key = f"{scheme}:list:{uri_prefix or ''}"
                    if self._cache_enabled and cache_key in self._cache:
                        cached_resources = self._cache[cache_key]
                        all_resources.extend(cached_resources)
                        self.logger.debug("Used cached resources for scheme: %s", scheme)
                        continue
                    
                    # Get resources from handler
                    resources = await handler.safe_list_resources(uri_prefix)
                    all_resources.extend(resources)
                    
                    # Cache the results
                    if self._cache_enabled:
                        self._cache[cache_key] = resources
                    
                except Exception as e:
                    self.logger.error("Error listing resources for scheme '%s': %s", scheme, e)
        
        self.logger.info("Listed %d total resources", len(all_resources))
        return all_resources
    
    async def read_resource(self, uri: str) -> ResourceResult:
        """Read a resource by URI.
        
        Args:
            uri: Resource URI
            
        Returns:
            Resource content and metadata
        """
        try:
            parsed = urlparse(uri)
            scheme = parsed.scheme
            
            if not scheme:
                return ResourceResult(
                    success=False,
                    error=f"Invalid URI format (missing scheme): {uri}"
                )
            
            # Check cache first
            cache_key = f"{scheme}:read:{uri}"
            if self._cache_enabled and cache_key in self._cache:
                cached_result = self._cache[cache_key]
                self.logger.debug("Used cached resource: %s", uri)
                return cached_result
            
            # Get handler for scheme
            handler = self.get_resource_handler(scheme)
            if not handler:
                return ResourceResult(
                    success=False,
                    error=f"No resource handler found for scheme: {scheme}"
                )
            
            # Read resource
            result = await handler.safe_read_resource(uri)
            
            # Cache successful results
            if self._cache_enabled and result.success:
                self._cache[cache_key] = result
            
            return result
            
        except Exception as e:
            error_msg = f"Error reading resource {uri}: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return ResourceResult(
                success=False,
                error=error_msg
            )
    
    def get_resource_definitions(self) -> List[Dict[str, Any]]:
        """Get MCP resource definitions for all registered handlers.
        
        Returns:
            List of MCP resource definitions
        """
        definitions = []
        
        # Get definitions from instantiated handlers
        for handler in self._resources.values():
            try:
                # Get sample resources to create definitions
                # Note: This is a simplified approach - in practice you might want
                # to have handlers provide their own definitions
                definition = {
                    "scheme": handler.scheme,
                    "description": handler.description,
                    "examples": []  # Could be populated by handlers
                }
                definitions.append(definition)
            except Exception as e:
                self.logger.error("Failed to get definition for resource handler '%s': %s", 
                                handler.scheme, e)
        
        # Get definitions from resource classes (instantiate temporarily)
        for scheme, resource_class in self._resource_classes.items():
            try:
                temp_instance = resource_class()
                definition = {
                    "scheme": temp_instance.scheme,
                    "description": temp_instance.description,
                    "examples": []
                }
                definitions.append(definition)
            except Exception as e:
                self.logger.error("Failed to get definition for resource class '%s': %s", 
                                scheme, e)
        
        return definitions
    
    def discover_resources(self, module_path: str) -> int:
        """Discover and register resource handlers from a module.
        
        Args:
            module_path: Python module path to search for resource handlers
            
        Returns:
            Number of resource handlers discovered and registered
        """
        import importlib
        import inspect
        
        try:
            module = importlib.import_module(module_path)
            discovered_count = 0
            
            # Find all BaseResource subclasses in the module
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, BaseResource) and 
                    obj is not BaseResource and 
                    not inspect.isabstract(obj)):
                    
                    try:
                        self.register_resource_class(obj)
                        discovered_count += 1
                    except ValueError as e:
                        self.logger.warning("Skipped resource class '%s': %s", name, e)
            
            self.logger.info("Discovered %d resource handlers from module: %s", 
                           discovered_count, module_path)
            return discovered_count
            
        except Exception as e:
            self.logger.error("Failed to discover resources from module '%s': %s", 
                            module_path, e)
            return 0
    
    def get_resource_info(self, scheme: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a resource handler.
        
        Args:
            scheme: Resource scheme
            
        Returns:
            Resource handler information dictionary or None if not found
        """
        handler = self.get_resource_handler(scheme)
        
        if handler is None:
            return None
        
        return {
            "scheme": handler.scheme,
            "description": handler.description,
            "class": handler.__class__.__name__,
            "module": handler.__class__.__module__
        }
    
    def clear_cache(self, scheme: Optional[str] = None) -> None:
        """Clear resource cache.
        
        Args:
            scheme: Optional scheme to clear cache for (clears all if None)
        """
        if scheme:
            # Clear cache for specific scheme
            cache_keys_to_remove = [key for key in self._cache.keys() 
                                  if key.startswith(f"{scheme}:")]
            for key in cache_keys_to_remove:
                del self._cache[key]
            self.logger.info("Cleared cache for scheme: %s", scheme)
        else:
            # Clear all cache
            cache_count = len(self._cache)
            self._cache.clear()
            self.logger.info("Cleared %d cache entries", cache_count)
    
    def set_cache_enabled(self, enabled: bool) -> None:
        """Enable or disable resource caching.
        
        Args:
            enabled: Whether to enable caching
        """
        self._cache_enabled = enabled
        if not enabled:
            self.clear_cache()
        self.logger.info("Resource caching %s", "enabled" if enabled else "disabled")
    
    def set_cache_ttl(self, ttl: int) -> None:
        """Set cache time-to-live.
        
        Args:
            ttl: Cache TTL in seconds
        """
        self._cache_ttl = ttl
        self.logger.info("Set cache TTL to %d seconds", ttl)
    
    def clear_resources(self) -> None:
        """Clear all registered resource handlers."""
        count = len(self._resources) + len(self._resource_classes)
        self._resources.clear()
        self._resource_classes.clear()
        self.clear_cache()
        self.logger.info("Cleared %d resource handlers", count)
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        # Call cleanup on handlers that support it
        for handler in self._resources.values():
            if hasattr(handler, 'cleanup') and callable(getattr(handler, 'cleanup')):
                try:
                    cleanup_method = getattr(handler, 'cleanup')
                    import inspect
                    if inspect.iscoroutinefunction(cleanup_method):
                        await cleanup_method()
                    else:
                        cleanup_method()
                except Exception as e:
                    self.logger.warning("Error during cleanup of resource handler '%s': %s", 
                                      handler.scheme, e)
        
        # Clear cache
        self.clear_cache()
        
        self.logger.info("Resource manager cleaned up")