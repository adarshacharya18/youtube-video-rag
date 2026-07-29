# Project: Phase 09 — Plugin SDK for Automated DSA Educational YouTube Video Pipeline

## Architecture
- External Developer SDK interface: `src/sdk/plugin_base.py` (`PluginNode` ABC)
- Dynamic Plugin Loader & Core Adapter: `src/core/workflow/plugin_loader.py` (`PluginLoader`, `PluginNodeAdapter`, `PluginError`, `PluginLoadError`, `PluginValidationError`)
- SDK Documentation: `PromptBook/Phase09/01_Plugin_SDK.md`
- Test Harness & In-Memory Entry Point Mocks: `tests/workflow/test_plugin_loader.py`

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | R1. Restricted Plugin SDK | Abstract base class `PluginNode` in `src/sdk/plugin_base.py` restricting third-party plugins to input/output dictionaries without direct SQLite StateLedger access | M1 | ORIGINAL_REQUEST |
| 2 | R2. Plugin Adapter & Dynamic Loader | `PluginNodeAdapter` and `PluginLoader` in `src/core/workflow/plugin_loader.py` utilizing `importlib.metadata.entry_points(group="dsa.plugins")` with `issubclass(cls, PluginNode)` enforcement | M1 | ORIGINAL_REQUEST |
| 3 | R3. SDK Documentation | Comprehensive developer documentation in `PromptBook/Phase09/01_Plugin_SDK.md` detailing packaging, entry point registration, plugin lifecycle, security, and integration | M2 | ORIGINAL_REQUEST |
| 4 | Verification & In-Memory Mock Testing | Test suite in `tests/workflow/test_plugin_loader.py` mocking `importlib.metadata.entry_points()` safely in memory without writing temp files to disk | M3 | ORIGINAL_REQUEST |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Plugin SDK & Loader | `src/sdk/plugin_base.py` and `src/core/workflow/plugin_loader.py` | None | DONE |
| M2 | SDK Documentation | `PromptBook/Phase09/01_Plugin_SDK.md` | M1 | DONE |
| M3 | Verification & Test Suite | `tests/workflow/test_plugin_loader.py` | M1 | DONE |

## Interface Contracts
### `PluginNode` (External Developer Interface)
```python
class PluginNode(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def process(self, inputs: dict[str, Any]) -> dict[str, Any]: ...
```

### `PluginNodeAdapter` (Core Pipeline Interface)
```python
class PluginNodeAdapter(Node):
    def __init__(self, plugin: PluginNode) -> None: ...
    @property
    def name(self) -> str: ...
    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]: ...
```

### `PluginLoader` (Dynamic Discovery Interface)
```python
class PluginLoader:
    def __init__(self, group: str = "dsa.plugins") -> None: ...
    def discover_entry_points(self) -> list[importlib.metadata.EntryPoint]: ...
    def load_and_validate(self, entry_point: importlib.metadata.EntryPoint) -> type[PluginNode]: ...
    def load_plugins(self) -> list[Node]: ...
```

## Code Layout
```
src/
├── sdk/
│   ├── __init__.py
│   └── plugin_base.py
└── core/
    └── workflow/
        └── plugin_loader.py
PromptBook/
└── Phase09/
    └── 01_Plugin_SDK.md
tests/
└── workflow/
    └── test_plugin_loader.py
```
