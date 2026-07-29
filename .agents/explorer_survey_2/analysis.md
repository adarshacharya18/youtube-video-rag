# Phase 09 Technical Analysis: Plugin SDK, Dynamic Plugin Loader, & In-Memory Entry Point Mocking

## Executive Summary

Phase 09 introduces an extensible Plugin SDK allowing third-party developers to inject custom pipeline processing nodes into the Workflow Engine via Python `entry_points` without altering core source code.

This technical analysis covers three core pillars:
1. **Python 3.10+ `importlib.metadata.entry_points()` Mechanics**: Modern entry point selection API, PEP 621 packaging standards, and entry point object lifecycle.
2. **Restricted Plugin SDK & Plugin Loader Architecture**: Designing `PluginNode` in `src/sdk/plugin_base.py`, state ledger isolation, dynamic loading/validation in `src/core/workflow/plugin_loader.py`, and adapting `PluginNode` to core `Node` via `PluginNodeAdapter`.
3. **In-Memory Pytest Mocking Strategy**: Safely mocking `importlib.metadata.entry_points()` in `tests/workflow/test_plugin_loader.py` without writing temporary files, `.dist-info` directories, or modifying disk state.

---

## 1. Python `importlib.metadata.entry_points()` Behavior (Python 3.10+)

### 1.1 API Evolution across Python Versions
- **Python < 3.10 (Legacy)**: `importlib.metadata.entry_points()` returned a standard Python dictionary mapping group names (`str`) to tuples/lists of `EntryPoint` objects (`dict[str, tuple[EntryPoint, ...]]`).
- **Python 3.10+ (Modern Standard)**:
  - `entry_points()` returns an `importlib.metadata.EntryPoints` collection (a tuple-like sequence of `EntryPoint` instances).
  - Dict-based key access `entry_points()["group_name"]` is **deprecated** and produces `DeprecationWarning` or errors.
  - The standard parameter-based query `importlib.metadata.entry_points(group="dsa.plugins")` returns an `EntryPoints` collection filtered to the specified group.
  - Alternatively, `importlib.metadata.entry_points().select(group="dsa.plugins")` can be called.

### 1.2 EntryPoint Object Attributes & Methods
An `importlib.metadata.EntryPoint` instance represents a registered entry point with the following key interface:

| Attribute / Method | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `.name` | `str` | Registered name of the entry point | `"custom_cleaner"` |
| `.value` | `str` | Object reference target string | `"my_package.module:CustomPluginClass"` |
| `.group` | `str` | Group namespace category | `"dsa.plugins"` |
| `.module` | `str` | Module path component of value | `"my_package.module"` |
| `.attr` | `str` | Object name within module | `"CustomPluginClass"` |
| `.load()` | `Callable` | Imports target module and returns attribute | `CustomPluginClass` |

### 1.3 How Entry Points Work for External Packages
Third-party packages register plugins in their `pyproject.toml` using PEP 621 entry points standard:

```toml
[project.entry-points."dsa.plugins"]
custom_summarizer = "dsa_ext_plugin.nodes:SummarizerPlugin"
custom_evaluator = "dsa_ext_plugin.nodes:EvaluatorPlugin"
```

When installed via `pip install .` or `pip install -e .`, python build backends write entry point metadata into `.dist-info/entry_points.txt`. `importlib.metadata` reads these metadata files at runtime without executing package code until `.load()` is invoked.

---

## 2. Architecture & Design of Plugin SDK & Plugin Loader

### 2.1 Restricted Plugin Interface (`src/sdk/plugin_base.py`)
To protect database integrity and maintain pipeline security, third-party plugins **must never** have direct access to the SQLite `StateLedger` or raw database connections.

```python
"""
Plugin SDK Interface for Third-Party Pipeline Node Extensions.
"""

from abc import ABC, abstractmethod
from typing import Any


class PluginNode(ABC):
    """
    Restricted Abstract Base Class for external plugin nodes.
    
    External plugins inherit from PluginNode. They receive input dictionaries
    and return output dictionaries. They do NOT receive direct access to
    StateLedger or run_id.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique name identifier for the plugin node.
        
        Returns:
            str: Unique plugin step name (e.g., 'custom_summarizer').
        """
        pass

    @abstractmethod
    def process(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """
        Execute isolated plugin processing logic.
        
        Args:
            inputs: Dictionary payload containing prior step outputs or run parameters.
            
        Returns:
            dict[str, Any]: Plugin processing output payload dictionary.
        """
        pass
```

### 2.2 Core Node Adapter (`PluginNodeAdapter`)
To execute `PluginNode` within `WorkflowEngine` (which expects `Node` instances), an internal `PluginNodeAdapter` class wraps the `PluginNode`:

```python
from src.core.orchestrator.state_ledger import StateLedger
from src.core.workflow.node import Node
from src.sdk.plugin_base import PluginNode

class PluginNodeAdapter(Node):
    """
    Adapter connecting restricted PluginNode instances to core WorkflowEngine Node contract.
    """

    def __init__(self, plugin: PluginNode) -> None:
        self.plugin = plugin

    @property
    def name(self) -> str:
        return self.plugin.name

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        # Collect prior step outputs from StateLedger securely on behalf of plugin
        inputs = self.get_completed_step_outputs(run_id, ledger)
        # Execute plugin logic in isolated context
        return self.plugin.process(inputs)
```

### 2.3 Dynamic Plugin Loader (`src/core/workflow/plugin_loader.py`)
`PluginLoader` discovers entry points under group `"dsa.plugins"`, loads target classes, verifies inheritance from `PluginNode`, and wraps them in `PluginNodeAdapter`.

```python
import importlib.metadata
from typing import Optional, Sequence

from src.core.exceptions import FatalError, PipelineStageError
from src.core.logger import get_logger
from src.core.workflow.node import Node
from src.sdk.plugin_base import PluginNode

logger = get_logger(__name__)


class PluginError(PipelineStageError):
    """Base exception for plugin loader errors."""
    pass


class PluginLoadError(PluginError):
    """Raised when an entry point fails to load (import error, missing attribute)."""
    pass


class PluginValidationError(PluginError):
    """Raised when a discovered plugin class fails PluginNode inheritance validation."""
    pass


class PluginLoader:
    """
    Dynamic discoverer and validator for third-party WorkflowEngine plugins.
    """

    DEFAULT_GROUP = "dsa.plugins"

    def __init__(self, group: str = DEFAULT_GROUP) -> None:
        self.group = group

    def discover_entry_points(() -> list[importlib.metadata.EntryPoint]:
        """Query importlib.metadata for entry points matching configured group."""
        try:
            eps = importlib.metadata.entry_points(group=self.group)
            return list(eps)
        except Exception as e:
            logger.error("Failed to query entry points", group=self.group, error=str(e))
            return []

    def load_and_validate(self, entry_point: importlib.metadata.EntryPoint) -> type[PluginNode]:
        """
        Load entry point and validate class inheritance.
        
        Raises:
            PluginLoadError: If loading module or attribute fails.
            PluginValidationError: If loaded object is not a subclass of PluginNode.
        """
        try:
            plugin_cls = entry_point.load()
        except Exception as e:
            logger.error("Failed to load plugin entry point", name=entry_point.name, error=str(e))
            raise PluginLoadError(f"Failed to load entry point '{entry_point.name}': {e}") from e

        if not isinstance(plugin_cls, type) or not issubclass(plugin_cls, PluginNode):
            logger.error("Plugin validation failed: does not inherit from PluginNode", name=entry_point.name)
            raise PluginValidationError(
                f"Plugin '{entry_point.name}' ({plugin_cls}) must be a class inheriting from PluginNode."
            )

        return plugin_cls

    def load_plugins(self) -> list[Node]:
        """
        Discover, load, validate, and instantiate all plugins as Node adapters.
        """
        eps = self.discover_entry_points()
        nodes: list[Node] = []

        for ep in eps:
            plugin_cls = self.load_and_validate(ep)
            instance = plugin_cls()
            nodes.append(PluginNodeAdapter(instance))

        return nodes
```

---

## 3. Pytest In-Memory Mocking Strategy for `importlib.metadata.entry_points()`

### 3.1 Why Disk-Based Mocking (Temp Files / `.dist-info`) Must Be Avoided
1. **Performance & Overhead**: Disk I/O during pytest execution slows test runs.
2. **Flakiness & Cleanup**: Leftover metadata files or incomplete teardown pollute global site-packages or sys.path.
3. **Environment Security**: Writing temp `.dist-info` files can pollute pytest cache or global virtual environments.

### 3.2 In-Memory Mock Pattern with `unittest.mock.patch`
Instead of creating files on disk, tests mock `importlib.metadata.entry_points` directly using `unittest.mock.patch` or pytest's `monkeypatch` fixture.

#### Example Mock EntryPoint Setup
```python
from unittest.mock import MagicMock, patch
import importlib.metadata
import pytest

from src.sdk.plugin_base import PluginNode
from src.core.workflow.plugin_loader import PluginLoader, PluginValidationError, PluginLoadError


class ValidDummyPlugin(PluginNode):
    @property
    def name(self) -> str:
        return "valid_dummy"

    def process(self, inputs: dict) -> dict:
        return {"processed": True, "input_received": inputs}


class InvalidDummyPlugin:
    """Does not inherit from PluginNode."""
    def name(self) -> str:
        return "invalid"


def create_mock_entry_point(name: str, target_class_or_fn: Any, group: str = "dsa.plugins"):
    """Helper to construct mock EntryPoint instances in memory."""
    mock_ep = MagicMock(spec=importlib.metadata.EntryPoint)
    mock_ep.name = name
    mock_ep.group = group
    mock_ep.value = f"mock_module:{target_class_or_fn.__name__}"
    mock_ep.load.return_value = target_class_or_fn
    return mock_ep
```

### 3.3 Test Suite Scenarios for `tests/workflow/test_plugin_loader.py`

| Test Case | Description | Expected Result |
| :--- | :--- | :--- |
| `test_plugin_loader_discovers_and_loads_valid_plugin` | Patch `entry_points` with `ValidDummyPlugin` mock. | `PluginLoader.load_plugins()` returns list containing `PluginNodeAdapter`, executable via `WorkflowEngine`. |
| `test_plugin_loader_rejects_non_plugin_node_class` | Patch `entry_points` with `InvalidDummyPlugin` mock. | `load_and_validate()` raises `PluginValidationError`. |
| `test_plugin_loader_rejects_function_or_primitive` | Patch `entry_points` returning a plain function. | `load_and_validate()` raises `PluginValidationError`. |
| `test_plugin_loader_handles_entry_point_load_exception` | Mock `entry_point.load.side_effect = ImportError(...)`. | `load_and_validate()` catches exception and raises `PluginLoadError`. |
| `test_plugin_loader_empty_entry_points` | Patch `entry_points` returning empty list `[]`. | `discover_plugins()` returns `[]` cleanly without error. |
| `test_plugin_adapter_executes_in_workflow_engine` | Wire `PluginNodeAdapter(ValidDummyPlugin())` into `WorkflowEngine`. | Engine executes step, passes inputs, records outputs in SQLite `StateLedger`. |

---

## 4. Verification & Testing Plan

1. **Verify Python 3.10+ Compatibility**:
   Ensure `importlib.metadata.entry_points(group=...)` functions identically under Python 3.10, 3.11, 3.12, and 3.13.
2. **Execute Full Workflow Test Suite**:
   Run `pytest tests/workflow/test_plugin_loader.py` to confirm zero disk I/O and 100% in-memory plugin discovery mocking.
3. **Verify Ledger Isolation**:
   Confirm that `PluginNode.process(inputs)` has no `ledger` parameter, preventing external code from executing SQL on `StateLedger`.
