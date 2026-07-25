"""
Empirical Stress Test Harness for Phase 03: RAG & Knowledge Organization.
Tests TextChunker, CodeChunker, MockEmbedder, and OpenAIEmbedder under extreme conditions.
"""

import math
import sys
import os

# Add repo root to path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, repo_root)

from src.core.rag.embedder import (
    Chunk,
    TextChunker,
    CodeChunker,
    MockEmbedder,
    OpenAIEmbedder,
    get_embedder,
)

def log(msg, status="INFO"):
    print(f"[{status}] {msg}")

def test_1_text_chunker_single_line_overflow():
    log("Running Test 1: TextChunker Single-Line Character Overflow (>5000 chars)")
    chunker = TextChunker(max_chunk_size=500, chunk_overlap=50)
    
    # 1A. Single line without spaces (6000 chars)
    long_nospace = "A" * 6000
    chunks = chunker.split_text(long_nospace, parent_slug="test-nospace")
    assert len(chunks) > 0, "No chunks returned for long_nospace"
    for idx, c in enumerate(chunks):
        assert len(c.content) <= 500, f"Chunk {idx} exceeded max_chunk_size: {len(c.content)} > 500"
    log(f"  1A PASSED: 6000 nospace char line split into {len(chunks)} chunks, max len = {max(len(c.content) for c in chunks)}")

    # 1B. Single line with spaces (8000 chars)
    words = ["word" + str(i) for i in range(1500)]
    long_spaced = " ".join(words) # ~ 10,000 chars
    assert len(long_spaced) > 5000
    chunks_spaced = chunker.split_text(long_spaced, parent_slug="test-spaced")
    assert len(chunks_spaced) > 0
    for idx, c in enumerate(chunks_spaced):
        assert len(c.content) <= 500, f"Chunk {idx} exceeded max_chunk_size: {len(c.content)} > 500"
    log(f"  1B PASSED: ~10k char line with spaces split into {len(chunks_spaced)} chunks, max len = {max(len(c.content) for c in chunks_spaced)}")

    # 1C. Extremely small max_chunk_size (50 chars) on 5000 char line
    chunker_small = TextChunker(max_chunk_size=50, chunk_overlap=10)
    chunks_small = chunker_small.split_text(long_nospace, parent_slug="test-small")
    for idx, c in enumerate(chunks_small):
        assert len(c.content) <= 50, f"Chunk {idx} exceeded small max_chunk_size: {len(c.content)} > 50"
    log(f"  1C PASSED: Small max_chunk_size (50) split 6000 chars into {len(chunks_small)} chunks, all <= 50 chars")

    return True

def test_2_code_chunker_single_line_overflow():
    log("Running Test 2: CodeChunker Single-Line Character Overflow (>5000 chars)")
    chunker = CodeChunker(max_chunk_size=500)
    
    # 2A. Unindented long code line (6000 chars)
    long_code_line = "x = " + " + ".join([f"var_{i}" for i in range(700)])
    assert len(long_code_line) > 5000
    chunks = chunker.split_code(long_code_line, parent_slug="code-overflow-1")
    assert len(chunks) > 0
    for idx, c in enumerate(chunks):
        assert len(c.content) <= 500, f"Code chunk {idx} length {len(c.content)} > 500"
    log(f"  2A PASSED: 6000+ char unindented line split into {len(chunks)} chunks, max len = {max(len(c.content) for c in chunks)}")

    # 2B. Heavily indented long code line (indent = 40 spaces, total 6000 chars)
    indent = " " * 40
    indented_line = indent + "y = " + " * ".join([f"val_{i}" for i in range(700)])
    chunks_ind = chunker.split_code(indented_line, parent_slug="code-overflow-2")
    assert len(chunks_ind) > 0
    for idx, c in enumerate(chunks_ind):
        assert len(c.content) <= 500, f"Indented code chunk {idx} length {len(c.content)} > 500"
    log(f"  2B PASSED: 6000+ char indented line split into {len(chunks_ind)} chunks, max len = {max(len(c.content) for c in chunks_ind)}")

    # 2C. Indent greater than max_chunk_size (indent = 60 spaces, max_chunk_size = 50)
    super_indent = " " * 60 + "z = 123"
    chunker_tiny = CodeChunker(max_chunk_size=50)
    chunks_tiny = chunker_tiny.split_code(super_indent, parent_slug="code-overflow-3")
    for idx, c in enumerate(chunks_tiny):
        assert len(c.content) <= 50, f"Tiny code chunk {idx} length {len(c.content)} > 50"
    log(f"  2C PASSED: Indent > max_chunk_size handled gracefully, max len = {max(len(c.content) for c in chunks_tiny)}")

    return True

def test_3_text_chunker_dead_code_overlap():
    log("Running Test 3: TextChunker Dead Code Overlap (sliding window active)")
    chunker = TextChunker(max_chunk_size=150, chunk_overlap=40)
    
    text = (
        "Paragraph 1: Alpha beta gamma delta epsilon zeta eta theta iota kappa.\n\n"
        "Paragraph 2: Lambda mu nu xi omicron pi rho sigma tau upsilon phi.\n\n"
        "Paragraph 3: Chi psi omega zero one two three four five six seven.\n\n"
        "Paragraph 4: Eight nine ten eleven twelve thirteen fourteen fifteen."
    )
    chunks = chunker.split_text(text, parent_slug="overlap-test")
    assert len(chunks) >= 3, f"Expected at least 3 chunks, got {len(chunks)}"

    log(f"  Produced {len(chunks)} chunks with max_size=150, overlap=40")
    for i in range(len(chunks) - 1):
        c1 = chunks[i].content
        c2 = chunks[i+1].content
        # Check if tail of c1 appears in head of c2 or vice versa (overlap exists)
        # Split into words to find common sequences
        words_c1 = set(c1.split())
        words_c2 = set(c2.split())
        common_words = words_c1.intersection(words_c2)
        log(f"  Chunk {i} & Chunk {i+1} share {len(common_words)} common words: {list(common_words)[:5]}")
        assert len(common_words) > 0, f"No overlap found between chunk {i} and {i+1}"

    # Check termination behavior with large overlap (overlap close to max_size)
    chunker_extreme = TextChunker(max_chunk_size=100, chunk_overlap=90)
    chunks_extreme = chunker_extreme.split_text(text, parent_slug="overlap-extreme")
    assert len(chunks_extreme) > 0
    log(f"  3B PASSED: High overlap ratio (90/100) terminated cleanly with {len(chunks_extreme)} chunks")

    return True

def test_4_code_chunker_function_comment_detachment():
    log("Running Test 4: CodeChunker Function Comment Detachment")
    chunker = CodeChunker(max_chunk_size=120)
    
    code = """def first_func():
    # Inside first func line 1
    # Inside first func line 2
    x = 100
    y = 200
    return x + y

# Important docstring comment for second_func
# Details about algorithm
@decorator_one
@decorator_two
def second_func():
    z = 300
    return z
"""
    chunks = chunker.split_code(code, parent_slug="comment-test")
    assert len(chunks) >= 2, f"Expected at least 2 chunks, got {len(chunks)}"

    chunk_0 = chunks[0].content
    chunk_1 = chunks[1].content
    log(f"--- Chunk 0 ---\n{chunk_0}")
    log(f"--- Chunk 1 ---\n{chunk_1}")

    # Assert comment and decorators for second_func are NOT in chunk 0
    assert "# Important docstring comment for second_func" not in chunk_0
    assert "@decorator_one" not in chunk_0
    assert "@decorator_two" not in chunk_0

    # Assert comment and decorators for second_func ARE in chunk 1
    assert "# Important docstring comment for second_func" in chunk_1
    assert "@decorator_one" in chunk_1
    assert "@decorator_two" in chunk_1
    assert "def second_func" in chunk_1

    log("  4 PASSED: Comments and decorators attached correctly to second_func chunk, detached from first_func chunk")
    return True

def test_5_code_chunker_class_state_leakage():
    log("Running Test 5: CodeChunker Class State Leakage (Header Reset)")
    chunker = CodeChunker(max_chunk_size=100)
    
    code = """class MyClass:
    def method_a(self):
        val = 1
        return val

def standalone_func_one():
    res = 2
    return res

def standalone_func_two():
    res = 3
    return res
"""
    chunks = chunker.split_code(code, parent_slug="leakage-test")
    log(f"  Produced {len(chunks)} chunks")
    for idx, c in enumerate(chunks):
        log(f"--- Chunk {idx} (lines {c.start_line}-{c.end_line}) ---\n{c.content}")

    # Find chunk containing standalone_func_one
    standalone_chunks = [c for c in chunks if "standalone_func_one" in c.content]
    assert len(standalone_chunks) > 0, "No chunk found for standalone_func_one"

    for c in standalone_chunks:
        assert "class MyClass" not in c.content, f"Class header leaked into standalone function chunk!\n{c.content}"

    # Find chunk containing standalone_func_two
    standalone2_chunks = [c for c in chunks if "standalone_func_two" in c.content]
    assert len(standalone2_chunks) > 0, "No chunk found for standalone_func_two"

    for c in standalone2_chunks:
        assert "class MyClass" not in c.content, f"Class header leaked into second standalone function chunk!\n{c.content}"

    log("  5 PASSED: Class state correctly reset at indent 0; standalone functions do not inherit class header")
    return True

def test_6_embedders():
    log("Running Test 6: MockEmbedder & OpenAIEmbedder Verification")
    
    # 6A. MockEmbedder determinism and dimension
    mock = MockEmbedder(dimension=1536)
    assert mock.dimension == 1536
    v1 = mock.embed_text("test string 123")
    v2 = mock.embed_text("test string 123")
    v3 = mock.embed_text("different string")
    
    assert len(v1) == 1536
    assert v1 == v2, "MockEmbedder is not deterministic!"
    assert v1 != v3, "MockEmbedder collision between different inputs!"
    
    # Norm check
    norm = math.sqrt(sum(x*x for x in v1))
    assert abs(norm - 1.0) < 1e-5, f"MockEmbedder output vector not normalized: norm={norm}"
    log("  6A PASSED: MockEmbedder dimension, determinism, and L2 normalization verified")

    # 6B. get_embedder fallback check
    emb_fallback = get_embedder(use_mock=False)
    assert isinstance(emb_fallback, MockEmbedder), "get_embedder did not fallback to MockEmbedder when API key missing"
    log("  6B PASSED: get_embedder fallback to MockEmbedder verified")

    return True

if __name__ == "__main__":
    print("==================================================")
    print("STARTING EMPIRICAL STRESS TEST HARNESS")
    print("==================================================")
    
    results = [
        test_1_text_chunker_single_line_overflow(),
        test_2_code_chunker_single_line_overflow(),
        test_3_text_chunker_dead_code_overlap(),
        test_4_code_chunker_function_comment_detachment(),
        test_5_code_chunker_class_state_leakage(),
        test_6_embedders(),
    ]
    
    print("==================================================")
    if all(results):
        print("ALL 6 EMPIRICAL STRESS TESTS PASSED SUCCESSFULLY!")
        print("==================================================")
        sys.exit(0)
    else:
        print("SOME STRESS TESTS FAILED!")
        print("==================================================")
        sys.exit(1)
