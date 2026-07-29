# Phase 09 Workflow Architecture & Plugin SDK Technical Analysis

## Executive Summary

This document presents a comprehensive architectural survey and technical design for **Phase 09: Plugin SDK** of the Automated DSA Educational YouTube Video Pipeline. 

The primary objective of Phase 09 is to establish an extensible, secure plugin framework utilizing Python `entry_points`. This framework enables third-party developers to inject custom pipeline nodes into the `WorkflowEngine` without modifying core pipeline code. Crucially, the design enforces a strict sandbox boundary: third-party plugins are denied direct access to the SQLite `StateLedger` (preventing arbitrary SQL execution, data corruption, or unauthorized state access), while cleanly receiving input state dictionaries and returning output payloads for core ledger management.

---

## 1. Existing Workflow Architecture Survey

### 1.1 Core Node Interface (`src/core/workflow/node.py`)

The existing pipeline node abstraction is defined by the abstract base class `Node`:

```python
class Node(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the step (e.g., 'ingest', 'plan', 'script', 'render')."""
        pass

    @abstractmethod
    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        """Execute node processing logic using run_id and active StateLedger."""
        pass
```

Key characteristics of `Node`:
- **Direct Ledger Coupling**: `execute()` receives the active `StateLedger` instance directly.
- **State Retrieval Helpers**: `Node` provides helper methods (`get_run_record`, `get_completed_step_outputs`, `get_step_output`) that invoke `ledger` methods (such as `ledger.get_run()` and `ledger.get_completed_steps()`).
- **Return Payload**: Nodes return a dictionary payload (`dict[str, Any]`), which is recorded into `StateLedger` by the `WorkflowEngine`.

### 1.2 State Ledger Architecture (`src/core/orchestrator/state_ledger.py`)

The `StateLedger` class manages thread-safe SQLite persistence for pipeline runs and step executions:
- **Database Schema**:
  - `pipeline_runs`: Stores `pipeline_run_id`, `slug`, `status` (`PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`), `created_at`, `updated_at`, `metadata`.
  - `step_executions`: Stores `step_execution_id`, `pipeline_run_id`, `step_name`, `status`, `input_payload`, `output_payload`, `error_message`, `error_details`, `created_at`, `updated_at`.
- **Database Configuration**: Configured with `PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL`, `PRAGMA foreign_keys=ON`, and `PRAGMA busy_timeout=5000`.
- **Raw Connection Access**: The internal `_conn: sqlite3.Connection` handle is held directly inside `StateLedger`.

### 1.3 Workflow Engine Lifecycle (`src/core/workflow/engine.py`)

`WorkflowEngine` manages sequential execution of a sequence of `Node` instances for a given `run_id`:
1. **Idempotency Check**: Queries `ledger.get_completed_steps(run_id)`. If a node's status is already `COMPLETED`, execution is skipped and the stored output is loaded from the ledger.
2. **Step Execution Start**: Calls `ledger.record_step_start(run_id, node.name)`, returning a `step_execution_id`.
3. **Execution & Exception Wrapping**: Invokes `node.execute(run_id, self.ledger)` within a `try/except` block.
   - **On Success**: Calls `ledger.record_step_completion(step_id, node_output)`.
   - **On Failure**: Calls `ledger.record_step_failure(step_id, error_message, error_details)` (which updates step and parent run status to `FAILED`) and short-circuits pipeline execution, returning an `EngineResult` with `success=False`.

---

## 2. Security Vulnerability & Design Gap Analysis

### 2.1 Security Risks of Direct State Ledger Access for Third-Party Plugins

In the core `Node` design, every node receives the `StateLedger` instance directly during `execute(run_id, ledger)`. For core internal nodes written by core developers, this design provides direct access to state query helpers. However, exposing `StateLedger` to external third-party plugins introduces critical security and architectural risks:

1. **Arbitrary Database Manipulation**: `StateLedger` holds `self._conn`, a raw `sqlite3.Connection`. A third-party plugin could execute arbitrary SQL statements (e.g., `DROP TABLE`, `UPDATE pipeline_runs`, or raw PRAGMA commands).
2. **State Ledger Integrity Invalidation**: An external plugin could directly mutate or delete step execution records, bypassing step idempotency tracking or spoofing step completion records for other stages.
3. **Unrestricted Data Exposure**: External plugins could query sensitive run metadata or outputs from unrelated workflow runs stored in the database.
4. **Tightly Coupled Internal SDK**: Forcing third-party developers to import and interact with SQLite `StateLedger` primitives creates high API surface area and tight coupling to internal database schema changes.

### 2.2 Functional Boundary Requirements for Plugin SDK

To fulfill Requirement R1 and Phase 09 Acceptance Criteria, the system must separate third-party plugin logic from database management:
- Third-party plugins must **never** receive `run_id` or `StateLedger` handles.
- Plugin logic must be encapsulated in a restricted **inputs-in, outputs-out** interface (`PluginNode`).
- The core pipeline must provide an **Adapter** layer that reads inputs from the `StateLedger`, feeds them to `PluginNode.process(inputs)`, and persists the returned output back to `StateLedger`.

---

## 3. Restricted `PluginNode` Interface Design (`src/sdk/plugin_base.py`)

### 3.1 Interface Specification

The restricted plugin interface will be defined in `src/sdk/plugin_base.py` as an abstract base class `PluginNode`:

```python
"""
Plugin Base Definitions for Phase 09 External Plugin SDK.

Defines the restricted PluginNode interface for third-party developers.
Plugins are restricted to accepting input dictionaries and returning output
payloads, denying direct access to the SQLite StateLedger or raw database connections.
"""

from abc import ABC, abstractmethod
from typing import Any


class PluginNode(ABC):
    """
    Restricted Abstract Base Class for external third-party workflow plugins.

    External plugins must inherit from PluginNode and implement `name` and `process()`.
    Plugins do NOT have access to StateLedger, sqlite3 connections, or run identifiers,
    ensuring a secure sandbox boundary.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique name identifier for the plugin step.

        Used for logging, step tracking, and prior step output indexing.

        Returns:
            str: Plugin step identifier.
        """
        pass

    @abstractmethod
    def process(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """
        Process external plugin business logic.

        Args:
            inputs: Dictionary containing pipeline context and outputs from prior completed steps.
                   Keys typically include:
                     - 'slug': Problem identifier.
                     - 'metadata': Run metadata dictionary.
                     - 'steps': Dict mapping step names to their respective output dictionaries.

        Returns:
            dict[str, Any]: Output dictionary payload to be safely stored in StateLedger by WorkflowEngine.

        Raises:
            Exception: If plugin execution fails. The error will be safely caught by WorkflowEngine.
        """
        pass
```

### 3.2 Input and Output Data Schema Contract

- **Input Contract (`inputs: dict[str, Any]`)**:
  - `"run_id"`: String identifier of the current execution run.
  - `"slug"`: Problem slug / title.
  - `"metadata"`: Dictionary of run metadata.
  - `"steps"`: Dictionary mapping previously completed step names (`step_name`) to their output payload dictionaries.
- **Output Contract**:
  - Must return a standard Python `dict[str, Any]`.
  - Non-dictionary returns will trigger a `TypeError` in the adapter layer.

---

## 4. Adapter & Dynamic Plugin Loader Design (`src/core/workflow/plugin_loader.py`)

To bridge the restricted `PluginNode` interface with `WorkflowEngine` (which expects core `Node` instances), we implement an adapter pattern and entry point dynamic loader in `src/core/workflow/plugin_loader.py`.

### 4.1 Adapter Pattern (`PluginNodeAdapter`)

`PluginNodeAdapter` subclasses core `Node` and wraps a `PluginNode` instance:

```python
class PluginNodeAdapter(Node):
    """
    Adapter bridging restricted PluginNode instances to the core Node interface.

    Handles reading prior step outputs and run metadata from StateLedger, constructing
    a safe inputs dictionary, calling PluginNode.process(inputs), and returning the output.
    """

    def __init__(self, plugin: PluginNode) -> None:
        if not isinstance(plugin, PluginNode):
            raise TypeError(f"Target plugin must be an instance of PluginNode, got {type(plugin)}")
        self._plugin = plugin

    @property
    def name(self) -> str:
        return self._plugin.name

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        # Extract run record metadata and prior completed step outputs from ledger
        run_record = self.get_run_record(run_id, ledger)
        completed_outputs = self.get_completed_step_outputs(run_id, ledger)

        # Construct safe inputs payload dictionary
        inputs: dict[str, Any] = {
            "run_id": run_id,
            "slug": run_record.slug,
            "metadata": run_record.metadata or {},
            "steps": completed_outputs,
        }

        # Execute plugin logic without exposing ledger
        output = self._plugin.process(inputs)

        if output is None:
            output = {}

        if not isinstance(output, dict):
            raise TypeError(
                f"Plugin '{self.name}' must return a dictionary payload, got {type(output).__name__}."
            )

        return output
```

### 4.2 Dynamic Plugin Loader (`PluginLoader`)

The `PluginLoader` discovers third-party plugins registered under Python `entry_points`:

- **Group Name**: `youtube_pipeline.plugins` (or configurable parameter).
- **Discovery Mechanism**: Uses `importlib.metadata.entry_points(group=...)`.
- **Validation**:
  1. Loads entry point class via `ep.load()`.
  2. Asserts `issubclass(ep_class, PluginNode)` and `ep_class is not PluginNode`.
  3. Instantiates `plugin_instance = ep_class()`.
  4. Wraps in `PluginNodeAdapter(plugin_instance)`.

```python
class PluginLoader:
    """
    Dynamic discovery and instantiation engine for external third-party PluginNode plugins.
    """

    DEFAULT_GROUP = "youtube_pipeline.plugins"

    @classmethod
    def load_plugins(cls, group: str = DEFAULT_GROUP) -> list[Node]:
        """
        Discover, validate, instantiate, and adapt external plugins from entry points.

        Args:
            group: Entry point group name to query.

        Returns:
            list[Node]: List of adapted Node instances ready for WorkflowEngine.

        Raises:
            PipelineStageError: If an entry point class does not inherit from PluginNode.
        """
        discovered_eps = entry_points(group=group)
        adapted_nodes: list[Node] = []

        for ep in discovered_eps:
            plugin_cls = ep.load()

            # Enforce strict inheritance check
            if not (isinstance(plugin_cls, type) and issubclass(plugin_cls, PluginNode) and plugin_cls is not PluginNode):
                raise PipelineStageError(
                    f"Entry point '{ep.name}' ({plugin_cls}) must inherit from PluginNode."
                )

            plugin_instance = plugin_cls()
            adapted_nodes.append(PluginNodeAdapter(plugin_instance))

        return adapted_nodes
```

---

## 5. Verification & Testing Strategy (`tests/workflow/test_plugin_loader.py`)

To satisfy Phase 09 Acceptance Criteria without requiring disk writes or actual package installation during unit tests, the test suite will utilize `unittest.mock.patch` on `importlib.metadata.entry_points`.

### 5.1 Test Scenarios

1. **Plugin Discovery & Inheritance Validation**:
   - Mock entry point returning a valid `PluginNode` subclass.
   - Verify `PluginLoader.load_plugins()` discovers and instantiates the plugin successfully.
2. **Invalid Plugin Rejection**:
   - Mock entry point returning a class that does *not* inherit from `PluginNode` (e.g., a standard class or core `Node`).
   - Verify `PluginLoader.load_plugins()` raises `PipelineStageError`.
3. **End-to-End Workflow Engine Integration & Sandbox Isolation**:
   - Execute an adapted `PluginNode` inside `WorkflowEngine` with an in-memory `StateLedger`.
   - Verify that prior step outputs (e.g., from `MockIngestNode`) are cleanly passed in `inputs["steps"]`.
   - Verify plugin returned outputs are correctly stored in `StateLedger`.
   - Verify that the `PluginNode` has no direct handle or access to `StateLedger`.
4. **Plugin Error Handling**:
   - Mock plugin throwing a `RuntimeError` during `process()`.
   - Verify `WorkflowEngine` catches the exception, updates ledger status to `FAILED`, and records error details.

---

## 6. Implementation Action Plan & Artifact Summary

| File Path | Purpose | Role |
|-----------|---------|------|
| `src/sdk/plugin_base.py` | Defines `PluginNode` abstract base class | Restricted SDK interface |
| `src/core/workflow/plugin_loader.py` | Implements `PluginNodeAdapter` & `PluginLoader` | Core engine bridge & discovery |
| `tests/workflow/test_plugin_loader.py` | Unit tests for loader, adapter, and mock entry points | Acceptance verification |
| `PromptBook/Phase09/01_Plugin_SDK.md` | Architectural & SDK developer documentation | SDK Documentation |

This survey and technical design complete all requirements for Phase 09 architecture planning.
