# AST Parsing Analysis & Ingestion Strategy Specification

**Author:** Explorer 1 (Phase 02 Knowledge Ingestion)  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Target Module:** `src/core/ingestion/parser.py`  
**Strategy Document:** `PromptBook/Phase02/01_Ingestion_Strategy.md`  
**Date:** 2026-07-24  

---

## 1. Executive Summary & Environment Audit

### 1.1 Python Environment Inspection Results
An inspection of the runtime environment (`Python 3.13.7`) was executed using `run_command` tools to evaluate Markdown parsing libraries available in the system:

| Library | Status | Version / Path | Recommendation |
| :--- | :--- | :--- | :--- |
| **`markdown-it-py`** | **Available** | `3.0.0` (`/usr/lib/python3/dist-packages/markdown_it`) | **Primary AST Parser Engine** |
| **`bs4` (BeautifulSoup4)** | **Available** | `4.13.3` (`/usr/lib/python3/dist-packages/bs4`) | **HTML Sanitizer & DOM Normalizer** |
| **`mistune`** | **Not Installed** | `ModuleNotFoundError` | Not used (Avoid unneeded system dependency) |
| **`marko`** | **Not Installed** | `ModuleNotFoundError` | Not used |

### 1.2 Key Finding & Architectural Decision
- **Standardization:** We standardize the DSA problem ingestion pipeline on **`markdown-it-py`** paired with **`BeautifulSoup4`**.
- **Rationale:** `markdown-it-py` provides a deterministic CommonMark/GFM token stream with explicit nesting levels, map line numbers, block vs. inline separation, and AST token structures. `bs4` acts as a DOM pre-processor for legacy HTML fragments (e.g. LeetCode GraphQL API outputs).
- **Elimination of Regex:** Brittle regex patterns in the legacy normalizer (`src/plugins/ingestion/normalizer.py`) fail on nested HTML, non-standard heading capitalization, multiline code blocks containing Markdown markers, and nested list items. The AST token parser guarantees structure-aware parsing.

---

## 2. DSA Markdown AST Token Investigation

### 2.1 AST Token Token Mapping for DSA Elements

DSA problem statements consistently feature predictable structural units. `markdown-it-py` decomposes these into specific AST token sequences:

```
[Markdown Input Source]
        │
        ▼ (markdown-it-py Tokenizer)
┌─────────────────────────────────────────────────────────────┐
│ Token 00: heading_open   (tag='h1', nesting=1, level=0)     │
│ Token 01: inline         (content='1. Two Sum')             │
│ Token 02: heading_close  (tag='h1', nesting=-1, level=0)    │
│ Token 03: paragraph_open (tag='p',  nesting=1, level=0)     │
│ Token 04: inline         (content='**Difficulty:** Easy')   │
│ Token 05: paragraph_close(tag='p',  nesting=-1, level=0)    │
│ Token 06: heading_open   (tag='h2', nesting=1, level=0)     │
│ Token 07: inline         (content='Description')            │
│ Token 08: heading_close  (tag='h2', nesting=-1, level=0)    │
│ ...                                                         │
│ Token 21: bullet_list_open (tag='ul', nesting=1)            │
│ Token 22: list_item_open   (tag='li', nesting=1)            │
│ Token 24: inline           (children=[text, code_inline])   │
│ Token 26: list_item_close  (tag='li', nesting=-1)           │
│ ...                                                         │
│ Token 73: fence            (tag='code', info='cpp')         │
└─────────────────────────────────────────────────────────────┘
```

#### Detailed Token Properties:

1. **Headings (`# Title`, `## Description`, `## Examples`, `## Constraints`, `## Complexity`)**
   - `heading_open`: `tag` is `'h1'`, `'h2'`, `'h3'`, etc. `nesting` is `1`. `level` represents indentation.
   - `inline`: Follows `heading_open`. `tok.content` contains raw section title string (e.g., `"Description"`, `"Example 1:"`, `"CONSTRAINTS"`).
   - `heading_close`: `tag` matches `heading_open`, `nesting` is `-1`.

2. **Code Blocks (```cpp, ```python, ```java, etc.)**
   - `fence`: `type='fence'`, `tag='code'`, `nesting=0`.
   - `tok.info`: Contains the language identifier string (e.g. `"cpp"`, `"python"`, `"java"`). Empty string if unspecified.
   - `tok.content`: Verbatim code content string, preserving tabs, indentation, and trailing newlines.

3. **List Items (`bullet_list`, `ordered_list`, `list_item`)**
   - `bullet_list_open` / `ordered_list_open`: `tag='ul'` or `'ol'`, `nesting=1`.
   - `list_item_open`: `tag='li'`, `nesting=1`.
   - `inline`: Contains tokens inside the list item (`text`, `code_inline`, `strong_open`, `em_open`, `html_inline`).
   - `list_item_close`: `tag='li'`, `nesting=-1`.

4. **HTML Tags Embedded in Markdown**
   - `html_inline`: Inline HTML elements such as `<b>`, `</b>`, `<code>`, `</code>`, `<sup>`, `<sub>`.
   - `html_block`: Block HTML elements such as `<pre><code>...</code></pre>`, `<div>...</div>`, `<p>...</p>`.

### 2.2 Regex Brittle Failures vs. AST Guarantees

| Feature / Case | Regex Approach (Legacy) | AST Token Approach (`markdown-it-py`) |
| :--- | :--- | :--- |
| **Nested HTML Tags** | Breaks when tags are nested (`<b><code>x</code></b>`) or split across line breaks. | Token stream breaks inline HTML into discreet `html_inline` nodes or parses clean inner text. |
| **Code Inside Descriptions** | Regex can misidentify ``` within code blocks as section delimiters. | Code is isolated within `fence` tokens; inner text is treated as raw data without sub-tokenization. |
| **Heading Flexibility** | Hardcoded regex like `r'^## Description'` misses variations (`## DESCRIPTION`, `## Problem Statement`, `### 1. Description`). | Token `heading_open` detects all headings regardless of depth; normalizer matches normalized lower-case text. |
| **List Extraction** | Line-by-line regex fails on multi-line list items or bullet points with code snippets. | `bullet_list_open` → `list_item_open` → `list_item_close` token bounds ensure exact item boundaries. |

---

## 3. `src/core/ingestion/parser.py` Architectural Specification

### 3.1 Data Model Architecture

The parser returns a structured Pydantic domain model `DSAProblemAST` representing the normalized AST problem structure:

```python
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class DifficultyLevel(str, Enum):
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"
    UNKNOWN = "Unknown"


class CodeBlockNode(BaseModel):
    language: str = "text"
    code: str
    is_solution: bool = True


class ExampleNode(BaseModel):
    example_number: int
    title: str
    input: str
    output: str
    explanation: Optional[str] = None
    raw_text: str


class ComplexityNode(BaseModel):
    time_complexity: Optional[str] = None
    space_complexity: Optional[str] = None
    notes: List[str] = Field(default_factory=list)


class ProblemMetadataNode(BaseModel):
    problem_id: Optional[str] = None
    title: str
    difficulty: DifficultyLevel = DifficultyLevel.UNKNOWN
    tags: List[str] = Field(default_factory=list)
    source_url: Optional[str] = None


class DSAProblemAST(BaseModel):
    metadata: ProblemMetadataNode
    description: str
    examples: List[ExampleNode] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    complexity: ComplexityNode = Field(default_factory=ComplexityNode)
    code_blocks: List[CodeBlockNode] = Field(default_factory=list)
    hints: List[str] = Field(default_factory=list)
    raw_markdown: str
```

### 3.2 Component Architecture & Pipeline Flow

```
                               ┌─────────────────────────┐
                               │ Raw Input String (MD/HTML)│
                               └────────────┬────────────┘
                                            │
                                            ▼
                               ┌─────────────────────────┐
                               │    HTMLPreprocessor     │
                               │(DOM Cleanup via BS4)    │
                               └────────────┬────────────┘
                                            │ Clean Markdown
                                            ▼
                               ┌─────────────────────────┐
                               │      ASTTokenizer       │
                               │(markdown-it-py GFM Parser)│
                               └────────────┬────────────┘
                                            │ Token List
                                            ▼
                               ┌─────────────────────────┐
                               │   ASTTokenVisitor       │
                               │ (State Machine Engine)  │
                               └────────────┬────────────┘
                                            │ Section Dispatch
                 ┌──────────────────────────┼──────────────────────────┐
                 ▼                          ▼                          ▼
      ┌────────────────────┐      ┌────────────────────┐     ┌────────────────────┐
      │ Section Extractors │      │ Example Extractor  │     │ CodeBlock Extract  │
      │(Desc, Constraints) │      │ (Input/Output/Exp) │     │ (Fence Token Info) │
      └──────────┬─────────┘      └─────────┬──────────┘     └─────────┬──────────┘
                 │                          │                          │
                 └──────────────────────────┼──────────────────────────┘
                                            │
                                            ▼
                               ┌─────────────────────────┐
                               │    ASTValidator &       │
                               │  DSAProblemAST Builder  │
                               └─────────────────────────┘
```

### 3.3 Visitor State Machine Implementation Architecture

The `ASTTokenVisitor` processes tokens sequentially, switching states based on heading tokens:

```python
class ParserState(str, Enum):
    HEADER = "HEADER"
    DESCRIPTION = "DESCRIPTION"
    EXAMPLES = "EXAMPLES"
    CONSTRAINTS = "CONSTRAINTS"
    COMPLEXITY = "COMPLEXITY"
    CODE = "CODE"
    HINTS = "HINTS"


class DSAMarkdownParser:
    """Production AST Parser for DSA Problem Statements using markdown-it-py."""

    def __init__(self):
        self._md = MarkdownIt("gfm-like")
        self._html_preprocessor = HTMLPreprocessor()

    def parse(self, content: str, source_metadata: Optional[Dict] = None) -> DSAProblemAST:
        # 1. Preprocess raw HTML inputs (e.g. from LeetCode GraphQL API)
        clean_md = self._html_preprocessor.normalize(content)

        # 2. Tokenize via markdown-it-py
        tokens = self._md.parse(clean_md)

        # 3. Traversal via Token State Machine
        visitor = ASTTokenVisitor(tokens, source_metadata)
        ast_data = visitor.process()

        # 4. Return validated Pydantic model
        return DSAProblemAST(**ast_data, raw_markdown=clean_md)
```

---

## 4. `PromptBook/Phase02/01_Ingestion_Strategy.md` Design Document Blueprint

The proposed structure for `PromptBook/Phase02/01_Ingestion_Strategy.md` details the AST ingestion strategy for RAG document chunking:

```markdown
# Phase02/01_Ingestion_Strategy.md

## 1. Executive Summary
- Standard AST-based ingestion framework for DSA educational content.
- Shift from regex string manipulation to markdown-it-py AST token parsing.

## 2. Ingestion Pipeline Architecture
- Input Layer: GraphQL JSON payloads, Markdown files, HTML scrapers.
- HTML Normalization Layer: DOM cleanup, converting <pre><code> to Markdown fenced blocks, transforming superscripts (<sup> -> ^).
- AST Parsing Layer: markdown-it-py GFM tokenizer + Token State Visitor.
- Structural Chunking Layer: Scoped splitting based on DSAProblemAST section boundaries (Description chunk, Example chunk, Constraint chunk, Solution Code chunk).

## 3. AST Token Traversal & Visitor Protocol
- State Machine Specification: Header matching rules, heading level hierarchy (h1=Title, h2=Main Section, h3=Sub-Example).
- List Traversal Protocol: Recursive bullet_list_open/close context stack.
- Fence Code Token Handling: Preserving syntax, language tag extraction (cpp, python, java, rust), code indentation retention.

## 4. Edge Case Handling Strategy
- Missing Headings: Fallback heuristic using line pattern detection.
- Embedded HTML: Inline html_inline sanitization vs block html_block pre-parsing.
- Non-standard Section Names: Fuzzy synonym matching ("Constraints" vs "Input Constraints", "Complexity" vs "Time & Space Complexity").
- Inline Math Notation: LaTeX conversion ($O(N \log N)$ vs html <sup>/<sub>).

## 5. RAG Vector DB Chunking Integration
- Section-Aware Chunk Metadata: Injecting `section_type`, `problem_title`, `difficulty`, `tags` into ChromaDB node metadata.
- Parent-Child Chunking Strategy: Parent node = Full DSAProblemAST document; Child nodes = Individual Section chunks (Description, Code, Complexity).
```

---

## 5. Verification & Testing Strategy

### 5.1 Verification Script
A prototype verification script was tested against complex sample Markdown and raw HTML problem statements.

### 5.2 Unit Test Suite Outline (`tests/core/test_parser.py`)
- `test_parse_standard_gfm_problem()`: Validates parsing of standard Markdown problem statements.
- `test_parse_raw_html_leetcode_content()`: Validates parsing of raw HTML string inputs from LeetCode.
- `test_extract_code_blocks()`: Validates language tag resolution for C++, Python, Java, Rust code blocks.
- `test_extract_examples_and_constraints()`: Validates structured item extraction for input/output examples and mathematical constraints.
- `test_malformed_markdown_fallback()`: Validates soft degradation when encountering non-standard header names or missing sections.
