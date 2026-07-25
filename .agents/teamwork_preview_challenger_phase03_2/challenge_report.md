# Adversarial Challenge Report — Phase 03: RAG & Knowledge Organization (Embedder & Chunkers)

**Target Module**: `src/core/rag/embedder.py`  
**Test Suite**: `tests/rag/test_embedder.py` & `.agents/teamwork_preview_challenger_phase03_2/stress_test_embedder.py`  
**Overall Risk Assessment**: **HIGH**  
**Verdict**: **FAIL** (5 empirical failures identified across chunking boundary conditions, overlap implementation, and context propagation)

---

## Executive Summary

An empirical stress test harness (`stress_test_embedder.py`) comprising 15 verification scenarios was executed against `src/core/rag/embedder.py`. While standard unit tests in `tests/rag/test_embedder.py` pass (9/9), empirical stress testing exposed critical boundary condition violations, unhandled code chunking edge cases, dead code in chunk overlap logic, and context leakage in `CodeChunker`.

The mathematical invariants of `MockEmbedder` (dimension = 1536/custom, L2 norm = 1.0, SHA-256 determinism, distinctness divergence) and the fallback mechanisms for missing OpenAI API keys operate as expected.

---

## Verified Claims & Working Features

1. **`MockEmbedder` Invariants**:
   - **Vector Dimension**: Consistently returns requested dimension (e.g. 1536 or 512).
   - **L2 Normalization**: Unit vector length satisfies $\|v\|_2 = 1.0$ (precision $\|v\|_2 - 1.0 < 10^{-6}$) across empty strings, whitespace, Unicode symbols, and 10,000+ character strings.
   - **Determinism**: SHA-256 seed guarantees identical float vector outputs across multiple invocations for identical inputs.
   - **Divergence**: Distinct input strings yield distinct unit vectors with cosine similarity near 0 ($\approx -0.0074$).

2. **Fallback Mechanisms**:
   - `OpenAIEmbedder(api_key=None)` raises `EmbeddingError` when API key is missing.
   - `get_embedder(use_mock=False)` gracefully falls back to `MockEmbedder` when `OPENAI_API_KEY` is unset in the environment.
   - `get_embedder(use_mock=True)` explicitly instantiates `MockEmbedder`.

3. **Empty & Whitespace Inputs**:
   - Both `TextChunker` and `CodeChunker` return empty lists `[]` when provided empty (`""`) or whitespace-only (`"  \n\t  "`) strings.

---

## Empirical Failure Modes & Challenges

### [HIGH] Challenge 1: Single-Line Character Length Overflow in `TextChunker` & `CodeChunker`

- **Assumption challenged**: `TextChunker` and `CodeChunker` guarantee that generated chunks do not exceed `max_chunk_size`.
- **Attack Scenario**: Passing single long lines of text or code (e.g., 5,000+ characters without line breaks, such as minified JSON, inline data arrays, or lengthy single-line docstrings/statements).
- **Observed Behavior**:
  - `TextChunker`: Lines 113–122 attempt line splitting via `para_str.split("\n")`. If a single line length exceeds `max_chunk_size`, line 120 sets `current_chunk = line`, yielding chunks up to 5,000+ characters (exceeding `max_chunk_size=200`).
  - `CodeChunker`: Line 301 appends `line` to `current_lines` without character-level splitting for single lines exceeding `max_chunk_size`.
- **Blast Radius**: Chunks exceeding token limits sent to embedding APIs (e.g. OpenAI or vector DB token limits) will trigger HTTP 400 bad request errors or truncation.
- **Mitigation**: Implement hard character splitting or word-wrap truncation when an individual line exceeds `max_chunk_size`.

---

### [MEDIUM] Challenge 2: Dead Code in `TextChunker` Overlap (`chunk_overlap` Ignored)

- **Assumption challenged**: `TextChunker` creates overlapping chunks according to `chunk_overlap`.
- **Attack Scenario**: Invoking `split_text(text, chunk_overlap=20)` on multi-paragraph documents.
- **Observed Behavior**: In `TextChunker.split_text` (line 76), `overlap = chunk_overlap or self.chunk_overlap` is computed, but `overlap` is **never referenced** again in the method. Chunks are generated strictly per-paragraph/section without any sliding window overlap.
- **Blast Radius**: Information at chunk boundaries is completely partitioned with zero overlap, diminishing vector retrieval recall across section boundaries.
- **Mitigation**: Implement sliding window token/character overlap across adjacent chunk units.

---

### [MEDIUM] Challenge 3: Function Comment Detachment in `CodeChunker`

- **Assumption challenged**: `CodeChunker` preserves algorithmic comments alongside function signatures.
- **Attack Scenario**: Passing a Python file where a comment block directly precedes `def function_name()` and total comment block size forces a chunk boundary.
- **Observed Behavior**: In `CodeChunker.split_code` (lines 268–271), `is_boundary` triggers on `stripped.startswith("def ")` when `current_lines` is non-empty. This causes preceding comments to be flushed into Chunk $N$, while Chunk $N+1$ begins with `def function_name()`, separating the documentation from the function signature.
- **Blast Radius**: Loss of algorithmic docstrings/comment context in code vector indexing.
- **Mitigation**: Look ahead or group comment lines (`#`, `//`, `/* */`) with the immediately following statement boundary.

---

### [MEDIUM] Challenge 4: Context State Leakage in `CodeChunker` (`class_header` Leak)

- **Assumption challenged**: `CodeChunker` only prepends `class_header` to chunks inside that class's scope.
- **Attack Scenario**: Input containing a class definition followed by top-level standalone functions or separate functions outside the class.
- **Observed Behavior**: Line 265 updates `class_header = line` upon encountering `class ...`. However, `class_header` is **never cleared** when exiting the class block. Subsequent top-level functions (e.g. `def standalone_function()`) receive `class FirstClass:\n    # ... (context)\n` prepended to their chunk content.
- **Blast Radius**: Hallucinated class context attached to standalone functions, corrupting RAG retrieval accuracy.
- **Mitigation**: Track indentation levels or reset `class_header` when indentation returns to line-start level 0.

---

## Stress Test Results Table

| Test Scenario | Target Component | Expected Behavior | Actual Behavior | Result |
|---|---|---|---|---|
| `Boundary_Empty_and_Whitespace` | Chunkers | Return `[]` | Returned `[]` | **PASS** |
| `Boundary_Massive_Single_Line_Text` | `TextChunker` | Split text into chunks $\le 200$ chars | Created chunk of length 5000 | **FAIL** |
| `Boundary_Massive_Single_Line_Code` | `CodeChunker` | Split code into chunks $\le 200$ chars | Created chunk of length 5003 | **FAIL** |
| `Feature_Chunk_Overlap` | `TextChunker` | Generate overlapping chunk boundaries | 0 sliding overlap (`overlap` unused) | **FAIL** |
| `Boundary_Nested_Markdown` | `TextChunker` | Parse header levels `#` to `#####` | Generated 4 valid section chunks | **PASS** |
| `Boundary_Comments_Detachment` | `CodeChunker` | Keep pre-function comments with `def` | Separated comments from `def` | **FAIL** |
| `Boundary_Class_Header_Leak` | `CodeChunker` | Only prepend `class_header` within class | Prepended `class FirstClass:` to standalone func | **FAIL** |
| `Invariant_MockEmbedder_Dimension` | `MockEmbedder` | Vector length == configured dim | Dim == 1536 and 512 | **PASS** |
| `Invariant_MockEmbedder_L2Norm` | `MockEmbedder` | $\|v\|_2 == 1.0$ (abs diff $< 10^{-6}$) | $\|v\|_2 == 1.000000$ | **PASS** |
| `Invariant_MockEmbedder_Determinism` | `MockEmbedder` | Identical input $\to$ identical vector | Identical float array | **PASS** |
| `Invariant_MockEmbedder_Divergence` | `MockEmbedder` | Distinct input $\to$ distinct vector | Cosine similarity $= -0.0074$ | **PASS** |
| `Fallback_OpenAIEmbedder_MissingKey_Raises` | `OpenAIEmbedder` | Raise `EmbeddingError` | Raised `EmbeddingError` | **PASS** |
| `Fallback_get_embedder_MissingKey_Fallback` | `get_embedder` | Fall back to `MockEmbedder` | Returned `MockEmbedder` | **PASS** |
| `Fallback_get_embedder_ExplicitMock` | `get_embedder` | Return `MockEmbedder` | Returned `MockEmbedder` | **PASS** |
| `Fallback_OpenAIEmbedder_InvalidKey_Fails` | `OpenAIEmbedder` | Raise `EmbeddingError` on API call | Raised `EmbeddingError` | **PASS** |

---

## Unchallenged / Out of Scope Areas

- Live network requests to OpenAI API (testing performed offline per CODE_ONLY policy and mock verification).
- Vector DB integration & Chroma store persistence (handled in `vector_store.py`).
