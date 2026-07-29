"""
Empirical Stress Test Runner for Phase 09 PluginLoader & PluginNodeAdapter.
"""

import importlib.metadata
import os
import sys
import traceback
from typing import Any
from unittest.mock import MagicMock, patch

from src.core.exceptions import PipelineError, PipelineStageError
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


class HelperTestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []

    def assert_test(self, name: str, condition: bool, details: str = ""):
        if condition:
            self.passed += 1
            self.results.append((name, "PASS", details))
            print(f"[PASS] {name}")
        else:
            self.failed += 1
            self.results.append((name, "FAIL", details))
            print(f"[FAIL] {name} - {details}")


def make_mock_ep(name: str, return_obj: Any) -> MagicMock:
    ep = MagicMock(spec=importlib.metadata.EntryPoint)
    ep.name = name
    ep.group = "dsa.plugins"
    ep.load.return_value = return_obj
    return ep


def run_all_stress_tests():
    runner = HelperTestRunner()
    print("=== STARTING PHASE 09 EMPIRICAL STRESS TESTS ===")

    # -------------------------------------------------------------
    # Category 1: Entry Point Returns Invalid Types / Objects
    # -------------------------------------------------------------

    # Test 1.1: EP returns integer primitive
    mock_ep = make_mock_ep("ep_int", 12345)
    with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
        loader = PluginLoader()
        try:
            loader.load_plugins()
            runner.assert_test("EP returns integer primitive", False, "Expected PluginValidationError, none raised")
        except PluginValidationError as e:
            runner.assert_test("EP returns integer primitive", True, f"Caught expected PluginValidationError: {e}")
        except Exception as e:
            runner.assert_test("EP returns integer primitive", False, f"Unexpected exception: {type(e).__name__}: {e}")

    # Test 1.2: EP returns string primitive
    mock_ep = make_mock_ep("ep_str", "some_string_class")
    with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
        loader = PluginLoader()
        try:
            loader.load_plugins()
            runner.assert_test("EP returns string primitive", False, "Expected PluginValidationError, none raised")
        except PluginValidationError as e:
            runner.assert_test("EP returns string primitive", True, f"Caught expected PluginValidationError: {e}")
        except Exception as e:
            runner.assert_test("EP returns string primitive", False, f"Unexpected exception: {type(e).__name__}: {e}")

    # Test 1.3: EP returns dict primitive
    mock_ep = make_mock_ep("ep_dict", {"key": "val"})
    with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
        loader = PluginLoader()
        try:
            loader.load_plugins()
            runner.assert_test("EP returns dict primitive", False, "Expected PluginValidationError, none raised")
        except PluginValidationError as e:
            runner.assert_test("EP returns dict primitive", True, f"Caught expected PluginValidationError: {e}")
        except Exception as e:
            runner.assert_test("EP returns dict primitive", False, f"Unexpected exception: {type(e).__name__}: {e}")

    # Test 1.4: EP returns list primitive
    mock_ep = make_mock_ep("ep_list", [1, 2, 3])
    with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
        loader = PluginLoader()
        try:
            loader.load_plugins()
            runner.assert_test("EP returns list primitive", False, "Expected PluginValidationError, none raised")
        except PluginValidationError as e:
            runner.assert_test("EP returns list primitive", True, f"Caught expected PluginValidationError: {e}")
        except Exception as e:
            runner.assert_test("EP returns list primitive", False, f"Unexpected exception: {type(e).__name__}: {e}")

    # Test 1.5: EP returns None
    mock_ep = make_mock_ep("ep_none", None)
    with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
        loader = PluginLoader()
        try:
            loader.load_plugins()
            runner.assert_test("EP returns None", False, "Expected PluginValidationError, none raised")
        except PluginValidationError as e:
            runner.assert_test("EP returns None", True, f"Caught expected PluginValidationError: {e}")
        except Exception as e:
            runner.assert_test("EP returns None", False, f"Unexpected exception: {type(e).__name__}: {e}")

    # Test 1.6: EP returns plain function
    def my_plugin_func(inputs):
        return {}

    mock_ep = make_mock_ep("ep_func", my_plugin_func)
    with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
        loader = PluginLoader()
        try:
            loader.load_plugins()
            runner.assert_test("EP returns plain function", False, "Expected PluginValidationError, none raised")
        except PluginValidationError as e:
            runner.assert_test("EP returns plain function", True, f"Caught expected PluginValidationError: {e}")
        except Exception as e:
            runner.assert_test("EP returns plain function", False, f"Unexpected exception: {type(e).__name__}: {e}")

    # Test 1.7: EP returns PluginNode ABC directly
    mock_ep = make_mock_ep("ep_abc", PluginNode)
    with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
        loader = PluginLoader()
        try:
            loader.load_plugins()
            runner.assert_test("EP returns PluginNode ABC directly", False, "Expected PluginValidationError, none raised")
        except PluginValidationError as e:
            runner.assert_test("EP returns PluginNode ABC directly", True, f"Caught expected PluginValidationError: {e}")
        except Exception as e:
            runner.assert_test("EP returns PluginNode ABC directly", False, f"Unexpected exception: {type(e).__name__}: {e}")

    # Test 1.8: EP returns instantiated PluginNode object (instance instead of class type)
    class ConcretePlugin(PluginNode):
        @property
        def name(self) -> str:
            return "concrete"

        def process(self, inputs: dict[str, Any]) -> dict[str, Any]:
            return {}

    instance = ConcretePlugin()
    mock_ep = make_mock_ep("ep_instance", instance)
    with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
        loader = PluginLoader()
        try:
            loader.load_plugins()
            runner.assert_test("EP returns PluginNode instance object", False, "Expected PluginValidationError, none raised")
        except PluginValidationError as e:
            runner.assert_test("EP returns PluginNode instance object", True, f"Caught expected PluginValidationError: {e}")
        except Exception as e:
            runner.assert_test("EP returns PluginNode instance object", False, f"Unexpected exception: {type(e).__name__}: {e}")

    # Test 1.9: EP returns class requiring non-default constructor arguments
    class RequiredArgsPlugin(PluginNode):
        def __init__(self, mandatory_arg: str):
            self.mandatory_arg = mandatory_arg

        @property
        def name(self) -> str:
            return "req_args"

        def process(self, inputs: dict[str, Any]) -> dict[str, Any]:
            return {}

    mock_ep = make_mock_ep("ep_req_args", RequiredArgsPlugin)
    with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
        loader = PluginLoader()
        try:
            loader.load_plugins()
            runner.assert_test("EP class requires constructor positional args", False, "Expected PluginLoadError, none raised")
        except PluginLoadError as e:
            runner.assert_test("EP class requires constructor positional args", True, f"Caught expected PluginLoadError: {e}")
        except Exception as e:
            runner.assert_test("EP class requires constructor positional args", False, f"Unexpected exception: {type(e).__name__}: {e}")

    # Test 1.10: EP load throws random exceptions (AttributeError, TypeError, SyntaxError)
    mock_ep = MagicMock(spec=importlib.metadata.EntryPoint)
    mock_ep.name = "broken_ep"
    mock_ep.load.side_effect = AttributeError("Module has no attribute 'Plugin'")
    with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
        loader = PluginLoader()
        try:
            loader.load_plugins()
            runner.assert_test("EP load() throws AttributeError", False, "Expected PluginLoadError, none raised")
        except PluginLoadError as e:
            runner.assert_test("EP load() throws AttributeError", True, f"Caught expected PluginLoadError: {e}")
        except Exception as e:
            runner.assert_test("EP load() throws AttributeError", False, f"Unexpected exception: {type(e).__name__}: {e}")

    # -------------------------------------------------------------
    # Category 2: PluginNodeAdapter Direct Instantiation & Validation
    # -------------------------------------------------------------

    # Test 2.1: Adapter initialized with primitive int
    try:
        PluginNodeAdapter(1234)  # type: ignore
        runner.assert_test("Adapter init with int", False, "Expected PluginValidationError, none raised")
    except PluginValidationError as e:
        runner.assert_test("Adapter init with int", True, f"Caught expected PluginValidationError: {e}")

    # Test 2.2: Adapter initialized with core Node instance (not PluginNode)
    class DummyCoreNode(Node):
        @property
        def name(self) -> str:
            return "core"

        def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
            return {}

    try:
        PluginNodeAdapter(DummyCoreNode())  # type: ignore
        runner.assert_test("Adapter init with core Node", False, "Expected PluginValidationError, none raised")
    except PluginValidationError as e:
        runner.assert_test("Adapter init with core Node", True, f"Caught expected PluginValidationError: {e}")

    # -------------------------------------------------------------
    # Category 3: Plugin process() Output & Payload Stress Testing
    # -------------------------------------------------------------

    ledger = StateLedger(":memory:")
    run_id = ledger.create_run("stress-run-001")

    # Test 3.1: Plugin returns empty dict payload {}
    class EmptyDictPlugin(PluginNode):
        @property
        def name(self) -> str:
            return "empty_dict_plugin"

        def process(self, inputs: dict[str, Any]) -> dict[str, Any]:
            return {}

    adapter = PluginNodeAdapter(EmptyDictPlugin())
    res = adapter.execute(run_id, ledger)
    runner.assert_test("Plugin process() returns empty dict", res == {}, f"Got {res}")

    # Test 3.2: Plugin returns None -> converted to empty dict {}
    class NoneReturnPlugin(PluginNode):
        @property
        def name(self) -> str:
            return "none_return_plugin"

        def process(self, inputs: dict[str, Any]) -> dict[str, Any]:
            return None  # type: ignore

    adapter = PluginNodeAdapter(NoneReturnPlugin())
    res = adapter.execute(run_id, ledger)
    runner.assert_test("Plugin process() returns None", res == {}, f"Got {res}")

    # Test 3.3: Plugin process() returns integer primitive
    class IntReturnPlugin(PluginNode):
        @property
        def name(self) -> str:
            return "int_return_plugin"

        def process(self, inputs: dict[str, Any]) -> dict[str, Any]:
            return 999  # type: ignore

    adapter = PluginNodeAdapter(IntReturnPlugin())
    try:
        adapter.execute(run_id, ledger)
        runner.assert_test("Plugin process() returns int", False, "Expected PluginValidationError, none raised")
    except PluginValidationError as e:
        runner.assert_test("Plugin process() returns int", True, f"Caught expected PluginValidationError: {e}")

    # Test 3.4: Plugin process() returns list
    class ListReturnPlugin(PluginNode):
        @property
        def name(self) -> str:
            return "list_return_plugin"

        def process(self, inputs: dict[str, Any]) -> dict[str, Any]:
            return ["a", "b", "c"]  # type: ignore

    adapter = PluginNodeAdapter(ListReturnPlugin())
    try:
        adapter.execute(run_id, ledger)
        runner.assert_test("Plugin process() returns list", False, "Expected PluginValidationError, none raised")
    except PluginValidationError as e:
        runner.assert_test("Plugin process() returns list", True, f"Caught expected PluginValidationError: {e}")

    # Test 3.5: Plugin process() returns string
    class StringReturnPlugin(PluginNode):
        @property
        def name(self) -> str:
            return "string_return_plugin"

        def process(self, inputs: dict[str, Any]) -> dict[str, Any]:
            return "invalid_string"  # type: ignore

    adapter = PluginNodeAdapter(StringReturnPlugin())
    try:
        adapter.execute(run_id, ledger)
        runner.assert_test("Plugin process() returns string", False, "Expected PluginValidationError, none raised")
    except PluginValidationError as e:
        runner.assert_test("Plugin process() returns string", True, f"Caught expected PluginValidationError: {e}")

    # Test 3.6: Plugin process() throws ZeroDivisionError
    class ZeroDivPlugin(PluginNode):
        @property
        def name(self) -> str:
            return "zero_div_plugin"

        def process(self, inputs: dict[str, Any]) -> dict[str, Any]:
            return {"val": 1 / 0}

    adapter = PluginNodeAdapter(ZeroDivPlugin())
    engine = WorkflowEngine(nodes=[adapter], ledger=ledger)
    engine_res = engine.run(run_id)
    runner.assert_test(
        "Plugin process() throws ZeroDivisionError in WorkflowEngine",
        engine_res.success is False and engine_res.status == StepStatus.FAILED and "division by zero" in str(engine_res.error),
        f"Result: {engine_res}"
    )

    # Test 3.7: Plugin process() throws KeyError
    class KeyErrorPlugin(PluginNode):
        @property
        def name(self) -> str:
            return "key_error_plugin"

        def process(self, inputs: dict[str, Any]) -> dict[str, Any]:
            return inputs["non_existent_key"]

    run_id_2 = ledger.create_run("stress-run-002")
    adapter = PluginNodeAdapter(KeyErrorPlugin())
    engine = WorkflowEngine(nodes=[adapter], ledger=ledger)
    engine_res = engine.run(run_id_2)
    runner.assert_test(
        "Plugin process() throws KeyError in WorkflowEngine",
        engine_res.success is False and engine_res.status == StepStatus.FAILED and "non_existent_key" in str(engine_res.error),
        f"Result: {engine_res}"
    )

    # Test 3.8: Plugin returns non-JSON serializable dict payload
    class NonJsonPlugin(PluginNode):
        @property
        def name(self) -> str:
            return "non_json_plugin"

        def process(self, inputs: dict[str, Any]) -> dict[str, Any]:
            return {"unserializable": object()}

    run_id_3 = ledger.create_run("stress-run-003")
    adapter = PluginNodeAdapter(NonJsonPlugin())
    engine = WorkflowEngine(nodes=[adapter], ledger=ledger)
    engine_res = engine.run(run_id_3)
    runner.assert_test(
        "Plugin returns non-JSON-serializable dict",
        engine_res.success is False and engine_res.status == StepStatus.FAILED,
        f"Result: {engine_res}"
    )

    # Test 3.9: Plugin with missing run_id in ledger
    adapter = PluginNodeAdapter(EmptyDictPlugin())
    try:
        adapter.execute("non-existent-run-id", ledger)
        runner.assert_test("Adapter execute with invalid run_id", False, "Expected PipelineError, none raised")
    except PipelineError as e:
        runner.assert_test("Adapter execute with invalid run_id", True, f"Caught expected PipelineError: {e}")

    # Test 3.10: Plugin property name raises exception during PluginLoader.load_plugins()
    class ExceptionNamePlugin(PluginNode):
        @property
        def name(self) -> str:
            raise RuntimeError("Property name evaluation failed")

        def process(self, inputs: dict[str, Any]) -> dict[str, Any]:
            return {}

    mock_ep = make_mock_ep("ep_exception_name", ExceptionNamePlugin)
    with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
        loader = PluginLoader()
        try:
            loader.load_plugins()
            runner.assert_test("Plugin property name throws exception during load", False, "Expected PluginLoadError/PluginValidationError, uncaught RuntimeError occurred")
        except (PluginLoadError, PluginValidationError) as e:
            runner.assert_test("Plugin property name throws exception during load", True, f"Caught plugin error: {e}")
        except RuntimeError as e:
            runner.assert_test("Plugin property name throws exception during load", False, f"Uncaught RuntimeError during adapter.name evaluation: {e}")
        except Exception as e:
            runner.assert_test("Plugin property name throws exception during load", False, f"Unexpected exception: {type(e).__name__}: {e}")

    # Test 3.11: PluginLoader classmethod invocation check
    try:
        # Calling on class without instance or self_or_cls arg
        PluginLoader.load_plugins()  # type: ignore
        runner.assert_test("PluginLoader classmethod load_plugins()", True, "Called class method successfully")
    except TypeError as e:
        runner.assert_test(
            "PluginLoader classmethod load_plugins()",
            False,
            f"TypeError raised because missing @classmethod decorator: {e}"
        )
    except Exception as e:
        runner.assert_test("PluginLoader classmethod load_plugins()", False, f"Unexpected exception: {type(e).__name__}: {e}")

    print("\n=== SUMMARY ===")
    print(f"Total: {runner.passed + runner.failed} | Passed: {runner.passed} | Failed: {runner.failed}")
    return runner.failed == 0


if __name__ == "__main__":
    success = run_all_stress_tests()
    sys.exit(0 if success else 1)
