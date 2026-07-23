# Phase 07 / 03: Workflow Parser Implementation

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code Updates: `src/core/workflow_def.py`](#2-source-code-updates-srccoreworkflow_defpy)
3. [Source Code: `src/core/workflow_parser.py`](#3-source-code-srccoreworkflow_parserpy)
4. [Design Decisions](#4-design-decisions)

---

# 1. Executive Summary

This document introduces the **Workflow Parser**. 

While the previous step constructed the strict Pydantic models, we require a dedicated Parser layer to handle File I/O, format human-readable error messages for DevOps operators, and strictly reject misspelled or **Unknown Fields**. 

By enforcing `extra="forbid"` on our Pydantic schema and trapping `yaml.YAMLError` and `json.JSONDecodeError`, we guarantee that a simple typo in a configuration file (e.g., `timout_sec` instead of `timeout_sec`) instantly halts the boot sequence with a clear error trace, rather than silently defaulting to a 1-hour timeout and crashing in production.

---

# 2. Source Code Updates: `src/core/workflow_def.py`

*(Updated to strictly forbid unknown fields for precise typo detection)*

```python
"""
Workflow Definition Models.
"""
import json
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.core.exceptions import PipelineError


class WorkflowDefinitionError(PipelineError):
    pass


class RetryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_retries: int = Field(default=3, ge=0)
    backoff_factor: float = Field(default=2.0, ge=1.0)
    initial_delay_sec: float = Field(default=1.0, ge=0.0)


class StepDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_id: str = Field(...)
    plugin_id: str = Field(...)
    depends_on: list[str] = Field(default_factory=list)
    conditions: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    timeout_sec: float = Field(default=3600.0)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    parallel_group: Optional[str] = Field(default=None)


class WorkflowMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    author: str = Field(default="system")
    description: str = Field(default="Automated Pipeline Workflow")
    tags: list[str] = Field(default_factory=list)


class WorkflowDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflow_id: str = Field(...)
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    metadata: WorkflowMetadata = Field(default_factory=WorkflowMetadata)
    global_parameters: dict[str, Any] = Field(default_factory=dict)
    steps: list[StepDefinition] = Field(..., min_length=1)

    def validate_dag(self) -> None:
        step_ids = {step.step_id for step in self.steps}
        for step in self.steps:
            for dep in step.depends_on:
                if dep not in step_ids:
                    raise WorkflowDefinitionError(f"Step '{step.step_id}' depends on missing step '{dep}'")

        visited = set()
        path = set()
        
        def visit(node_id: str) -> None:
            if node_id in path:
                raise WorkflowDefinitionError(f"Fatal Circular Dependency detected involving step '{node_id}'")
            if node_id in visited:
                return
            path.add(node_id)
            step = next(s for s in self.steps if s.step_id == node_id)
            for dep in step.depends_on:
                visit(dep)
            path.remove(node_id)
            visited.add(node_id)

        for s in self.steps:
            visit(s.step_id)
```

---

# 3. Source Code: `src/core/workflow_parser.py`

```python
"""
Workflow Parser.

Validates and parses declarative JSON/YAML files into strict DAG models.
Provides human-readable error reporting and strictly rejects unknown fields.
"""

import json
import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from src.core.exceptions import PipelineError
from src.core.workflow_def import WorkflowDefinition


class ParserError(PipelineError):
    """Raised when a workflow file contains structural or syntax errors."""
    pass


class WorkflowParser:
    """
    Centralized file parsing utility for the Workflow Engine.
    Handles I/O safely and converts raw Python Exceptions into 
    human-readable DevOps formatting.
    """
    _logger = logging.getLogger(__name__)

    @staticmethod
    def parse(file_path: str | Path) -> WorkflowDefinition:
        """Dynamically routes the file to the correct decoding engine based on extension."""
        path = Path(file_path)
        if not path.exists():
            raise ParserError(f"Workflow file not found: {path.absolute()}")

        ext = path.suffix.lower()
        if ext in (".yml", ".yaml"):
            return WorkflowParser._parse_yaml(path)
        elif ext == ".json":
            return WorkflowParser._parse_json(path)
        else:
            raise ParserError(
                f"Unsupported workflow extension '{ext}'. Must be .json, .yml, or .yaml"
            )

    @staticmethod
    def _parse_yaml(path: Path) -> WorkflowDefinition:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return WorkflowParser._validate_and_build(data, path)
        except yaml.YAMLError as e:
            raise ParserError(f"YAML Syntax Error in '{path.name}':\n{e}") from e
        except Exception as e:
            if isinstance(e, ParserError):
                raise
            raise ParserError(f"Failed to read YAML file '{path.name}': {e}") from e

    @staticmethod
    def _parse_json(path: Path) -> WorkflowDefinition:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return WorkflowParser._validate_and_build(data, path)
        except json.JSONDecodeError as e:
            raise ParserError(f"JSON Syntax Error in '{path.name}':\n{e}") from e
        except Exception as e:
            if isinstance(e, ParserError):
                raise
            raise ParserError(f"Failed to read JSON file '{path.name}': {e}") from e

    @staticmethod
    def _validate_and_build(data: Any, path: Path) -> WorkflowDefinition:
        """
        Executes strict Pydantic model hydration. 
        Translates raw Pydantic errors into readable log traces.
        """
        if not isinstance(data, dict):
            raise ParserError(f"Root of workflow file '{path.name}' must be a key-value mapping (dict).")
            
        try:
            # 1. Pydantic Type & Unknown Field Validation
            model = WorkflowDefinition(**data)
            
            # 2. Mathematical Directed Acyclic Graph Validation
            model.validate_dag()
            
            WorkflowParser._logger.info(
                f"Successfully parsed workflow '{model.workflow_id}' (v{model.version}) from {path.name}"
            )
            return model
            
        except ValidationError as e:
            # Human readable error formatting for CLI/DevOps consumption
            errors = []
            for err in e.errors():
                loc = " -> ".join([str(l) for l in err["loc"]])
                msg = err["msg"]
                errors.append(f" - [Field: '{loc}'] {msg}")
                
            error_str = "\n".join(errors)
            raise ParserError(
                f"Schema Validation Failed for '{path.name}'. Correct the following errors:\n{error_str}"
            ) from e
```

---

# 4. Design Decisions

1. **Unknown Field Rejection (`extra="forbid"`):** I updated the underlying models to include `model_config = ConfigDict(extra="forbid")`. If an administrator tries to pass `time_out: 600` instead of `timeout_sec: 600`, Pydantic will instantly throw an error. This is crucial for avoiding silent configuration bugs in production.
2. **Dynamic Format Routing:** The parser checks `path.suffix` and safely routes it to `yaml.safe_load` or `json.load`. This guarantees we will never accidentally interpret malicious Python code from a compromised YAML string (since we strictly avoid `yaml.load`).
3. **DevOps Friendly Error Logs:** By default, Pydantic's `ValidationError` output is extremely noisy and difficult for humans to read. The `_validate_and_build()` method catches the raw error, iterates through the underlying JSON arrays, and translates it into a flat, readable list (`- [Field: 'steps -> 0 -> timeout_sec'] input must be a number`). This drastically improves Developer Experience (DX).
