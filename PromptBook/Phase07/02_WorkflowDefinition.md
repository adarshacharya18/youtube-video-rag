# Phase 07 / 02: Workflow Definition Implementation

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/workflow_def.py`](#2-source-code-srccoreworkflow_defpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document introduces the **Workflow Definition** models. 

To maintain total decoupling, the Workflow Orchestrator cannot contain hardcoded Python functions defining how steps connect. Instead, the pipelines are defined using declarative JSON or YAML files. 

This implementation provides strict Pydantic schemas that map these files into strongly-typed Python objects. It includes powerful configuration nodes (Retries, Timeouts, Parallel Groups, and Conditionals) and mathematically guarantees that the defined steps form a valid **Directed Acyclic Graph (DAG)** without circular dependencies.

---

# 2. Source Code: `src/core/workflow_def.py`

```python
"""
Workflow Definition Models.

Provides strictly validated Pydantic models for parsing declarative Workflow DAGs 
from YAML and JSON files. Includes mathematical Cycle Detection to prevent 
infinite loops in production.
"""

import json
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError

from src.core.exceptions import PipelineError


class WorkflowDefinitionError(PipelineError):
    """Raised when a workflow file is malformed or contains circular dependencies."""
    pass


class RetryPolicy(BaseModel):
    """Configuration for local step-level exponential backoff."""
    max_retries: int = Field(default=3, ge=0, description="Max failed attempts before triggering DLQ.")
    backoff_factor: float = Field(default=2.0, ge=1.0, description="Multiplier for backoff time.")
    initial_delay_sec: float = Field(default=1.0, ge=0.0, description="Starting wait time after first failure.")


class StepDefinition(BaseModel):
    """A discrete block of execution assigned to a specific Plugin."""
    step_id: str = Field(..., description="Unique ID for this step within the workflow.")
    plugin_id: str = Field(..., description="The targeted plugin (e.g., 'core.scraper.leetcode').")
    
    depends_on: list[str] = Field(
        default_factory=list, 
        description="IDs of steps that must successfully COMPLETED before this step unlocks."
    )
    
    conditions: dict[str, Any] = Field(
        default_factory=dict, 
        description="Rules for skipping this step (e.g., {'skip_upload': True})."
    )
    
    parameters: dict[str, Any] = Field(
        default_factory=dict, 
        description="Hardcoded configuration parameters passed into the plugin context."
    )
    
    timeout_sec: float = Field(
        default=3600.0, # 1 hour default
        description="Max allowed execution time before triggering a fatal TimeoutError."
    )
    
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    
    parallel_group: Optional[str] = Field(
        default=None, 
        description="Optional tag. Steps with identical parallel_group IDs execute concurrently."
    )


class WorkflowMetadata(BaseModel):
    """Informational data for dashboards and audit logs."""
    author: str = Field(default="system")
    description: str = Field(default="Automated Pipeline Workflow")
    tags: list[str] = Field(default_factory=list)


class WorkflowDefinition(BaseModel):
    """The Root schema for a complete Pipeline definition file."""
    workflow_id: str = Field(..., description="Global unique identifier (e.g., 'daily-leetcode').")
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$", description="Strict SemVer (e.g., '1.0.0').")
    
    metadata: WorkflowMetadata = Field(default_factory=WorkflowMetadata)
    global_parameters: dict[str, Any] = Field(default_factory=dict)
    
    steps: list[StepDefinition] = Field(..., min_length=1)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "WorkflowDefinition":
        """Natively parses and strictly validates a YAML workflow template."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            # The **data unpack triggers Pydantic's Rust validation engine
            model = cls(**data)
            model.validate_dag()
            return model
        except ValidationError as e:
            raise WorkflowDefinitionError(f"Validation failed for YAML workflow '{path}': {e}") from e
        except Exception as e:
            raise WorkflowDefinitionError(f"Failed to parse YAML workflow '{path}': {e}") from e

    @classmethod
    def from_json(cls, path: str | Path) -> "WorkflowDefinition":
        """Natively parses and strictly validates a JSON workflow template."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            model = cls(**data)
            model.validate_dag()
            return model
        except ValidationError as e:
            raise WorkflowDefinitionError(f"Validation failed for JSON workflow '{path}': {e}") from e
        except Exception as e:
            raise WorkflowDefinitionError(f"Failed to parse JSON workflow '{path}': {e}") from e

    def validate_dag(self) -> None:
        """
        Validates that the steps form a mathematically sound Directed Acyclic Graph (DAG).
        1. Ensures no step relies on a phantom/missing dependency.
        2. Executes Cycle Detection (DFS) to prevent infinite orchestration loops.
        """
        step_ids = {step.step_id for step in self.steps}
        
        # 1. Valid Reference Check
        for step in self.steps:
            for dep in step.depends_on:
                if dep not in step_ids:
                    raise WorkflowDefinitionError(
                        f"Step '{step.step_id}' depends on missing/unknown step '{dep}'"
                    )

        # 2. Cycle Detection (Depth-First Search)
        visited = set()
        path = set()
        
        def visit(node_id: str) -> None:
            if node_id in path:
                # We reached a node we are currently tracing back from -> Cycle!
                raise WorkflowDefinitionError(
                    f"Fatal Circular Dependency detected involving step '{node_id}'"
                )
            if node_id in visited:
                return
                
            path.add(node_id)
            
            # Find the actual step object
            step = next(s for s in self.steps if s.step_id == node_id)
            for dep in step.depends_on:
                visit(dep)
                
            path.remove(node_id)
            visited.add(node_id)

        for s in self.steps:
            visit(s.step_id)
```

---

# 3. Design Decisions

1. **Declarative Separation:** By forcing the DAG logic into JSON/YAML, we achieve ultimate Separation of Concerns. A content strategist can edit the `daily-leetcode.yaml` file to swap the `voice_generator` plugin for the `elevenlabs_generator` plugin without ever needing to touch or compile the Python orchestration code.
2. **Cycle Detection (DFS):** If an administrator accidentally configures `Step A depends on Step B` and `Step B depends on Step A`, a naive Orchestrator would hang forever waiting for one to finish. The `validate_dag()` method executes a Depth-First Search immediately upon parsing the file. It will instantly crash the boot sequence with a `WorkflowDefinitionError`, ensuring broken DAGs never reach the production queue.
3. **Local Overrides:** While the core Event Bus and Orchestrator have global Retries and Timeouts, the `StepDefinition` allows localized overrides. You can set the `Video Render` step to have a `timeout_sec: 14400` (4 hours) while keeping the `Scraper` step locked to `timeout_sec: 300` (5 minutes). 
4. **SemVer Validation:** The `version` string natively enforces Regex pattern matching `r"^\d+\.\d+\.\d+$"`. This prevents developers from deploying sloppy tags like `v1` or `latest`, maintaining a strictly versioned Audit Log for State Persistence.
