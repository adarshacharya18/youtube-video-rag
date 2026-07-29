# Technical Analysis & Architectural Survey: Phase 09 Plugin SDK

## Executive Summary

Phase 09 introduces an extensible, secure **Plugin SDK** for the Automated DSA Educational YouTube Video Pipeline. Utilizing Python's native `importlib.metadata` `entry_points` mechanism, external developers can build and distribute standalone Python packages containing custom pipeline nodes. These custom nodes can be dynamically discovered and injected into the Phase 08 `WorkflowEngine` without modifying core codebase files.

To prevent third-party plugins from corrupting the system state or attempting unauthorized database modifications, Phase 09 enforces a **Restricted Plugin Execution Model**. External plugins inherit from a restricted `PluginNode` interface (`src/sdk/plugin_base.py`) that strictly exposes a pure functional `process(inputs: dict[str, Any]) -> dict[str, Any]` interface. External plugins are explicitly denied direct access to the `StateLedger` (SQLite database). Instead, the core pipeline uses an adapter (`PluginNodeAdapter` in `src/core/workflow/plugin_loader.py`) to handle ledger state retrieval, input extraction, output recording, and idempotency tracking on behalf of the plugin.

---

## 1. Required Documentation Specification: `PromptBook/Phase09/01_Plugin_SDK.md`

`PromptBook/Phase09/01_Plugin_SDK.md` must be created to serve as the definitive specification and developer manual for the Phase 09 Plugin SDK. It should contain the following 6 core sections:

### Section 1: Executive Summary & Architectural Overview
- **Goal**: Explain how third-party plugins extend the video generation pipeline seamlessly.
- **Architectural Diagram**: ASCII or Mermaid sequence showing `WorkflowEngine` -> `PluginNodeAdapter` -> `PluginNode` -> `StateLedger`.
- **Isolation Principle**: Detail why direct `StateLedger` access is denied to third-party code and how the core engine acts as a secure intermediary.

### Section 2: Package Structure & Entry Point Configuration
- **Standard Package Layout**: Show directory tree for external plugin packages.
- **`pyproject.toml` Entry Points**:
  ```toml
  [project.entry-points."youtube_pipeline.plugins"]
  custom_analyzer = "my_plugin_package.module:CustomAnalyzerNode"
  ```
- **`setup.py` Entry Points (Legacy support)**:
  ```python
  from setuptools import setup

  setup(
      name="my_plugin_package",
      version="0.1.0",
      entry_points={
          "youtube_pipeline.plugins": [
              "custom_analyzer = my_plugin_package.module:CustomAnalyzerNode",
          ],
      },
  )
  ```
- **Group Naming Standard**: `youtube_pipeline.plugins`.

### Section 3: Restricted Plugin Lifecycle (`PluginNode`)
- **Location**: `src/sdk/plugin_base.py`.
- **Class Contract**: `PluginNode(ABC)` with abstract property `name` and abstract method `process(inputs: dict[str, Any]) -> dict[str, Any]`.
- **Input Payload Guarantee**: `inputs` contains read-only dictionary of prior step outputs (`inputs["prior_outputs"]`), pipeline `run_id`, problem `slug`, and pipeline execution metadata.
- **Output Payload Requirement**: Returns a serializable JSON-compatible dictionary payload to be written to `StateLedger` by `WorkflowEngine`.

### Section 4: Dynamic Discovery & Adapter Pattern (`PluginLoader`)
- **Location**: `src/core/workflow/plugin_loader.py`.
- **Discovery Mechanism**: `importlib.metadata.entry_points(group="youtube_pipeline.plugins")`.
- **Type Validation**: Enforces `issubclass(cls, PluginNode)` and raises `PluginValidationError` for non-compliant classes.
- **Adapter Mechanism**: `PluginNodeAdapter(Node)` wraps `PluginNode` to implement core `Node.execute(run_id, ledger)` interface without exposing `ledger` to `PluginNode`.

### Section 5: Step-by-Step Developer Tutorial
- Concrete walkthrough creating a custom plugin node (e.g. `NotionExporterNode` or `CodeMetricsNode`), installing it in editable mode (`pip install -e .`), and running it via `WorkflowEngine`.

### Section 6: Testing & Verification Strategy
- Outlining `pytest tests/workflow/test_plugin_loader.py` test suite, unit tests, isolation assertions, and `importlib.metadata` entry point mocking.

---

## 2. Component Design & Code Contracts

### 2.1 Restricted Plugin Base (`src/sdk/plugin_base.py`)

```python
"""
Restricted Plugin Base Interface for Phase 09 Plugin SDK.

Defines the PluginNode interface for external developers. External plugins
are explicitly isolated from direct SQLite StateLedger access.
"""

from abc import ABC, abstractmethod
from typing import Any


class PluginNode(ABC):
    """
    Restricted Base Class for external third-party plugin nodes.

    Plugins accept an inputs dictionary (containing prior step outputs and run metadata)
    and return an output dictionary payload. Direct access to StateLedger or database
    connections is strictly prohibited.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique name identifier for the plugin node step.

        Returns:
            str: Unique step identifier (e.g., 'custom_metrics', 'notion_sync').
        """
        pass

    @abstractmethod
    def process(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """
        Execute isolated plugin processing logic.

        Args:
            inputs: Read-only dictionary containing prior step outputs, run_id, slug,
                    and pipeline execution metadata.

        Returns:
            dict[str, Any]: Dictionary payload to be persisted into StateLedger.

        Raises:
            Exception: If plugin execution fails.
        """
        pass
```

### 2.2 Adapter Pattern & Plugin Loader (`src/core/workflow/plugin_loader.py`)

```python
"""
Dynamic Plugin Loader and Adapter for Phase 09 Plugin SDK.

Discovers external plugin nodes via importlib.metadata entry points, validates inheritance
from PluginNode, and wraps them in PluginNodeAdapter for WorkflowEngine compatibility.
"""

import importlib.metadata
from typing import Any, Sequence

from src.core.exceptions import PipelineError
from src.core.logger import get_logger
from src.core.orchestrator.state_ledger import StateLedger
from src.core.workflow.node import Node
from src.sdk.plugin_base import PluginNode

logger = get_logger(__name__)

ENTRY_POINT_GROUP = "youtube_pipeline.plugins"


class PluginValidationError(PipelineError):
    """Raised when an external plugin fails validation (e.g. does not inherit from PluginNode)."""
    pass


class PluginNodeAdapter(Node):
    """
    Adapter wrapping a restricted PluginNode inside a core Workflow Node interface.

    Handles StateLedger reading and writing on behalf of the plugin, enforcing
    isolation boundaries so third-party plugins cannot manipulate SQLite state directly.
    """

    def __init__(self, plugin: PluginNode) -> None:
        if not isinstance(plugin, PluginNode):
            raise PluginValidationError(
                f"Expected PluginNode instance, got {type(plugin).__name__}"
            )
        self.plugin = plugin

    @property
    def name(self) -> str:
        return self.plugin.name

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        run_record = self.get_run_record(run_id, ledger)
        completed_outputs = self.get_completed_step_outputs(run_id, ledger)

        inputs = {
            "run_id": run_id,
            "slug": run_record.slug,
            "prior_outputs": completed_outputs,
            "status": run_record.status.value if hasattr(run_record.status, "value") else str(run_record.status),
        }

        # Invoke restricted plugin process method without providing ledger instance
        return self.plugin.process(inputs)


class PluginLoader:
    """
    Dynamic discoverer and loader for external workflow plugins using entry points.
    """

    def __init__(self, group: str = ENTRY_POINT_GROUP) -> None:
        self.group = group

    def discover_entry_points(self) -> Sequence[importlib.metadata.EntryPoint]:
        """Discover entry points for the configured group."""
        eps = importlib.metadata.entry_points()
        if hasattr(eps, "select"):
            return list(eps.select(group=self.group))
        elif isinstance(eps, dict):
            return eps.get(self.group, [])
        return [ep for ep in eps if ep.group == self.group]

    def load_plugins((self) -> list[Node]:
        """
        Discover, validate, instantiate, and adapt external plugin nodes.

        Returns:
            list[Node]: List of PluginNodeAdapter instances wrapped as core Node objects.

        Raises:
            PluginValidationError: If a discovered plugin class does not inherit from PluginNode.
        """
        entry_points = self.discover_entry_points()
        loaded_nodes: list[Node] = []

        for ep in entry_points:
            logger.info("Loading plugin entry point", ep_name=ep.name, value=ep.value)
            try:
                plugin_cls = ep.load()
            except Exception as e:
                logger.error("Failed to load plugin entry point", ep_name=ep.name, error=str(e))
                raise PluginValidationError(f"Could not load entry point '{ep.name}': {e}") from e

            if not isinstance(plugin_cls, type) or not issubclass(plugin_cls, PluginNode):
                logger.error("Invalid plugin class hierarchy", ep_name=ep.name, cls=str(plugin_cls))
                raise PluginValidationError(
                    f"Plugin class '{plugin_cls}' from entry point '{ep.name}' must inherit from PluginNode."
                )

            try:
                plugin_instance = plugin_cls()
            except Exception as e:
                logger.error("Failed to instantiate plugin", ep_name=ep.name, error=str(e))
                raise PluginValidationError(f"Could not instantiate plugin '{ep.name}': {e}") from e

            adapter = PluginNodeAdapter(plugin_instance)
            loaded_nodes.append(adapter)
            logger.info("Successfully loaded plugin node", step_name=adapter.name)

        return loaded_nodes
```

---

## 3. Acceptance Criteria for Phase 09

### Criteria 1: Verification & Testing
- **AC 1.1**: Running `pytest tests/workflow/test_plugin_loader.py` executes cleanly and passes all test cases.
- **AC 1.2**: `test_plugin_loader.py` safely mocks `importlib.metadata.entry_points()` to supply synthetic mock `PluginNode` classes without creating temporary files or installing external pip packages.
- **AC 1.3**: The test suite proves that when `WorkflowEngine` executes a pipeline containing an adapted external plugin, prior step outputs are passed to `process(inputs)`, and returned outputs are persisted into SQLite `StateLedger`.
- **AC 1.4**: The test suite verifies that invalid plugin classes (classes not inheriting from `PluginNode`) are rejected with `PluginValidationError`.
- **AC 1.5**: The test suite verifies that exceptions raised inside plugin `process()` are gracefully caught by `WorkflowEngine`, updating the step and run status in `StateLedger` to `FAILED`.

### Criteria 2: Implementation & Decoupling
- **AC 2.1**: `src/sdk/plugin_base.py` exists and defines `PluginNode(ABC)` with `name` property and `process(inputs: dict[str, Any]) -> dict[str, Any]` signature.
- **AC 2.2**: `src/core/workflow/plugin_loader.py` exists, implementing `PluginNodeAdapter` and `PluginLoader`.
- **AC 2.3**: `PluginNode` explicitly denies direct SQLite ledger access. No `StateLedger` parameter or reference is passed to `PluginNode.process()`.

### Criteria 3: Documentation
- **AC 3.1**: `PromptBook/Phase09/01_Plugin_SDK.md` exists and details:
  1. Package structure & `setup.py` / `pyproject.toml` entry points configuration under `youtube_pipeline.plugins`.
  2. Restricted `PluginNode` lifecycle and isolation boundary rationale.
  3. `PluginLoader` discovery mechanism via `importlib.metadata` and `PluginNodeAdapter` design.
  4. End-to-end tutorial for third-party plugin authors.

---

## 4. Verification Steps Matrix

| Target | Command / Check | Expected Result | Invalidation Condition |
| --- | --- | --- | --- |
| Unit Tests | `pytest tests/workflow/test_plugin_loader.py` | 100% tests pass, discovery & execution verified | Any failing test or mock error |
| Regression | `pytest tests/workflow/test_engine.py` | 100% core engine tests pass | Core engine regression |
| Class Hierarchy | Inspection of `src/sdk/plugin_base.py` | `PluginNode` ABC present, no `ledger` parameters in `process` | `StateLedger` parameter added to `process()` |
| Entry Point Discovery | Mocking `importlib.metadata.entry_points` | Discovers, validates, instantiates, and adapts plugin | Loader accepts non-`PluginNode` classes |
| Documentation | Inspection of `PromptBook/Phase09/01_Plugin_SDK.md` | Complete documentation matching all 6 required sections | Missing file or missing entry point config sections |
