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
