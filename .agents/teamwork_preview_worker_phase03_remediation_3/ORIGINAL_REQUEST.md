## 2026-07-25T05:52:07Z
<USER_REQUEST>
MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

You are Worker 4 (Remediation 3) for Phase 03: RAG & Knowledge Organization.
Working directory: `/home/adarsh/Documents/Youtube-Channel/.agents/teamwork_preview_worker_phase03_remediation_3`

Please read Challenger 4's detailed report at:
- `/home/adarsh/Documents/Youtube-Channel/.agents/teamwork_preview_challenger_phase03_re-challenge_2/challenge_report.md`

Your mission is to fix the 2 active defects in `src/core/rag/embedder.py`:

1. Fix Defect 1 (`TextChunker` Single-Unit Overlap):
   - In `TextChunker.split_text`, line 249 (`i = max(next_i, i + 1)`) forced `i` to advance to `i + 1` whenever `next_i == i`, dropping overlap units from subsequent chunks.
   - When a chunk contains discrete units (e.g. paragraphs where unit length > max_chunk_size - chunk_overlap), if `chunk_overlap > 0`, extract trailing character overlap from the tail of the preceding chunk or ensure preceding overlap text is prepended to the new chunk content so zero-overlap does NOT occur.

2. Fix Defect 3 (`CodeChunker` Class Header Context Preservation):
   - In `CodeChunker.split_code`, when encountering an unindented top-level line (`indent == 0` that is not `#` or `@` and not starting with `class `/`struct ` such as `import os`, `GLOBAL_VAR = 100`, `if __name__ == ...`), if `current_lines` contains lines from a class block, treat this line as a chunk boundary (`is_boundary = True`).
   - Treating top-level non-comment lines as chunk boundaries ensures `current_lines` (containing the end of the class method) is flushed with the active `class_header` intact BEFORE `class_header` is reset to `""` for top-level code.

Tests & Verification:
- Update/expand `tests/rag/test_embedder.py` to add explicit unit tests for both edge cases:
  - Paragraphs/units where unit length > `max_chunk_size - chunk_overlap`, confirming non-zero character overlap in subsequent chunks.
  - Class definition followed by top-level `import` or `GLOBAL_VAR` or `if __name__`, confirming the last class method chunk retains its `class_header` context prefix.
- Run tests: `.venv/bin/pytest tests/rag/test_embedder.py` and `.venv/bin/pytest tests/rag/test_vector_store.py` and `.venv/bin/pytest tests/core tests/ingestion tests/rag`.
- Document handoff report in `/home/adarsh/Documents/Youtube-Channel/.agents/teamwork_preview_worker_phase03_remediation_3/handoff.md`.
- Report completion back to parent orchestrator (conversation ID: 8f381ec0-0a11-43e5-afd2-842c2ad1f1db).
</USER_REQUEST>
