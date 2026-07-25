# Phase 03 RAG & Knowledge Organization Re-Challenge Report

**Target File**: `src/core/rag/embedder.py`  
**Test Suite**: `tests/rag/test_embedder.py` & `stress_harness.py`  
**Date**: 2026-07-25  
**Role**: Empirical Challenger (critic, specialist)  

---

## Executive Summary & Verdict

**VERDICT: FAIL / REJECTED**

While the unit test suite (`.venv/bin/pytest tests/rag/test_embedder.py`) passes 14/14 tests, empirical stress testing using custom stress harnesses surfaced **3 active edge-case defects** in `src/core/rag/embedder.py`:

1. **TextChunker Dead Code Overlap Bug**: `chunk_overlap` produces **0 overlap** whenever chunks consist of single discrete units (e.g. paragraphs or sections), because `range(j - 1, i, -1)` evaluates to an empty range when `j = i + 1`.
2. **CodeChunker Empty Chunk Emission Bug**: When a function boundary triggers a chunk split and preceding comments/decorators are detached, leading blank lines in `prev_chunk_lines` result in an **empty chunk (`content=""`)** being appended to the returned chunks list.
3. **CodeChunker Premature Class State Reset Bug**: Class header reset on indent 0 occurs *before* flushing pending lines of the preceding class method block, causing the last chunk of a class method to **lose its `class_header` context prefix**.

Requirements 1 and 2 (Single-Line Character Overflow for TextChunker and CodeChunker) are fully resolved and passed all stress tests up to 10,000+ character lines.

---

## Challenge Summary

**Overall risk assessment**: **HIGH**  
*(Chunking errors impair vector retrieval quality, produce empty vectors in embedding pipelines, and strip contextual metadata from class code chunks.)*

---

## Detailed Findings & Challenges

### [High Risk] Challenge 1: `TextChunker` Fails to Apply Overlap to Single-Unit Chunks (Requirement 3)

- **Assumption Challenged**: Setting `chunk_overlap > 0` guarantees sliding window overlap between consecutive text chunks.
- **Attack Scenario**: Submit text consisting of paragraphs/sections where each paragraph exceeds `max_chunk_size - chunk_overlap` but is less than `max_chunk_size`.
  - **Reproduction Code**:
    ```python
    from src.core.rag.embedder import TextChunker

    chunker = TextChunker(max_chunk_size=80, chunk_overlap=30)
    text = "Short para 1.\n\nParagraph two is longer and takes up most of the max chunk size limit."
    chunks = chunker.split_text(text)
    # Result: Chunk 0 = 'Short para 1.', Chunk 1 = 'Paragraph two is longer...'
    # Overlap between Chunk 0 and Chunk 1: 0 characters (expected up to 30 chars).
    ```
- **Blast Radius**: Documents split at section or paragraph boundaries receive **zero overlap**, creating hard retrieval boundaries and missing context across chunk boundaries in RAG searches.
- **Root Cause**: In `TextChunker.split_text` (lines 236-245 of `embedder.py`), the loop iterating over previous units to compute overlap is:
  ```python
  for k in range(j - 1, i, -1):
  ```
  When a chunk contains a single unit (`j = i + 1`), `j - 1` equals `i`. Python's `range(i, i, -1)` is **empty**, so the loop never executes, `next_i` remains `j`, and `units[i]` is completely omitted from the next chunk.
- **Suggested Defense**: Change the range stop index to `i - 1` or explicitly allow unit `i` to be included in `overlap_acc` calculation when `overlap_acc + len(units[i]) <= overlap`.

---

### [Medium Risk] Challenge 2: `CodeChunker` Emits Empty Chunks (`content=""`) during Comment Detachment (Requirement 4)

- **Assumption Challenged**: Comment detachment cleanly transfers comments/decorators to the next function chunk without generating phantom empty chunks.
- **Attack Scenario**: Submit multi-function code where a chunk size split occurs at a blank line prior to comments/decorators.
  - **Reproduction Code**:
    ```python
    from src.core.rag.embedder import CodeChunker

    code = """def first_func():
        # Inside first func line 1
        # Inside first func line 2
        x = 100
        y = 200
        return x + y

    # Comment for second func
    @decorator
    def second_func():
        return 2
    """
    chunker = CodeChunker(max_chunk_size=120)
    chunks = chunker.split_code(code)
    # Output chunks:
    # Chunk 0: 'def first_func():\n ... return x + y'
    # Chunk 1: ''  <-- EMPTY CHUNK EMITTED!
    # Chunk 2: '# Comment for second func\n@decorator\ndef second_func():'
    ```
- **Blast Radius**: Embedding engines (e.g. OpenAIEmbedder) receive empty strings, generating waste API calls or zero-vector noise in vector stores.
- **Root Cause**: In `CodeChunker.split_code` (lines 428-454 of `embedder.py`), `prev_chunk_lines` evaluated to `['']`. `CodeChunker` creates a `Chunk` object without verifying `if content.strip():`.
- **Suggested Defense**: Add a check `if content.strip():` before appending `Chunk` to `chunks`, and ensure `k` calculation in comment detachment ignores leading blank lines.

---

### [Medium Risk] Challenge 3: `CodeChunker` Prematurely Resets `class_header` Context Prefix (Requirement 5)

- **Assumption Challenged**: Resetting `class_header` at indent 0 preserves `class_header` context prefixes for all chunks belonging to class methods.
- **Attack Scenario**: Submit a class with methods followed by a standalone top-level function at indent 0.
  - **Reproduction Code**:
    ```python
    from src.core.rag.embedder import CodeChunker

    code = """class MyClass:
        def method_one(self):
            a = 1
            b = 2
            return a + b

        def method_two(self):
            c = 3
            d = 4
            return c + d

    def standalone():
        return 0
    """
    chunker = CodeChunker(max_chunk_size=100)
    chunks = chunker.split_code(code)
    # Chunk 4: ' return c + d\n' (MISSING 'class MyClass:\n # ... (context)\n' header prefix!)
    ```
- **Blast Radius**: Code chunks representing the ends of class methods lose class context headers, diminishing RAG semantic retrieval precision for method implementations.
- **Root Cause**: In `CodeChunker.split_code` (lines 380-386 of `embedder.py`), `class_header` is reset to `""` when inspecting `def standalone():` at the start of the loop, *before* flushing `current_lines` (which contains `return c + d` from `method_two`).
- **Suggested Defense**: Defer resetting `class_header` until *after* pending `current_lines` from the preceding class block have been flushed/emitted into a chunk.

---

## Stress Test Results Matrix

| Test Scenario | Target Component | Expected Behavior | Actual Behavior | Result |
| :--- | :--- | :--- | :--- | :--- |
| **Single line > 6000 chars (nospace)** | `TextChunker` | Split into sub-lines <= 500 chars | Split into 12 chunks, max len = 500 | **PASS** |
| **Single line > 10k chars (spaced)** | `TextChunker` | Split into sub-lines <= 500 chars | Split into 25 chunks, max len = 500 | **PASS** |
| **Single code line > 6000 chars (unindented)** | `CodeChunker` | Split into sub-lines <= 500 chars | Split into 14 chunks, max len = 500 | **PASS** |
| **Single code line > 6000 chars (indented)** | `CodeChunker` | Split into sub-lines <= 500 chars | Split into 15 chunks, max len = 500 | **PASS** |
| **Indent > max_chunk_size (60 spaces, max 50)** | `CodeChunker` | Handle gracefully <= 50 chars | Split into 1 chunk, max len = 7 | **PASS** |
| **Sliding window overlap (multi-unit)** | `TextChunker` | Consecutive chunks share words | Chunks share 13+ common words | **PASS** |
| **Sliding window overlap (single-unit)** | `TextChunker` | Consecutive chunks share words | **0 overlap between chunks** | **FAIL** |
| **Function comment detachment (basic)** | `CodeChunker` | Comments attached to `def` | Comments attached to `def` | **PASS** |
| **Function comment detachment (line split)** | `CodeChunker` | Comments attached, no empty chunks | **Empty chunk `content=""` emitted** | **FAIL** |
| **Class state reset (top level)** | `CodeChunker` | Standalone func does not inherit class header | Standalone func chunk has no class header | **PASS** |
| **Class state reset (pending flush)** | `CodeChunker` | Class method tail retains class header | **Class method tail loses class header** | **FAIL** |
| **MockEmbedder determinism & norm** | `MockEmbedder` | Deterministic unit vector (norm=1.0) | Deterministic output, L2 norm = 1.0 | **PASS** |
| **get_embedder fallback** | `get_embedder` | Return `MockEmbedder` if API key missing | Returns `MockEmbedder` instance | **PASS** |

---

## Unchallenged Areas

- **OpenAI API Live Embedding Call**: Live network call to OpenAI API was not tested as network access is restricted to offline CODE_ONLY mode. Mock fallback behavior was tested and verified.

---

## Recommendations for Implementation Team

1. Fix `TextChunker.split_text`: Update the overlap range to include index `i` (e.g. `range(j - 1, i - 1, -1)`), ensuring single-unit chunks participate in sliding window overlap.
2. Fix `CodeChunker.split_code` empty chunk bug: Add `if not content.strip(): continue` or filter out empty chunks before returning.
3. Fix `CodeChunker.split_code` class header state reset: Save `active_class_header = class_header` prior to line state updates when emitting pending chunks on boundary lines.
