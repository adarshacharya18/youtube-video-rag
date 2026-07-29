# Phase 11: Script & Narration Generation

## Overview

Phase 11 introduces automated, structured YouTube script generation for Data Structures and Algorithms (DSA) educational videos. Built as a workflow engine node (`ScriptGeneratorNode`), this phase converts raw DSA problem descriptions into a timed, highly engaging script divided according to key YouTube audience retention metrics.

---

## 1. Scripting Structure & Retention Logic

YouTube educational videos require explicit structural pacing to maintain high viewer retention. The script format is divided into four core sections:

1. **Hook (15–30 Seconds)**:
   - **Goal**: Instantly grab viewer attention with a high-stakes problem setup or intrigue.
   - **Components**: Spoken narration highlighting the core challenge, paired with high-impact visual cues.

2. **Context (Problem & Intuition)**:
   - **Goal**: Break down problem statement, inputs, outputs, constraints, and naive vs optimal intuition.
   - **Components**: Clear spoken narration and visual layout setup (e.g. array/graph diagrams).

3. **Solution (Step-by-Step Code Walkthrough)**:
   - **Goal**: Walk through the algorithmic solution line-by-line.
   - **Components**: Spoken narration synced with code snippet highlighting and visual animation cues.

4. **Complexity (Big-O Asymptotic Analysis)**:
   - **Goal**: Explain Big-O Time Complexity ($O(N)$, $O(\log N)$) and Space Complexity ($O(1)$, $O(N)$) along with trade-offs.
   - **Components**: Spoken narration and visual complexity card cues.

---

## 2. Pydantic JSON Schema Contract

The script generation process enforces strict validation via the `YouTubeScript` Pydantic V2 schema (`src/models/script.py`).

### Model Definitions

```python
class VisualCue(BaseModel):
    cue_id: str
    animation_type: str
    description: str
    timestamp_seconds: float = 0.0
    parameters: Dict[str, Any] = Field(default_factory=dict)

class HookSection(BaseModel):
    title: str = "Hook"
    narration: str
    visual_cues: List[VisualCue] = Field(default_factory=list)
    estimated_duration: float

class ContextSection(BaseModel):
    title: str = "Context"
    narration: str
    visual_cues: List[VisualCue] = Field(default_factory=list)
    estimated_duration: float

class SolutionSection(BaseModel):
    title: str = "Solution"
    narration: str
    code_snippet: Optional[str] = None
    visual_cues: List[VisualCue] = Field(default_factory=list)
    estimated_duration: float

class ComplexitySection(BaseModel):
    title: str = "Complexity"
    narration: str
    time_complexity: str = "O(N)"
    space_complexity: str = "O(1)"
    visual_cues: List[VisualCue] = Field(default_factory=list)
    estimated_duration: float

class YouTubeScript(BaseModel):
    topic: str
    slug: str  # Must match regex ^[a-z0-9-]+$
    difficulty: str = "Medium"
    hook: HookSection
    context: ContextSection
    solution: SolutionSection
    complexity: ComplexitySection
    total_duration: float
    spoken_narration: List[str] = Field(default_factory=list)
    visual_cues: List[VisualCue] = Field(default_factory=list)
```

### Invariants & Validation Rules
- **Duration Match**: `total_duration` must equal the sum of section durations (`hook + context + solution + complexity`) within a tolerance of $\pm 0.1$s.
- **Slug Standard**: `slug` must match pattern `^[a-z0-9-]+$`.
- **Auto-Aggregation**: `spoken_narration` and `visual_cues` automatically populate from section components if not explicitly passed.

---

## 3. Intelligent Error-Feedback Retry Architecture

To handle LLM hallucinations, corrupted JSON output, or schema mismatches, `ScriptGeneratorNode` uses an **Error-Feedback Retry Loop**:

```
 ┌────────────────────────────────────────────────────────┐
 │ 1. Render Prompt from PromptLoader (script_generation) │
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 2. Invoke LLM Provider                                 │
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
              /─────────────────────────────\
             /  Is output valid JSON &       \
            <   conforms to YouTubeScript     >
             \  Pydantic model?              /
              \─────────────────────────────/
                             │
                   ┌─────────┴─────────┐
             YES   │                   │  NO (ValidationError / JSONDecodeError)
                   ▼                   ▼
    ┌──────────────────────┐  ┌───────────────────────────────────┐
    │ Save Output Payload  │  │ Append Exact Error String (str(e))│
    │ to StateLedger       │  │ to Prompt Context                 │
    └──────────────────────┘  └─────────────────┬─────────────────┘
                                                │
                                                ▼
                                    /───────────────────────\
                                   /  Attempts < max_retries \
                                  <   (default 3)?           >
                                   \───────────────────────/
                                                │
                                      ┌─────────┴─────────┐
                                YES   │                   │  NO
                                      ▼                   ▼
                          ┌─────────────────────┐   ┌────────────────────┐
                          │ Retry Generation    │   │ Raise              │
                          │ with Feedback Prompt│   │ ScriptGeneration-  │
                          └─────────────────────┘   │ Error              │
                                                    └────────────────────┘
```

When `ValidationError` or `JSONDecodeError` is caught, `ScriptGeneratorNode` appends `str(e)` to the prompt context. On the retry attempt, the LLM receives the exact error details describing which field or constraint failed, enabling immediate target self-correction.

---

## 4. Workflow Engine Integration & Usage

### Execution Contract

`ScriptGeneratorNode` subclasses `Node` (`src/core/workflow/node.py`):
- `name`: Returns `"script_generator"`.
- `execute(run_id, ledger)`: Reads completed step outputs (e.g. `ingest` or `plan`) from `StateLedger`, generates the verified script, and records the output payload.

```python
from src.pipeline.nodes.script_generator_node import ScriptGeneratorNode
from src.core.orchestrator.state_ledger import StateLedger

node = ScriptGeneratorNode(llm_provider=llm_client, max_retries=3)
result = node.execute(run_id=run_id, ledger=ledger)
```
