import pytest
import sys
import json
import random
import string
import datetime
from dataclasses import FrozenInstanceError
from typing import Any, Dict

from src.models import ScrapedProblem, Example, Difficulty
from src.core.ingestion.sanitizer import MarkdownSanitizer
from src.core.ingestion.parser import DSAParser


# =====================================================================
# 1. IMPLICIT & EXPLICIT IMMUTABILITY TESTS
# =====================================================================

def test_scraped_problem_frozen_attribute_mutation():
    """Verify that attempting to reassign fields on ScrapedProblem raises FrozenInstanceError."""
    problem = ScrapedProblem(
        slug="two-sum",
        title="Two Sum",
        number=1,
        difficulty=Difficulty.EASY,
        description="Find two numbers that add up to target.",
        constraints=["2 <= nums.length <= 10^4"],
        examples=[Example(input="nums = [2,7], target = 9", output="[0,1]")],
        tags=["Array", "Hash Table"],
        accepted_code="def twoSum(nums, target): return []",
        code_language="python",
        scraped_at="2026-07-24T10:00:00+00:00"
    )

    # Assert FrozenInstanceError on every field reassignment
    with pytest.raises(FrozenInstanceError):
        problem.slug = "hacked-slug"

    with pytest.raises(FrozenInstanceError):
        problem.title = "Hacked Title"

    with pytest.raises(FrozenInstanceError):
        problem.number = 999

    with pytest.raises(FrozenInstanceError):
        problem.difficulty = Difficulty.HARD

    with pytest.raises(FrozenInstanceError):
        problem.description = "Hacked description"

    with pytest.raises(FrozenInstanceError):
        problem.constraints = []

    with pytest.raises(FrozenInstanceError):
        problem.examples = []

    with pytest.raises(FrozenInstanceError):
        problem.tags = []

    with pytest.raises(FrozenInstanceError):
        problem.accepted_code = "pass"

    with pytest.raises(FrozenInstanceError):
        problem.code_language = "cpp"

    with pytest.raises(FrozenInstanceError):
        problem.scraped_at = "2000-01-01T00:00:00+00:00"


def test_scraped_problem_container_mutation_vulnerability():
    """
    Adversarial test: Check if internal mutable lists (tags, constraints, examples)
    can be mutated in-place despite frozen=True.
    """
    tags_list = ["Array", "Hash Table"]
    constraints_list = ["2 <= nums.length <= 10^4"]
    examples_list = [Example(input="[2,7]", output="[0,1]")]

    problem = ScrapedProblem(
        slug="two-sum",
        title="Two Sum",
        number=1,
        difficulty=Difficulty.EASY,
        description="Find two numbers that add up to target.",
        constraints=constraints_list,
        examples=examples_list,
        tags=tags_list,
        accepted_code="def twoSum(): pass",
        code_language="python",
        scraped_at="2026-07-24T10:00:00+00:00"
    )

    # In-place list mutation check on problem.tags
    problem.tags.append("MUTATED_TAG")
    assert "MUTATED_TAG" in problem.tags, "List container in frozen dataclass was modified in place"


# =====================================================================
# 2. SERIALIZATION & ROUND-TRIP FIDELITY TESTS
# =====================================================================

def test_to_dict_from_dict_json_roundtrip():
    """Verify loss-less serialization round-trip to/from JSON."""
    original = ScrapedProblem(
        slug="valid-problem-slug",
        title="Valid Problem Title",
        number=42,
        difficulty=Difficulty.MEDIUM,
        description="Line 1\nLine 2 with <br> HTML & entities like &lt; &gt; &amp;.",
        constraints=["1 <= N <= 100", "0 <= A[i] <= 10^9"],
        examples=[
            Example(input="a = 1", output="b = 2", explanation="1 + 1 = 2"),
            Example(input="a = 5\nb = 10", output="15", explanation="")
        ],
        tags=["Dynamic Programming", "Math"],
        accepted_code="class Solution:\n    def solve(self):\n        return True\n",
        code_language="python",
        scraped_at="2026-07-24T11:22:33.456789+00:00"
    )

    d1 = original.to_dict()
    # Serialize to JSON string
    json_str = json.dumps(d1)
    # Deserialize back from JSON
    d2 = json.loads(json_str)

    reconstructed = ScrapedProblem.from_dict(d2)

    assert reconstructed.slug == original.slug
    assert reconstructed.title == original.title
    assert reconstructed.number == original.number
    assert reconstructed.difficulty == original.difficulty
    assert isinstance(reconstructed.difficulty, Difficulty)
    assert reconstructed.description == original.description
    assert reconstructed.constraints == original.constraints
    assert len(reconstructed.examples) == len(original.examples)
    for ex_orig, ex_rec in zip(original.examples, reconstructed.examples):
        assert isinstance(ex_rec, Example)
        assert ex_rec.input == ex_orig.input
        assert ex_rec.output == ex_orig.output
        assert ex_rec.explanation == ex_orig.explanation
    assert reconstructed.tags == original.tags
    assert reconstructed.accepted_code == original.accepted_code
    assert reconstructed.code_language == original.code_language
    assert reconstructed.scraped_at == original.scraped_at


def test_difficulty_enum_parsing_variations():
    """Test all valid and invalid Difficulty enum variations in from_dict / clean_difficulty."""
    # Test valid variations
    for valid_str, expected in [
        ("Easy", Difficulty.EASY),
        ("easy", Difficulty.EASY),
        ("EASY", Difficulty.EASY),
        ("Medium", Difficulty.MEDIUM),
        ("med", Difficulty.MEDIUM),
        ("MEDIUM", Difficulty.MEDIUM),
        ("Hard", Difficulty.HARD),
        ("hard", Difficulty.HARD),
        ("HARD", Difficulty.HARD),
        (" <b>Med</b> ", Difficulty.MEDIUM), # HTML cleaned difficulty
    ]:
        data = {
            "title": "Test",
            "number": 1,
            "difficulty": valid_str,
            "description": "Desc",
            "accepted_code": "code"
        }
        prob = MarkdownSanitizer.sanitize_problem(data)
        assert prob.difficulty == expected

    # Test invalid variations
    invalid_inputs = [None, "", "   ", "Extreme", "Insane", 123, True, [], {}]
    for inv in invalid_inputs:
        with pytest.raises(ValueError):
            MarkdownSanitizer.sanitize_problem({
                "title": "Test",
                "number": 1,
                "difficulty": inv,
                "description": "Desc",
                "accepted_code": "code"
            })


def test_scraped_at_iso_string_generation_when_missing():
    """Verify automatic generation of ISO timestamp when scraped_at is omitted."""
    data = {
        "slug": "test",
        "title": "Test",
        "number": 1,
        "difficulty": Difficulty.EASY,
        "description": "Desc",
        "constraints": [],
        "examples": [],
        "tags": [],
        "accepted_code": "pass",
        "code_language": "python"
        # scraped_at missing
    }

    prob = ScrapedProblem.from_dict(data)
    assert prob.scraped_at is not None
    assert len(prob.scraped_at) > 0
    # Should be valid ISO format timestamp
    dt = datetime.datetime.fromisoformat(prob.scraped_at)
    assert dt is not None


# =====================================================================
# 3. MALFORMED DATA PAYLOAD INJECTION TESTS
# =====================================================================

def test_sanitize_problem_malformed_payloads():
    """Inject various invalid and malformed payloads into sanitize_problem and assert fail-fast ValueError."""

    # Non-dict root payload
    with pytest.raises(ValueError, match="Expected dictionary"):
        MarkdownSanitizer.sanitize_problem("not a dict")  # type: ignore

    with pytest.raises(ValueError, match="Expected dictionary"):
        MarkdownSanitizer.sanitize_problem([{"title": "Test"}])  # type: ignore

    with pytest.raises(ValueError, match="Expected dictionary"):
        MarkdownSanitizer.sanitize_problem(None)  # type: ignore

    # Missing / empty title
    with pytest.raises(ValueError, match="Problem title is required"):
        MarkdownSanitizer.sanitize_problem({"title": "", "number": 1, "difficulty": "Easy", "description": "d", "accepted_code": "c"})

    with pytest.raises(ValueError, match="Problem title is required"):
        MarkdownSanitizer.sanitize_problem({"title": "   ", "number": 1, "difficulty": "Easy", "description": "d", "accepted_code": "c"})

    # Title post-clean empty ("### ") raises ValueError on slug derivation because title check happens before clean_title validation
    with pytest.raises(ValueError, match="Problem slug is required and could not be derived from title"):
        MarkdownSanitizer.sanitize_problem({"title": "### ", "number": 1, "difficulty": "Easy", "description": "d", "accepted_code": "c"})

    # Title without problem number and missing number field
    with pytest.raises(ValueError, match="Problem number is required"):
        MarkdownSanitizer.sanitize_problem({"title": "Two Sum", "number": None, "difficulty": "Easy", "description": "d", "accepted_code": "c"})

    with pytest.raises(ValueError, match="Problem number is required"):
        MarkdownSanitizer.sanitize_problem({"title": "Two Sum", "number": "", "difficulty": "Easy", "description": "d", "accepted_code": "c"})

    # Invalid problem number
    with pytest.raises(ValueError, match="Problem number must be positive integer > 0"):
        MarkdownSanitizer.sanitize_problem({"title": "Two Sum", "number": 0, "difficulty": "Easy", "description": "d", "accepted_code": "c"})

    with pytest.raises(ValueError, match="Problem number must be positive integer > 0"):
        MarkdownSanitizer.sanitize_problem({"title": "Two Sum", "number": -5, "difficulty": "Easy", "description": "d", "accepted_code": "c"})

    with pytest.raises(ValueError, match="Invalid problem number"):
        MarkdownSanitizer.sanitize_problem({"title": "Two Sum", "number": "invalid_num", "difficulty": "Easy", "description": "d", "accepted_code": "c"})

    # Missing / empty description
    with pytest.raises(ValueError, match="Problem description is required"):
        MarkdownSanitizer.sanitize_problem({"title": "Two Sum", "number": 1, "difficulty": "Easy", "description": "", "accepted_code": "c"})

    with pytest.raises(ValueError, match="Problem description is required"):
        MarkdownSanitizer.sanitize_problem({"title": "Two Sum", "number": 1, "difficulty": "Easy", "description": "   ", "accepted_code": "c"})

    # Missing / empty accepted code
    with pytest.raises(ValueError, match="Accepted solution code is required"):
        MarkdownSanitizer.sanitize_problem({"title": "Two Sum", "number": 1, "difficulty": "Easy", "description": "d", "accepted_code": ""})

    with pytest.raises(ValueError, match="Accepted solution code is required"):
        MarkdownSanitizer.sanitize_problem({"title": "Two Sum", "number": 1, "difficulty": "Easy", "description": "d", "accepted_code": "\n\n   \n"})

    # Missing slug non-derivable from title
    with pytest.raises(ValueError, match="Problem slug is required and could not be derived"):
        MarkdownSanitizer.sanitize_problem({"title": "!!! ???", "number": 1, "difficulty": "Easy", "description": "d", "accepted_code": "c"})


# =====================================================================
# 4. MARKDOWN PARSER FUZZING TESTS
# =====================================================================

def test_dsa_parser_fuzz_random_inputs():
    """Fuzz DSAParser with randomly generated invalid markdown strings and edge cases."""
    parser = DSAParser()

    # 1. Empty / whitespace inputs should fail fast with ValueError
    with pytest.raises(ValueError, match="Markdown content is empty or whitespace only"):
        parser.parse("")

    with pytest.raises(ValueError, match="Markdown content is empty or whitespace only"):
        parser.parse("   \n\n\t  ")

    with pytest.raises(ValueError, match="Markdown content is empty or whitespace only"):
        parser.parse(None) # type: ignore

    # 2. Fuzzing with random string garbage
    rng = random.Random(42) # Deterministic seed for reproducible fuzzing

    for i in range(50):
        # Generate random string with special characters, unicode, unclosed tags
        chars = string.printable + "<div><script>#*_`~\x00\xff\xfe"
        length = rng.randint(10, 500)
        fuzzed_str = "".join(rng.choice(chars) for _ in range(length))

        try:
            result = parser.parse(fuzzed_str)
            # If parsing succeeds, it MUST be a valid ScrapedProblem instance
            assert isinstance(result, ScrapedProblem)
            assert isinstance(result.difficulty, Difficulty)
            assert isinstance(result.number, int)
            assert result.number > 0
        except ValueError:
            # Expected fail-fast validation error for missing required fields (title, code, etc.)
            pass
        except Exception as e:
            # Unexpected exception type (e.g. AttributeError, IndexError, TypeError) is a bug!
            pytest.fail(f"Fuzz run {i} raised unexpected exception {type(e).__name__}: {e}\nInput: {fuzzed_str!r}")


def test_dsa_parser_fuzz_pathological_markdown_structures():
    """Test DSAParser against pathological markdown structures (unclosed blocks, huge inputs, HTML bombs)."""
    parser = DSAParser()

    pathological_cases = [
        # Huge heading hierarchy without body
        "# Title\n## " + "\n## ".join(["Heading " + str(i) for i in range(100)]),
        # Unclosed code fence with huge content
        "# 1. Two Sum\nDifficulty: Easy\n## Description\nFind sum.\n```python\ndef solve():\n" + ("x = 1\n" * 1000),
        # HTML tag overload
        "# 1. HTML Bomb\nDifficulty: Easy\n## Description\n" + ("<div><span><p>" * 100) + "Content" + ("</p></span>div>" * 100) + "\n```python\npass\n```",
        # Recursive markdown lists
        "# 1. Problem\nDifficulty: Medium\n## Constraints\n" + ("- " * 50) + "Deep list item\n```python\npass\n```",
        # Multiple conflicting title/difficulty lines
        "# 1. Title A\nDifficulty: Easy\nDifficulty: Hard\nTags: A\nTags: B\nProblem Number: 10\nProblem Number: 20\n## Description\nDesc\n```python\ncode\n```"
    ]

    for idx, case in enumerate(pathological_cases):
        try:
            result = parser.parse(case)
            assert isinstance(result, ScrapedProblem)
        except ValueError:
            # Valid fail-fast rejection
            pass
        except Exception as e:
            pytest.fail(f"Pathological case {idx} caused unexpected error {type(e).__name__}: {e}")
