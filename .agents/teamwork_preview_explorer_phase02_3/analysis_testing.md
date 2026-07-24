# Phase 02 Knowledge Ingestion — Test Architecture, Mock Fixtures & Parser Test Specifications

**Author:** Explorer 3 (Phase 02 Knowledge Ingestion Testing & Fixture Design)  
**Date:** 2026-07-24  
**Target Module:** `tests/ingestion/test_parser.py` & `tests/fixtures/ingestion/`  
**Status:** Completed Analysis & Specification Report  

---

## 1. Executive Summary

This report establishes the testing strategy, synthetic Markdown dataset, and test suite specification for **Phase 02 Knowledge Ingestion** of the Automated DSA Educational YouTube Video Pipeline.

Phase 02 ingests raw Data Structures & Algorithms (DSA) problem statements (Markdown, HTML, JSON), cleans and sanitizes noisy/insecure content, parses raw documents into structured Abstract Syntax Trees (AST), and yields strongly typed domain models (`ScrapedProblem`, `Example`, `Difficulty`) consumed by downstream RAG retrieval and animation generation modules.

### Key Contributions of this Document:
1. **Pytest & Project Convention Audit**: Systemic breakdown of existing test structures in `tests/`, `pytest.ini`, `pyproject.toml`, and `conftest.py`.
2. **Synthetic Mock Fixture Suite**: Complete, production-grade synthetic Markdown problem fixtures covering core DSA archetypes (Arrays, Linked Lists, Trees) and complex edge cases (messy HTML, varied syntax headers, missing optional fields).
3. **Comprehensive Test Specification for `tests/ingestion/test_parser.py`**: Detailed specification of unit, edge-case, integration, and performance tests for both `MarkdownSanitizer` and `DSAParser`.

---

## 2. Existing Test Suite Architecture & Project Conventions

An audit of `/home/adarsh/Documents/Youtube-Channel/tests/` and configuration files reveals established project conventions:

### 2.1 Pytest Configuration (`pytest.ini` & `pyproject.toml`)
- **Pytest Flags**: `-v --strict-markers --cov=src --cov-report=term-missing`
- **Python Version**: `>= 3.10` (using modern type hints like `list[str]`, `dict[str, Any]`, `str | None`).
- **Registered Test Markers**:
  - `@pytest.mark.unit`: Fast, isolated tests execution without disk/network dependencies.
  - `@pytest.mark.integration`: Tests wiring multiple modules or reading local disk fixtures.
  - `@pytest.mark.e2e`: Complete pipeline workflow tests.
  - `@pytest.mark.performance`: Benchmarks validating throughput/latency bounds.

### 2.2 Shared Fixtures (`tests/conftest.py`)
- **Isolated Directories**: `temp_data_dir(tmp_path: Path) -> Path` creates isolated directories per test invocation.
- **Config Override**: `test_config(temp_data_dir: Path) -> PipelineConfig` sets `ENVIRONMENT="testing"`, routes file system activity to `tmp_path`, sets fast retries (`max_retries=1`), and enables `DEBUG` logging.
- **Mock Services**: `mock_logger(mocker: Any)` intercepts structlog instances to keep test outputs clean.
- **Data Factories**: `mock_problem_factory()` uses closure-based factory functions to dynamically generate sample dictionaries.

### 2.3 Structural Conventions
- **Explicit Type Hints**: Every test function and fixture includes complete argument and return type annotations.
- **Docstrings**: Mandatory top-of-file summary docstring and function-level docstrings detailing the exact guarantee verified.
- **AAA Pattern**: Arrange, Act, Assert layout with clear logical separation.
- **Strict Assertions**: Direct field-by-field verification rather than loose substring matches where contracts are defined.

---

## 3. Synthetic Mock Markdown Fixture Suite

To validate parser robustly, we define seven synthetic Markdown fixtures representing standard DSA problem schemas alongside messy edge cases. These fixtures will be stored in `tests/fixtures/ingestion/`.

---

### Fixture 1: `two_sum.md` (Standard Easy - Array / Hash Table)
**Purpose**: Happy path validation for standard LeetCode-style problem with multiple examples, constraints with exponents, tags, and multi-language solutions.

```markdown
# 1. Two Sum

**Difficulty:** Easy  
**Tags:** Array, Hash Table  

## Description
Given an array of integers `nums` and an integer `target`, return *indices of the two numbers* such that they add up to `target`.

You may assume that each input would have **exactly one solution**, and you may not use the same element twice. You can return the answer in any order.

## Examples

### Example 1
**Input:** `nums = [2,7,11,15], target = 9`  
**Output:** `[0,1]`  
**Explanation:** Because `nums[0] + nums[1] == 9`, we return `[0, 1]`.

### Example 2
**Input:** `nums = [3,2,4], target = 6`  
**Output:** `[1,2]`  
**Explanation:** `nums[1] + nums[2] == 6`.

### Example 3
**Input:** `nums = [3,3], target = 6`  
**Output:** `[0,1]`  

## Constraints
- `2 <= nums.length <= 10^4`
- `-10^9 <= nums[i] <= 10^9`
- `-10^9 <= target <= 10^9`
- **Only one valid answer exists.**

## Solution

```python
class Solution:
    def twoSum(self, nums: list[int], target: int) -> list[int]:
        seen = {}
        for i, num in enumerate(nums):
            diff = target - num
            if diff in seen:
                return [seen[diff], i]
            seen[num] = i
        return []
```

```cpp
#include <vector>
#include <unordered_map>

class Solution {
public:
    std::vector<int> twoSum(std::vector<int>& nums, int target) {
        std::unordered_map<int, int> seen;
        for (int i = 0; i < nums.size(); ++i) {
            int diff = target - nums[i];
            if (seen.find(diff) != seen.end()) {
                return {seen[diff], i};
            }
            seen[nums[i]] = i;
        }
        return {};
    }
};
```
```

---

### Fixture 2: `reverse_linked_list.md` (Standard Easy - Linked List / Pointers)
**Purpose**: Validates parsing of structural pointer problems, iterative vs recursive solution code blocks, and ASCII graph representation in description.

```markdown
# 206. Reverse Linked List

**Difficulty:** Easy  
**Tags:** Linked List, Two Pointers, Recursion  

## Description
Given the `head` of a singly linked list, reverse the list, and return *the reversed list*.

```
[1] -> [2] -> [3] -> [4] -> [5]
              ↓
[5] -> [4] -> [3] -> [2] -> [1]
```

## Examples

### Example 1
**Input:** `head = [1,2,3,4,5]`  
**Output:** `[5,4,3,2,1]`  

### Example 2
**Input:** `head = [1,2]`  
**Output:** `[2,1]`  

### Example 3
**Input:** `head = []`  
**Output:** `[]`  

## Constraints
- The number of nodes in the list is the range `[0, 5000]`.
- `-5000 <= Node.val <= 5000`

## Solution

```python
# Definition for singly-linked list.
# class ListNode:
#     def __init__(self, val=0, next=None):
#         self.val = val
#         self.next = next

class Solution:
    def reverseList(self, head: ListNode | None) -> ListNode | None:
        prev, curr = None, head
        while curr:
            nxt = curr.next
            curr.next = prev
            prev = curr
            curr = nxt
        return prev
```
```

---

### Fixture 3: `binary_tree_level_order.md` (Standard Medium - Tree / BFS)
**Purpose**: Medium difficulty verification with nested array outputs in examples and multi-line explanations.

```markdown
# 102. Binary Tree Level Order Traversal

**Difficulty:** Medium  
**Tags:** Tree, Breadth-First Search, Binary Tree  

## Description
Given the `root` of a binary tree, return *the level order traversal of its nodes' values*. (i.e., from left to right, level by level).

## Examples

### Example 1
**Input:** `root = [3,9,20,null,null,15,7]`  
**Output:** `[[3],[9,20],[15,7]]`  
**Explanation:** 
Level 1: 3
Level 2: 9, 20
Level 3: 15, 7

### Example 2
**Input:** `root = [1]`  
**Output:** `[[1]]`  

### Example 3
**Input:** `root = []`  
**Output:** `[]`  

## Constraints
- The number of nodes in the tree is in the range `[0, 2000]`.
- `-1000 <= Node.val <= 1000`

## Solution

```python
from collections import deque

class Solution:
    def levelOrder(self, root: TreeNode | None) -> list[list[int]]:
        if not root:
            return []
        res, q = [], deque([root])
        while q:
            level = []
            for _ in range(len(q)):
                node = q.popleft()
                level.append(node.val)
                if node.left:
                    q.append(node.left)
                if node.right:
                    q.append(node.right)
            res.append(level)
        return res
```
```

---

### Fixture 4: `messy_html_problem.md` (Edge Case - HTML Cleanup & Security Sanitization)
**Purpose**: Validates `MarkdownSanitizer` handling of dirty raw HTML, inline styles, `<sup>` tags, `<script>` injection attempts, and unclosed HTML markup.

```markdown
# 70. Climbing Stairs

<div class="difficulty-tag" style="color: green; font-size: 14px;">Difficulty: Easy</div>
<div class="tags-container"><span>Dynamic Programming</span> | <span>Math</span></div>

<p>You are climbing a staircase. It takes <code>n</code> steps to reach the top.</p>
<script>alert("XSS Attack!");</script>
<p>Each time you can either climb <code>1</code> or <code>2</code> steps. In how many distinct ways can you climb to the top?</p>

<h3>Examples</h3>

<div class="example-box">
  <p><strong>Example 1:</strong></p>
  <pre><code>Input: n = 2
Output: 2
Explanation: There are two ways to climb to the top.
1. 1 step + 1 step
2. 2 steps</code></pre>
</div>

<div class="example-box">
  <p><strong>Example 2:</strong></p>
  <pre><code>Input: n = 3
Output: 3
Explanation: There are three ways to climb to the top.
1. 1 step + 1 step + 1 step
2. 1 step + 2 steps
3. 2 steps + 1 step</code></pre>
</div>

<h3>Constraints</h3>
<ul>
  <li><code>1 &lt;= n &lt;= 45</code></li>
  <li><code>2<sup>10</sup> &lt;= limit</code></li>
</ul>

<h3>Solution</h3>

```python
class Solution:
    def climbStairs(self, n: int) -> int:
        if n <= 2:
            return n
        a, b = 1, 2
        for _ in range(3, n + 1):
            a, b = b, a + b
        return b
```
```

---

### Fixture 5: `varied_code_headers_problem.md` (Edge Case - Non-standard Headers & Code Tags)
**Purpose**: Tests parser flexibility against alternative section headers (`Problem Statement`, `Sample Tests`, `Code Solutions`) and language aliases (`py`, `c++`, `cpp20`).

```markdown
# Problem 53: Maximum Subarray

Difficulty: Medium
Tags: Array, Dynamic Programming, Divide and Conquer

## Problem Statement
Given an integer array `nums`, find the subarray with the largest sum, and return *its sum*.

## Sample Tests

### Test Case 1
Input: nums = [-2,1,-3,4,-1,2,1,-5,4]
Output: 6
Explanation: The subarray [4,-1,2,1] has the largest sum 6.

### Test Case 2
Input: nums = [1]
Output: 1

## Constraints Section
- 1 <= nums.length <= 10^5
- -10^4 <= nums[i] <= 10^4

## Code Implementation

```py
class Solution:
    def maxSubArray(self, nums: list[int]) -> int:
        max_sum = cur_sum = nums[0]
        for x in nums[1:]:
            cur_sum = max(x, cur_sum + x)
            max_sum = max(max_sum, cur_sum)
        return max_sum
```

```c++
#include <vector>
#include <algorithm>

class Solution {
public:
    int maxSubArray(std::vector<int>& nums) {
        int maxSum = nums[0], curSum = nums[0];
        for (size_t i = 1; i < nums.size(); ++i) {
            curSum = std::max(nums[i], curSum + nums[i]);
            maxSum = std::max(maxSum, curSum);
        }
        return maxSum;
    }
};
```
```

---

### Fixture 6: `missing_optional_fields.md` (Edge Case - Minimal Input & Missing Fields)
**Purpose**: Validates graceful fallback behavior when optional fields (tags, explanations, solution code blocks, constraints) are absent.

```markdown
# 344. Reverse String

Difficulty: Easy

## Description
Write a function that reverses a string. The input string is given as an array of characters `s`.

You must do this by modifying the input array in-place with `O(1)` extra memory.

## Examples

### Example 1
Input: s = ["h","e","l","l","o"]
Output: ["o","l","l","e","h"]

### Example 2
Input: s = ["H","a","n","n","a","h"]
Output: ["h","a","n","n","a","H"]
```

---

### Fixture 7: `malformed_invalid_problem.md` (Invalid Input - Parsing Failures)
**Purpose**: Validates error handling when essential structure is broken (no problem number/title, invalid difficulty level).

```markdown
This document contains no header title and no difficulty specification.
Just random text with broken code block:

```python
def broken_func():
    pass
```
```

---

## 4. Test Suite Specification for `tests/ingestion/test_parser.py`

Below is the detailed specification for `tests/ingestion/test_parser.py`, outlining module imports, fixtures, unit tests, edge case tests, integration tests, and performance benchmarks.

---

### 4.1 Test Suite Setup & Fixtures

```python
"""
Unit and Integration Test Suite for Markdown Ingestion Parser and Sanitizer.

Validates MarkdownSanitizer and DSAParser against happy paths, edge cases,
dirty HTML inputs, non-standard section headers, and malformed inputs.
"""

from pathlib import Path
import pytest
from src.core.ingestion.models import ScrapedProblem, Example, Difficulty
from src.core.ingestion.sanitizer import MarkdownSanitizer
from src.core.ingestion.parser import DSAParser, ParserError

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "ingestion"

@pytest.fixture
def sanitizer() -> MarkdownSanitizer:
    """Provides a fresh MarkdownSanitizer instance."""
    return MarkdownSanitizer()

@pytest.fixture
def parser() -> DSAParser:
    """Provides a fresh DSAParser instance."""
    return DSAParser()

@pytest.fixture
def load_fixture():
    """Helper fixture to read mock markdown fixture files from disk."""
    def _loader(filename: str) -> str:
        filepath = FIXTURES_DIR / filename
        assert filepath.exists(), f"Fixture file not found: {filepath}"
        return filepath.read_text(encoding="utf-8")
    return _loader
```

---

### 4.2 Test Matrix Overview

| Test Name | Component | Type | Primary Objective / Target Guarantee |
|---|---|---|---|
| `test_sanitizer_removes_script_and_style_tags` | `MarkdownSanitizer` | Unit | Strips dangerous `<script>` and inline `<style>` tags. |
| `test_sanitizer_converts_html_formatting_to_markdown` | `MarkdownSanitizer` | Unit | Converts `<code>`, `<em>`, `<b>`, `<sup>` to clean Markdown syntax. |
| `test_sanitizer_normalizes_crlf_and_whitespace` | `MarkdownSanitizer` | Unit | Converts CRLF `\r\n` to LF `\n` and trims excessive trailing spaces. |
| `test_sanitizer_preserves_code_fences` | `MarkdownSanitizer` | Unit | Ensures inside of ``` code blocks remains uncorrupted. |
| `test_parser_happy_path_two_sum` | `DSAParser` | Unit | Parses `two_sum.md` accurately into `ScrapedProblem`. |
| `test_parser_happy_path_reverse_linked_list` | `DSAParser` | Unit | Parses pointer problem with structural ASCII diagram. |
| `test_parser_happy_path_binary_tree` | `DSAParser` | Unit | Parses medium difficulty tree problem with multi-line examples. |
| `test_parser_messy_html_problem` | `DSAParser` | Edge Case | Combines sanitizer + parser to parse dirty HTML documents. |
| `test_parser_varied_headers_and_language_aliases` | `DSAParser` | Edge Case | Parses `py`/`c++` code fences and custom header names. |
| `test_parser_missing_optional_fields` | `DSAParser` | Edge Case | Handles missing tags, constraints, explanations cleanly. |
| `test_parser_malformed_input_raises_error` | `DSAParser` | Invalid Input | Raises `ParserError` when problem title or number is missing. |
| `test_parser_invalid_difficulty_raises_error` | `DSAParser` | Invalid Input | Handles unrecognized difficulty strings gracefully. |
| `test_integration_file_to_dataclass_end_to_end` | System | Integration | Full end-to-end file reading, sanitization, parsing pipeline. |
| `test_parser_performance_benchmark` | System | Performance | Parses 500 documents in under 1000ms (< 2ms/doc). |

---

### 4.3 Detailed Test Method Specifications

#### Unit Tests: `MarkdownSanitizer`

1. **`test_sanitizer_removes_script_and_style_tags(sanitizer)`**
   - **Arrange**: Raw string with `<script>alert("XSS")</script>` and `<style>body{color:red}</style>`.
   - **Act**: Call `sanitizer.sanitize(raw)`.
   - **Assert**: Output contains neither `<script>` nor `<style>` nor inner malicious logic.

2. **`test_sanitizer_converts_html_formatting_to_markdown(sanitizer)`**
   - **Arrange**: Raw HTML `<p>Given <code>nums</code> array with <sup>10</sup> elements.</p>`.
   - **Act**: Call `sanitizer.sanitize(raw)`.
   - **Assert**: Markdown output contains `` `nums` `` and `^10` or converted inline markdown without HTML tags.

3. **`test_sanitizer_normalizes_crlf_and_whitespace(sanitizer)`**
   - **Arrange**: String containing Windows line endings `\r\n` and triple blank lines.
   - **Act**: Call `sanitizer.sanitize(raw)`.
   - **Assert**: Output uses Unix `\n` line endings and max two consecutive newlines.

4. **`test_sanitizer_preserves_code_fences(sanitizer)`**
   - **Arrange**: Markdown with code block containing `<vector>` or HTML-like C++ code.
   - **Act**: Call `sanitizer.sanitize(raw)`.
   - **Assert**: Code inside fences ```cpp ... ``` remains verbatim without tag stripping.

---

#### Unit Tests: `DSAParser`

5. **`test_parser_happy_path_two_sum(parser, load_fixture)`**
   - **Arrange**: Load `two_sum.md` fixture.
   - **Act**: `problem = parser.parse(content)`.
   - **Assert**:
     - `problem.number == 1`
     - `problem.title == "Two Sum"`
     - `problem.slug == "two-sum"`
     - `problem.difficulty == Difficulty.EASY`
     - `problem.tags == ["Array", "Hash Table"]`
     - `len(problem.examples) == 3`
     - `problem.examples[0].input == "nums = [2,7,11,15], target = 9"`
     - `problem.examples[0].output == "[0,1]"`
     - `problem.examples[0].explanation == "Because nums[0] + nums[1] == 9, we return [0, 1]."`
     - `len(problem.constraints) == 4`
     - `"python"` in problem.code_solutions and `"cpp"` in problem.code_solutions.

6. **`test_parser_happy_path_reverse_linked_list(parser, load_fixture)`**
   - **Arrange**: Load `reverse_linked_list.md`.
   - **Act**: `problem = parser.parse(content)`.
   - **Assert**: Verify `number == 206`, `difficulty == Difficulty.EASY`, tags `["Linked List", "Two Pointers", "Recursion"]`, ASCII diagram preserved in description.

7. **`test_parser_happy_path_binary_tree(parser, load_fixture)`**
   - **Arrange**: Load `binary_tree_level_order.md`.
   - **Act**: `problem = parser.parse(content)`.
   - **Assert**: Verify `number == 102`, `difficulty == Difficulty.MEDIUM`, nested array example output `[[3],[9,20],[15,7]]`.

---

#### Edge Case Tests

8. **`test_parser_messy_html_problem(parser, load_fixture)`**
   - **Arrange**: Load `messy_html_problem.md`.
   - **Act**: `problem = parser.parse(content)`.
   - **Assert**: HTML tags stripped, difficulty correctly parsed as `Difficulty.EASY`, XSS payload absent from description.

9. **`test_parser_varied_headers_and_language_aliases(parser, load_fixture)`**
   - **Arrange**: Load `varied_code_headers_problem.md`.
   - **Act**: `problem = parser.parse(content)`.
   - **Assert**: Headers `Problem Statement`, `Sample Tests` parsed correctly; ```py normalized to `"python"`, ```c++ normalized to `"cpp"`.

10. **`test_parser_missing_optional_fields(parser, load_fixture)`**
    - **Arrange**: Load `missing_optional_fields.md`.
    - **Act**: `problem = parser.parse(content)`.
    - **Assert**: `problem.tags == []`, `problem.constraints == []`, `problem.code_solutions == {}`, example explanations set to `None` without crashing.

---

#### Invalid Input Tests

11. **`test_parser_malformed_input_raises_error(parser, load_fixture)`**
    - **Arrange**: Load `malformed_invalid_problem.md`.
    - **Act & Assert**: `with pytest.raises(ParserError): parser.parse(content)`.

12. **`test_parser_invalid_difficulty_raises_error(parser)`**
    - **Arrange**: Markdown text with `Difficulty: Super Hard`.
    - **Act & Assert**: `with pytest.raises(ParserError, match="Invalid difficulty"): parser.parse(raw)`.

---

#### Integration & Performance Tests

13. **`test_integration_file_to_dataclass_end_to_end(parser, sanitizer, temp_path)`**
    - **Arrange**: Write raw Markdown file to `tmp_path / "problem.md"`.
    - **Act**: Read file, run `sanitizer.sanitize()`, then `parser.parse()`.
    - **Assert**: Returned `ScrapedProblem` passes full validation schema and serializes cleanly to dict.

14. **`test_parser_performance_benchmark(parser, load_fixture)`**
    - **Arrange**: Load `two_sum.md` content string.
    - **Act**: Run `parser.parse(content)` 500 times inside high-resolution timer (`time.perf_counter()`).
    - **Assert**: Average time per parse < 2.0 milliseconds.

---

## 5. Verification & Execution Instructions

Once Implementer creates `src/core/ingestion/sanitizer.py`, `src/core/ingestion/parser.py`, and `tests/ingestion/test_parser.py`, the test suite can be run via pytest:

```bash
# Run unit tests only
pytest tests/ingestion/test_parser.py -m unit -v

# Run full test suite with code coverage
pytest tests/ingestion/test_parser.py -v --cov=src/core/ingestion --cov-report=term-missing
```

---
*Report compiled by Explorer 3 — Phase 02 Knowledge Ingestion.*
