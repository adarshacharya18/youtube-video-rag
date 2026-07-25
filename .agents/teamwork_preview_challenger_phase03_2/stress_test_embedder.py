"""
Empirical Stress Test Harness for RAG Embedder and Dual Chunking System.
Tests boundary conditions, invariants, edge cases, and fallback mechanisms.
"""

import math
import os
import sys
from typing import List, Dict, Any

# Ensure project root is in sys.path
PROJECT_ROOT = "/home/adarsh/Documents/Youtube-Channel"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.exceptions import EmbeddingError
from src.core.rag.embedder import (
    Chunk,
    CodeChunker,
    MockEmbedder,
    OpenAIEmbedder,
    TextChunker,
    get_embedder,
)

results: Dict[str, Dict[str, Any]] = {}

def record_test(name: str, passed: bool, details: str):
    results[name] = {"passed": passed, "details": details}
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}: {details}")

# ============================================================================
# 1. Chunking Boundary Conditions
# ============================================================================

def test_empty_and_whitespace_inputs():
    chunker_text = TextChunker(max_chunk_size=100)
    chunker_code = CodeChunker(max_chunk_size=100)

    # Empty text & code
    t_empty = chunker_text.split_text("")
    c_empty = chunker_code.split_code("")
    assert t_empty == [], f"Expected empty list for empty text, got {t_empty}"
    assert c_empty == [], f"Expected empty list for empty code, got {c_empty}"

    # Whitespace-only text & code
    t_ws = chunker_text.split_text("   \n\n\t   \n  ")
    c_ws = chunker_code.split_code("   \n\n\t   \n  ")
    assert t_ws == [], f"Expected empty list for whitespace text, got {t_ws}"
    assert c_ws == [], f"Expected empty list for whitespace code, got {c_ws}"

    record_test("Boundary_Empty_and_Whitespace", True, "Empty and whitespace inputs return empty lists correctly.")

def test_massive_single_line_text():
    chunker = TextChunker(max_chunk_size=200)
    long_line = "A" * 5000  # Single line with 5,000 characters
    chunks = chunker.split_text(long_line)

    over_limit = [c for c in chunks if len(c.content) > 200]
    if over_limit:
        record_test(
            "Boundary_Massive_Single_Line_Text",
            False,
            f"TextChunker failed to split single long line of 5000 chars: generated chunk of length {len(over_limit[0].content)} > max_chunk_size 200"
        )
    else:
        record_test(
            "Boundary_Massive_Single_Line_Text",
            True,
            f"TextChunker split 5000 char line into {len(chunks)} chunks, all <= 200 chars."
        )

def test_massive_single_line_code():
    chunker = CodeChunker(max_chunk_size=200)
    long_code_line = "x = " + "+".join(["1"] * 2500)  # ~10,000 chars single line
    chunks = chunker.split_code(long_code_line)

    over_limit = [c for c in chunks if len(c.content) > 200]
    if over_limit:
        record_test(
            "Boundary_Massive_Single_Line_Code",
            False,
            f"CodeChunker failed to split single long code line: generated chunk of length {len(over_limit[0].content)} > max_chunk_size 200"
        )
    else:
        record_test(
            "Boundary_Massive_Single_Line_Code",
            True,
            f"CodeChunker split long line into {len(chunks)} chunks within size limit."
        )

def test_chunk_overlap_implementation():
    # Test if chunk_overlap actually creates overlap using unique sequential tokens
    chunker = TextChunker(max_chunk_size=60, chunk_overlap=20)
    words = [f"word{i:03d}" for i in range(40)]
    text = " ".join(words[:20]) + "\n\n" + " ".join(words[20:])
    chunks = chunker.split_text(text)
    
    # Verify if end of chunk N appears at start of chunk N+1
    has_actual_overlap = False
    if len(chunks) >= 2:
        c0_tokens = chunks[0].content.split()
        c1_tokens = chunks[1].content.split()
        # Check if the last token of c0 is present in c1
        if c0_tokens[-1] in c1_tokens:
            has_actual_overlap = True

    if not has_actual_overlap and len(chunks) >= 2:
        record_test(
            "Feature_Chunk_Overlap",
            False,
            f"TextChunker chunk_overlap (50/20) is dead code: `overlap` variable is unused, resulting in 0 sliding overlap between chunks."
        )
    else:
        record_test(
            "Feature_Chunk_Overlap",
            True,
            f"TextChunker generated chunks with sliding window overlap."
        )

def test_nested_markdown_and_code():
    chunker = TextChunker(max_chunk_size=300)
    doc = """# Main Header

Here is some text.

## Subsection 1
```python
def foo():
    # Inside code block inside markdown
    return 42
```

### Sub-subsection 1.1
- Item 1
- Item 2

#### Sub-sub-subsection 1.1.1
##### Header Level 5 (Non-standard split boundary)
Text under header level 5.
"""
    chunks = chunker.split_text(doc, parent_slug="nested-doc")
    assert len(chunks) > 0, "No chunks generated for nested markdown"
    
    h1_found = any("Main Header" in c.content for c in chunks)
    code_found = any("def foo():" in c.content for c in chunks)
    h5_found = any("Header Level 5" in c.content for c in chunks)
    
    assert h1_found and code_found and h5_found, "Missing nested sections in text chunks"
    record_test("Boundary_Nested_Markdown", True, f"Successfully parsed nested markdown into {len(chunks)} chunks.")

def test_comments_only_code():
    chunker = CodeChunker(max_chunk_size=150)
    comments_code = """# Comment line 1: Explanation of algorithm step 1.
# Comment line 2: Explanation of algorithm step 2.
# Comment line 3: Explanation of algorithm step 3.
# Comment line 4: Explanation of algorithm step 4.
# Comment line 5: Explanation of algorithm step 5.
# Comment line 6: Explanation of algorithm step 6.
def function_after_comments():
    pass
"""
    chunks = chunker.split_code(comments_code)
    
    func_chunk = None
    for c in chunks:
        if "def function_after_comments" in c.content:
            func_chunk = c
            break
            
    comment_in_func_chunk = func_chunk and ("Comment line 6" in func_chunk.content or "Comment line 5" in func_chunk.content)
    
    if len(chunks) > 1 and not comment_in_func_chunk:
        record_test(
            "Boundary_Comments_Detachment",
            False,
            f"CodeChunker split comment block immediately preceding 'def': 'def function_after_comments' was placed in chunk {func_chunk.chunk_id if func_chunk else 'None'} without its preceding comment context."
        )
    else:
        record_test(
            "Boundary_Comments_Detachment",
            True,
            f"CodeChunker preserved comments preceding function definition."
        )

def test_class_header_context_propagation():
    chunker = CodeChunker(max_chunk_size=150)
    code = """class FirstClass:
    def method_one(self):
        val = 1 + 2 + 3 + 4 + 5 + 6 + 7 + 8 + 9 + 10
        return val

def standalone_function():
    print("I am standalone and not inside FirstClass")
"""
    chunks = chunker.split_code(code)
    
    standalone_chunk = None
    for c in chunks:
        if "standalone_function" in c.content:
            standalone_chunk = c
            break

    if standalone_chunk and "class FirstClass:" in standalone_chunk.content:
        record_test(
            "Boundary_Class_Header_Leak",
            False,
            f"CodeChunker state leak: prepended 'class FirstClass:' header to standalone top-level function outside the class scope!"
        )
    else:
        record_test(
            "Boundary_Class_Header_Leak",
            True,
            "CodeChunker did not leak class header to standalone top-level function."
        )

# ============================================================================
# 2. MockEmbedder Invariants
# ============================================================================

def test_mock_embedder_invariants():
    # 1. Dimension invariant
    embedder_default = MockEmbedder(dimension=1536)
    embedder_custom = MockEmbedder(dimension=512)
    
    assert embedder_default.dimension == 1536
    assert embedder_custom.dimension == 512

    # 2. Vector dimension and L2 Norm == 1.0 invariant across various inputs
    test_inputs = [
        "",
        " ",
        "a",
        "Two Sum Problem",
        "A" * 10000,
        "Unicode test: 🚀 🤖 🧮 💻 🐍",
        "Special chars: !@#$%^&*()_+{}[]|\\:\";'<>?,./",
    ]

    norms_pass = True
    dims_pass = True
    norm_failures = []

    for text in test_inputs:
        v1536 = embedder_default.embed_text(text)
        v512 = embedder_custom.embed_text(text)

        if len(v1536) != 1536 or len(v512) != 512:
            dims_pass = False

        norm1536 = math.sqrt(sum(x * x for x in v1536))
        norm512 = math.sqrt(sum(x * x for x in v512))

        if abs(norm1536 - 1.0) > 1e-6:
            norms_pass = False
            norm_failures.append(f"text='{text[:20]}...' norm1536={norm1536}")

        if abs(norm512 - 1.0) > 1e-6:
            norms_pass = False
            norm_failures.append(f"text='{text[:20]}...' norm512={norm512}")

    record_test("Invariant_MockEmbedder_Dimension", dims_pass, f"Dimension invariant satisfied (1536 and 512).")
    record_test("Invariant_MockEmbedder_L2Norm", norms_pass, f"L2 norm == 1.0 (abs diff < 1e-6) satisfied for all test strings. Failures: {norm_failures}")

    # 3. Determinism invariant (identical text produces identical vector)
    v_a1 = embedder_default.embed_text("Same Input Text")
    v_a2 = embedder_default.embed_text("Same Input Text")
    assert v_a1 == v_a2, "Determinism invariant violated!"
    record_test("Invariant_MockEmbedder_Determinism", True, "Identical text produces identical float vector.")

    # 4. Divergence invariant (distinct text produces distinct vector & cosine similarity < 0.95)
    v_b = embedder_default.embed_text("Different Input Text")
    assert v_a1 != v_b, "Divergence invariant violated!"
    
    dot_product = sum(x * y for x, y in zip(v_a1, v_b))
    record_test(
        "Invariant_MockEmbedder_Divergence",
        dot_product < 0.95,
        f"Distinct text produced distinct vector. Cosine similarity (dot product of unit vectors) = {dot_product:.4f}"
    )

# ============================================================================
# 3. OpenAI Fallback & Error Handling Behavior
# ============================================================================

def test_openai_fallback_behavior():
    old_key = os.environ.get("OPENAI_API_KEY")
    try:
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]

        raised_error = False
        err_msg = ""
        try:
            OpenAIEmbedder(api_key=None)
        except EmbeddingError as e:
            raised_error = True
            err_msg = str(e)

        assert raised_error, "OpenAIEmbedder did not raise EmbeddingError when API key is missing!"
        record_test("Fallback_OpenAIEmbedder_MissingKey_Raises", True, f"OpenAIEmbedder raised EmbeddingError: '{err_msg}'")

        emb = get_embedder(use_mock=False)
        assert isinstance(emb, MockEmbedder), f"Expected MockEmbedder fallback, got {type(emb)}"
        record_test("Fallback_get_embedder_MissingKey_Fallback", True, "get_embedder fallback to MockEmbedder succeeded when key is missing.")

        emb_mock = get_embedder(use_mock=True)
        assert isinstance(emb_mock, MockEmbedder)
        record_test("Fallback_get_embedder_ExplicitMock", True, "get_embedder(use_mock=True) returned MockEmbedder.")

        invalid_key_raised = False
        try:
            emb_invalid = OpenAIEmbedder(api_key="sk-invalid-key-1234567890abcdef")
            emb_invalid.embed_text("test")
        except EmbeddingError as e:
            invalid_key_raised = True
            err_msg = str(e)
        except Exception as e:
            err_msg = f"Unexpected exception: {type(e).__name__}: {e}"

        if invalid_key_raised:
            record_test("Fallback_OpenAIEmbedder_InvalidKey_Fails", True, f"OpenAIEmbedder with invalid key correctly raised EmbeddingError: {err_msg}")
        else:
            record_test("Fallback_OpenAIEmbedder_InvalidKey_Fails", False, f"OpenAIEmbedder with invalid key did not raise EmbeddingError as expected. Output/Error: {err_msg}")

    finally:
        if old_key is not None:
            os.environ["OPENAI_API_KEY"] = old_key


def main():
    print("=" * 70)
    print("RUNNING EMPIRICAL STRESS TEST SUITE FOR RAG EMBEDDER & CHUNKERS")
    print("=" * 70)

    test_empty_and_whitespace_inputs()
    test_massive_single_line_text()
    test_massive_single_line_code()
    test_chunk_overlap_implementation()
    test_nested_markdown_and_code()
    test_comments_only_code()
    test_class_header_context_propagation()
    test_mock_embedder_invariants()
    test_openai_fallback_behavior()

    print("=" * 70)
    total = len(results)
    passed = sum(1 for r in results.values() if r["passed"])
    failed = total - passed
    print(f"SUMMARY: Total Tests: {total} | Passed: {passed} | Failed: {failed}")
    print("=" * 70)

    if failed > 0:
        print("\nFAILED TESTS DETAILS:")
        for k, v in results.items():
            if not v["passed"]:
                print(f"- {k}: {v['details']}")
        sys.exit(1)
    else:
        print("\nALL EMPIRICAL STRESS TESTS PASSED SUCCESSFULLY.")
        sys.exit(0)

if __name__ == "__main__":
    main()
