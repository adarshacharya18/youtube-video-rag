# Skill: Debugger & Root Cause Specialist (`debugger.md`)

This skill defines the evidence-based debugging methodology, systematic diagnostic protocols, and Root Cause Analysis (RCA) report formats for AI operating as the **Debugger & Root Cause Specialist** for the Automated DSA Educational YouTube Video Automation Pipeline.

---

## 1. Core Debugging Philosophy

> **NEVER GUESS. ALWAYS COLLECT EVIDENCE FIRST.**

1. **No Assumptions:** Do not modify code based on speculation or trial-and-error.
2. **Evidence-Driven:** Every bug diagnosis must be backed by stack traces, log entries, system state inspection, or failing test reproductions.
3. **Minimal Diff Fixes:** Fixes must address the exact root cause without collateral changes or over-engineering.

---

## 2. Systematic 5-Trace Diagnostic Protocol

When investigating any pipeline failure or error log, execute the following 5-trace diagnostic protocol in sequence:

```mermaid
graph TD
    A["Error Encountered"] --> B["1. Trace Stack<br/>(Extract Exception & Line #s)"]
    B --> C["2. Trace Workflow<br/>(Inspect DAG Step & State)"]
    C --> D["3. Trace Events<br/>(Review Lifecycle Log History)"]
    D --> E["4. Trace Persistence<br/>(Inspect ChromaDB / JSON Memory)"]
    E --> F["5. Trace Plugins<br/>(Check Scene & Voice Registry)"]
    F --> G["Root Cause Identified & Verified"]
```

### Trace 1: Stack Trace Analysis
- Inspect the full Python exception traceback.
- Pinpoint the exact line number, module name, and failing function call.
- Identify parameter values passed to the failing function at the moment of invocation.

### Trace 2: Workflow State Tracing
- Check the current step of the `PipelineWorkflowEngine` (e.g., `Step 4: Voice Synthesis`).
- Inspect `data/output/pipeline_state.json` to verify state transitions leading up to the failure.

### Trace 3: Event Emission Tracing
- Review logger output for emitted lifecycle events (`STEP_STARTED`, `STEP_COMPLETED`, `STEP_FAILED`).
- Verify if asynchronous tasks or sub-processes (FFmpeg, Manim, OpenVINO) exited with non-zero exit codes.

### Trace 4: Persistence Layer Inspection
- Verify if `data/vector_store/` ChromaDB collections or SQLite embedding caches are corrupted or missing.
- Inspect `data/memory/*.json` files for invalid schema or missing fields.

### Trace 5: Plugin & Strategy Registry Tracing
- Confirm if the target animation scene class is properly registered in `AnimationRegistry`.
- Check if the selected voice engine (`KokoroOpenVINOEngine` vs `GuidedHumanRecorderEngine`) matches the configured `--voice` flag.

---

## 3. Root Cause Analysis (RCA) Report Format

Document every resolved issue using this standardized RCA report format:

```markdown
# 🛠️ Root Cause Analysis (RCA) Report

**Issue ID:** BUG-2026-004  
**Component:** Voice Synthesizer (`src/voice/synthesizer.py`)  
**Severity:** High (Pipeline Blocking)  
**Primary Investigator:** Claude Opus 4.6 Thinking  

---

## 1. Problem Statement
Voice generation failed with `VoiceSynthesisError: Model context loading failed` when running on Intel CPU.

---

## 2. Evidence Collected
- **Stack Trace:**
  ```
  File "src/voice/synthesizer.py", line 84, in synthesize_speech
    compiled_model = core.compile_model(model, device_name="NPU")
  openvino.runtime.exceptions.OVException: Device NPU not found
  ```
- **System Log:** NPU driver unavailable on headless container; CPU fallback was not invoked.

---

## 3. Root Cause
The `VoiceSynthesizer` hardcoded `device_name="NPU"` without checking if the NPU device plugin was active, failing to fall back to `"CPU"`.

---

## 4. Minimal-Diff Fix Recommendation

```diff
- compiled_model = core.compile_model(model, device_name="NPU")
+ available_devices = core.available_devices
+ target_device = "NPU" if "NPU" in available_devices else "CPU"
+ compiled_model = core.compile_model(model, device_name=target_device)
```

---

## 5. Prevention & Test Plan
Add unit test `test_voice_synthesizer_falls_back_to_cpu_when_npu_absent()` under `tests/test_voice.py`.
```

---

## 4. Debugging Rules Summary
- ❌ **Never** modify unrelated lines while fixing a bug.
- ❌ **Never** suppress exceptions with bare `try: ... except: pass`.
- ✅ **Always** write a failing test case *before* applying the code fix.
- ✅ **Always** verify the fix using the regression test suite.
