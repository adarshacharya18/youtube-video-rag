# Project: Phase 12 Media Production (Animation - Manim)

## Architecture
- **Pipeline Node Abstraction**: `AnimationGeneratorNode` inherits from `Node` (`src/core/workflow/node.py`), executing within `WorkflowEngine`.
- **State Integration**: Reads `script_generator` output from SQLite `StateLedger` via `run_id`, extracts `VisualCue` list from `YouTubeScript`, maps visual cues to Manim scene templates, and writes `RenderSegment` objects back to `StateLedger`.
- **Subprocess Isolation**: Manim binary is executed via `subprocess.run()` with strict timeout (120s), isolated temporary directories (`tempfile.TemporaryDirectory()`), pipe management, and mandatory `close_fds=True`.
- **Memory & Storage Sanitation**: All temp files/directories and file descriptors are explicitly cleaned up in `finally` blocks on both success and failure.
- **Caching**: Content-addressable SHA-256 hash of visual cue parameters to reuse previously rendered video clips.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | AnimationGeneratorNode | Core node inheriting from `Node`, reading visual cues from ledger, executing Manim, returning `RenderSegment` outputs | M1 | R1 |
| 2 | Visual Cue to Scene Mapping | Mapping script `VisualCue.animation_type` (`array_highlight`, `tree_traversal`, `code_highlight`, `linkedlist_operation`, etc.) to Manim scene templates in `src/animation/scenes/` | M1 | R1 |
| 3 | Secure Subprocess Execution | Executing Manim binary securely via `subprocess.run()` with configurable CLI flags, quality flags (`-ql`, `-qm`, `-qh`), and timeout enforcement | M1 | R2 |
| 4 | Memory & Tempdir Cleanup | Explicit context management of temporary output directories and file descriptors, cleaned up on success and failure | M1 | R2 |
| 5 | SHA-256 Render Caching | Content-addressable caching mechanism preventing redundant renders | M1 | R2 |
| 6 | Unit & Integration Test Suite | `tests/pipeline/test_animation_node.py` utilizing a mock Python script to simulate Manim binary, testing CLI flags and tempdir deletion | M2 | Acceptance Criteria |
| 7 | Fail-Safe & Leak Tests | Verifying tempdir deletion and FD cleanup on both successful execution and simulated rendering failure | M2 | Acceptance Criteria |
| 8 | Architectural Documentation | `PromptBook/Phase12/01_Animation_Production.md` documenting rendering boundaries, caching, memory architecture, and CLI invocation strategies | M3 | R3 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Animation Generator Node & Subprocess Execution | `src/pipeline/nodes/animation_generator_node.py` | Core Node, StateLedger | DONE |
| M2 | Test Suite with Mock Manim Binary | `tests/pipeline/test_animation_node.py` | M1 | DONE |
| M3 | Animation Production Documentation | `PromptBook/Phase12/01_Animation_Production.md` | M1 | PLANNED |


## Interface Contracts
### `AnimationGeneratorNode` ↔ `StateLedger`
- Input step: `"script_generator"`
- Input payload: Dict containing `"script"` (serialized `YouTubeScript`) and `"slug"`.
- Output payload: Dict containing `"segments"` (list of serialized `RenderSegment` dicts) and `"render_count"`.
- Exception: `AnimationError` on subprocess failure, invalid cues, or render timeouts.

## Code Layout
- Node Implementation: `src/pipeline/nodes/animation_generator_node.py`
- Renderer Abstraction: `src/animation/renderer.py`
- Scene Templates: `src/animation/scenes/` (`base_scene.py`, `array_scene.py`, `tree_scene.py`, `code_scene.py`, `graph_scene.py`, `hashmap_scene.py`, `linkedlist_scene.py`, `stack_queue_scene.py`, `complexity_scene.py`)
- Test Suite: `tests/pipeline/test_animation_node.py`
- Architectural Documentation: `PromptBook/Phase12/01_Animation_Production.md`
