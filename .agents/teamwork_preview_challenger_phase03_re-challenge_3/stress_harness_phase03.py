"""
Empirical Stress Testing Harness for Phase 03 RAG Embedder Re-Challenge 3.
Tests TextChunker, CodeChunker, MockEmbedder, and OpenAIEmbedder against 3 target defects and additional edge cases.
"""

import sys
import random
import math
from typing import List, Dict, Any, Tuple

from src.core.rag.embedder import (
    TextChunker,
    CodeChunker,
    MockEmbedder,
    OpenAIEmbedder,
    get_embedder,
    Chunk,
)


def test_defect_1_single_unit_overlap() -> Tuple[bool, str]:
    """
    Defect 1 Test: TextChunker sliding window overlap for single-unit text chunks.
    Verifies if chunk_overlap > 0 actually includes non-zero overlapping text from previous single-unit chunks.
    """
    print("\n--- Testing Defect 1: TextChunker Single-Unit Overlap ---")
    
    # Subtest 1a: Standard single-unit overlap
    u1 = "A" * 30
    u2 = "B" * 80
    text = f"{u1}\n\n{u2}"

    chunker = TextChunker(max_chunk_size=100, chunk_overlap=50)
    chunks = chunker.split_text(text)

    print(f"Subtest 1a - Number of chunks generated: {len(chunks)}")
    for idx, c in enumerate(chunks):
        print(f"  Chunk {idx} (len {len(c.content)}): {repr(c.content)}")

    if len(chunks) < 2:
        return False, "Subtest 1a FAIL: Expected at least 2 chunks"

    # Check non-zero overlap from u1 in Chunk 1
    overlap_in_chunk1 = any(char == "A" for char in chunks[1].content)
    if not overlap_in_chunk1:
        return False, f"Subtest 1a FAIL: Chunk 1 does not contain overlapping text from Chunk 0 ('{u1}'). Overlap is 0."
    print("  Subtest 1a PASS: Non-zero overlap character present in chunk 1")

    # Subtest 1b: Chain of multiple discrete units
    u_a = "A" * 60
    u_b = "B" * 60
    u_c = "C" * 60
    text_b = f"{u_a}\n\n{u_b}\n\n{u_c}"
    chunker_b = TextChunker(max_chunk_size=100, chunk_overlap=30)
    chunks_b = chunker_b.split_text(text_b)

    print(f"Subtest 1b - Chunks generated: {len(chunks_b)}")
    for idx, c in enumerate(chunks_b):
        print(f"  Chunk {idx} (len {len(c.content)}): {repr(c.content)}")

    if len(chunks_b) != 3:
        return False, f"Subtest 1b FAIL: Expected 3 chunks, got {len(chunks_b)}"

    if "A" not in chunks_b[1].content:
        return False, "Subtest 1b FAIL: Chunk 1 missing overlap from Chunk 0 ('A')"
    if "B" not in chunks_b[2].content:
        return False, "Subtest 1b FAIL: Chunk 2 missing overlap from Chunk 1 ('B')"

    print("  Subtest 1b PASS: Overlap preserved across multi-unit chain")

    # Subtest 1c: Non-zero overlap verification when consecutive chunks consist of single discrete units
    u_x = "Section 1: " + "X" * 70
    u_y = "Section 2: " + "Y" * 70
    text_c = f"{u_x}\n\n{u_y}"
    chunker_c = TextChunker(max_chunk_size=100, chunk_overlap=40)
    chunks_c = chunker_c.split_text(text_c)

    print(f"Subtest 1c - Chunks generated: {len(chunks_c)}")
    for idx, c in enumerate(chunks_c):
        print(f"  Chunk {idx} (len {len(c.content)}): {repr(c.content)}")

    if len(chunks_c) < 2:
        return False, f"Subtest 1c FAIL: Expected 2 chunks, got {len(chunks_c)}"

    if "X" not in chunks_c[1].content:
        return False, "Subtest 1c FAIL: Chunk 1 missing overlap from Section 1"

    print("  Subtest 1c PASS: Discrete section units overlap verified")

    return True, "Defect 1 PASS: All single-unit overlap subtests succeeded with non-zero overlap."


def test_defect_2_empty_chunk_emission() -> Tuple[bool, str]:
    """
    Defect 2 Test: CodeChunker empty chunk emission.
    Fuzzes CodeChunker with 2,000 randomized code structures to verify zero empty chunks are emitted.
    """
    print("\n--- Testing Defect 2: CodeChunker Empty Chunk Emission ---")

    def generate_random_code() -> str:
        lines = []
        types = ["def", "class", "comment", "decorator", "blank", "statement", "indent_stmt"]
        for _ in range(random.randint(5, 100)):
            t = random.choice(types)
            if t == "def":
                indent = " " * (4 * random.randint(0, 3))
                lines.append(f"{indent}def func_{random.randint(1, 100)}():")
            elif t == "class":
                lines.append(f"class Class_{random.randint(1, 100)}:")
            elif t == "comment":
                indent = " " * (4 * random.randint(0, 3))
                lines.append(f"{indent}# Comment line {random.randint(1, 1000)}")
            elif t == "decorator":
                indent = " " * (4 * random.randint(0, 3))
                lines.append(f"{indent}@decorator_{random.randint(1, 10)}")
            elif t == "blank":
                lines.append(" " * random.randint(0, 8))
            elif t == "statement":
                lines.append(f"var_{random.randint(1, 100)} = {random.randint(1, 100)}")
            elif t == "indent_stmt":
                indent = " " * (4 * random.randint(1, 4))
                lines.append(f"{indent}val = {random.randint(1, 100)}")
        return "\n".join(lines)

    chunker = CodeChunker(max_chunk_size=120)
    empty_chunks = 0
    total_chunks = 0

    random.seed(42)
    for _ in range(2000):
        code = generate_random_code()
        chunks = chunker.split_code(code)
        total_chunks += len(chunks)
        for c in chunks:
            if not c.content or not c.content.strip():
                empty_chunks += 1

    print(f"Total chunks tested across 2,000 fuzzer runs: {total_chunks}")
    print(f"Empty chunks found: {empty_chunks}")

    if empty_chunks == 0:
        print("  PASS: Zero empty chunks emitted across 2,000 fuzz iterations")
        return True, f"Defect 2 PASS: 0 empty chunks across {total_chunks} chunks tested."
    else:
        return False, f"Defect 2 FAIL: Found {empty_chunks} empty chunks emitted out of {total_chunks} total chunks."


def test_defect_3_class_header_preservation() -> Tuple[bool, str]:
    """
    Defect 3 Test: CodeChunker class header context preservation.
    Verifies that class methods retain class header context when followed by unindented top-level statements.
    """
    print("\n--- Testing Defect 3: CodeChunker Class Header Context Preservation ---")

    # Subtest 3a: class followed by import os / import sys
    code_a = """class Foo:
    def method(self):
        x = 1
        return x

import os
import sys
"""
    chunker = CodeChunker(max_chunk_size=60)
    chunks_a = chunker.split_code(code_a)

    print(f"Subtest 3a - Chunks generated: {len(chunks_a)}")
    for idx, c in enumerate(chunks_a):
        print(f"  Chunk {idx} (lines {c.start_line}-{c.end_line}): {repr(c.content.replace('\n', '\\n'))}")

    method_tail_a = [c for c in chunks_a if "return x" in c.content]
    if not method_tail_a:
        return False, "Subtest 3a FAIL: Could not find chunk containing 'return x'"

    c_a = method_tail_a[0]
    if "class Foo:" not in c_a.content:
        return False, f"Subtest 3a FAIL: Chunk with 'return x' lost 'class Foo:' context header: {repr(c_a.content)}"
    print("  Subtest 3a PASS: Method tail retained 'class Foo:' header when followed by top-level imports")

    # Subtest 3b: class followed by global variable declaration
    code_b = """class Calculator:
    def add(self, a, b):
        result = a + b
        return result

GLOBAL_CONST = 42
def top_level_func():
    pass
"""
    chunker_b = CodeChunker(max_chunk_size=70)
    chunks_b = chunker_b.split_code(code_b)

    print(f"Subtest 3b - Chunks generated: {len(chunks_b)}")
    for idx, c in enumerate(chunks_b):
        print(f"  Chunk {idx} (lines {c.start_line}-{c.end_line}): {repr(c.content.replace('\n', '\\n'))}")

    method_tail_b = [c for c in chunks_b if "return result" in c.content]
    if not method_tail_b:
        return False, "Subtest 3b FAIL: Could not find chunk containing 'return result'"

    c_b = method_tail_b[0]
    if "class Calculator:" not in c_b.content:
        return False, f"Subtest 3b FAIL: Chunk with 'return result' lost 'class Calculator:' context: {repr(c_b.content)}"
    print("  Subtest 3b PASS: Method tail retained 'class Calculator:' header when followed by top-level constant")

    # Subtest 3c: class followed by if __name__ == '__main__':
    code_c = """class Runner:
    def run(self):
        step1()
        step2()

if __name__ == '__main__':
    Runner().run()
"""
    chunker_c = CodeChunker(max_chunk_size=60)
    chunks_c = chunker_c.split_code(code_c)

    print(f"Subtest 3c - Chunks generated: {len(chunks_c)}")
    for idx, c in enumerate(chunks_c):
        print(f"  Chunk {idx} (lines {c.start_line}-{c.end_line}): {repr(c.content.replace('\n', '\\n'))}")

    method_tail_c = [c for c in chunks_c if "step2()" in c.content]
    if not method_tail_c:
        return False, "Subtest 3c FAIL: Could not find chunk containing 'step2()'"

    c_c = method_tail_c[0]
    if "class Runner:" not in c_c.content:
        return False, f"Subtest 3c FAIL: Chunk with 'step2()' lost 'class Runner:' context: {repr(c_c.content)}"
    print("  Subtest 3c PASS: Method tail retained 'class Runner:' header when followed by main block")

    return True, "Defect 3 PASS: All class header context preservation subtests succeeded."


def test_embedder_components() -> Tuple[bool, str]:
    """
    Stress test MockEmbedder and get_embedder factory.
    """
    print("\n--- Testing MockEmbedder & Embedder Factory ---")
    mock = MockEmbedder(dimension=1536)
    
    # Test dimension
    if mock.dimension != 1536:
        return False, f"MockEmbedder dimension expected 1536, got {mock.dimension}"

    # Test determinism
    vec1 = mock.embed_text("test input vector")
    vec2 = mock.embed_text("test input vector")
    if vec1 != vec2:
        return False, "MockEmbedder is not deterministic for identical inputs"

    # Test L2 norm
    norm = math.sqrt(sum(x * x for x in vec1))
    if abs(norm - 1.0) > 1e-6:
        return False, f"MockEmbedder output vector L2 norm is {norm}, expected 1.0"

    # Test empty string input
    vec_empty = mock.embed_text("")
    if len(vec_empty) != 1536 or abs(math.sqrt(sum(x * x for x in vec_empty)) - 1.0) > 1e-6:
        return False, "MockEmbedder failed on empty string"

    # Test get_embedder fallback
    embedder_fallback = get_embedder(use_mock=True)
    if not isinstance(embedder_fallback, MockEmbedder):
        return False, "get_embedder(use_mock=True) did not return MockEmbedder"

    print("  PASS: MockEmbedder and factory function verified")
    return True, "Embedder components PASS"


def run_all_tests():
    print("============================================================")
    print("  EMPIRICAL STRESS TEST HARNESS — PHASE 03 RE-CHALLENGE 3  ")
    print("============================================================")

    res1, msg1 = test_defect_1_single_unit_overlap()
    res2, msg2 = test_defect_2_empty_chunk_emission()
    res3, msg3 = test_defect_3_class_header_preservation()
    res4, msg4 = test_embedder_components()

    print("\n============================================================")
    print("                      SUMMARY MATRIX                        ")
    print("============================================================")
    print(f"Defect 1 (TextChunker Single-Unit Overlap):    {'PASS' if res1 else 'FAIL'} | {msg1}")
    print(f"Defect 2 (CodeChunker Empty Chunk Emission):    {'PASS' if res2 else 'FAIL'} | {msg2}")
    print(f"Defect 3 (CodeChunker Class Header Context):   {'PASS' if res3 else 'FAIL'} | {msg3}")
    print(f"Embedder Components (MockEmbedder & Factory):  {'PASS' if res4 else 'FAIL'} | {msg4}")
    print("============================================================")

    overall_pass = res1 and res2 and res3 and res4
    print(f"\nOVERALL VERDICT: {'PASS' if overall_pass else 'FAIL / REJECTED'}")
    return overall_pass


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
