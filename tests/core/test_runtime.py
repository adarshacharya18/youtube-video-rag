"""
Tests for the Application Runtime and Lifecycle Management.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.core.config import PipelineConfig
from src.core.container import Container, ValidationError
from src.core.exceptions import PipelineError
from src.core.runtime import ApplicationRuntime, RuntimeState


@pytest.fixture
def mock_config(tmp_path):
    """Provides a sterile, temporary configuration for tests."""
    return PipelineConfig(temp_dir=tmp_path)


@pytest.fixture
def runtime():
    """Provides a fresh Runtime instance per test."""
    return ApplicationRuntime()


# ==========================================
# Startup Tests
# ==========================================

@pytest.mark.asyncio
async def test_runtime_startup_success(runtime, mock_config):
    """Verifies the golden path: Config -> Health Checks -> DI Container -> Running."""
    with patch("src.core.runtime.load_config", return_value=mock_config):
        with patch("src.core.runtime.run_health_checks") as mock_health:
            with patch("src.core.runtime.build_container") as mock_build:
                await runtime.start()
                
                assert runtime._state == RuntimeState.RUNNING
                mock_health.assert_called_once()
                mock_build.assert_called_once()


@pytest.mark.asyncio
async def test_runtime_startup_failure_rolls_back(runtime):
    """Verifies that if Config or DI fails, the Runtime catches it and stops safely."""
    with patch("src.core.runtime.load_config", side_effect=Exception("Disk Error")):
        with pytest.raises(PipelineError, match="Runtime startup failed: Disk Error"):
            await runtime.start()
            
        assert runtime._state == RuntimeState.ERROR


# ==========================================
# Shutdown Tests
# ==========================================

@pytest.mark.asyncio
async def test_runtime_shutdown_sequence(runtime, mock_config):
    """Verifies that subsystems are shut down in the correct reverse order."""
    runtime._state = RuntimeState.RUNNING
    runtime.config = mock_config
    
    mock_workflow = AsyncMock()
    mock_plugin = AsyncMock()
    mock_bus = AsyncMock()
    
    runtime.workflow_engine = mock_workflow
    runtime.plugin_manager = mock_plugin
    runtime.event_bus = mock_bus
    
    await runtime.stop()
    
    assert runtime._state == RuntimeState.STOPPED
    mock_workflow.stop.assert_awaited_once()
    mock_plugin.stop.assert_awaited_once()
    mock_bus.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_runtime_shutdown_handles_timeouts(runtime, mock_config):
    """Verifies that if a plugin hangs forever, the runtime forcefully cuts it off."""
    runtime._state = RuntimeState.RUNNING
    runtime.config = mock_config
    
    mock_bus = AsyncMock()
    
    # We patch asyncio.wait_for to simulate a TimeoutError being thrown
    # when the runtime tries to drain the Event Bus.
    with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
        runtime.event_bus = mock_bus
        await runtime.stop()
        
    # The runtime MUST swallow the timeout and reach the STOPPED state safely
    assert runtime._state == RuntimeState.STOPPED


# ==========================================
# Configuration & Hot Reload Tests
# ==========================================

@pytest.mark.asyncio
async def test_runtime_hot_reload_success(runtime, mock_config):
    """Verifies that hot_reload updates the in-memory config without restarting."""
    runtime._state = RuntimeState.RUNNING
    runtime.config = mock_config
    
    # Change the config to simulate an admin updating an env var
    new_config = PipelineConfig(temp_dir=mock_config.temp_dir, log_level="DEBUG")
    
    with patch("src.core.runtime.load_config", return_value=new_config):
        await runtime.reload()
        
    assert runtime.config.log_level == "DEBUG"


# ==========================================
# Dependency Injection Tests
# ==========================================

def test_container_validation_failure():
    """Verifies the DI Container enforces structural types during registration."""
    from typing import Protocol, runtime_checkable

    @runtime_checkable
    class DuckProtocol(Protocol):
        def quack(self) -> str: ...

    class BadDuck:
        def bark(self) -> str: return "woof"

    container = Container()
    
    # Attempting to register a dog as a duck should instantly fail
    with pytest.raises(ValidationError, match="does not structurally implement Protocol"):
        container.register_singleton(DuckProtocol, BadDuck())


def test_container_circular_dependency():
    """Verifies that infinite DI recursion is caught and terminated."""
    from src.core.container import CircularDependencyError

    class ServiceA: pass
    class ServiceB: pass

    container = Container()
    
    # Create an infinite loop: A needs B, B needs A
    container.register_factory(ServiceA, lambda c: c.resolve(ServiceB))
    container.register_factory(ServiceB, lambda c: c.resolve(ServiceA))

    with pytest.raises(CircularDependencyError, match="Circular dependency detected"):
        container.resolve(ServiceA)
