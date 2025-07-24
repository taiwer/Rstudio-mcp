"""Integration tests for workspace management tools."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.rstudio_mcp.api_wrapper import ExecutionResult, RStudioAPIWrapper
from src.rstudio_mcp.tools.workspace_management_tools import (
    CleanWorkspaceTool,
    ListWorkspaceObjectsTool,
    LoadWorkspaceTool,
    SaveWorkspaceTool,
)


class MockRStudioAPI:
    """Mock RStudio API for integration testing."""
    
    def __init__(self):
        self.workspace_objects = {}
        self.workspace_files = {}
    
    async def execute_r_code(self, code: str, capture_plots: bool = True) -> ExecutionResult:
        """Mock R code execution with realistic behavior."""
        try:
            # Handle different R operations based on code content
            if "save(" in code and "file =" in code:
                return self._handle_save_workspace(code)
            elif "load(" in code:
                return self._handle_load_workspace(code)
            elif "rm(list = ls())" in code:
                return self._handle_clear_all(code)
            elif "rm(list =" in code and "c(" in code:
                return self._handle_remove_objects(code)
            elif "size_threshold" in code and "large_objects" in code:
                return self._handle_remove_large_objects(code)
            elif 'class(obj)[1] ==' in code:
                return self._handle_remove_by_class(code)
            elif "gc()" in code:
                return self._handle_garbage_collect(code)
            elif "ls(" in code or "object_names <-" in code:
                return self._handle_list_objects(code)
            elif "object.size(" in code:
                return self._handle_object_info(code)
            else:
                return ExecutionResult(success=True, output="")
                
        except Exception as e:
            return ExecutionResult(success=False, error=str(e))
    
    def _handle_save_workspace(self, code: str) -> ExecutionResult:
        """Handle workspace save operations."""
        # Extract file path from code
        import re
        file_match = re.search(r'file = "([^"]+)"', code)
        if not file_match:
            return ExecutionResult(success=False, error="No file path found")
        
        file_path = file_match.group(1)
        
        # Simulate saving workspace
        self.workspace_files[file_path] = dict(self.workspace_objects)
        
        object_count = len(self.workspace_objects)
        output = f"Workspace saved successfully\nObjects saved: {object_count}\nFile size: 1024 bytes\n"
        
        return ExecutionResult(success=True, output=output)
    
    def _handle_load_workspace(self, code: str) -> ExecutionResult:
        """Handle workspace load operations."""
        # Extract file path from code
        import re
        file_match = re.search(r'load\("([^"]+)"\)', code)
        if not file_match:
            return ExecutionResult(success=False, error="No file path found")
        
        file_path = file_match.group(1)
        
        # Check if file exists in our mock system
        if file_path not in self.workspace_files:
            return ExecutionResult(success=False, error="File not found")
        
        # Load objects from file
        self.workspace_objects.update(self.workspace_files[file_path])
        
        object_count = len(self.workspace_objects)
        object_names = ", ".join(self.workspace_objects.keys())
        output = f"Workspace loaded successfully\nObjects loaded: {object_count}\nObject names: {object_names}\n"
        
        return ExecutionResult(success=True, output=output)
    
    def _handle_list_objects(self, code: str) -> ExecutionResult:
        """Handle object listing operations."""
        if "jsonlite::toJSON" in code:
            # Return detailed object information
            if not self.workspace_objects:
                return ExecutionResult(success=True, output="工作空间为空\n{}")
            
            # Create mock object info
            obj_info = {}
            for name, obj_data in self.workspace_objects.items():
                obj_info[name] = {
                    "name": name,
                    "class": obj_data.get("class", "numeric"),
                    "type": obj_data.get("type", "double"),
                    "size": obj_data.get("size", 800),
                    "dimensions": obj_data.get("dimensions"),
                    "summary": f"{name} summary"
                }
            
            # Apply filtering if specified
            if 'class == "' in code:
                import re
                class_match = re.search(r'class == "([^"]+)"', code)
                if class_match:
                    filter_class = class_match.group(1)
                    obj_info = {k: v for k, v in obj_info.items() if v["class"] == filter_class}
            
            # Apply sorting if specified
            if 'sort_key <- "' in code:
                import re
                sort_match = re.search(r'sort_key <- "([^"]+)"', code)
                if sort_match:
                    sort_key = sort_match.group(1)
                    if sort_key == "name":
                        obj_info = dict(sorted(obj_info.items()))
                    elif sort_key == "size":
                        obj_info = dict(sorted(obj_info.items(), key=lambda x: x[1]["size"], reverse=True))
                    elif sort_key == "class":
                        obj_info = dict(sorted(obj_info.items(), key=lambda x: x[1]["class"]))
            
            object_count = len(obj_info)
            output = f"工作空间对象总数: {object_count}\n\n对象列表:\n"
            
            for name, info in obj_info.items():
                size_mb = round(info["size"] / 1024 / 1024, 3)
                dims_str = ""
                if info["dimensions"]:
                    if isinstance(info["dimensions"], list):
                        dims_str = f"[{' x '.join(map(str, info['dimensions']))}]"
                    else:
                        dims_str = f"[{info['dimensions']}]"
                
                output += f"  {name}: {info['class']} {dims_str} ({size_mb:.3f} MB)\n"
            
            output += f"\n{json.dumps(obj_info, indent=2)}"
            return ExecutionResult(success=True, output=output)
        else:
            # Simple object listing
            object_names = list(self.workspace_objects.keys())
            if not object_names:
                return ExecutionResult(success=True, output="")
            return ExecutionResult(success=True, output=" ".join(object_names))
    
    def _handle_clear_all(self, code: str) -> ExecutionResult:
        """Handle clear all objects operation."""
        object_count = len(self.workspace_objects)
        self.workspace_objects.clear()
        
        output = f"已清空所有工作空间对象\n删除对象数量: {object_count}\n垃圾回收结果:\n          used (Mb) gc trigger (Mb) max used (Mb)\nNcells  450000  24.1    1000000   53.4   750000  40.1\nVcells  900000  6.9    2000000   15.3  1500000  11.5\n"
        return ExecutionResult(success=True, output=output)
    
    def _handle_remove_objects(self, code: str) -> ExecutionResult:
        """Handle remove specific objects operation."""
        # Extract object names from code
        import re
        objects_match = re.search(r'c\(([^)]+)\)', code)
        if not objects_match:
            return ExecutionResult(success=True, output="没有找到要删除的对象\n")
        
        # Parse object names
        objects_str = objects_match.group(1)
        object_names = [name.strip().strip('"') for name in objects_str.split(',')]
        
        # Remove existing objects
        removed_objects = []
        missing_objects = []
        
        for name in object_names:
            if name in self.workspace_objects:
                del self.workspace_objects[name]
                removed_objects.append(name)
            else:
                missing_objects.append(name)
        
        output = ""
        if removed_objects:
            output += f"已删除对象: {', '.join(removed_objects)}\n"
        if missing_objects:
            output += f"未找到的对象: {', '.join(missing_objects)}\n"
        
        return ExecutionResult(success=True, output=output)
    
    def _handle_garbage_collect(self, code: str) -> ExecutionResult:
        """Handle garbage collection operation."""
        output = """垃圾回收完成
回收前内存使用:
          used (Mb) gc trigger (Mb) max used (Mb)
Ncells  500000  26.7    1000000   53.4   750000  40.1
Vcells 1000000  7.6    2000000   15.3  1500000  11.5

回收后内存使用:
          used (Mb) gc trigger (Mb) max used (Mb)
Ncells  450000  24.1    1000000   53.4   750000  40.1
Vcells  900000  6.9    2000000   15.3  1500000  11.5
"""
        return ExecutionResult(success=True, output=output)
    
    def _handle_remove_large_objects(self, code: str) -> ExecutionResult:
        """Handle remove large objects operation."""
        import re
        
        # Extract size threshold
        threshold_match = re.search(r'(\d+(?:\.\d+)?)\s*\*\s*1024\s*\*\s*1024', code)
        if not threshold_match:
            return ExecutionResult(success=False, error="No size threshold found")
        
        threshold_mb = float(threshold_match.group(1))
        threshold_bytes = threshold_mb * 1024 * 1024
        
        # Find and remove large objects
        large_objects = []
        object_sizes = []
        
        for name, obj_data in list(self.workspace_objects.items()):
            obj_size = obj_data.get("size", 800)
            if obj_size > threshold_bytes:
                large_objects.append(name)
                object_sizes.append(obj_size)
                del self.workspace_objects[name]
        
        if large_objects:
            output = f"已删除大对象 (>{threshold_mb}MB):\n"
            for i, name in enumerate(large_objects):
                size_mb = round(object_sizes[i] / 1024 / 1024, 2)
                output += f"  {name}: {size_mb}MB\n"
        else:
            output = f"没有找到大于 {threshold_mb}MB 的对象\n"
        
        return ExecutionResult(success=True, output=output)
    
    def _handle_remove_by_class(self, code: str) -> ExecutionResult:
        """Handle remove objects by class operation."""
        import re
        
        # Extract class name
        class_match = re.search(r'class\(obj\)\[1\]\s*==\s*"([^"]+)"', code)
        if not class_match:
            return ExecutionResult(success=False, error="No class filter found")
        
        target_class = class_match.group(1)
        
        # Find and remove objects of specified class
        objects_to_remove = []
        
        for name, obj_data in list(self.workspace_objects.items()):
            if obj_data.get("class") == target_class:
                objects_to_remove.append(name)
                del self.workspace_objects[name]
        
        if objects_to_remove:
            output = f"已删除类型为 '{target_class}' 的对象:\n"
            output += f"  {', '.join(objects_to_remove)}\n"
        else:
            output = f"没有找到类型为 '{target_class}' 的对象\n"
        
        return ExecutionResult(success=True, output=output)
    
    def _handle_object_info(self, code: str) -> ExecutionResult:
        """Handle object information queries."""
        # This is a simplified handler for object size and info queries
        return ExecutionResult(success=True, output="800")
    
    def add_mock_object(self, name: str, obj_class: str = "numeric", obj_type: str = "double", 
                       size: int = 800, dimensions=None):
        """Add a mock object to the workspace."""
        self.workspace_objects[name] = {
            "class": obj_class,
            "type": obj_type,
            "size": size,
            "dimensions": dimensions
        }


@pytest.fixture
def mock_api():
    """Create mock API for integration testing."""
    return MockRStudioAPI()


@pytest.fixture
def workspace_tools(mock_api):
    """Create workspace management tools with mock API."""
    return {
        "save": SaveWorkspaceTool(mock_api),
        "load": LoadWorkspaceTool(mock_api),
        "list": ListWorkspaceObjectsTool(mock_api),
        "clean": CleanWorkspaceTool(mock_api)
    }


class TestWorkspaceManagementIntegration:
    """Integration tests for workspace management tools."""
    
    @pytest.mark.asyncio
    async def test_complete_workspace_workflow(self, mock_api, workspace_tools):
        """Test complete workflow: create objects -> save -> clear -> load -> verify."""
        
        # 1. Setup initial workspace with mock objects
        mock_api.add_mock_object("x", "numeric", "double", 800, 100)
        mock_api.add_mock_object("y", "data.frame", "list", 2048, [10, 3])
        mock_api.add_mock_object("z", "character", "character", 400, 50)
        
        # 2. List initial objects
        list_result = await workspace_tools["list"].execute({
            "include_details": True,
            "sort_by": "name"
        })
        
        assert list_result.success is True
        assert "工作空间对象总数: 3" in list_result.content[1]["text"]
        assert "x: numeric" in list_result.content[1]["text"]
        assert "y: data.frame" in list_result.content[1]["text"]
        assert "z: character" in list_result.content[1]["text"]
        
        # Verify metadata
        assert list_result.metadata["object_count"] == 3
        assert "x" in list_result.metadata["objects"]
        
        # 3. Save workspace
        with tempfile.NamedTemporaryFile(suffix='.RData', delete=False) as f:
            temp_file = f.name
        
        try:
            save_result = await workspace_tools["save"].execute({
                "file_path": temp_file,
                "include_hidden": False,
                "compress": True,
                "overwrite": True
            })
            
            assert save_result.success is True
            assert "成功保存" in save_result.content[0]["text"]
            assert "Objects saved: 3" in save_result.content[1]["text"]
            
            # 4. Clear workspace
            clean_result = await workspace_tools["clean"].execute({
                "action": "clear_all",
                "confirm": True
            })
            
            assert clean_result.success is True
            assert "clear_all" in clean_result.content[0]["text"]
            assert "删除对象数量: 3" in clean_result.content[1]["text"]
            
            # 5. Verify workspace is empty
            empty_list_result = await workspace_tools["list"].execute({})
            assert empty_list_result.success is True
            assert "工作空间为空" in empty_list_result.content[1]["text"]
            
            # 6. Load workspace back
            load_result = await workspace_tools["load"].execute({
                "file_path": temp_file,
                "clear_current": False,
                "verbose": True
            })
            
            assert load_result.success is True
            assert "成功从文件加载" in load_result.content[0]["text"]
            assert "Objects loaded: 3" in load_result.content[1]["text"]
            assert "x, y, z" in load_result.content[1]["text"]
            
            # 7. Verify objects are restored
            final_list_result = await workspace_tools["list"].execute({
                "include_details": True
            })
            
            assert final_list_result.success is True
            assert "工作空间对象总数: 3" in final_list_result.content[1]["text"]
            
        finally:
            Path(temp_file).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_selective_object_removal(self, mock_api, workspace_tools):
        """Test selective removal of objects by different criteria."""
        
        # Setup workspace with different types of objects
        mock_api.add_mock_object("small_num", "numeric", "double", 800)
        mock_api.add_mock_object("large_df", "data.frame", "list", 15 * 1024 * 1024)  # 15MB
        mock_api.add_mock_object("medium_list", "list", "list", 5 * 1024 * 1024)  # 5MB
        mock_api.add_mock_object("another_df", "data.frame", "list", 2048)
        
        # 1. List all objects initially
        initial_list = await workspace_tools["list"].execute({"include_details": True})
        assert initial_list.success is True
        assert initial_list.metadata["object_count"] == 4
        
        # 2. Remove objects by name
        remove_result = await workspace_tools["clean"].execute({
            "action": "remove_objects",
            "object_names": ["small_num", "medium_list"],
            "confirm": True
        })
        
        assert remove_result.success is True
        assert "已删除对象: small_num, medium_list" in remove_result.content[1]["text"]
        
        # 3. Verify removal
        after_remove_list = await workspace_tools["list"].execute({})
        assert after_remove_list.success is True
        assert after_remove_list.metadata["object_count"] == 2
        
        # 4. Remove large objects (>10MB)
        remove_large_result = await workspace_tools["clean"].execute({
            "action": "remove_large",
            "size_threshold_mb": 10.0,
            "confirm": True
        })
        
        assert remove_large_result.success is True
        assert "已删除大对象" in remove_large_result.content[1]["text"]
        
        # 5. Remove by class
        remove_class_result = await workspace_tools["clean"].execute({
            "action": "remove_by_class",
            "object_class": "data.frame",
            "confirm": True
        })
        
        assert remove_class_result.success is True
        # Note: The exact output depends on what objects remain after previous operations
    
    @pytest.mark.asyncio
    async def test_workspace_filtering_and_sorting(self, mock_api, workspace_tools):
        """Test workspace object filtering and sorting functionality."""
        
        # Setup diverse workspace
        mock_api.add_mock_object("z_numeric", "numeric", "double", 1000)
        mock_api.add_mock_object("a_dataframe", "data.frame", "list", 5000, [100, 5])
        mock_api.add_mock_object("m_character", "character", "character", 500, 20)
        mock_api.add_mock_object("b_dataframe", "data.frame", "list", 3000, [50, 3])
        
        # 1. Test sorting by name (default)
        name_sorted = await workspace_tools["list"].execute({
            "sort_by": "name",
            "include_details": True
        })
        
        assert name_sorted.success is True
        # Objects should appear in alphabetical order in the output
        content = name_sorted.content[1]["text"]
        a_pos = content.find("a_dataframe")
        b_pos = content.find("b_dataframe")
        m_pos = content.find("m_character")
        z_pos = content.find("z_numeric")
        
        assert a_pos < b_pos < m_pos < z_pos
        
        # 2. Test sorting by size
        size_sorted = await workspace_tools["list"].execute({
            "sort_by": "size",
            "include_details": True
        })
        
        assert size_sorted.success is True
        # Should be sorted by size (largest first)
        
        # 3. Test filtering by class
        df_filtered = await workspace_tools["list"].execute({
            "filter_class": "data.frame",
            "include_details": True
        })
        
        assert df_filtered.success is True
        # Should only show data.frame objects
        content = df_filtered.content[1]["text"]
        assert "a_dataframe" in content
        assert "b_dataframe" in content
        assert "z_numeric" not in content
        assert "m_character" not in content
        
        # 4. Test including hidden objects (simulated)
        hidden_included = await workspace_tools["list"].execute({
            "include_hidden": True
        })
        
        assert hidden_included.success is True
    
    @pytest.mark.asyncio
    async def test_error_handling_scenarios(self, mock_api, workspace_tools):
        """Test error handling in various scenarios."""
        
        # 1. Try to load non-existent workspace file
        load_result = await workspace_tools["load"].execute({
            "file_path": "/nonexistent/path/workspace.RData"
        })
        
        assert load_result.success is False
        assert "文件不存在" in load_result.error
        
        # 2. Try to save without overwrite permission
        with tempfile.NamedTemporaryFile(suffix='.RData', delete=False) as f:
            existing_file = f.name
        
        try:
            save_result = await workspace_tools["save"].execute({
                "file_path": existing_file,
                "overwrite": False
            })
            
            assert save_result.success is False
            assert "已存在" in save_result.error
            
        finally:
            Path(existing_file).unlink(missing_ok=True)
        
        # 3. Try to remove objects without confirmation
        clean_result = await workspace_tools["clean"].execute({
            "action": "clear_all",
            "confirm": False
        })
        
        assert clean_result.success is False
        assert "confirm=true" in clean_result.error
        
        # 4. Try to remove objects without specifying names
        remove_result = await workspace_tools["clean"].execute({
            "action": "remove_objects",
            "confirm": True
        })
        
        assert remove_result.success is False
        assert "需要指定object_names参数" in remove_result.error
        
        # 5. Try to remove by class without specifying class
        class_result = await workspace_tools["clean"].execute({
            "action": "remove_by_class",
            "confirm": True
        })
        
        assert class_result.success is False
        assert "需要指定object_class参数" in class_result.error
    
    @pytest.mark.asyncio
    async def test_garbage_collection_integration(self, mock_api, workspace_tools):
        """Test garbage collection functionality."""
        
        # Add some objects to workspace
        mock_api.add_mock_object("test_obj", "numeric", "double", 1000)
        
        # Run garbage collection
        gc_result = await workspace_tools["clean"].execute({
            "action": "garbage_collect"
        })
        
        assert gc_result.success is True
        assert "垃圾回收完成" in gc_result.content[1]["text"]
        assert "回收前内存使用" in gc_result.content[1]["text"]
        assert "回收后内存使用" in gc_result.content[1]["text"]
        
        # Verify metadata
        assert gc_result.metadata["action"] == "garbage_collect"
    
    @pytest.mark.asyncio
    async def test_workspace_persistence_across_operations(self, mock_api, workspace_tools):
        """Test that workspace state persists correctly across multiple operations."""
        
        # 1. Start with empty workspace
        initial_list = await workspace_tools["list"].execute({})
        assert initial_list.success is True
        assert "工作空间为空" in initial_list.content[1]["text"]
        
        # 2. Add objects (simulated by directly adding to mock)
        mock_api.add_mock_object("persistent_obj", "numeric", "double", 800)
        
        # 3. Verify object exists
        list_with_obj = await workspace_tools["list"].execute({})
        assert list_with_obj.success is True
        assert list_with_obj.metadata["object_count"] == 1
        
        # 4. Save workspace
        with tempfile.NamedTemporaryFile(suffix='.RData', delete=False) as f:
            temp_file = f.name
        
        try:
            save_result = await workspace_tools["save"].execute({
                "file_path": temp_file,
                "overwrite": True
            })
            assert save_result.success is True
            
            # 5. Perform garbage collection (should not affect objects)
            gc_result = await workspace_tools["clean"].execute({
                "action": "garbage_collect"
            })
            assert gc_result.success is True
            
            # 6. Verify object still exists after GC
            list_after_gc = await workspace_tools["list"].execute({})
            assert list_after_gc.success is True
            assert list_after_gc.metadata["object_count"] == 1
            
            # 7. Clear workspace
            clear_result = await workspace_tools["clean"].execute({
                "action": "clear_all",
                "confirm": True
            })
            assert clear_result.success is True
            
            # 8. Verify workspace is empty
            empty_list = await workspace_tools["list"].execute({})
            assert empty_list.success is True
            assert "工作空间为空" in empty_list.content[1]["text"]
            
            # 9. Reload from saved file
            load_result = await workspace_tools["load"].execute({
                "file_path": temp_file
            })
            assert load_result.success is True
            
            # 10. Verify object is restored
            final_list = await workspace_tools["list"].execute({})
            assert final_list.success is True
            assert final_list.metadata["object_count"] == 1
            
        finally:
            Path(temp_file).unlink(missing_ok=True)