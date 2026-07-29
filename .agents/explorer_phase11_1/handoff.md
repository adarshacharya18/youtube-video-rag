# Handoff Report: Phase 11 Core Node Abstraction & Execution Model Investigation

## 1. Observation
- **Core Node Abstract Base Class**: Defined in `src/core/workflow/node.py` (lines 18–131). `Node(ABC)` requires `@property @abstractmethod def name(self) -> str` (line 30) and `@abstractmethod def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]` (line 42). Provides three helper methods:
  - `get_run_record(run_id, ledger)` (lines 59–79): Retrieves `PipelineRunRecord` or raises `PipelineStageError`.
  - `get_completed_step_outputs(run_id, ledger)` (lines 81–98): Returns `{step_name: output_payload}` for completed steps.
  - `get_step_output(run_id, ledger, step_name)` (lines 100–131): Returns `output_payload` for a specific step or raises `PipelineStageError`.
- **Workflow Engine**: Defined in `src/core/workflow/engine.py` (lines 75–268). `WorkflowEngine` executes nodes sequentially.
  - Step idempotency check (lines 146–158): Skips execution if `StepStatus.COMPLETED` is found in `StateLedger` for `node.name`.
  - Lifecycle event emissions (lines 160–165, 174–182, 214–223): Emits `NodeStarted`, `NodeCompleted`, and `NodeFailed` to `EventBus` if configured.
  - Fault tolerance (lines 192–238): Catches node execution exceptions, logs error details, records step failure in `StateLedger` (lines 209–213), emits `NodeFailed` event, and returns `EngineResult` with `success=False` and `status=StepStatus.FAILED`.
- **Plugin Integration**: Defined in `src/core/workflow/plugin_loader.py` (lines 38–103). `PluginNodeAdapter(Node)` wraps `PluginNode` (`src/sdk/plugin_base.py:13–56`) and adapts its `process(inputs: dict) -> dict` interface to `execute(run_id, ledger)`.
- **Structured Output & Exception Hierarchy**: `BaseLLMProvider` in `src/core/llm/provider.py` (lines 32–279) uses `chat_model.with_structured_output(response_model)` to generate Pydantic outputs and translates exceptions into hierarchy in `src/core/exceptions.py` (lines 13–165).
- **Test Executions**: Running `pytest tests/workflow/test_engine.py tests/workflow/test_plugin_loader.py` succeeds with 22 passed tests.

## 2. Logic Chain
1. **Node Inheritance Requirements**: Any new node (including Phase 11 `ScriptGeneratorNode` at `src/pipeline/nodes/script_generator_node.py`) must inherit directly from `Node` (or wrap a `PluginNode` via `PluginNodeAdapter`).
2. **Method Contracts**: Subclasses must implement `name` (returning a unique string identifier such as `"script"`) and `execute(run_id, ledger)`.
3. **Data Communication Protocol**: Subclasses must not pass in-memory state objects directly to subsequent steps. Input state must be queried from `StateLedger` using `self.get_step_output(run_id, ledger, prior_step_name)`. The return payload must be a `dict[str, Any]` which `WorkflowEngine` saves to `StateLedger`.
4. **Error Handling Alignment**: Standard exceptions raised inside `execute()` will be caught by `WorkflowEngine`, recorded in SQLite as `FAILED`, and will safely short-circuit the workflow. Node-internal retries (such as an LLM Error-Feedback loop for JSON/Pydantic validation errors) must be handled inside `execute()` before re-raising unrecoverable errors.

## 3. Caveats
- `src/pipeline/nodes/` directory and `script_generator_node.py` do not exist yet; they will be created during the Phase 11 implementation phase.
- No existing production nodes currently live in `src/pipeline/nodes/`; the patterns are established in core adapters (`PluginNodeAdapter`) and workflow test node mocks (`MockIngestNode`, `MockPlanNode`).

## 4. Conclusion
The core `Node` abstraction (`src/core/workflow/node.py`) and `WorkflowEngine` (`src/core/workflow/engine.py`) provide a well-defined, robust foundation for implementing Phase 11 `ScriptGeneratorNode`. The node signature, state ledger helpers, dictionary-based output payloads, and exception handling are verified and ready for downstream implementation.

## 5. Verification Method
1. Run engine & plugin unit tests:
   ```bash
   pytest tests/workflow/test_engine.py tests/workflow/test_plugin_loader.py
   ```
2. Inspect core node abstraction file:
   `/home/adarsh/Documents/Youtube-Channel/src/core/workflow/node.py`
3. Inspect core workflow engine file:
   `/home/adarsh/Documents/Youtube-Channel/src/core/workflow/engine.py`
4. Inspect comprehensive analysis report:
   `/home/adarsh/Documents/Youtube-Channel/.agents/explorer_phase11_1/analysis.md`
