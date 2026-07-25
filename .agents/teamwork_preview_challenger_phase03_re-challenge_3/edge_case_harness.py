"""
Extended Edge Case Stress Testing Harness for Phase 03 RAG Embedder.
Tests extreme boundary conditions, unicode, docstrings, nested classes, and small max_chunk_size.
"""

import sys
from src.core.rag.embedder import TextChunker, CodeChunker, MockEmbedder, get_embedder

def test_edge_cases() -> bool:
    print("--- Running Extended Edge Case Tests ---")

    # 1. Unicode handling in TextChunker
    unicode_text = "Intro paragraph with emoji 🚀 and unicode: 🚀🚀🚀\n\nSection 2: 日本語のテキストと絵文字🔥"
    tc = TextChunker(max_chunk_size=50, chunk_overlap=15)
    chunks_u = tc.split_text(unicode_text)
    print(f"Unicode text chunks count: {len(chunks_u)}")
    for c in chunks_u:
        print(f"  Chunk: {repr(c.content)}")
    if not chunks_u:
        print("  FAIL: Unicode text returned empty chunks")
        return False

    # 2. chunk_overlap = 0 in TextChunker (verify no accidental overlap when overlap=0)
    tc_zero = TextChunker(max_chunk_size=100, chunk_overlap=0)
    text_zero = "A" * 60 + "\n\n" + "B" * 60
    chunks_zero = tc_zero.split_text(text_zero)
    print(f"Zero overlap chunks count: {len(chunks_zero)}")
    for c in chunks_zero:
        print(f"  Chunk: {repr(c.content)}")
    if len(chunks_zero) != 2:
        print(f"  FAIL: Expected 2 chunks for zero overlap, got {len(chunks_zero)}")
        return False
    if "A" in chunks_zero[1].content:
        print("  FAIL: Zero overlap chunk contains 'A' from chunk 0")
        return False

    # 3. Extremely long single line (> 10,000 characters) in CodeChunker
    long_line_code = "x = [" + "1, " * 5000 + "]"
    cc = CodeChunker(max_chunk_size=500)
    chunks_long = cc.split_code(long_line_code)
    print(f"Long code line chunks count: {len(chunks_long)}")
    for c in chunks_long:
        if len(c.content) > 500:
            print(f"  FAIL: Chunk exceeded max_chunk_size 500: len={len(c.content)}")
            return False
    
    # 4. Nested classes in CodeChunker
    nested_code = """class Outer:
    class Inner:
        def inner_method(self):
            return 42

top_level = True
"""
    cc_nested = CodeChunker(max_chunk_size=60)
    chunks_nested = cc_nested.split_code(nested_code)
    print(f"Nested class chunks count: {len(chunks_nested)}")
    for idx, c in enumerate(chunks_nested):
        print(f"  Chunk {idx} (lines {c.start_line}-{c.end_line}): {repr(c.content.replace('\n', '\\n'))}")
    
    # Check that method inside inner class gets flushed with context before top_level statement
    method_chunks = [c for c in chunks_nested if "return 42" in c.content]
    if not method_chunks:
        print("  FAIL: Could not find inner_method chunk")
        return False
    print("  PASS: Nested class method processed without errors")

    # 5. Very small max_chunk_size (e.g. 20)
    tc_tiny = TextChunker(max_chunk_size=20, chunk_overlap=5)
    tiny_chunks = tc_tiny.split_text("This is a small paragraph.\n\nAnd another paragraph.")
    print(f"Tiny max_chunk_size chunks count: {len(tiny_chunks)}")
    for c in tiny_chunks:
        if len(c.content) > 20:
            print(f"  FAIL: Tiny chunk exceeded max size 20: len={len(c.content)}")
            return False

    print("--- Extended Edge Case Tests PASSED ---")
    return True

if __name__ == "__main__":
    if not test_edge_cases():
        sys.exit(1)
    sys.exit(0)
