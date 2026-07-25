"""
Unit tests for RAG embedders and dual chunking engine (TextChunker & CodeChunker).
"""

import math
import pytest
from src.models import Difficulty, Example, ScrapedProblem
from src.core.exceptions import EmbeddingError
from src.core.rag.embedder import (
    BaseEmbedder,
    Chunk,
    CodeChunker,
    MockEmbedder,
    OpenAIEmbedder,
    TextChunker,
    get_embedder,
)


def create_sample_problem() -> ScrapedProblem:
    """Helper fixture creating a synthetic ScrapedProblem instance."""
    return ScrapedProblem(
        slug="two-sum",
        title="Two Sum",
        number=1,
        difficulty=Difficulty.EASY,
        description="Given an array of integers `nums` and an integer `target`, return indices of the two numbers such that they add up to `target`.",
        constraints=["2 <= nums.length <= 104", "-109 <= nums[i] <= 109", "-109 <= target <= 109"],
        examples=[
            Example(input="nums = [2,7,11,15], target = 9", output="[0,1]", explanation="Because nums[0] + nums[1] == 9, we return [0, 1]."),
            Example(input="nums = [3,2,4], target = 6", output="[1,2]", explanation=""),
        ],
        tags=["Array", "Hash Table"],
        accepted_code="""class Solution:
    def twoSum(self, nums: list[int], target: int) -> list[int]:
        seen = {}
        for i, num in enumerate(nums):
            diff = target - num
            if diff in seen:
                return [seen[diff], i]
            seen[num] = i
        return []
""",
        code_language="python",
        scraped_at="2026-07-25T10:00:00Z",
    )


# ============================================================================
# 1. Chunk Data Model Tests
# ============================================================================

def test_chunk_dataclass():
    chunk = Chunk(
        chunk_id="test_0",
        content="Hello world",
        chunk_type="text",
        metadata={"slug": "two-sum"},
        parent_slug="two-sum",
        start_line=1,
        end_line=10,
    )
    d = chunk.to_dict()
    assert d["chunk_id"] == "test_0"
    assert d["content"] == "Hello world"
    assert d["chunk_type"] == "text"
    assert d["metadata"] == {"slug": "two-sum"}
    assert d["parent_slug"] == "two-sum"
    assert d["start_line"] == 1
    assert d["end_line"] == 10


# ============================================================================
# 2. TextChunker Tests
# ============================================================================

def test_text_chunker_split_text():
    chunker = TextChunker(max_chunk_size=100, chunk_overlap=10)
    text = """# Header 1
Paragraph 1 content goes here.

## Section 2
Paragraph 2 content goes here with more details.
"""
    chunks = chunker.split_text(text, parent_slug="sample-slug")
    assert len(chunks) > 0
    for c in chunks:
        assert c.chunk_type == "text"
        assert c.parent_slug == "sample-slug"
        assert c.metadata["slug"] == "sample-slug"


def test_text_chunker_chunk_problem():
    problem = create_sample_problem()
    chunker = TextChunker(max_chunk_size=300)
    chunks = chunker.chunk_problem(problem)

    assert len(chunks) >= 1
    full_content = "\n".join(c.content for c in chunks)
    assert "Two Sum" in full_content
    assert "Constraints" in full_content
    assert "Examples" in full_content
    for c in chunks:
        assert c.chunk_type == "text"
        assert c.metadata["difficulty"] == "Easy"
        assert c.metadata["tags"] == "Array,Hash Table"


# ============================================================================
# 3. CodeChunker Tests
# ============================================================================

def test_code_chunker_short_code():
    problem = create_sample_problem()
    chunker = CodeChunker(max_chunk_size=1000)
    chunks = chunker.chunk_problem(problem)

    assert len(chunks) == 1
    c = chunks[0]
    assert c.chunk_type == "code"
    assert c.parent_slug == "two-sum"
    assert c.start_line == 1
    assert c.end_line > 1
    assert "def twoSum" in c.content
    assert c.metadata["code_language"] == "python"


def test_code_chunker_long_code_splitting():
    long_code = """class LargeSolution:
    def method_one(self):
        # Method 1 logic
        a = 1
        b = 2
        return a + b

    def method_two(self):
        # Method 2 logic
        c = 3
        d = 4
        return c * d
"""
    chunker = CodeChunker(max_chunk_size=120)
    chunks = chunker.split_code(long_code, parent_slug="long-problem")

    assert len(chunks) >= 2
    for c in chunks:
        assert c.chunk_type == "code"
        assert c.start_line is not None
        assert c.end_line is not None
        assert c.end_line >= c.start_line


# ============================================================================
# 4. Embedder Engine & MockEmbedder Tests
# ============================================================================

def test_mock_embedder_determinism_and_norm():
    embedder = MockEmbedder(dimension=1536)
    assert embedder.dimension == 1536

    vec1 = embedder.embed_text("Two Sum Problem")
    vec2 = embedder.embed_text("Two Sum Problem")
    vec3 = embedder.embed_text("Different Problem String")

    # Dimensions
    assert len(vec1) == 1536
    assert len(vec2) == 1536
    assert len(vec3) == 1536

    # Determinism
    assert vec1 == vec2

    # Distinctness
    assert vec1 != vec3

    # L2 Normalization (unit vector)
    l2_norm = math.sqrt(sum(x * x for x in vec1))
    assert pytest.approx(l2_norm, abs=1e-5) == 1.0


def test_mock_embedder_batch_and_chunks():
    embedder = MockEmbedder()
    chunks = [
        Chunk(chunk_id="c1", content="Text 1", chunk_type="text"),
        Chunk(chunk_id="c2", content="Text 2", chunk_type="text"),
    ]

    embeddings = embedder.embed_chunks(chunks)
    assert len(embeddings) == 2
    assert embeddings[0] == embedder.embed_text("Text 1")
    assert embeddings[1] == embedder.embed_text("Text 2")


def test_openai_embedder_fallback_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(EmbeddingError):
        OpenAIEmbedder(api_key="")

    # get_embedder should fallback to MockEmbedder
    emb = get_embedder(use_mock=False)
    assert isinstance(emb, MockEmbedder)


def test_get_embedder_explicit_mock():
    emb = get_embedder(use_mock=True)
    assert isinstance(emb, MockEmbedder)


# ============================================================================
# 5. Chunker Edge Case Remediation Tests
# ============================================================================

def test_text_chunker_single_line_character_overflow():
    """Requirement 1: TextChunker splits lines longer than max_chunk_size without exceeding limit."""
    chunker = TextChunker(max_chunk_size=40, chunk_overlap=0)
    long_line = "This_is_a_very_long_single_line_that_exceeds_the_maximum_allowed_chunk_size_of_forty_characters."
    chunks = chunker.split_text(long_line, parent_slug="overflow-text")

    assert len(chunks) > 1
    for c in chunks:
        assert len(c.content) <= 40, f"Chunk content length {len(c.content)} exceeds max_chunk_size 40"

    reconstructed = "".join(c.content.replace("\n", "") for c in chunks)
    assert "This_is_a_very_long_single_line" in reconstructed


def test_code_chunker_single_line_character_overflow():
    """Requirement 2: CodeChunker splits code lines longer than max_chunk_size without exceeding limit."""
    chunker = CodeChunker(max_chunk_size=50)
    long_code = (
        "def test_func():\n"
        "    very_long_variable_name_that_goes_on_and_on_and_on_exceeding_the_chunk_limit = 1234567890"
    )
    chunks = chunker.split_code(long_code, parent_slug="overflow-code")

    assert len(chunks) > 1
    for c in chunks:
        assert len(c.content) <= 50, f"Chunk content length {len(c.content)} exceeds max_chunk_size 50"


def test_text_chunker_dead_code_overlap():
    """Requirement 3: TextChunker sliding window overlap is active and used in successive chunks."""
    chunker = TextChunker(max_chunk_size=60, chunk_overlap=25)
    text = (
        "First paragraph with some text content.\n\n"
        "Second paragraph with additional text details.\n\n"
        "Third paragraph concluding the section."
    )
    chunks = chunker.split_text(text, parent_slug="overlap-test")

    assert len(chunks) >= 2
    chunk_0_words = chunks[0].content.split()
    chunk_1_content = chunks[1].content

    overlapping_found = any(w in chunk_1_content for w in chunk_0_words[-3:])
    assert overlapping_found, "Expected overlap between chunk 0 and chunk 1"


def test_code_chunker_function_comment_detachment():
    """Requirement 4: Comments and decorators preceding a function belong to that function's chunk."""
    code = """def function_one():
    return 1

# Helper comment for function two
@staticmethod
def function_two():
    return 2
"""
    chunker = CodeChunker(max_chunk_size=60)
    chunks = chunker.split_code(code, parent_slug="comment-test")

    assert len(chunks) >= 2
    chunk_0_content = chunks[0].content
    chunk_1_content = chunks[1].content

    assert "# Helper comment for function two" not in chunk_0_content
    assert "# Helper comment for function two" in chunk_1_content
    assert "@staticmethod" in chunk_1_content


def test_code_chunker_class_state_leakage():
    """Requirement 5: Class header context resets when returning to top-level scope."""
    code = """class FirstClass:
    def class_method(self):
        a = 1
        return a

def standalone_function():
    b = 2
    return b
"""
    chunker = CodeChunker(max_chunk_size=60)
    chunks = chunker.split_code(code, parent_slug="leakage-test")

    assert len(chunks) >= 2
    standalone_chunk = [c for c in chunks if "def standalone_function" in c.content]
    assert len(standalone_chunk) == 1
    assert "class FirstClass" not in standalone_chunk[0].content


def test_text_chunker_single_unit_overlap_accumulation():
    """Defect 1 fix: Single-unit chunks accumulate overlap when advancing to next chunk without infinite loops."""
    chunker = TextChunker(max_chunk_size=80, chunk_overlap=30)
    text = "Short para 1.\n\nParagraph two is longer and takes up most of the max chunk size limit."
    chunks = chunker.split_text(text)

    assert len(chunks) == 2
    assert chunks[0].content == "Short para 1."
    assert "Paragraph two is longer" in chunks[1].content


def test_code_chunker_empty_chunk_emission():
    """Defect 2 fix: Comment detachment with leading blank lines does not emit empty chunks (content="")."""
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

    assert len(chunks) >= 1
    for c in chunks:
        assert c.content.strip() != "", "No chunk should have empty content"


def test_code_chunker_premature_class_state_reset():
    """Defect 3 fix: Indent 0 top-level line preserves active_class_header for flushing pending lines of class methods."""
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

    # Verify method_two chunk contains class MyClass header prefix
    method_two_chunks = [c for c in chunks if "return c + d" in c.content]
    assert len(method_two_chunks) == 1
    assert "class MyClass:" in method_two_chunks[0].content

    # Verify standalone chunk does NOT contain class MyClass header
    standalone_chunks = [c for c in chunks if "standalone" in c.content]
    assert len(standalone_chunks) == 1
    assert "class MyClass:" not in standalone_chunks[0].content


def test_text_chunker_single_unit_overlap_discrete_units():
    """Defect 1 fix: Paragraphs/units where unit length > max_chunk_size - chunk_overlap.
    Confirms non-zero character overlap in subsequent chunks.
    """
    u1 = "A" * 30
    u2 = "B" * 80
    text = f"{u1}\n\n{u2}"

    chunker = TextChunker(max_chunk_size=100, chunk_overlap=50)
    chunks = chunker.split_text(text)

    assert len(chunks) == 2
    assert chunks[0].content == u1
    # Chunk 1 must contain trailing character overlap from Chunk 0 (u1)
    assert chunks[1].content.startswith("A" * 18)
    assert u2 in chunks[1].content
    # Confirm non-zero character overlap between chunk 0 and chunk 1
    assert any(char == "A" for char in chunks[1].content)


def test_code_chunker_class_header_top_level_statements():
    """Defect 3 fix: Class definition followed by top-level import, GLOBAL_VAR, or if __name__.
    Confirms the last class method chunk retains its class_header context prefix.
    """
    code = """class Foo:
    def method(self):
        x = 1
        return x

import os
GLOBAL_VAR = 100

if __name__ == "__main__":
    pass
"""
    chunker = CodeChunker(max_chunk_size=60)
    chunks = chunker.split_code(code)

    # Find the chunk containing 'return x'
    method_chunks = [c for c in chunks if "return x" in c.content]
    assert len(method_chunks) == 1, "Expected exactly 1 chunk containing method return statement"
    assert "class Foo:" in method_chunks[0].content, (
        "Class method tail chunk lost 'class Foo:' context header prefix!"
    )



