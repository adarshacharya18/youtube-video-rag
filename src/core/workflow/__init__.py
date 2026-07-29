"""
Workflow Engine Module for Phase 08.

Provides abstract node definitions, fault-tolerant execution engine,
and execution result objects for the automated DSA video pipeline.
"""

from src.core.workflow.engine import EngineResult, WorkflowEngine
from src.core.workflow.node import Node
from src.core.workflow.plugin_loader import (
    PluginError,
    PluginLoadError,
    PluginLoader,
    PluginNodeAdapter,
    PluginValidationError,
)

__all__ = [
    "Node",
    "WorkflowEngine",
    "EngineResult",
    "PluginLoader",
    "PluginNodeAdapter",
    "PluginError",
    "PluginLoadError",
    "PluginValidationError",
]

