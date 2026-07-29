"""
Empirical render test script for Phase 07 Milestone 2 templates.
"""
import sys
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.core.llm.prompt_loader import PromptLoader
from src.core.exceptions import TemplateRenderError, TemplateNotFoundError

def test_educational_plan_full():
    print("=== Testing educational_plan.j2 with full complex context ===")
    loader = PromptLoader()
    context = {
        "topic": "LRU Cache Implementation",
        "slug": "lru-cache-implementation",
        "target_audience": "Intermediate",
        "difficulty": "Medium",
        "target_duration_seconds": 600,
        "problem_description": "Design a data structure that follows the constraints of a Least Recently Used (LRU) cache.",
        "constraints": [
            "Capacity > 0",
            "get and put must operate in O(1) average time complexity",
        ],
        "learning_objectives": [
            "Understand doubly linked lists combined with hash maps",
            "Implement O(1) node eviction and lookup",
        ],
        "rag_context": [
            "A doubly linked list node has prev and next pointers.",
            "A hash map maps keys to doubly linked list node pointers.",
        ],
        "code_implementations": {
            "python": "class LRUCache:\n    def __init__(self, capacity: int):\n        pass",
            "cpp": "class LRUCache {\npublic:\n    LRUCache(int capacity) {}\n};",
        },
    }
    rendered = loader.render("educational_plan.j2", context)
    print("Rendered length:", len(rendered))
    assert "LRU Cache Implementation" in rendered
    assert "lru-cache-implementation" in rendered
    assert "O(1) node eviction and lookup" in rendered
    assert "Context Block 1" in rendered
    assert "Language: python" in rendered
    assert "Language: cpp" in rendered
    print("PASS: educational_plan full rendering")

def test_educational_plan_minimal():
    print("=== Testing educational_plan.j2 with minimal context (optional keys missing) ===")
    loader = PromptLoader()
    context = {
        "topic": "Binary Search",
        "slug": "binary-search",
        "target_audience": "Beginner",
        "difficulty": "Easy",
        "target_duration_seconds": 300,
        "problem_description": "Given a sorted array of integers nums and an integer target, write a function to search target in nums.",
    }
    try:
        rendered = loader.render("educational_plan.j2", context)
        print("Rendered length:", len(rendered))
        assert "Binary Search" in rendered
        assert "Beginner" in rendered
        print("PASS: educational_plan minimal rendering")
    except Exception as e:
        print("FAIL: educational_plan minimal rendering failed with error:", type(e), e)
        raise

def test_code_explanation_full():
    print("=== Testing code_explanation.j2 with full complex context ===")
    loader = PromptLoader()
    context = {
        "topic": "Two Sum",
        "language": "python",
        "code": "def two_sum(nums, target):\n    seen = {}\n    for i, num in enumerate(nums):\n        diff = target - num\n        if diff in seen:\n            return [seen[diff], i]\n        seen[num] = i\n    return []",
        "time_complexity": "O(N)",
        "space_complexity": "O(N)",
        "line_highlights": [2, 4, 6],
        "pitfalls": ["Forgetting zero-based index", "Overwriting key in map"],
    }
    rendered = loader.render("code_explanation.j2", context)
    print("Rendered length:", len(rendered))
    assert "Two Sum" in rendered
    assert "O(N)" in rendered
    assert "Line 2:" in rendered
    assert "Forgetting zero-based index" in rendered
    assert "[2, 4, 6]" in rendered
    print("PASS: code_explanation full rendering")

def test_code_explanation_minimal():
    print("=== Testing code_explanation.j2 with minimal context (pitfalls and line_highlights omitted) ===")
    loader = PromptLoader()
    context = {
        "topic": "Two Sum",
        "language": "python",
        "code": "def two_sum(nums, target): pass",
        "time_complexity": "O(N)",
        "space_complexity": "O(N)",
    }
    try:
        rendered = loader.render("code_explanation.j2", context)
        print("Rendered length:", len(rendered))
        assert "Two Sum" in rendered
        print("PASS: code_explanation minimal rendering")
    except Exception as e:
        print("FAIL: code_explanation minimal rendering failed with error:", type(e), e)
        raise

def test_code_explanation_common_pitfalls_alias():
    print("=== Testing code_explanation.j2 using 'common_pitfalls' alias ===")
    loader = PromptLoader()
    context = {
        "topic": "Reverse Linked List",
        "language": "cpp",
        "code": "ListNode* reverseList(ListNode* head) { ... }",
        "time_complexity": "O(N)",
        "space_complexity": "O(1)",
        "common_pitfalls": ["Losing pointer reference to next node", "Null pointer dereference"],
    }
    try:
        rendered = loader.render("code_explanation.j2", context)
        print("Rendered length:", len(rendered))
        assert "Losing pointer reference to next node" in rendered
        print("PASS: code_explanation common_pitfalls alias rendering")
    except Exception as e:
        print("FAIL: code_explanation common_pitfalls alias failed with error:", type(e), e)
        raise

if __name__ == "__main__":
    test_educational_plan_full()
    test_educational_plan_minimal()
    test_code_explanation_full()
    test_code_explanation_minimal()
    test_code_explanation_common_pitfalls_alias()
