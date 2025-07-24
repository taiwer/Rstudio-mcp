"""Tests for environment manager."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.rstudio_mcp.api_wrapper import ExecutionResult, RStudioAPIWrapper
from src.rstudio_mcp.environment_manager import (
    Environment,
    EnvironmentConfig,
    EnvironmentManager,
    EnvironmentStatus,
)
from src.rstudio_mcp.exceptions import EnvironmentError


class TestEnvironment:
    """Test Environment data model."""
    
    def test_environment_creation(self):
        """Test Environment model creation."""
        env = Environment(
            name="test_env",
            r_version="4.3.0",
            path="/path/to/env",
            packages=["base", "utils"],
            is_active=True
        )
        
        assert env.name == "test_env"
        assert env.r_version == "4.3.0"
        assert env.path == "/path/to/env"
        assert env.packages == ["base", "utils"]
        assert env.is_active is True
        assert isinstance(env.created_at, datetime)
    
    def test_environment_name_validation(self):
        """Test environment name validation."""
        # Valid name
        env = Environment(name="valid_name", r_version="4.3.0", path="/path")
        assert env.name == "valid_name"
        
        # Empty name should fail
        with pytest.raises(ValueError, match="Environment name cannot be empty"):
            Environment(name="", r_version="4.3.0", path="/path")
        
        # Invalid characters should fail
        with pytest.raises(ValueError, match="invalid characters"):
            Environment(name="invalid/name", r_version="4.3.0", path="/path")
    
    def test_environment_path_expansion(self):
        """Test path expansion in Environment model."""
        env = Environment(name="test", r_version="4.3.0", path="~/test_env")
        
        # Path should be expanded and resolved
        assert env.path == str(Path("~/test_env").expanduser().resolve())
    
    def test_environment_json_serialization(self):
        """Test Environment JSON serialization."""
        env = Environment(
            name="test_env",
            r_version="4.3.0",
            path="/path/to/env"
        )
        
        # Should be able to serialize to dict
        env_dict = env.dict()
        assert env_dict["name"] == "test_env"
        assert env_dict["r_version"] == "4.3.0"
        assert "created_at" in env_dict


class TestEnvironmentStatus:
    """Test EnvironmentStatus data model."""
    
    def test_environment_status_creation(self):
        """Test EnvironmentStatus creation."""
        status = EnvironmentStatus(
            name="test_env",
            is_active=True,
            r_version="4.3.0",
            package_count=10,
            health_status="healthy"
        )
        
        assert status.name == "test_env"
        assert status.is_active is True
        assert status.r_version == "4.3.0"
        assert status.package_count == 10
        assert status.health_status == "healthy"


class TestEnvironmentConfig:
    """Test EnvironmentConfig data model."""
    
    def test_environment_config_creation(self):
        """Test EnvironmentConfig creation."""
        config = EnvironmentConfig(
            name="test_env",
            r_version="4.3.0",
            description="Test environment",
            packages=["ggplot2", "dplyr"]
        )
        
        assert config.name == "test_env"
        assert config.r_version == "4.3.0"
        assert config.description == "Test environment"
        assert config.packages == ["ggplot2", "dplyr"]
    
    def test_environment_config_name_validation(self):
        """Test EnvironmentConfig name validation."""
        # Valid name
        config = EnvironmentConfig(name="valid_name")
        assert config.name == "valid_name"
        
        # Empty name should fail
        with pytest.raises(ValueError, match="Environment name cannot be empty"):
            EnvironmentConfig(name="")


class TestEnvironmentManager:
    """Test EnvironmentManager class."""
    
    @pytest.fixture
    def mock_api_wrapper(self):
        """Mock API wrapper."""
        api = Mock(spec=RStudioAPIWrapper)
        api.get_r_version = AsyncMock(return_value="4.3.0")
        api.execute_r_code = AsyncMock(return_value=ExecutionResult(success=True))
        return api
    
    @pytest.fixture
    def temp_base_path(self):
        """Temporary base path for environments."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def env_manager(self, mock_api_wrapper, temp_base_path):
        """Environment manager instance."""
        return EnvironmentManager(mock_api_wrapper, temp_base_path)
    
    def test_initialization(self, env_manager, temp_base_path):
        """Test EnvironmentManager initialization."""
        assert env_manager.base_path == Path(temp_base_path).resolve()
        assert env_manager.base_path.exists()
        assert env_manager.registry_file.name == "environments.json"
        assert isinstance(env_manager._environments, dict)
    
    def test_load_empty_registry(self, env_manager):
        """Test loading empty registry."""
        # Should start with empty environments
        assert len(env_manager._environments) == 0
    
    def test_load_existing_registry(self, mock_api_wrapper, temp_base_path):
        """Test loading existing registry."""
        # Create a registry file
        registry_file = Path(temp_base_path) / "environments.json"
        registry_data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "environments": [
                {
                    "name": "test_env",
                    "r_version": "4.3.0",
                    "path": str(Path(temp_base_path) / "test_env"),
                    "packages": ["base"],
                    "is_active": False,
                    "created_at": datetime.now().isoformat(),
                    "description": None
                }
            ]
        }
        
        with open(registry_file, 'w') as f:
            json.dump(registry_data, f)
        
        # Create manager - should load existing registry
        manager = EnvironmentManager(mock_api_wrapper, temp_base_path)
        
        assert len(manager._environments) == 1
        assert "test_env" in manager._environments
        assert manager._environments["test_env"].name == "test_env"
    
    @pytest.mark.asyncio
    async def test_create_environment_basic(self, env_manager, temp_base_path):
        """Test basic environment creation."""
        config = EnvironmentConfig(name="test_env", description="Test environment")
        
        environment = await env_manager.create_environment(config)
        
        assert environment.name == "test_env"
        assert environment.r_version == "4.3.0"  # From mock
        assert environment.description == "Test environment"
        assert Path(environment.path).resolve() == Path(temp_base_path).resolve() / "test_env"
        
        # Check environment was registered
        assert "test_env" in env_manager._environments
        
        # Check directory was created
        env_path = Path(environment.path)
        assert env_path.exists()
        assert (env_path / "library").exists()
        assert (env_path / ".Rprofile").exists()
    
    @pytest.mark.asyncio
    async def test_create_environment_with_packages(self, env_manager):
        """Test environment creation with packages."""
        config = EnvironmentConfig(
            name="test_env",
            packages=["ggplot2", "dplyr"]
        )
        
        environment = await env_manager.create_environment(config)
        
        # Should have attempted to install packages
        assert env_manager.api.execute_r_code.call_count >= 2  # At least one call per package
        
        # Check packages were added to environment
        assert "ggplot2" in environment.packages
        assert "dplyr" in environment.packages
    
    @pytest.mark.asyncio
    async def test_create_environment_duplicate_name(self, env_manager):
        """Test creating environment with duplicate name."""
        config = EnvironmentConfig(name="test_env")
        
        # Create first environment
        await env_manager.create_environment(config)
        
        # Try to create duplicate
        with pytest.raises(EnvironmentError, match="already exists"):
            await env_manager.create_environment(config)
    
    @pytest.mark.asyncio
    async def test_create_environment_failure_cleanup(self, env_manager, temp_base_path):
        """Test cleanup on environment creation failure."""
        config = EnvironmentConfig(name="test_env")
        
        # Make registry save fail
        with patch.object(env_manager, '_save_registry', side_effect=Exception("Registry save failed")):
            with pytest.raises(EnvironmentError, match="Failed to create environment"):
                await env_manager.create_environment(config)
        
        # Environment should not be registered
        assert "test_env" not in env_manager._environments
        
        # Directory should be cleaned up
        env_path = Path(temp_base_path) / "test_env"
        assert not env_path.exists()
    
    @pytest.mark.asyncio
    async def test_list_environments(self, env_manager):
        """Test listing environments."""
        # Create test environments
        config1 = EnvironmentConfig(name="env1")
        config2 = EnvironmentConfig(name="env2")
        
        await env_manager.create_environment(config1)
        await env_manager.create_environment(config2)
        
        environments = await env_manager.list_environments()
        
        assert len(environments) == 2
        env_names = [env.name for env in environments]
        assert "env1" in env_names
        assert "env2" in env_names
    
    @pytest.mark.asyncio
    async def test_get_environment(self, env_manager):
        """Test getting environment by name."""
        config = EnvironmentConfig(name="test_env")
        created_env = await env_manager.create_environment(config)
        
        # Get existing environment
        retrieved_env = await env_manager.get_environment("test_env")
        assert retrieved_env is not None
        assert retrieved_env.name == "test_env"
        
        # Get non-existent environment
        missing_env = await env_manager.get_environment("missing_env")
        assert missing_env is None
    
    @pytest.mark.asyncio
    async def test_delete_environment(self, env_manager, temp_base_path):
        """Test environment deletion."""
        config = EnvironmentConfig(name="test_env")
        environment = await env_manager.create_environment(config)
        
        env_path = Path(environment.path)
        assert env_path.exists()
        
        # Delete environment
        success = await env_manager.delete_environment("test_env")
        
        assert success is True
        assert "test_env" not in env_manager._environments
        assert not env_path.exists()
    
    @pytest.mark.asyncio
    async def test_delete_active_environment_without_force(self, env_manager):
        """Test deleting active environment without force."""
        config = EnvironmentConfig(name="test_env")
        environment = await env_manager.create_environment(config)
        
        # Make environment active
        environment.is_active = True
        
        # Should fail without force
        with pytest.raises(EnvironmentError, match="Cannot delete active environment"):
            await env_manager.delete_environment("test_env")
    
    @pytest.mark.asyncio
    async def test_delete_active_environment_with_force(self, env_manager):
        """Test deleting active environment with force."""
        config = EnvironmentConfig(name="test_env")
        environment = await env_manager.create_environment(config)
        
        # Make environment active
        environment.is_active = True
        
        # Should succeed with force
        success = await env_manager.delete_environment("test_env", force=True)
        assert success is True
        assert "test_env" not in env_manager._environments
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_environment(self, env_manager):
        """Test deleting non-existent environment."""
        with pytest.raises(EnvironmentError, match="not found"):
            await env_manager.delete_environment("missing_env")
    
    @pytest.mark.asyncio
    async def test_switch_environment(self, env_manager):
        """Test switching environments."""
        # Create two environments
        config1 = EnvironmentConfig(name="env1")
        config2 = EnvironmentConfig(name="env2")
        
        env1 = await env_manager.create_environment(config1)
        env2 = await env_manager.create_environment(config2)
        
        # Make env1 active
        env1.is_active = True
        
        # Switch to env2
        success = await env_manager.switch_environment("env2")
        
        assert success is True
        assert not env1.is_active
        assert env2.is_active
        
        # Verify R code was executed to switch
        env_manager.api.execute_r_code.assert_called()
    
    @pytest.mark.asyncio
    async def test_switch_to_nonexistent_environment(self, env_manager):
        """Test switching to non-existent environment."""
        with pytest.raises(EnvironmentError, match="not found"):
            await env_manager.switch_environment("missing_env")
    
    @pytest.mark.asyncio
    async def test_switch_environment_failure(self, env_manager):
        """Test environment switch failure."""
        config = EnvironmentConfig(name="test_env")
        environment = await env_manager.create_environment(config)
        
        # Make R execution fail
        env_manager.api.execute_r_code.return_value = ExecutionResult(
            success=False, error="R execution failed"
        )
        
        with pytest.raises(EnvironmentError, match="Failed to switch environment"):
            await env_manager.switch_environment("test_env")
    
    @pytest.mark.asyncio
    async def test_get_environment_status(self, env_manager):
        """Test getting environment status."""
        config = EnvironmentConfig(name="test_env")
        environment = await env_manager.create_environment(config)
        
        status = await env_manager.get_environment_status("test_env")
        
        assert status is not None
        assert status.name == "test_env"
        assert status.r_version == "4.3.0"
        assert status.health_status in ["healthy", "warning", "error"]
        assert isinstance(status.package_count, int)
    
    @pytest.mark.asyncio
    async def test_get_status_nonexistent_environment(self, env_manager):
        """Test getting status of non-existent environment."""
        status = await env_manager.get_environment_status("missing_env")
        assert status is None
    
    @pytest.mark.asyncio
    async def test_validate_environment(self, env_manager):
        """Test environment validation."""
        config = EnvironmentConfig(name="test_env")
        environment = await env_manager.create_environment(config)
        
        validation = await env_manager.validate_environment("test_env")
        
        assert validation["valid"] is True
        assert validation["name"] == "test_env"
        assert "checks" in validation
        assert validation["checks"]["directory_exists"] is True
        assert validation["checks"]["r_profile_exists"] is True
        assert validation["checks"]["library_directory_exists"] is True
    
    @pytest.mark.asyncio
    async def test_validate_nonexistent_environment(self, env_manager):
        """Test validating non-existent environment."""
        validation = await env_manager.validate_environment("missing_env")
        
        assert validation["valid"] is False
        assert "not found" in validation["error"]
    
    @pytest.mark.asyncio
    async def test_validate_corrupted_environment(self, env_manager, temp_base_path):
        """Test validating corrupted environment."""
        config = EnvironmentConfig(name="test_env")
        environment = await env_manager.create_environment(config)
        
        # Remove R profile to simulate corruption
        r_profile = Path(environment.path) / ".Rprofile"
        r_profile.unlink()
        
        validation = await env_manager.validate_environment("test_env")
        
        assert validation["valid"] is False
        assert validation["checks"]["r_profile_exists"] is False
    
    def test_save_and_load_registry(self, env_manager, temp_base_path):
        """Test saving and loading registry."""
        # Create environment manually
        env = Environment(
            name="test_env",
            r_version="4.3.0",
            path=str(Path(temp_base_path) / "test_env"),
            packages=["base", "utils"]
        )
        env_manager._environments["test_env"] = env
        
        # Save registry
        env_manager._save_registry()
        
        # Verify registry file exists
        assert env_manager.registry_file.exists()
        
        # Create new manager and verify it loads the registry
        new_manager = EnvironmentManager(env_manager.api, temp_base_path)
        
        assert len(new_manager._environments) == 1
        assert "test_env" in new_manager._environments
        loaded_env = new_manager._environments["test_env"]
        assert loaded_env.name == "test_env"
        assert loaded_env.r_version == "4.3.0"
        assert loaded_env.packages == ["base", "utils"]
    
    def test_cleanup(self, env_manager):
        """Test environment manager cleanup."""
        # Should not raise any exceptions
        env_manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_copy_environment(self, env_manager):
        """Test copying from existing environment."""
        # Create source environment with packages
        source_config = EnvironmentConfig(
            name="source_env",
            packages=["ggplot2", "dplyr"]
        )
        source_env = await env_manager.create_environment(source_config)
        
        # Create target environment copying from source
        target_config = EnvironmentConfig(
            name="target_env",
            copy_from="source_env"
        )
        target_env = await env_manager.create_environment(target_config)
        
        # Target should have same packages as source
        assert "ggplot2" in target_env.packages
        assert "dplyr" in target_env.packages
    
    @pytest.mark.asyncio
    async def test_copy_from_nonexistent_environment(self, env_manager):
        """Test copying from non-existent environment."""
        config = EnvironmentConfig(
            name="target_env",
            copy_from="missing_env"
        )
        
        with pytest.raises(EnvironmentError, match="Source environment .* not found"):
            await env_manager.create_environment(config)


@pytest.mark.integration
class TestEnvironmentManagerIntegration:
    """Integration tests for EnvironmentManager."""
    
    @pytest.mark.asyncio
    async def test_full_environment_lifecycle(self):
        """Test complete environment lifecycle."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock API wrapper
            api = Mock(spec=RStudioAPIWrapper)
            api.get_r_version = AsyncMock(return_value="4.3.0")
            api.execute_r_code = AsyncMock(return_value=ExecutionResult(success=True))
            
            manager = EnvironmentManager(api, temp_dir)
            
            # Create environment
            config = EnvironmentConfig(
                name="integration_test",
                description="Integration test environment",
                packages=["base"]
            )
            
            environment = await manager.create_environment(config)
            assert environment.name == "integration_test"
            
            # List environments
            environments = await manager.list_environments()
            assert len(environments) == 1
            
            # Get environment status
            status = await manager.get_environment_status("integration_test")
            assert status is not None
            assert status.name == "integration_test"
            
            # Validate environment
            validation = await manager.validate_environment("integration_test")
            assert validation["valid"] is True
            
            # Switch environment
            success = await manager.switch_environment("integration_test")
            assert success is True
            
            # Delete environment
            success = await manager.delete_environment("integration_test", force=True)
            assert success is True
            
            # Verify deletion
            environments = await manager.list_environments()
            assert len(environments) == 0