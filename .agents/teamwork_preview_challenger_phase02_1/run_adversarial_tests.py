#!/usr/bin/env python3
"""
Adversarial and Stress-Testing Suite for Phase 02 Knowledge Ingestion (DSAParser & MarkdownSanitizer)
"""

import sys
import os
import time
import math
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.ingestion.parser import DSAParser
from src.core.ingestion.sanitizer import MarkdownSanitizer
from src.models import Difficulty, Example, ScrapedProblem


class AdversarialTestRunner:
    def __init__(self):
        self.parser = DSAParser()
        self.results = []
        self.benchmark_metrics = {}

    def log_result(self, test_name: str, passed: bool, details: str, metrics: Dict[str, Any] = None):
        res = {
            "test_name": test_name,
            "status": "PASS" if passed else "FAIL",
            "details": details,
            "metrics": metrics or {}
        }
        self.results.append(res)
        status_str = "✅ PASS" if passed else "❌ FAIL"
        print(f"[{status_str}] {test_name}: {details}")

    # =========================================================================
    # 1. LATENCY BENCHMARK (< 5ms per document target)
    # =========================================================================
    def test_latency_benchmark(self):
        print("\n--- Running Suite 1: Standard Document Latency Benchmark ---")
        fixtures_dir = PROJECT_ROOT / "tests" / "fixtures" / "ingestion"
        fixture_files = list(fixtures_dir.glob("*.md"))
        
        # Exclude malformed fixture which is expected to fail
        valid_fixtures = [f for f in fixture_files if "malformed" not in f.name]
        
        iterations = 500
        timing_records = {f.name: [] for f in valid_fixtures}
        
        for fixture in valid_fixtures:
            content = fixture.read_text(encoding="utf-8")
            # Warmup
            for _ in range(10):
                self.parser.parse(content)
            
            # Benchmark
            for _ in range(iterations):
                t0 = time.perf_counter()
                self.parser.parse(content)
                t1 = time.perf_counter()
                timing_records[fixture.name].append((t1 - t0) * 1000.0) # in ms

        all_times = []
        fixture_stats = {}

        for name, times in timing_records.items():
            times.sort()
            all_times.extend(times)
            mean_t = sum(times) / len(times)
            p50 = times[int(len(times) * 0.50)]
            p95 = times[int(len(times) * 0.95)]
            p99 = times[int(len(times) * 0.99)]
            max_t = max(times)
            fixture_stats[name] = {
                "mean_ms": round(mean_t, 3),
                "p50_ms": round(p50, 3),
                "p95_ms": round(p95, 3),
                "p99_ms": round(p99, 3),
                "max_ms": round(max_t, 3)
            }

        all_times.sort()
        overall_mean = sum(all_times) / len(all_times)
        overall_p50 = all_times[int(len(all_times) * 0.50)]
        overall_p95 = all_times[int(len(all_times) * 0.95)]
        overall_p99 = all_times[int(len(all_times) * 0.99)]

        self.benchmark_metrics = {
            "overall_mean_ms": round(overall_mean, 3),
            "overall_p50_ms": round(overall_p50, 3),
            "overall_p95_ms": round(overall_p95, 3),
            "overall_p99_ms": round(overall_p99, 3),
            "per_fixture": fixture_stats
        }

        passed = overall_p95 < 5.0
        details = f"Overall P50: {overall_p50:.3f}ms, P95: {overall_p95:.3f}ms, Mean: {overall_mean:.3f}ms (Target: < 5ms)"
        self.log_result("Latency Benchmark (<5ms)", passed, details, self.benchmark_metrics)

    # =========================================================================
    # 2. MASSIVE/HUGE MARKDOWN (Up to 10MB)
    # =========================================================================
    def test_huge_markdown_scaling(self):
        print("\n--- Running Suite 2: Huge Markdown Scaling (Up to 10MB) ---")
        sizes_kb = [10, 100, 1000, 5000, 10000] # up to 10MB
        
        base_template = """# {num}. Massive Problem Statement {size}KB

Difficulty: Hard
Tags: Array, Dynamic Programming, Scalability
Slug: massive-problem-{size}kb

## Description
{desc}

## Constraints
- 1 <= N <= 10^5
- Array elements are integers.

## Examples
Example 1:
Input: nums = [1, 2, 3]
Output: 6
Explanation: Sum is 6.

## Solution
```python
def solve(nums):
    return sum(nums)
```
"""

        for size_kb in sizes_kb:
            target_bytes = size_kb * 1024
            # Repeat paragraph to reach target size
            para = "Given an array of integers, we need to process complex operations repeatedly. " * 50 + "\n\n"
            repeat_count = max(1, target_bytes // len(para))
            desc = para * repeat_count
            
            md_content = base_template.format(num=size_kb, size=size_kb, desc=desc)
            actual_mb = len(md_content.encode('utf-8')) / (1024 * 1024)
            
            t0 = time.perf_counter()
            error_occurred = None
            parsed_prob = None
            try:
                parsed_prob = self.parser.parse(md_content)
            except Exception as e:
                error_occurred = str(e)
            t1 = time.perf_counter()
            duration_ms = (t1 - t0) * 1000.0

            passed = (error_occurred is None) and (parsed_prob is not None)
            details = f"Size: {actual_mb:.2f}MB, Duration: {duration_ms:.2f}ms, Error: {error_occurred}"
            self.log_result(f"Huge Markdown ({size_kb}KB)", passed, details, {
                "size_mb": round(actual_mb, 2),
                "duration_ms": round(duration_ms, 2),
                "success": passed,
                "error": error_occurred
            })

    # =========================================================================
    # 3. UNICODE & EMOJI HEAVY INPUTS
    # =========================================================================
    def test_unicode_and_emojis(self):
        print("\n--- Running Suite 3: Unicode & Emoji Heavy Inputs ---")
        
        # Subtest 3A: Emojis and Unicode in Title, Tags, Description
        md_unicode = """# 42. 🚀 Pathfinding in 🌐 Multiverse Matrix 🤖🔥

Difficulty: Medium
Tags: 🌳 Tree, 🕸️ Graph, 𝒪(N log N) Algorithm, 算法, 検索
Slug: pathfinding-multiverse-matrix

## Description
Find the shortest path in a 𝒩-dimensional grid with obstacles 🛑 and warp gates 🌀.
Given start (x₀, y₀) and target (x₁, y₁).
Special Unicode characters: ™️®️©️ 𝞪 𝞫 𝞲 𝞴 𝞵 𝚺 𝛀 𝛁.
Arabic: Dynamic programming algorithm graph.
Chinese: 寻找矩阵中的最短路径 dynamically.

## Constraints
- 1 <= N <= 10⁵
- -10⁹ <= matrix[i][j] <= 10⁹

## Examples
Example 1:
Input: grid = [[1, 🎃], [🤖, 1]]
Output: 2 🏁
Explanation: Path found with cost 2.

## Solution
```python
def multiverse_path(grid: list) -> int:
    # 🚀 Fast path solver
    return len(grid) 🤖
```
"""
        try:
            prob = self.parser.parse(md_unicode)
            passed = (prob.number == 42 and "Pathfinding" in prob.title and "🌳 Tree" in prob.tags)
            self.log_result("Unicode & Emoji Normal Parse", passed, f"Title: {prob.title!r}, Tags: {prob.tags}")
        except Exception as e:
            self.log_result("Unicode & Emoji Normal Parse", False, f"Exception: {e}")

        # Subtest 3B: Pure Emoji Title (Slug Derivation Failure)
        md_pure_emoji = """# 🚀🔥💻💯

Difficulty: Easy
Tags: Array

## Description
Problem with pure emoji title.

## Solution
```python
pass
```
"""
        try:
            prob = self.parser.parse(md_pure_emoji)
            self.log_result("Pure Emoji Title Handling", True, f"Title: {prob.title!r}, Slug: {prob.slug!r}")
        except ValueError as ve:
            self.log_result("Pure Emoji Title Handling", False, f"ValueError (Slug Derivation Bug): {ve}")
        except Exception as e:
            self.log_result("Pure Emoji Title Handling", False, f"Unexpected Exception: {e}")

    # =========================================================================
    # 4. DEEPLY NESTED LISTS & MATH HTML TAGS (<sup>, <sub>, <katex>, XSS)
    # =========================================================================
    def test_nested_lists_and_html_math(self):
        print("\n--- Running Suite 4: Deeply Nested Lists & Math HTML Tags ---")

        # Subtest 4A: Math HTML tags (<sup>, <sub>, <katex>) - checking for mathematical corruption
        md_math = """# 100. Power Math Calculation

Difficulty: Hard
Tags: Math

## Description
Given an integer n, calculate 10<sup>5</sup> + 2<sup>3</sup> and x<sub>i</sub> + y<sub>j</sub>.
Also compute <katex>x^2 + y^2 = z^2</katex>.

## Constraints
- 1 <= n <= 10<sup>9</sup>
- Complexity must be O(N<sup>2</sup>)

## Examples
Example 1:
Input: n = 2<sup>3</sup>
Output: 8

## Solution
```python
def pow_math(n):
    return 10**5
```
"""
        try:
            prob = self.parser.parse(md_math)
            has_105_corruption = "105" in prob.description and "10<sup>5</sup>" not in prob.description and "10^5" not in prob.description
            has_23_corruption = "23" in prob.description and "2<sup>3</sup>" not in prob.description
            
            details = f"Description parsed: {prob.description!r}. Constraints: {prob.constraints!r}"
            if has_105_corruption or has_23_corruption:
                self.log_result("Math HTML Tags Preservation (<sup>/<sub>)", False, f"CRITICAL DATA CORRUPTION DETECTED! '10<sup>5</sup>' stripped to '105'! Details: {details}")
            else:
                self.log_result("Math HTML Tags Preservation (<sup>/<sub>)", True, details)
        except Exception as e:
            self.log_result("Math HTML Tags Preservation (<sup>/<sub>)", False, f"Exception: {e}")

        # Subtest 4B: Moderate Nested Lists (5 levels) vs Deep Nested Lists (10 levels)
        for depth_count in [5, 10]:
            nested_lines = []
            for depth in range(1, depth_count + 1):
                indent = "  " * (depth - 1)
                nested_lines.append(f"{indent}* Level {depth} constraint line n <= {depth}")
            nested_md = "\n".join(nested_lines)

            md_nested_list = f"""# 101. Nested List Problem {depth_count}

Difficulty: Easy
Tags: Recursion

## Description
Nested list problem.

## Constraints
{nested_md}

## Solution
```python
def nested(): pass
```
"""
            try:
                t0 = time.perf_counter()
                prob = self.parser.parse(md_nested_list)
                t1 = time.perf_counter()
                duration_ms = (t1 - t0) * 1000.0
                self.log_result(f"Nested Lists ({depth_count} levels)", True, f"Duration: {duration_ms:.2f}ms, Constraints extracted: {len(prob.constraints)}")
            except Exception as e:
                self.log_result(f"Nested Lists ({depth_count} levels)", False, f"Section Header Lost / Exception: {e}")

        # Subtest 4C: Malicious / XSS HTML Tags
        md_xss = """# 102. XSS Test Problem

Difficulty: Easy
Tags: Security

## Description
Problem containing <script>alert('XSS')</script> and <iframe src="http://evil.com"></iframe> and <img src="x" onerror="alert(1)">.

## Constraints
- <svg onload="alert(1)">

## Solution
```python
def xss(): pass
```
"""
        try:
            prob = self.parser.parse(md_xss)
            has_script = "<script>" in prob.description or "<iframe" in prob.description
            self.log_result("XSS / Malicious HTML Tag Stripping", not has_script, f"Description: {prob.description!r}")
        except Exception as e:
            self.log_result("XSS / Malicious HTML Tag Stripping", False, f"Exception: {e}")

    # =========================================================================
    # 5. UNCLOSED CODE FENCES & MIXED LANGUAGES
    # =========================================================================
    def test_unclosed_fences_and_mixed_languages(self):
        print("\n--- Running Suite 5: Unclosed Code Fences & Mixed Languages ---")

        # Subtest 5A: Unclosed Code Fence at EOF
        md_unclosed = """# 200. Unclosed Code Fence Problem

Difficulty: Easy
Tags: Strings

## Description
Given a string s.

## Solution
```python
class Solution:
    def solve(self, s: str) -> str:
        return s[::-1]
"""
        try:
            prob = self.parser.parse(md_unclosed)
            passed = bool(prob.accepted_code and "class Solution" in prob.accepted_code)
            self.log_result("Unclosed Code Fence at EOF", passed, f"Accepted Code: {prob.accepted_code!r}, Lang: {prob.code_language}")
        except Exception as e:
            self.log_result("Unclosed Code Fence at EOF", False, f"Exception: {e}")

        # Subtest 5B: Mixed Languages (Python, C++, Java, Rust) in description vs CODE section
        md_mixed_langs = """# 201. Multi Language Problem

Difficulty: Medium
Tags: Array

## Description
Here is an example in C++:
```cpp
int solve() { return 42; }
```
And here is Java:
```java
public class Solution { public int solve() { return 42; } }
```

## Solution
```python
class Solution:
    def solve(self) -> int:
        return 42
```
"""
        try:
            prob = self.parser.parse(md_mixed_langs)
            passed = (prob.code_language == "python" and "def solve" in prob.accepted_code)
            self.log_result("Mixed Language Preference (CODE section over Description)", passed, f"Lang: {prob.code_language!r}, Code: {prob.accepted_code!r}")
        except Exception as e:
            self.log_result("Mixed Language Preference (CODE section over Description)", False, f"Exception: {e}")

        # Subtest 5C: Code Fence with no language specified
        md_no_lang = """# 202. No Language Specifier

Difficulty: Easy

## Description
Test without lang tag.

## Solution
```
def no_lang():
    return True
```
"""
        try:
            prob = self.parser.parse(md_no_lang)
            passed = (prob.code_language == "python" and "def no_lang" in prob.accepted_code)
            self.log_result("Code Fence without Language Tag (Default Python)", passed, f"Lang: {prob.code_language!r}")
        except Exception as e:
            self.log_result("Code Fence without Language Tag (Default Python)", False, f"Exception: {e}")

    # =========================================================================
    # 6. EDGE CASES IN METADATA & PARSING
    # =========================================================================
    def test_metadata_edge_cases(self):
        print("\n--- Running Suite 6: Metadata & Parsing Edge Cases ---")

        # Subtest 6A: Missing H1 Heading (Title in metadata or derived)
        md_no_h1 = """**Difficulty:** Hard
**Tags:** Dynamic Programming
**Number:** 300

## Description
Problem without H1 heading.

## Solution
```python
def solve(): pass
```
"""
        try:
            prob = self.parser.parse(md_no_h1)
            self.log_result("Missing H1 Heading", True, f"Title: {prob.title!r}, Slug: {prob.slug!r}")
        except ValueError as ve:
            self.log_result("Missing H1 Heading", False, f"ValueError expected (No H1 title): {ve}")
        except Exception as e:
            self.log_result("Missing H1 Heading", False, f"Unexpected Exception: {e}")

        # Subtest 6B: Invalid Difficulty Enum String
        md_bad_diff = """# 301. Bad Difficulty Problem

Difficulty: Extreme
Tags: Array

## Description
Desc.

## Solution
```python
def solve(): pass
```
"""
        try:
            prob = self.parser.parse(md_bad_diff)
            self.log_result("Invalid Difficulty Enum ('Extreme')", False, f"Unexpectedly accepted: {prob.difficulty}")
        except ValueError as ve:
            self.log_result("Invalid Difficulty Enum ('Extreme')", True, f"Correctly rejected with ValueError: {ve}")
        except Exception as e:
            self.log_result("Invalid Difficulty Enum ('Extreme')", False, f"Unexpected Exception: {e}")

        # Subtest 6C: Problem Number in Title vs Metadata
        md_title_num = """# 456. Problem Title With Number In H1

Difficulty: Medium
Tags: Array

## Description
Desc.

## Solution
```python
def solve(): pass
```
"""
        try:
            prob = self.parser.parse(md_title_num)
            passed = (prob.number == 456 and prob.title == "Problem Title With Number In H1")
            self.log_result("Problem Number Stripped from Title", passed, f"Num: {prob.number}, Title: {prob.title!r}")
        except Exception as e:
            self.log_result("Problem Number Stripped from Title", False, f"Exception: {e}")

    def run_all(self):
        print("=================================================================")
        print("STARTING ADVERSARIAL STRESS-TEST SUITE FOR KNOWLEDGE INGESTION")
        print("=================================================================")
        
        self.test_latency_benchmark()
        self.test_huge_markdown_scaling()
        self.test_unicode_and_emojis()
        self.test_nested_lists_and_html_math()
        self.test_unclosed_fences_and_mixed_languages()
        self.test_metadata_edge_cases()

        print("\n=================================================================")
        print("TEST SUITE SUMMARY")
        print("=================================================================")
        pass_count = sum(1 for r in self.results if r["status"] == "PASS")
        fail_count = sum(1 for r in self.results if r["status"] == "FAIL")
        total = len(self.results)
        print(f"Total Tests: {total} | Passed: {pass_count} | Failed: {fail_count}")

        # Dump results JSON for reporting
        summary_path = Path(__file__).parent / "test_results.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump({
                "total": total,
                "passed": pass_count,
                "failed": fail_count,
                "benchmark_metrics": self.benchmark_metrics,
                "results": self.results
            }, f, indent=2)
        print(f"Results saved to {summary_path}")


if __name__ == "__main__":
    runner = AdversarialTestRunner()
    runner.run_all()
