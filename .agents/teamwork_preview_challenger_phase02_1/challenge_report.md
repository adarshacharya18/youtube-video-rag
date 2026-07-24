# Adversarial Stress-Test Report: Knowledge Ingestion (`DSAParser` & `MarkdownSanitizer`)

**Target Subsystem**: `src/core/ingestion/parser.py` & `src/core/ingestion/sanitizer.py`  
**Execution Timestamp**: 2026-07-24T05:53:16Z  
**Test Suite**: `.agents/teamwork_preview_challenger_phase02_1/run_adversarial_tests.py`

---

## Challenge Summary

**Overall risk assessment**: **HIGH**

While `DSAParser` and `MarkdownSanitizer` achieve outstanding performance (< 0.8ms average execution latency for standard problem files) and scale linearly to 10MB documents without memory crashes, adversarial stress-testing identified **1 CRITICAL data corruption flaw** and **3 HIGH/MEDIUM failure modes**.

---

## Challenges & Vulnerability Analysis

### [CRITICAL] Challenge 1: HTML Subscript/Superscript Tag Stripping Corrupts Exponent Values (`10<sup>5</sup>` -> `105`)

- **Assumption Challenged**: Using `BeautifulSoup(text, "html.parser").get_text()` cleanly strips HTML formatting without corrupting mathematical bounds and complexity expressions.
- **Attack Scenario**: Problem statements containing HTML mathematical formatting (e.g. `10<sup>5</sup>`, `2<sup>3</sup>`, `O(N<sup>2</sup>)`, `x<sub>i</sub>`).
- **Blast Radius**: **High Data Corruption**. `BeautifulSoup.get_text()` strips the `<sup>` tags without introducing space or exponent notation (`^`), concatenating the exponent digits directly to the base number:
  - `10<sup>5</sup>` becomes `105`
  - `2<sup>3</sup>` becomes `23`
  - `10<sup>9</sup>` becomes `109`
  - `O(N<sup>2</sup>)` becomes `O(N2)`
  Downstream components (RAG chunking, script generation, test case generation) receive severely incorrect mathematical constraints ($105$ instead of $100,000$).
- **Vulnerable Code**: `src/core/ingestion/sanitizer.py` lines 27-28:
  ```python
  soup = BeautifulSoup(soup_str, "html.parser")
  stripped = soup.get_text()
  ```
- **Mitigation**: Pre-process text to replace `<sup>text</sup>` with `^text` (or `^{text}`) and `<sub>text</sub>` with `_text` before passing to BeautifulSoup, or preserve math HTML tags.

---

### [HIGH] Challenge 2: Deep List Indentation Hijacking Swallows Section Headers (> 7 Levels)

- **Assumption Challenged**: Markdown AST traversal correctly isolates section headings (`## Solution`, `## Examples`) regardless of preceding list nesting depth.
- **Attack Scenario**: Problem statements with lists indented > 7 levels (or 16+ leading spaces).
- **Blast Radius**: CommonMark parser rules classify deeply indented lines as indented code block continuations inside the open list item. Top-level `heading_open` tokens for subsequent sections (`## Solution`) are never emitted. `DSAParser` fails to recognize the Solution section, resulting in missing `accepted_code` and throwing `ValueError: Accepted solution code is required and cannot be empty`.
- **Vulnerable Code**: `src/core/ingestion/parser.py` lines 55-79 and token loop line 115.
- **Mitigation**: Normalize list indentation before parsing or inspect text content of indented blocks for section headers (`## Solution`, `## Examples`).

---

### [MEDIUM] Challenge 3: Pure Emoji / Non-ASCII Title Slug Derivation Failure

- **Assumption Challenged**: Title cleaning and slug derivation (`re.sub(r"[^\w\s-]", "", title.lower())`) always produces a non-empty string for valid problem titles.
- **Attack Scenario**: Problems with pure emoji titles (e.g. `# 🚀🔥💻💯`) or non-ASCII character titles.
- **Blast Radius**: `re.sub` strips all emoji characters, reducing `slug` to an empty string `""`. `MarkdownSanitizer.sanitize_problem` raises an unhandled `ValueError: Problem slug is required and could not be derived from title`.
- **Vulnerable Code**: `src/core/ingestion/sanitizer.py` lines 173-176:
  ```python
  slug = re.sub(r"[^\w\s-]", "", title.lower())
  slug = re.sub(r"[_\s]+", "-", slug).strip("-")
  if not slug:
      raise ValueError("Problem slug is required and could not be derived from title")
  ```
- **Mitigation**: Fall back to a default slug format (e.g., `problem-{number}`) or hash when regex stripping yields an empty string.

---

### [LOW] Challenge 4: Missing H1 Heading Rejection

- **Assumption Challenged**: All markdown problem sources start with an `# H1` heading for the title.
- **Attack Scenario**: Markdowns where title is given in metadata (e.g., `Title: Two Sum`) or H2 headings (`## Two Sum`).
- **Blast Radius**: `DSAParser` only sets `raw_data["title"]` when `level == "h1"`. Ingestion fails fast with `ValueError: Problem title is required and cannot be empty`.
- **Vulnerable Code**: `src/core/ingestion/parser.py` lines 61-63.
- **Mitigation**: Allow title extraction from metadata lines if no H1 token is encountered.

---

## Stress Test Results

| Test Scenario | Input Description | Expected Behavior | Actual Behavior | Result |
| :--- | :--- | :--- | :--- | :--- |
| **Standard Latency** | 500 iterations per fixture | Latency < 5.0 ms (P95) | Mean: **0.754ms**, P95: **1.269ms** | **PASS** |
| **10MB Huge Markdown** | 9.76 MB generated markdown | Complete parse < 5s, no OOM | Parsed in **1050.79 ms (~1.05s)** | **PASS** |
| **Unicode & Emojis** | Title & tags with emojis + CJK | Parse unicode correctly | Title & tags extracted cleanly | **PASS** |
| **Pure Emoji Title** | Title `# 🚀🔥💻💯` | Generate slug or fallback | `ValueError: Problem slug is required...` | **FAIL** |
| **Math HTML (`<sup>`)** | `10<sup>5</sup>` constraint | Preserve exponent math | Corrupted to `105` | **FAIL** |
| **Nested Lists (5 levels)**| 5-level indented list | Extract constraints & code | Constraints extracted, code parsed | **PASS** |
| **Nested Lists (10 levels)**| 10-level indented list | Extract constraints & code | Header lost -> `ValueError` | **FAIL** |
| **XSS HTML Tags** | `<script>` & `<iframe>` tags | Strip dangerous markup | Tags stripped cleanly | **PASS** |
| **Unclosed Fence at EOF**| Code fence missing closing ` ``` ` | Parse code block | Code block extracted | **PASS** |
| **Mixed Languages** | C++ in desc, Python in solution | Prefer CODE section lang | Language set to `python` | **PASS** |
| **No-Lang Code Fence** | ` ``` ` without lang tag | Default to `python` | Defaulted to `python` | **PASS** |
| **Invalid Difficulty** | `Difficulty: Extreme` | Raise `ValueError` | `ValueError` raised correctly | **PASS** |
| **Number in H1 Title** | `# 456. Problem Title` | Strip number from title | Number: 456, Title stripped | **PASS** |

---

## Performance Metrics Benchmark Summary

- **Total Fixture Runs**: 3,000 document parses across 6 standard problem fixtures.
- **Mean Execution Time**: **0.754 ms**
- **50th Percentile (P50)**: **0.759 ms**
- **95th Percentile (P95)**: **1.269 ms**
- **99th Percentile (P99)**: **1.890 ms**
- **Target Performance Benchmark (< 5ms)**: **PASSED (100% of standard documents under 2.0ms)**

---

## Unchallenged Areas

- **Database Persistence**: Out of scope for parser unit challenge.
- **Network Scraper Fetching**: Scraper network interactions not part of parser AST phase.
