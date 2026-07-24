import pytest
from pathlib import Path
from dataclasses import FrozenInstanceError

from src.models import Difficulty, Example, ScrapedProblem
from src.core.ingestion.models import (
    Difficulty as IngestionDifficulty,
    Example as IngestionExample,
    ScrapedProblem as IngestionScrapedProblem,
)
from src.core.ingestion.sanitizer import MarkdownSanitizer, DataSanitizer
from src.core.ingestion.parser import DSAParser


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "ingestion"


def load_fixture(filename: str) -> str:
    path = FIXTURES_DIR / filename
    return path.read_text(encoding="utf-8")


# ============================================================================
# 1. Models & Enum Unit Tests
# ============================================================================

def test_difficulty_enum():
    assert Difficulty.EASY.value == "Easy"
    assert Difficulty.MEDIUM.value == "Medium"
    assert Difficulty.HARD.value == "Hard"

    assert Difficulty.from_string("easy") == Difficulty.EASY
    assert Difficulty.from_string("EASY") == Difficulty.EASY
    assert Difficulty.from_string("Med") == Difficulty.MEDIUM
    assert Difficulty.from_string("Medium") == Difficulty.MEDIUM
    assert Difficulty.from_string("Hard") == Difficulty.HARD

    with pytest.raises(ValueError):
        Difficulty.from_string("UNKNOWN")

    with pytest.raises(ValueError):
        Difficulty.from_string(None)


def test_example_dataclass_serialization():
    ex = Example(input="nums = [1, 2]", output="3", explanation="1 + 2 = 3")
    d = ex.to_dict()
    assert d == {"input": "nums = [1, 2]", "output": "3", "explanation": "1 + 2 = 3"}

    ex_reconstructed = Example.from_dict(d)
    assert ex_reconstructed == ex


def test_scraped_problem_frozen_and_serialization():
    prob = ScrapedProblem(
        slug="two-sum",
        title="Two Sum",
        number=1,
        difficulty=Difficulty.EASY,
        description="Find two numbers.",
        constraints=["1 <= n <= 10"],
        examples=[Example(input="a", output="b")],
        tags=["Array"],
        accepted_code="def two_sum(): pass",
        code_language="python",
        scraped_at="2026-07-24T10:00:00Z",
    )

    # Immutability check
    with pytest.raises((AttributeError, TypeError, FrozenInstanceError)):
        prob.title = "New Title"  # type: ignore

    # Serialization roundtrip
    d = prob.to_dict()
    assert d["slug"] == "two-sum"
    assert d["difficulty"] == "Easy"
    assert d["examples"][0] == {"input": "a", "output": "b", "explanation": ""}

    prob_reconstructed = ScrapedProblem.from_dict(d)
    assert prob_reconstructed == prob


def test_core_ingestion_models_bridge():
    assert IngestionDifficulty is Difficulty
    assert IngestionExample is Example
    assert IngestionScrapedProblem is ScrapedProblem


# ============================================================================
# 2. MarkdownSanitizer Unit Tests
# ============================================================================

def test_sanitizer_html_unescape_and_strip():
    html_text = "<p>Given an array &amp; integer target with &lt;tag&gt; <b>bold</b> text.</p>"
    clean = MarkdownSanitizer.clean_html(html_text)
    assert clean == 'Given an array & integer target with <tag> bold text.'


def test_sanitizer_code_indentation_preservation():
    code = "\n\n    def test():\n        return True\n\n"
    preserved = MarkdownSanitizer.preserve_code_blocks(code)
    assert preserved == "    def test():\n        return True"


def test_sanitizer_normalize_whitespace():
    text = "Line 1  \r\nLine 2\r\n\r\n\r\n\r\nLine 3"
    norm = MarkdownSanitizer.normalize_whitespace(text)
    assert norm == "Line 1\nLine 2\n\nLine 3"


def test_sanitizer_title_and_tag_cleaning():
    title = "# 1. Two Sum"
    assert MarkdownSanitizer.clean_title(title) == "1. Two Sum"

    tags = [" Array ", "<b>Hash Table</b>", "Array", ""]
    clean_tags = MarkdownSanitizer.clean_tags(tags)
    assert clean_tags == ["Array", "Hash Table"]


def test_sanitizer_problem_validation_fail_fast():
    # Missing title
    with pytest.raises(ValueError, match="title"):
        MarkdownSanitizer.sanitize_problem({
            "number": 1,
            "difficulty": "Easy",
            "description": "Desc",
            "accepted_code": "code",
        })

    # Invalid number
    with pytest.raises(ValueError, match="number"):
        MarkdownSanitizer.sanitize_problem({
            "title": "Title",
            "number": -5,
            "difficulty": "Easy",
            "description": "Desc",
            "accepted_code": "code",
        })

    # Missing accepted code
    with pytest.raises(ValueError, match="Accepted solution code"):
        MarkdownSanitizer.sanitize_problem({
            "title": "Title",
            "number": 1,
            "difficulty": "Easy",
            "description": "Desc",
            "accepted_code": "",
        })


# ============================================================================
# 3. DSAParser Integration Tests with Fixtures
# ============================================================================

def test_parser_two_sum_fixture():
    content = load_fixture("two_sum.md")
    parser = DSAParser()
    prob = parser.parse(content)

    assert prob.slug == "two-sum"
    assert prob.title == "Two Sum"
    assert prob.number == 1
    assert prob.difficulty == Difficulty.EASY
    assert "Array" in prob.tags
    assert "Hash Table" in prob.tags
    assert len(prob.examples) == 3
    assert prob.examples[0].input == "nums = [2,7,11,15], target = 9"
    assert prob.examples[0].output == "[0,1]"
    assert "nums[0] + nums[1] == 9" in prob.examples[0].explanation
    assert len(prob.constraints) == 4
    assert prob.code_language == "python"
    assert "class Solution:" in prob.accepted_code


def test_parser_reverse_linked_list_fixture():
    content = load_fixture("reverse_linked_list.md")
    parser = DSAParser()
    prob = parser.parse(content)

    assert prob.slug == "reverse-linked-list"
    assert prob.title == "Reverse Linked List"
    assert prob.number == 206
    assert prob.difficulty == Difficulty.EASY
    assert "Linked List" in prob.tags
    assert len(prob.examples) == 3
    assert prob.examples[0].input == "head = [1,2,3,4,5]"
    assert prob.examples[0].output == "[5,4,3,2,1]"
    assert prob.code_language == "python"
    assert "def reverseList" in prob.accepted_code


def test_parser_binary_tree_level_order_fixture():
    content = load_fixture("binary_tree_level_order.md")
    parser = DSAParser()
    prob = parser.parse(content)

    assert prob.slug == "binary-tree-level-order-traversal"
    assert prob.title == "Binary Tree Level Order Traversal"
    assert prob.number == 102
    assert prob.difficulty == Difficulty.MEDIUM
    assert "Tree" in prob.tags
    assert "Breadth-First Search" in prob.tags
    assert len(prob.examples) == 3
    assert prob.examples[0].output == "[[3],[9,20],[15,7]]"
    assert "deque" in prob.accepted_code


def test_parser_messy_html_fixture():
    content = load_fixture("messy_html_problem.md")
    parser = DSAParser()
    prob = parser.parse(content)

    assert prob.slug == "3sum"
    assert prob.title == "3Sum"
    assert prob.number == 15
    assert prob.difficulty == Difficulty.MEDIUM
    assert "Two Pointers" in prob.tags
    # Confirm HTML tags stripped and entities unescaped
    assert "<p>" not in prob.description
    assert "&ne;" not in prob.description
    assert "i ≠ j" in prob.description or "i != j" in prob.description or "i" in prob.description
    assert "<br/>" not in prob.examples[0].input
    assert prob.examples[0].input == "nums = [-1,0,1,2,-1,-4]"


def test_parser_varied_code_headers_fixture():
    content = load_fixture("varied_code_headers_problem.md")
    parser = DSAParser()
    prob = parser.parse(content)

    assert prob.title == "Climbing Stairs"
    assert prob.number == 70
    assert prob.difficulty == Difficulty.HARD
    assert "Math" in prob.tags
    assert prob.code_language == "cpp"
    assert "class Solution" in prob.accepted_code
    assert "climbStairs" in prob.accepted_code


def test_parser_missing_optional_fields_fixture():
    content = load_fixture("missing_optional_fields.md")
    parser = DSAParser()
    prob = parser.parse(content)

    assert prob.title == "Reverse String"
    assert prob.number == 344
    assert prob.difficulty == Difficulty.EASY
    assert prob.tags == []
    assert len(prob.examples) == 1
    assert prob.examples[0].explanation == ""


def test_parser_malformed_invalid_problem_fixture():
    content = load_fixture("malformed_invalid_problem.md")
    parser = DSAParser()

    with pytest.raises(ValueError):
        parser.parse(content)


# ============================================================================
# 4. Edge Case Tests (Reviewer 2 & Challenger 1 Identified Fixes)
# ============================================================================

def test_html_entity_and_tag_cleaning_order():
    """
    Edge Case 1: Unescape HTML entities BEFORE or DURING tag stripping so that
    &lt;p&gt;text&lt;/p&gt; gets stripped of <p> tags cleanly rather than leaking raw <p> tags into markdown.
    """
    raw_html = "&lt;p&gt;Given an array &amp; integer target.&lt;/p&gt;"
    cleaned = MarkdownSanitizer.clean_html(raw_html)
    assert "<p>" not in cleaned
    assert "</p>" not in cleaned
    assert cleaned == "Given an array & integer target."


def test_math_exponent_preservation():
    """
    Edge Case 2: Ensure 10<sup>5</sup> and 2<sup>3</sup> become 10^5 and 2^3 rather than 105 and 23.
    """
    raw_text = "Constraints: 1 &lt;= n &lt;= 10<sup>5</sup> and 2<sup>3</sup> operations."
    cleaned = MarkdownSanitizer.clean_html(raw_text)
    assert "10^5" in cleaned
    assert "2^3" in cleaned
    assert "105" not in cleaned
    assert "23" not in cleaned


def test_problem_number_less_than_or_equal_to_zero_validation():
    """
    Edge Case 3: Validate that number <= 0 ALWAYS raises ValueError("Problem number must be a positive integer")
    regardless of whether number came from data["number"] or title regex extraction (e.g. # 0. Title).
    """
    # 1. From dictionary data["number"] = 0
    with pytest.raises(ValueError, match="Problem number must be a positive integer"):
        MarkdownSanitizer.sanitize_problem({
            "title": "Two Sum",
            "number": 0,
            "difficulty": "Easy",
            "description": "Desc",
            "accepted_code": "def two_sum(): pass",
        })

    # 2. From dictionary data["number"] = -1
    with pytest.raises(ValueError, match="Problem number must be a positive integer"):
        MarkdownSanitizer.sanitize_problem({
            "title": "Two Sum",
            "number": -1,
            "difficulty": "Easy",
            "description": "Desc",
            "accepted_code": "def two_sum(): pass",
        })

    # 3. From title regex extraction "# 0. Title"
    with pytest.raises(ValueError, match="Problem number must be a positive integer"):
        MarkdownSanitizer.sanitize_problem({
            "title": "# 0. Two Sum",
            "difficulty": "Easy",
            "description": "Desc",
            "accepted_code": "def two_sum(): pass",
        })


def test_code_block_section_scoping():
    """
    Edge Case 4: Prevent illustrative code fences inside DESCRIPTION or EXAMPLES from hijacking accepted_code.
    Only set accepted_code when current_section is CODE or SOLUTION.
    """
    markdown = """# 1. Scoped Code Problem

- **Difficulty:** Easy

## Description
Here is an example snippet in description:
```python
# Illustrative snippet
x = 10
```

## Solution Code
```python
class Solution:
    def solve(self):
        return True
```
"""
    parser = DSAParser()
    prob = parser.parse(markdown)
    assert "x = 10" not in prob.accepted_code
    assert "class Solution:" in prob.accepted_code
    assert "def solve(self):" in prob.accepted_code


def test_single_line_example_regex():
    """
    Edge Case 5: Update _parse_examples regex lookahead to handle same-line Input: ..., Output: ...
    without bleeding Output: into input.
    """
    parser = DSAParser()
    examples = parser._parse_examples(["Input: nums = [1, 2], Output: 3, Explanation: 1+2=3"])
    assert len(examples) == 1
    assert examples[0].input == "nums = [1, 2]"
    assert examples[0].output == "3"
    assert examples[0].explanation == "1+2=3"

    # Multi-line single block without newlines between Input and Output
    examples_no_exp = parser._parse_examples(['Input: s = "hello", Output: "olleh"'])
    assert len(examples_no_exp) == 1
    assert examples_no_exp[0].input == 's = "hello"'
    assert examples_no_exp[0].output == '"olleh"'


def test_emoji_title_slug_fallback():
    """
    Edge Case 6: If title slug filtering results in empty string (e.g. # 🚀🔥),
    fallback to f"problem-{number}" or "problem".
    """
    data = {
        "title": "# 🚀🔥",
        "number": 42,
        "difficulty": "Easy",
        "description": "Problem with emoji title",
        "accepted_code": "def solution(): pass",
    }
    prob = MarkdownSanitizer.sanitize_problem(data)
    assert prob.slug == "problem-42"

