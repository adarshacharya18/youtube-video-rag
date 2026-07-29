# Changes Log — Phase 11 Iteration 2 Remediation

## 1. `src/models/script.py`
- **Location**: Line 231 (in `validate_script_invariants`)
- **Modification**: Changed `if abs(self.total_duration - section_sum) > 0.1:` to `if round(abs(self.total_duration - section_sum), 4) > 0.1:`.
- **Rationale**: Mitigates IEEE 754 floating-point sum artifacts (e.g. `55.8 + 38.08 + 15.47 + 13.91 = 123.25999999999999`) where `abs(123.36 - 123.25999999999999) = 0.10000000000000853 > 0.1`, which caused false-positive `ValidationError` exceptions for valid $\pm 0.10$s boundary inputs. Rounding the difference to 4 decimal places before comparing against `0.1` ensures domain tolerance boundaries are strictly and cleanly evaluated.

## 2. `tests/pipeline/test_script_node.py`
- **Location**: `test_duration_validation_tolerance` (Lines 412-436)
- **Modification**: Added float precision boundary test case validating section durations `55.8`, `38.08`, `15.47`, `13.91` with `total_duration = 123.36`.
- **StateLedger API Verification**: Confirmed all `StateLedger` interactions in `tests/pipeline/test_script_node.py` (specifically `test_state_ledger_input_context_retrieval`) call `record_step_start(pipeline_run_id, step_name, input_payload)` followed by `record_step_completion(step_execution_id, output_payload)` as expected by `src/core/orchestrator/state_ledger.py`.
