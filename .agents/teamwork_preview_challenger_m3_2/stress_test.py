"""
Empirical Stress-Testing Harness for core/base.py and core/exceptions.py
========================================================================
Phase 01: Initial Setup & Global Architecture
Challenger Agent 2 empirical verification suite.
"""

import inspect
import sys
from datetime import datetime
from typing import get_type_hints

from src.core.base import (
    BasePipelineResult,
    PipelineModule,
    Service,
    Repository,
    Provider,
    Factory,
    Command,
    Configuration,
    Lifecycle,
    Validator,
)
from src.core import exceptions
from src.core.exceptions import (
    PipelineError,
    RetryableError,
    FatalError,
    ConfigurationError,
    ValidationError,
    PipelineValidationError,
    PipelineStageError,
    NetworkError,
    AuthenticationError,
    RateLimitError,
    ScraperError,
    ProblemNotFoundError,
    TagExplorerError,
    RAGError,
    IndexNotFoundError,
    EmbeddingError,
    KnowledgeConflictError,
    ScriptGenerationError,
    VoiceGenerationError,
    AnimationError,
    AssemblyError,
    YouTubeUploadError,
)


def run_all_stress_tests() -> None:
    print("=" * 70)
    print("EMPIRICAL STRESS-TEST SUITE: CORE PROTOCOLS & EXCEPTION HIERARCHY")
    print("=" * 70)

    # ---------------------------------------------------------
    # TEST GROUP 1: PipelineModule @runtime_checkable Validation
    # ---------------------------------------------------------
    print("\n--- TEST GROUP 1: PipelineModule @runtime_checkable Protocol ---")

    class ValidModule:
        def execute(self, payload: str) -> str:
            return payload.upper()

    class MissingExecuteModule:
        def run(self, payload: str) -> str:
            return payload

    class NoArgsExecuteModule:
        def execute(self) -> str:
            return "no_args"

    class AttributeExecuteModule:
        def __init__(self):
            self.execute = "not_a_method"

    class PropertyExecuteModule:
        @property
        def execute(self):
            return lambda payload: payload

    valid_inst = ValidModule()
    missing_inst = MissingExecuteModule()
    no_args_inst = NoArgsExecuteModule()
    attr_inst = AttributeExecuteModule()
    prop_inst = PropertyExecuteModule()

    print(f"[1.1] Valid class instance: isinstance(ValidModule(), PipelineModule) -> {isinstance(valid_inst, PipelineModule)}")
    print(f"[1.2] Missing execute method: isinstance(MissingExecuteModule(), PipelineModule) -> {isinstance(missing_inst, PipelineModule)}")
    print(f"[1.3] Signature mismatch (0 args): isinstance(NoArgsExecuteModule(), PipelineModule) -> {isinstance(no_args_inst, PipelineModule)}")
    print(f"[1.4] Non-callable attribute: isinstance(AttributeExecuteModule(), PipelineModule) -> {isinstance(attr_inst, PipelineModule)}")
    print(f"[1.5] Property returning callable: isinstance(PropertyExecuteModule(), PipelineModule) -> {isinstance(prop_inst, PipelineModule)}")

    # Class vs Instance isinstance trap
    print(f"[1.6] Uninstantiated Class Object: isinstance(ValidModule, PipelineModule) -> {isinstance(ValidModule, PipelineModule)}")
    try:
        ValidModule.execute("test")  # type: ignore
    except TypeError as e:
        print(f"      Calling execute on Class Object raises TypeError: {e}")

    # ---------------------------------------------------------
    # TEST GROUP 2: Empty Marker Protocol Behavior (Service)
    # ---------------------------------------------------------
    print("\n--- TEST GROUP 2: Empty Protocol (Service) Runtime Check ---")
    class DummyClass:
        pass

    print(f"[2.1] Arbitrary user class: isinstance(DummyClass(), Service) -> {isinstance(DummyClass(), Service)}")
    print(f"[2.2] Built-in primitive int: isinstance(42, Service) -> {isinstance(42, Service)}")
    print(f"[2.3] Built-in None: isinstance(None, Service) -> {isinstance(None, Service)}")

    # ---------------------------------------------------------
    # TEST GROUP 3: Multi-method Protocol Completeness Checks
    # ---------------------------------------------------------
    print("\n--- TEST GROUP 3: Multi-method Protocols (Lifecycle, Repository) ---")
    class IncompleteLifecycle:
        def initialize(self) -> None:
            pass

    class CompleteLifecycle:
        def initialize(self) -> None:
            pass
        def shutdown(self) -> None:
            pass

    print(f"[3.1] Missing 1 of 2 methods (Lifecycle): isinstance(IncompleteLifecycle(), Lifecycle) -> {isinstance(IncompleteLifecycle(), Lifecycle)}")
    print(f"[3.2] All methods present (Lifecycle): isinstance(CompleteLifecycle(), Lifecycle) -> {isinstance(CompleteLifecycle(), Lifecycle)}")

    # ---------------------------------------------------------
    # TEST GROUP 4: Operational vs Transient Error Categorization
    # ---------------------------------------------------------
    print("\n--- TEST GROUP 4: Exception Hierarchy & Categorization ---")

    all_exceptions = [
        obj for name, obj in inspect.getmembers(exceptions, inspect.isclass)
        if issubclass(obj, Exception) and obj is not Exception
    ]

    retryable = [cls for cls in all_exceptions if issubclass(cls, RetryableError)]
    fatal = [cls for cls in all_exceptions if issubclass(cls, FatalError)]
    unclassified = [
        cls for cls in all_exceptions 
        if not issubclass(cls, RetryableError) and not issubclass(cls, FatalError)
    ]

    print(f"Total custom exception classes defined: {len(all_exceptions)}")
    print(f"[4.1] Subclasses of RetryableError ({len(retryable)}): {[c.__name__ for c in retryable]}")
    print(f"[4.2] Subclasses of FatalError ({len(fatal)}): {[c.__name__ for c in fatal]}")
    print(f"[4.3] Unclassified Base/Module Errors ({len(unclassified)}): {[c.__name__ for c in unclassified]}")

    # Test MRO for multiple inheritance exceptions
    prob_err = ProblemNotFoundError("404 Slug Not Found")
    print(f"[4.4] Multiple Inheritance ProblemNotFoundError:")
    print(f"      isinstance(prob_err, ScraperError) -> {isinstance(prob_err, ScraperError)}")
    print(f"      isinstance(prob_err, FatalError) -> {isinstance(prob_err, FatalError)}")
    print(f"      isinstance(prob_err, PipelineError) -> {isinstance(prob_err, PipelineError)}")

    embed_err = EmbeddingError("API Connection Timeout")
    print(f"[4.5] Multiple Inheritance EmbeddingError:")
    print(f"      isinstance(embed_err, RAGError) -> {isinstance(embed_err, RAGError)}")
    print(f"      isinstance(embed_err, RetryableError) -> {isinstance(embed_err, RetryableError)}")
    print(f"      isinstance(embed_err, PipelineError) -> {isinstance(embed_err, PipelineError)}")

    # ---------------------------------------------------------
    # TEST GROUP 5: BasePipelineResult Edge Cases
    # ---------------------------------------------------------
    print("\n--- TEST GROUP 5: BasePipelineResult Dataclass Behaviors ---")
    res_success = BasePipelineResult(success=True, data={"result": 100})
    res_fail = BasePipelineResult(
        success=False,
        error=FatalError("Database corrupted"),
        error_message="Database corrupted",
        execution_time_ms=45.2
    )

    print(f"[5.1] Success result: success={res_success.success}, data={res_success.data}, err={res_success.error}")
    print(f"[5.2] Failure result: success={res_fail.success}, err_type={type(res_fail.error).__name__}, msg='{res_fail.error_message}'")
    print(f"[5.3] Timestamp auto-generation: timestamp type is {type(res_success.timestamp).__name__}, tz info is {res_success.timestamp.tzinfo}")

    print("\n" + "=" * 70)
    print("ALL EMPIRICAL STRESS-TESTS COMPLETED SUCCESSFULLY.")
    print("=" * 70)

if __name__ == "__main__":
    run_all_stress_tests()
