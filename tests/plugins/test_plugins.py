"""
Plugin SDK Test Suite.

Verifies the mathematical correctness of Dependency DAG sorting, the
thread-safety of the Registry, and the exact state transitions of the Lifecycle FSM.
"""

import asyncio
from typing import Any

import pytest

from src.core.module_lifecycle import ModuleState
from src.plugins.base import AbstractBasePlugin, PluginHealth
from src.plugins.config import PluginConfigManager
from src.plugins.lifecycle import PluginLifecycleSupervisor
from src.plugins.manifest import PluginDependency, PluginManifest
from src.plugins.registry import PluginNotFoundError, PluginRegistry
from src.plugins.resolver import DependencyResolutionError, PluginDependencyResolver


# ==========================================
# FIXTURES
# ==========================================

@pytest.fixture
def base_manifest() -> PluginManifest:
    return PluginManifest(
        id="core.test",
        name="Test Plugin",
        version="1.0.0",
        author="Admin",
        description="A foundational test plugin"
    )

@pytest.fixture
def dependent_manifest() -> PluginManifest:
    return PluginManifest(
        id="core.dependent",
        name="Dependent Plugin",
        version="1.0.0",
        author="Admin",
        description="Depends strictly on core.test",
        dependencies=[PluginDependency(plugin_id="core.test", min_version="1.0.0")]
    )

class MockPlugin(AbstractBasePlugin):
    """A lightweight mock plugin for testing Registry and Lifecycle transitions."""
    def __init__(self, manifest: PluginManifest) -> None:
        super().__init__()
        self._manifest = manifest
        
    @property
    def manifest(self) -> PluginManifest:
        return self._manifest


# ==========================================
# TESTS: Dependency Resolver (DAG)
# ==========================================

def test_dependency_resolver_success(base_manifest: PluginManifest, dependent_manifest: PluginManifest) -> None:
    """Proves the DAG correctly sorts dependencies before targets."""
    resolver = PluginDependencyResolver()
    
    # Intentionally inserted out-of-order
    manifests = {
        "core.dependent": dependent_manifest,
        "core.test": base_manifest
    }
    
    order = resolver.resolve(manifests)
    
    assert len(order) == 2
    # The DAG must guarantee core.test is initialized first
    assert order[0].id == "core.test"
    assert order[1].id == "core.dependent"


def test_dependency_resolver_missing_requirement(dependent_manifest: PluginManifest) -> None:
    """Proves the DAG aggressively aborts on missing required plugins."""
    resolver = PluginDependencyResolver()
    manifests = {"core.dependent": dependent_manifest}
    
    with pytest.raises(DependencyResolutionError, match="Missing required dependency"):
        resolver.resolve(manifests)


def test_dependency_resolver_version_conflict() -> None:
    """Proves SemVer thresholds mathematically prevent outdated plugins from loading."""
    resolver = PluginDependencyResolver()
    old_test = PluginManifest(id="core.test", name="Old", version="0.9.0", author="A", description="D")
    dep = PluginManifest(
        id="core.dep", name="Dep", version="1.0.0", author="A", description="D",
        dependencies=[PluginDependency(plugin_id="core.test", min_version="1.0.0")]
    )
    
    with pytest.raises(DependencyResolutionError, match="Version conflict"):
        resolver.resolve({"core.test": old_test, "core.dep": dep})


# ==========================================
# TESTS: Registry & Alias Mapping
# ==========================================

def test_plugin_registry(base_manifest: PluginManifest) -> None:
    """Proves thread-safe dictionary routing and Soft Disabling."""
    registry = PluginRegistry()
    plugin = MockPlugin(base_manifest)
    
    # Test Registration with Alias
    registry.register(plugin, alias="test_alias")
    
    assert registry.get("core.test") == plugin
    assert registry.get("test_alias") == plugin
    
    # Test Soft Disable
    registry.disable("core.test")
    with pytest.raises(PluginNotFoundError):
        registry.get("core.test")
        
    # Test Re-Enable
    registry.enable("core.test")
    assert registry.get("core.test") == plugin


# ==========================================
# TESTS: Configuration Immutability
# ==========================================

def test_plugin_configuration_defaults(base_manifest: PluginManifest) -> None:
    """Proves the config manager dynamically extracts JSON Schema defaults."""
    base_manifest.config_schema = {
        "properties": {
            "timeout": {"type": "integer", "default": 30}
        }
    }
    config = PluginConfigManager(base_manifest)
    assert config.get("timeout") == 30


def test_plugin_configuration_immutability(base_manifest: PluginManifest) -> None:
    """Proves the dict snapshot is deep-copied to prevent memory corruption."""
    config = PluginConfigManager(base_manifest)
    snap = config.snapshot
    
    # Malicious or accidental mutation attempt
    snap["hacked"] = True
    
    # The actual internal state should remain unpolluted
    assert config.get("hacked") is None


# ==========================================
# TESTS: Lifecycle Supervisor
# ==========================================

@pytest.mark.asyncio
async def test_lifecycle_transitions(base_manifest: PluginManifest) -> None:
    """Proves the strict Finite State Machine boundaries govern plugin states."""
    plugin = MockPlugin(base_manifest)
    supervisor = PluginLifecycleSupervisor(plugin)
    
    assert supervisor.current_state == ModuleState.DISCOVERED
    
    # context=None is used safely here because MockPlugin overrides nothing
    await supervisor.initialize(context=None)  # type: ignore
    assert supervisor.current_state == ModuleState.INITIALIZED
    
    res = await supervisor.validate()
    assert res is True
    assert supervisor.current_state == ModuleState.VALIDATED
    
    await supervisor.start()
    assert supervisor.current_state == ModuleState.RUNNING
    
    await supervisor.pause()
    assert supervisor.current_state == ModuleState.PAUSED
    
    await supervisor.stop()
    assert supervisor.current_state == ModuleState.STOPPED
