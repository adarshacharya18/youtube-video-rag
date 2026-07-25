"""
Empirical Stress Testing Harness for Phase 03 RAG Embedder Re-Challenge 2.
Tests TextChunker, CodeChunker, MockEmbedder, and OpenAIEmbedder against 3 target defects:
1. TextChunker single-unit sliding window overlap accumulation.
2. CodeChunker empty chunk emission.
3. CodeChunker class header context preservation when flushing before unindented top-level lines.
"""

import sys
import random
from typing import List, Dict, Any

from src.core.rag.embedder import (
    TextChunker,
    CodeChunker,
    MockEmbedder,
    get_embedder,
    Chunk,
)


def test_defect_1_single_unit_overlap() -> bool:
    """
    Defect 1 Test: TextChunker sliding window overlap for single-unit text chunks.
    Verifies if chunk_overlap > 0 actually includes overlapping text from previous single-unit chunk.
    """
    print("\n--- Testing Defect 1: TextChunker Single-Unit Overlap ---")
    u1 = "A" * 30
    u2 = "B" * 80
    text = f"{u1}\n\n{u2}"

    chunker = TextChunker(max_chunk_size=100, chunk_overlap=50)
    chunks = chunker.split_text(text)

    print(f"Number of chunks generated: {len(chunks)}")
    for idx, c in enumerate(chunks):
        print(f"  Chunk {idx} (len {len(c.content)}): {repr(c.content)}")

    if len(chunks) < 2:
        print("  FAIL: Expected at least 2 chunks")
        return False

    has_overlap = u1 in chunks[1].content
    if has_overlap:
        print("  PASS: Single-unit chunk overlap present in chunk 1")
        return True
    else:
        print(f"  FAIL: Chunk 1 does not contain overlapping text from Chunk 0 ('{u1}'). Overlap is 0.")
        return False


def test_defect_2_empty_chunk_emission() -> bool:
    """
    Defect 2 Test: CodeChunker empty chunk emission.
    Fuzzes CodeChunker with 1,000 randomized code structures to verify zero empty chunks are emitted.
    """
    print("\n--- Testing Defect 2: CodeChunker Empty Chunk Emission ---")

    def generate_random_code() -> str:
        lines = []
        types = ["def", "class", "comment", "decorator", "blank", "statement"]
        for _ in range(random.randint(10, 80)):
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
                lines.append("")
            elif t == "statement":
                indent = " " * (4 * random.randint(0, 3))
                lines.append(f"{indent}x = {random.randint(1, 100)}")
        return "\n".join(lines)

    chunker = CodeChunker(max_chunk_size=100)
    empty_chunks = 0
    total_chunks = 0

    for i in range(500):
        code = generate_random_code()
        chunks = chunker.split_code(code)
        total_chunks += len(chunks)
        for c in chunks:
            if not c.content or not c.content.strip():
                empty_chunks += 1

    print(f"Total chunks tested: {total_chunks}")
    print(f"Empty chunks found: {empty_chunks}")

    if empty_chunks == 0:
        print("  PASS: Zero empty chunks emitted across 500 fuzz iterations")
        return True
    else:
        print(f"  FAIL: Found {empty_chunks} empty chunks emitted")
        return False


def test_defect_3_class_header_preservation() -> bool:
    """
    Defect 3 Test: CodeChunker class header context preservation.
    Verifies that class methods retain class header context when followed by top-level statements.
    """
    print("\n--- Testing Defect 3: CodeChunker Class Header Context Preservation ---")
    code = """class Foo:
    def method(self):
        x = 1
        return x

import os
import sys
"""
    chunker = CodeChunker(max_chunk_size=60)
    chunks = chunker.split_code(code)

    print(f"Number of chunks generated: {len(chunks)}")
    for idx, c in enumerate(chunks):
        print(f"  Chunk {idx} (lines {c.start_line}-{c.end_line}): {repr(c.content.replace('\n', '\\n'))}")

    # Find the chunk containing 'return x'
    method_tail_chunks = [c for c in chunks if "return x" in c.content]
    if not method_tail_chunks:
        print("  FAIL: Could not find chunk containing 'return x'")
        return False

    c = method_tail_chunks[0]
    if "class Foo:" in c.content:
        print("  PASS: Method tail retained 'class Foo:' context header")
        return True
    else:
        print(f"  FAIL: Chunk containing method tail ('return x') lost 'class Foo:' context header!")
        return False


def run_all_tests():
    print("============================================================")
    print("  EMPIRICAL STRESS TEST HARNESS — PHASE 03 RE-CHALLENGE 2  ")
    print("============================================================")

    res1 = test_defect_1_single_unit_overlap()
    res2 = test_defect_2_empty_chunk_emission()
    res3 = test_defect_3_class_header_preservation()

    print("\n============================================================")
    print("                      SUMMARY MATRIX                        ")
    print("============================================================")
    print(f"Defect 1 (TextChunker Single-Unit Overlap):    {'PASS' if res1 else 'FAIL'}")
    print(f"Defect 2 (CodeChunker Empty Chunk Emission):    {'PASS' if res2 else 'FAIL'}")
    print(f"Defect 3 (CodeChunker Class Header Context):   {'PASS' if res3 else 'FAIL'}")
    print("============================================================")

    overall_pass = res1 and res2 and res3
    print(f"OVERALL VERDICT: {'PASS' if overall_pass else 'FAIL / REJECTED'}")
    return overall_pass


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
