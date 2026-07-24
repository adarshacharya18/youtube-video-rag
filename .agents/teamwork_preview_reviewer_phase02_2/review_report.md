# Phase 02 Knowledge Ingestion — Independent Code & Adversarial Review Report

**Reviewer**: Reviewer 2 (`teamwork_preview_reviewer_phase02_2`)  
**Roles**: reviewer, critic  
**Target Files Reviewed**:
- `src/models/enums.py`
- `src/models/problem.py`
- `src/core/ingestion/sanitizer.py`
- `src/core/ingestion/parser.py`
- `PromptBook/Phase02/01_Ingestion_Strategy.md`
- `tests/ingestion/test_parser.py`

---

## 1. Review Summary

**Verdict**: **REQUEST_CHANGES**

**Summary**:  
The Phase 02 implementation introduces a well-structured AST-based Markdown parsing pipeline using `markdown-it-py` and an immutable frozen dataclass (`ScrapedProblem`). The test suite (`tests/ingestion/test_parser.py`) passes 16/16 unit and integration tests with strong statement coverage (94% on `parser.py`, 90% on `sanitizer.py`). There are **no integrity violations** (no hardcoded test results, facade implementations, or self-certifying shortcuts).

However, adversarial stress testing revealed **4 major defects** and **1 minor flaw** where edge-case inputs (such as entity-escaped HTML tags, problem number 0, illustrative code fences in descriptions, and single-line example inputs) bypass validation or corrupt extracted problem data.

---

## 2. Integrity Assessment

- **Hardcoded test results / expected outputs in source**: NONE FOUND.
- **Dummy / facade implementations**: NONE FOUND.
- **Bypassed logic or shortcuts**: NONE FOUND.
- **Fabricated verification logs**: NONE FOUND.

---

## 3. Findings

### Major Findings

#### [Major] Finding 1: Escaped HTML Markup Entities Leak Raw HTML Tags
- **Where**: `src/core/ingestion/sanitizer.py`, lines 23–33 (`clean_html`)
- **Why**: The `clean_html` method checks `if "<" in text and ">" in text:` before invoking BeautifulSoup tag stripping. If input markdown contains entity-encoded HTML tags (e.g. `&lt;p&gt;Hello&lt;/p&gt;`), literal `<` and `>` are not present in `text` yet. The parser skips BeautifulSoup, and subsequently executes `html.unescape(stripped)`, which converts `&lt;p&gt;` into literal `<p>Hello</p>` HTML markup in the final output.
- **Impact**: Contaminates downstream problem descriptions with raw HTML tags instead of clean markdown text.
- **Suggestion**: Perform HTML unescaping first or perform tag stripping after entity unescaping (or parse HTML unconditionally/robustly).

#### [Major] Finding 2: Title-Derived Problem Number `0` Bypasses `number > 0` Validation
- **Where**: `src/core/ingestion/sanitizer.py`, lines 181–196 (`sanitize_problem`)
- **Why**: When problem number is missing from metadata and derived from title via regex (e.g., `# 0. Problem Title`), `number` is assigned `0` inside the `if raw_number is None:` block. The `if number <= 0:` validation check is located strictly inside the `else` block (when `raw_number` is provided explicitly).
- **Impact**: Violates specification contract in `01_Ingestion_Strategy.md` Section 5 (`Number: Required positive integer > 0`) by permitting `ScrapedProblem(number=0)`.
- **Suggestion**: Move the `if number <= 0:` check outside the `if/else` block so all extracted problem numbers are validated regardless of source.

#### [Major] Finding 3: Illustrative Code Fences in Description Hijack Accepted Solution Code
- **Where**: `src/core/ingestion/parser.py`, lines 88–96 (`parse`)
- **Why**: If a markdown description contains an illustrative code block (e.g., ASCII tree diagram or sample input format inside a code fence ``` 1 -> 2 -> 3 ```), `raw_data["accepted_code"]` is populated because `not raw_data["accepted_code"]` is true. If the document later provides the actual Python solution without an explicit `## Solution` section header, `parse` ignores the solution block because `raw_data["accepted_code"]` is already filled.
- **Impact**: Solution code is overwritten or replaced by illustration snippets.
- **Suggestion**: Ensure code blocks in `DESCRIPTION` section are not treated as solution code unless explicitly under a solution header or at the end of document after description.

#### [Major] Finding 4: Single-Line Example Input/Output Regex Match Bleed
- **Where**: `src/core/ingestion/parser.py`, line 236 (`_parse_examples`)
- **Why**: The regex for extracting `Input:` looks for a trailing newline before `Output:` (`r"Input:\s*(.*?)(?=\n\s*(?:Output|Explanation|Input|Example)|$)"`). When `Input:` and `Output:` are formatted on the same line (e.g., `Input: nums = [1, 2], Output: 3`), `Input:` matches all the way to the end of the line, capturing `'nums = [1, 2], Output: 3'` as the input string.
- **Impact**: Pollutes `Example.input` string with `Output:` label and value.
- **Suggestion**: Update regex pattern to match `Output:` without requiring a leading newline (e.g., `(?=\s*(?:Output|Explanation|Input|Example)|$)`).

---

### Minor Findings

#### [Minor] Finding 5: Bulleted Tag List Items Under `## Tags` Section Not Extracted
- **Where**: `src/core/ingestion/parser.py`, lines 113–124 (`_collect_list_item_text` and `_parse_metadata_lines`)
- **Why**: If tags are listed as markdown bullet points under a `## Tags` section (e.g., `- Array\n- Hash Table`), the parser does not track `TAGS` as a section, and `_parse_metadata_lines` only matches lines with explicit `Tags:` prefix.
- **Impact**: Results in `tags = []` for bullet-formatted tag lists.
- **Suggestion**: Add `"tags"` to heading keyword detection in `DSAParser.parse` and collect list items into `raw_data["tags"]`.

---

## 4. Verified Claims

| Claim / Specification | Verification Command / Method | Result |
|---|---|---|
| Pytest suite passes 16/16 tests | `.venv/bin/pytest tests/ingestion/test_parser.py -v` | **PASS** (16 passed in 0.19s) |
| Immutability of `ScrapedProblem` | `prob.title = "X"` raises `FrozenInstanceError` | **PASS** |
| `Difficulty.from_string` handling | Evaluated "easy", "EASY", "Med", "Medium", "Hard" | **PASS** |
| Fail-fast validation on missing fields | Missing title, missing description, missing code raise `ValueError` | **PASS** |
| Sanitizer indentation preservation | Preserves inner code indentation; strips blank padding | **PASS** |

---

## 5. Stress Test & Adversarial Edge-Case Results

| Scenario | Expected Behavior | Actual Behavior | Result |
|---|---|---|---|
| Empty string input | Raise `ValueError` | Raised `ValueError("Markdown content is empty...")` | **PASS** |
| Escaped HTML tags (`&lt;p&gt;x&lt;/p&gt;`) | Strip tags to `"x"` | Returned literal `"<p>x</p>"` | **FAIL** (Finding 1) |
| Title with problem number 0 (`# 0. Test`) | Raise `ValueError` (number > 0) | Created `ScrapedProblem(number=0)` | **FAIL** (Finding 2) |
| Code fence in description | Extract real solution code | Captured description diagram code | **FAIL** (Finding 3) |
| Single-line example (`Input: x, Output: y`) | `input="x"`, `output="y"` | `input="x, Output: y"`, `output="y"` | **FAIL** (Finding 4) |
| Bulleted tags under `## Tags` | `tags=["Array", "Tree"]` | `tags=[]` | **FAIL** (Finding 5) |

---

## 6. Verdict Rationale

While the core architecture (AST parsing, frozen dataclasses, fail-fast validation) is solid and all pre-existing tests pass, the 4 major edge-case vulnerabilities cause silent data corruption during knowledge ingestion. Therefore, the implementation requires targeted fixes before Phase 02 approval.
