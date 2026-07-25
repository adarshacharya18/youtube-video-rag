# Handoff Report: Remediation 3 for Phase 03 RAG & Knowledge Organization

**Worker**: Worker 4 (Remediation 3)  
**Target File**: `src/core/rag/embedder.py`  
**Test Suite**: `tests/rag/test_embedder.py`  
**Date**: 2026-07-25  
**Status**: COMPLETE / VERIFIED  

---

## 1. Observation

1. **Defect 1 (`TextChunker` Single-Unit Overlap)**:
   - Line 249 of `src/core/rag/embedder.py` previously executed `i = max(next_i, i + 1)` whenever `next_i == i`. When a text document was split into discrete paragraph units where unit length exceeded `max_chunk_size - chunk_overlap`, setting `next_i` to `i` forced `i` to advance to `i + 1`, dropping preceding unit content entirely and resulting in zero overlap between consecutive chunks.
   - Verbatim error/finding from Challenger 4: Chunk 1 produced 0 character overlap from Chunk 0 when paragraphs exceeded `max_chunk_size - chunk_overlap`.

2. **Defect 3 (`CodeChunker` Class Header Context Preservation)**:
   - In `CodeChunker.split_code`, `class_header` was reset to `""` immediately upon encountering an unindented line at `indent == 0` (that was not `class `, `struct `, `#`, or `@`).
   - Unindented statements such as `import os`, `GLOBAL_VAR = 100`, or `if __name__ == ...` were not recognized as boundary triggers (`is_boundary` was `False`), causing `line` to be appended to `current_lines` while `class_header` was already cleared to `""`. When `current_lines` was subsequently flushed, the trailing class method lines lost their `class_header` context prefix.

---

## 2. Logic Chain

1. **Defect 1 Remediation**:
   - In `TextChunker.split_text`, when unit-level overlap cannot prepend full units (e.g. `next_i == j` or `next_i == i`, so `i` advances to `j` via `i = j`), we check if `overlap > 0` and `chunks` is non-empty and `i == j_prev`.
   - If `i == j_prev` (meaning zero unit-level overlap occurred), `TextChunker` calculates available space `avail = max_size - len(unit_str)`.
   - If `avail > 0`, it extracts `max_overlap_chars = min(overlap, avail - len(sep))` trailing characters from `chunks[-1].content` and prepends `overlap_str + sep` to `unit_str`.
   - This guarantees non-zero character overlap for single-unit chunks while strictly respecting `max_chunk_size`.

2. **Defect 3 Remediation**:
   - In `CodeChunker.split_code`, we defined `is_top_level_non_comment` as an unindented line (`indent == 0`) that is not `#` or `@`.
   - We updated `is_boundary` to evaluate `bool(current_lines and (... or (is_top_level_non_comment and active_class_header)))`.
   - When an unindented top-level line is encountered while `active_class_header` is present, `is_boundary` becomes `True`, forcing `current_lines` (containing the end of the class method) to flush using `active_class_header`.
   - The state reset of `class_header` (setting it to `""` for top-level code or updating it for a new `class ` definition) was moved to execute AFTER boundary checks and chunk flushes complete for the line.

---

## 3. Caveats

- **Character Overlap Fitting**: If a single discrete paragraph unit is already exactly `max_chunk_size` characters long, no preceding character overlap can be prepended without exceeding `max_chunk_size`. When `len(unit) < max_chunk_size`, trailing character overlap is prepended up to the available capacity.
- **No network testing**: OpenAI API tests were run using MockEmbedder fallback in offline CODE_ONLY network mode.

---

## 4. Conclusion

Both active defects in `src/core/rag/embedder.py` are resolved with genuine, minimal logic changes. `TextChunker` guarantees non-zero character overlap across discrete unit chunks, and `CodeChunker` preserves `class_header` context prefixes when flushing class method blocks prior to unindented top-level statements. All 62 unit tests across `tests/core`, `tests/ingestion`, and `tests/rag` pass.

---

## 5. Verification Method

To independently verify this implementation:

1. Run embedder test suite:
   ```bash
   .venv/bin/pytest tests/rag/test_embedder.py
   ```
2. Run vector store test suite:
   ```bash
   .venv/bin/pytest tests/rag/test_vector_store.py
   ```
3. Run all core, ingestion, and rag tests:
   ```bash
   .venv/bin/pytest tests/core tests/ingestion tests/rag
   ```
4. Verify explicit edge cases:
   - `test_text_chunker_single_unit_overlap_discrete_units`: Confirms non-zero character overlap in subsequent chunks for paragraphs > `max_chunk_size - chunk_overlap`.
   - `test_code_chunker_class_header_top_level_statements`: Confirms class method tail chunk retains `class_header` context prefix when followed by top-level `import`, `GLOBAL_VAR`, or `if __name__`.
