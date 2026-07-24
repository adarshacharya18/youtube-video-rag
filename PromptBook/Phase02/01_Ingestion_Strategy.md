# 01_Ingestion_Strategy.md — Knowledge Ingestion & AST Parsing Strategy

This document details the architectural design, AST parsing pipeline, data sanitization rules, and data model contracts for **Phase 02 Knowledge Ingestion** in the Automated DSA Educational YouTube Video Pipeline.

---

## 1. Executive Summary & Architecture Overview

The Knowledge Ingestion subsystem transforms raw Markdown and HTML problem statements (scraped from LeetCode or other DSA sources) into standardized, strictly validated Python dataclasses (`ScrapedProblem`).

### Architecture Pipeline
```
[ Raw Markdown / HTML ]
          │
          ▼
   ┌──────────────┐
   │  DSAParser   │ ──(1. Tokenize AST via markdown-it-py v3.0.0)
   └──────────────┘ ──(2. Traverse AST for Title, Meta, Sections)
          │
          ▼
 ┌──────────────────┐
 │ MarkdownSanitizer│ ──(3. HTML Unescape & Tag Strip via bs4)
 └──────────────────┘ ──(4. Indentation & Whitespace Normalization)
          │
          ▼
┌───────────────────┐
│  ScrapedProblem   │ ──(5. Strict Fail-Fast Validation & Frozen Dataclass)
└───────────────────┘
```

---

## 2. Domain Data Models & Contracts

All ingested problem data is stored in immutable (frozen) dataclasses with explicit type hints and strict JSON serialization methods.

### 2.1 Enum: `Difficulty`
Located in `src/models/enums.py`.
- Members: `EASY = "Easy"`, `MEDIUM = "Medium"`, `HARD = "Hard"`.
- Features robust parsing via `Difficulty.from_string(...)` supporting case-insensitive lookups ("easy", "EASY", "Med", "Medium", "Hard").

### 2.2 Dataclass: `Example`
Located in `src/models/problem.py`.
- Fields:
  - `input`: `str` (sanitized problem input)
  - `output`: `str` (sanitized expected output)
  - `explanation`: `str` (optional explanation)
- Methods: `to_dict() -> Dict[str, Any]`, `from_dict(data: Dict[str, Any]) -> Example`.

### 2.3 Frozen Dataclass: `ScrapedProblem`
Located in `src/models/problem.py` (re-exported via `src/models/__init__.py` and `src/core/ingestion/models.py`).
- Fields:
  - `slug`: `str` (URL-friendly identifier)
  - `title`: `str` (Problem title)
  - `number`: `int` (Problem number, e.g. 1)
  - `difficulty`: `Difficulty` (Enum: EASY, MEDIUM, HARD)
  - `description`: `str` (Problem statement narrative)
  - `constraints`: `List[str]` (List of problem constraint strings)
  - `examples`: `List[Example]` (List of test cases/examples)
  - `tags`: `List[str]` (Topic tags, e.g. Array, Hash Table)
  - `accepted_code`: `str` (Accepted Python or C++ reference implementation)
  - `code_language`: `str` (e.g. "python", "cpp")
  - `scraped_at`: `str` (ISO 8601 timestamp string)
- Methods: `to_dict() -> Dict[str, Any]`, `from_dict(data: Dict[str, Any]) -> ScrapedProblem`.

---

## 3. Data Sanitization Strategy (`MarkdownSanitizer`)

Located in `src/core/ingestion/sanitizer.py`.

### Key Sanitization Operations
1. **HTML Entity Unescaping & Tag Stripping (`clean_html`)**:
   - Uses `html.unescape` for entities (`&lt;`, `&gt;`, `&amp;`, `&quot;`, `&#39;`).
   - Uses BeautifulSoup (`bs4` v4.13.3+) to strip HTML tags (`<b>`, `<span>`, `<div>`, `<p>`) while preserving text structure.
2. **Code Indentation Preservation (`preserve_code_blocks`)**:
   - Preserves Python/C++ code indentation, tab characters, and inner vertical alignment.
   - Strips top/bottom blank padding lines without altering code body spacing.
3. **Whitespace Normalization (`normalize_whitespace`)**:
   - Converts CRLF (`\r\n`) to LF (`\n`).
   - Strips trailing whitespace per line.
   - Collapses 3+ consecutive newlines to 2 newlines.
4. **Metadata & Title Cleaning (`clean_title`, `clean_tags`, `clean_difficulty`)**:
   - Normalizes titles, strips `#` markdown header tags.
   - Sanitizes and deduplicates topic tags.
   - Validates difficulty string against `Difficulty` enum.

---

## 4. AST Parsing Strategy (`DSAParser`)

Located in `src/core/ingestion/parser.py`.

### Token Traversal Engine (`markdown-it-py` v3.0.0)
Instead of fragile regular expressions, `DSAParser` parses markdown into an Abstract Syntax Tree (AST) using `markdown-it-py`:
1. **Heading Processing (`heading_open`)**:
   - Level 1 (`h1`): Extract main title and problem number.
   - Level 2/3 (`h2`/`h3`): Map section headings to canonical sections: `DESCRIPTION`, `EXAMPLES`, `CONSTRAINTS`, `CODE`, `METADATA`.
2. **Metadata Key-Value Extraction (`_parse_metadata_lines`)**:
   - Scans text lines and lists for `Difficulty:`, `Tags:`, `Number:`, `Slug:`, `Scraped At:`, `Language:`.
3. **Example Parsing (`_parse_examples`)**:
   - Cleans HTML markup and markdown bold formatting (`**Input:**` -> `Input:`).
   - Splits on `Example X:` or `Input:` tokens.
   - Extracts structured `input`, `output`, and `explanation`.
4. **Code Block Extraction (`fence`)**:
   - Captures code fences (` ```python `, ` ```cpp `).
   - Preserves solution implementation and detects code language.

---

## 5. Fail-Fast Error Handling & Validation

`MarkdownSanitizer.sanitize_problem(...)` performs strict runtime validation:
- **Title**: Required, non-empty string.
- **Slug**: Derived automatically from title if missing; required non-empty.
- **Number**: Required positive integer (`number > 0`).
- **Difficulty**: Must resolve to a valid `Difficulty` enum.
- **Description**: Required non-empty problem description.
- **Accepted Code**: Required non-empty reference solution code.

If any required field is missing or invalid, a `ValueError` with detailed context is raised immediately.

---

## 6. Performance & Scalability Guidelines

1. **Parser Reuse**: `DSAParser` initializes the `MarkdownIt` engine once during instantiation (`__init__`) to eliminate per-document parsing overhead.
2. **BeautifulSoup Parsing**: HTML tag stripping is conditionally invoked only when HTML brackets (`<` and `>`) are detected, keeping plain markdown processing fast.
3. **Memory Footprint**: Immutable `ScrapedProblem` dataclasses facilitate low-overhead serialization and safe thread sharing across pipeline workers.
