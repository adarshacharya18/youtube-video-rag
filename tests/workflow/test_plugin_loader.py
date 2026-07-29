"""
Unit tests for Plugin SDK, PluginLoader, PluginNodeAdapter, and WorkflowEngine integration.

All entry point discoveries are mocked in memory via unittest.mock.patch.
No temporary files or disk modifications are made during test execution.
"""

import importlib.metadata
from typing import Any
from unittest.mock import MagicMock, patch
import pytest

from src.core.exceptions import PipelineError
from src.core.orchestrator.state_ledger import StateLedger, StepStatus
from src.core.workflow import EngineResult, Node, WorkflowEngine
from src.core.workflow.plugin_loader import (
    PluginError,
    PluginLoadError,
    PluginLoader,
    PluginNodeAdapter,
    PluginValidationError,
)
from src.sdk import PluginNode


class DummyValidPlugin(PluginNode):
    """Valid concrete implementation of PluginNode."""

    @property
    def name(self) -> str:
        return "dummy_valid_plugin"

    def process(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {
            "processed": True,
            "received_slug": inputs.get("slug"),
            "received_steps": list(inputs.get("steps", {}).keys()),
            "custom_result": "Success",
        }


class DummyFailingPlugin(PluginNode):
    """PluginNode that intentionally raises a runtime exception."""

    @property
    def name(self) -> str:
        return "dummy_failing_plugin"

    def process(self, inputs: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("Simulated plugin process failure")


class DummyNonDictPlugin(PluginNode):
    """PluginNode that returns an invalid non-dictionary payload."""

    @property
    def name(self) -> str:
        return "dummy_non_dict_plugin"

    def process(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return "invalid_string_return"  # type: ignore[return-value]


class DummyBrokenInitPlugin(PluginNode):
    """PluginNode whose instantiation raises an exception."""

    def __init__(self) -> None:
        raise ValueError("Initialization failure in plugin constructor")

    @property
    def name(self) -> str:
        return "broken_init"

    def process(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {}


class InvalidNonSubclassPlugin:
    """Class that does NOT inherit from PluginNode."""

    @property
    def name(self) -> str:
        return "invalid_plugin"

    def process(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {}


class MockIngestNode(Node):
    """Core Node for testing prior step output passing."""

    @property
    def name(self) -> str:
        return "ingest"

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        run = self.get_run_record(run_id, ledger)
        return {
            "slug": run.slug,
            "raw_data": f"Ingested data for {run.slug}",
        }


def make_mock_entry_point(name: str, target: Any, group: str = "dsa.plugins") -> MagicMock:
    """Helper utility to create a mock EntryPoint instance."""
    mock_ep = MagicMock(spec=importlib.metadata.EntryPoint)
    mock_ep.name = name
    mock_ep.group = group
    mock_ep.value = f"mock_module:{getattr(target, '__name__', str(target))}"
    mock_ep.load.return_value = target
    return mock_ep


def test_plugin_node_abstract_instantiation_raises():
    """Verify that instantiating abstract PluginNode directly or without process/name raises TypeError."""
    with pytest.raises(TypeError):
        PluginNode()  # type: ignore[abstract]

    class IncompletePlugin(PluginNode):
        @property
        def name(self) -> str:
            return "incomplete"

    with pytest.raises(TypeError):
        IncompletePlugin()  # type: ignore[abstract]


def test_plugin_node_adapter_type_validation():
    """Verify PluginNodeAdapter raises PluginValidationError if given a non-PluginNode instance."""
    with pytest.raises(PluginValidationError, match="must be an instance of PluginNode"):
        PluginNodeAdapter(InvalidNonSubclassPlugin())  # type: ignore[arg-type]


def test_plugin_loader_empty_entry_points():
    """Verify PluginLoader handles empty entry points discovery cleanly."""
    with patch("importlib.metadata.entry_points", return_value=[]):
        loader = PluginLoader(group="dsa.plugins")
        nodes = loader.load_plugins()
        assert nodes == []


def test_plugin_loader_valid_discovery_and_instantiation():
    """Verify PluginLoader discovers, validates, instantiates, and adapts valid PluginNode entry points."""
    mock_ep = make_mock_entry_point("valid_plugin", DummyValidPlugin)
    with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
        loader = PluginLoader(group="dsa.plugins")
        nodes = loader.load_plugins()

        assert len(nodes) == 1
        adapter = nodes[0]
        assert isinstance(adapter, PluginNodeAdapter)
        assert adapter.name == "dummy_valid_plugin"


def test_plugin_loader_rejects_non_subclass_class():
    """Verify PluginLoader raises PluginValidationError when entry point class does not inherit from PluginNode."""
    mock_ep = make_mock_entry_point("invalid_plugin", InvalidNonSubclassPlugin)
    with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
        loader = PluginLoader(group="dsa.plugins")
        with pytest.raises(PluginValidationError, match="must inherit from PluginNode"):
            loader.load_plugins()


def test_plugin_loader_rejects_function_entry_point():
    """Verify PluginLoader raises PluginValidationError when entry point is a plain function."""
    def plain_function(inputs: dict) -> dict:
        return {}

    mock_ep = make_mock_entry_point("function_plugin", plain_function)
    with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
        loader = PluginLoader(group="dsa.plugins")
        with pytest.raises(PluginValidationError, match="must inherit from PluginNode"):
            loader.load_plugins()


def test_plugin_loader_handles_entry_point_load_failure():
    """Verify PluginLoader raises PluginLoadError when ep.load() raises an exception."""
    mock_ep = MagicMock(spec=importlib.metadata.EntryPoint)
    mock_ep.name = "broken_load_ep"
    mock_ep.load.side_effect = ImportError("No module named 'non_existent_module'")

    with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
        loader = PluginLoader(group="dsa.plugins")
        with pytest.raises(PluginLoadError, match="Failed to load plugin entry point"):
            loader.load_plugins()


def test_plugin_loader_handles_plugin_instantiation_failure():
    """Verify PluginLoader raises PluginLoadError when plugin class instantiation raises an exception."""
    mock_ep = make_mock_entry_point("broken_init_plugin", DummyBrokenInitPlugin)
    with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
        loader = PluginLoader(group="dsa.plugins")
        with pytest.raises(PluginLoadError, match="Failed to instantiate plugin class"):
            loader.load_plugins()


def test_end_to_end_plugin_execution_in_workflow_engine():
    """Verify successful execution of an adapted PluginNode within WorkflowEngine using StateLedger."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("two-sum-problem")

    plugin = DummyValidPlugin()
    adapter = PluginNodeAdapter(plugin)

    engine = WorkflowEngine(nodes=[MockIngestNode(), adapter], ledger=ledger)
    result = engine.run(run_id)

    assert result.success is True
    assert result.status == StepStatus.COMPLETED
    assert result.completed_steps == ["ingest", "dummy_valid_plugin"]
    assert result.failed_step is None

    # Check plugin output recorded in result and StateLedger
    assert "dummy_valid_plugin" in result.outputs
    plugin_output = result.outputs["dummy_valid_plugin"]
    assert plugin_output["processed"] is True
    assert plugin_output["received_slug"] == "two-sum-problem"
    assert "ingest" in plugin_output["received_steps"]
    assert plugin_output["custom_result"] == "Success"

    # Verify step completion in StateLedger
    completed_steps = ledger.get_completed_steps(run_id)
    assert "dummy_valid_plugin" in completed_steps
    assert completed_steps["dummy_valid_plugin"].output_payload["custom_result"] == "Success"


def test_end_to_end_failing_plugin_execution_in_workflow_engine():
    """Verify WorkflowEngine captures plugin process exception, updates StateLedger to FAILED, and short-circuits."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("failing-plugin-run")

    failing_adapter = PluginNodeAdapter(DummyFailingPlugin())

    engine = WorkflowEngine(nodes=[MockIngestNode(), failing_adapter], ledger=ledger)
    result = engine.run(run_id)

    assert result.success is False
    assert result.status == StepStatus.FAILED
    assert result.failed_step == "dummy_failing_plugin"
    assert "Simulated plugin process failure" in str(result.error)
    assert result.completed_steps == ["ingest"]

    # Verify StateLedger run and step records reflect FAILED status
    run_record = ledger.get_run(run_id)
    assert run_record is not None
    assert run_record.status == StepStatus.FAILED


def test_plugin_adapter_non_dict_return_handling():
    """Verify PluginNodeAdapter raises PluginValidationError when process() returns non-dictionary."""
    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("non-dict-return-run")

    non_dict_adapter = PluginNodeAdapter(DummyNonDictPlugin())
    engine = WorkflowEngine(nodes=[non_dict_adapter], ledger=ledger)
    result = engine.run(run_id)

    assert result.success is False
    assert result.status == StepStatus.FAILED
    assert result.failed_step == "dummy_non_dict_plugin"
    assert "must return a dictionary payload" in str(result.error)
