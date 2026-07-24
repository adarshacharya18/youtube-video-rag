# Phase 02 Knowledge Ingestion: Data Models Placement & Sanitizer Design Specification

**Author:** Explorer 2 (Phase 02 Knowledge Ingestion)  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Working Directory:** `/home/adarsh/Documents/Youtube-Channel/.agents/teamwork_preview_explorer_phase02_2`  
**Status:** Canonical Design Analysis Report  
**Date:** July 2026  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Domain Data Models & Placement Strategy](#2-domain-data-models--placement-strategy)
   - [2.1 Domain Models Overview (`ScrapedProblem`, `Example`, `Difficulty`)](#21-domain-models-overview-scrapedproblem-example-difficulty)
   - [2.2 Architectural Placement Options Analysis](#22-architectural-placement-options-analysis)
   - [2.3 Recommended Placement & Bridge Pattern](#23-recommended-placement--bridge-pattern)
   - [2.4 Data Model Code Specifications](#24-data-model-code-specifications)
3. [Design Specification for `src/core/ingestion/sanitizer.py`](#3-design-specification-for-srccoreingestionsanitizerpy)
   - [3.1 Sanitizer Architecture & Core Responsibilities](#31-sanitizer-architecture--core-responsibilities)
   - [3.2 HTML Entity Unescaping & CSS Formatting Rules](#32-html-entity-unescaping--css-formatting-rules)
   - [3.3 Code Block & Indentation Preservation Strategy](#33-code-block--indentation-preservation-strategy)
   - [3.4 Whitespace Normalization (Text vs. Code)](#34-whitespace-normalization-text-vs-code)
   - [3.5 Title, Difficulty, and Tag Standardization](#35-title-difficulty-and-tag-standardization)
   - [3.6 Example & Constraint Formatting Logic](#36-example--constraint-formatting-logic)
   - [3.7 Complete Python Reference Implementation (`sanitizer.py`)](#37-complete-python-reference-implementation-sanitizerpy)
4. [Immutability, Validation, and JSON Serialization](#4-immutability-validation-and-json-serialization)
   - [4.1 Frozen Dataclass Rules & Immutability Guarantees](#41-frozen-dataclass-rules--immutability-guarantees)
   - [4.2 Strict Validation Logic (`__post_init__`)](#42-strict-validation-logic-__post_init__)
   - [4.3 JSON Round-Trip Serialization & Codecs](#43-json-round-trip-serialization--codecs)
5. [Pipeline Integration Strategy](#5-pipeline-integration-strategy)
   - [5.1 Integration with Connectors & Normalizers](#51-integration-with-connectors--normalizers)
   - [5.2 Downstream Contracts (RAG, Tag Explorer, Script Generator)](#52-downstream-contracts-rag-tag-explorer-script-generator)
6. [Testing Strategy & Edge Case Matrix](#6-testing-strategy--edge-case-matrix)

---

## 1. Executive Summary

This report establishes the architectural specification for domain model placement and designs `src/core/ingestion/sanitizer.py` for Phase 02 (Knowledge Ingestion) of the Automated DSA Educational YouTube Video Pipeline.

### Key Architectural Decisions:
1. **Model Placement:** Primary domain models (`ScrapedProblem`, `Example`, `Difficulty`, etc.) MUST reside in `src/models/` (specifically `src/models/problem.py` and `src/models/enums.py`), conforming to Layer 1 of the canonical folder architecture (`PromptBook/04_Folder_Structure.md`). `src/core/ingestion/models.py` or `src/core/models.py` will act as re-exporting bridges if backward compatibility or core-layer imports require it.
2. **Sanitizer Engine Design:** `src/core/ingestion/sanitizer.py` provides deterministic, zero-dependency HTML cleaning, whitespace normalization, title/difficulty/tag standardization, code-indentation preservation, and example parsing.
3. **Immutability & Safety:** All domain models are implemented as `@dataclass(frozen=True)` with explicit `__post_init__` fail-fast validation, supporting complete bidirectional JSON round-trip serialization (handling `datetime` ISO 8601 formatting and `Enum` name mapping).

---

## 2. Domain Data Models & Placement Strategy

### 2.1 Domain Models Overview (`ScrapedProblem`, `Example`, `Difficulty`)

As specified in `PromptBook/Phase01/04_Data_Models.md`:

- **`Difficulty` Enum:** Represents problem complexity on LeetCode (`EASY`, `MEDIUM`, `HARD`).
- **`Example` Dataclass:** Value object representing a single problem test case.
  - `input: str` (required, non-empty)
  - `output: str` (required, non-empty)
  - `explanation: str | None` (optional)
- **`ScrapedProblem` Dataclass:** The root data model output by the scraper and ingested into the knowledge pipeline.
  - `slug: str` (canonical ID, e.g., `"two-sum"`)
  - `title: str` (human-readable title, e.g., `"Two Sum"`)
  - `number: int` (LeetCode problem number, e.g., `1`)
  - `difficulty: Difficulty` (`EASY`, `MEDIUM`, or `HARD`)
  - `description: str` (cleaned Markdown problem statement)
  - `constraints: list[str]` (bulleted array of constraints)
  - `examples: list[Example]` (list of input/output test cases)
  - `tags: list[str]` (array of topic tags)
  - `accepted_code: str` (optimal solution source code)
  - `code_language: str` (e.g., `"cpp"`)
  - `scraped_at: datetime` (timestamp of extraction in UTC)

---

### 2.2 Architectural Placement Options Analysis

We evaluated three potential module locations for `ScrapedProblem`, `Example`, and `Difficulty`:

| Criteria | Option A: `src/models/` (Canonical Layer 1) | Option B: `src/core/ingestion/models.py` | Option C: `src/core/models.py` |
|---|---|---|---|
| **Layer Alignment** | **Perfect.** Matches `PromptBook/04_Folder_Structure.md` Layer 1 specification. Leaf package with zero internal dependencies. | **Sub-optimal.** Places domain data contracts inside a specific feature package (`ingestion`). | **Moderate.** Bloats `core/` with domain data structures instead of keeping infrastructure separate. |
| **Dependency Graph** | Direct leaf (`models` -> standard library). All pipeline modules (`scraper`, `tags`, `rag`, `script`, `orchestrator`) import from `src.models`. | Ingestion-dependent. Other modules would need to import from `src.core.ingestion.models`, introducing cross-module coupling. | Infrastructure-dependent. `core` handles logging/config, not domain models. |
| **Circular Dependency Risk** | **Zero.** `src.models` never imports from `src.core` or any module. | Low, but violates separation of concerns. | Low, but pollutes shared infrastructure. |
| **JSON Codec Maintenance** | Centralized in `src.models`. | Fragmented across sub-packages. | Centralized in core, but violates Layer 1 leaf rule. |

---

### 2.3 Recommended Placement & Bridge Pattern

**Primary Recommendation:**
1. **`src/models/enums.py`**: Houses `Difficulty`, `PipelineStatus`, `AnimationStyle`, `SectionType`.
2. **`src/models/problem.py`**: Houses `Example` and `ScrapedProblem`.
3. **`src/models/__init__.py`**: Re-exports `Difficulty`, `Example`, `ScrapedProblem` for convenience imports (`from src.models import ScrapedProblem, Difficulty, Example`).

**Bridge Pattern (`src/core/ingestion/models.py` or `src/core/models.py`):**
To ensure backward compatibility and smooth integration with legacy or core plugins, `src/core/ingestion/models.py` re-exports `ScrapedProblem`, `Example`, and `Difficulty` from `src.models`. Intermediate ingestion-only structures (e.g., `RawContent`, `NormalizedDocument`) reside in `src/plugins/ingestion/connector_base.py` or `src/core/ingestion/models.py`.

```
[Layer 1: src/models/]
    ├── enums.py          --> Difficulty Enum
    ├── problem.py        --> Example, ScrapedProblem Dataclasses
    └── __init__.py      --> Public Re-exports

[Layer 2: src/core/ingestion/]
    ├── models.py         --> Imports & re-exports from src.models + Ingestion DTOs
    └── sanitizer.py      --> ProblemSanitizer (uses src.models)
```

---

### 2.4 Data Model Code Specifications

#### `src/models/enums.py`

```python
"""
Domain Enumerations for the DSA Video Pipeline.
Leaf module: standard library dependencies only.
"""

from enum import Enum, unique


@unique
class Difficulty(str, Enum):
    """LeetCode problem difficulty level."""
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"

    @classmethod
    def from_str(cls, value: str) -> "Difficulty":
        """Flexible string parser converting various representations to Difficulty enum."""
        if not isinstance(value, str):
            raise TypeError(f"Difficulty expected string, got {type(value).__name__}")
            
        val_clean = value.strip().upper()
        if val_clean in ("EASY", "1"):
            return cls.EASY
        elif val_clean in ("MEDIUM", "2"):
            return cls.MEDIUM
        elif val_clean in ("HARD", "3"):
            return cls.HARD
        else:
            raise ValueError(f"Invalid difficulty string: '{value}'. Expected EASY, MEDIUM, or HARD.")
```

#### `src/models/problem.py`

```python
"""
Problem Domain Models.
Leaf module: standard library dependencies only.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Self

from src.models.enums import Difficulty


@dataclass(frozen=True)
class Example:
    """Represents a single LeetCode test case example."""
    input: str
    output: str
    explanation: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.input, str):
            raise TypeError(f"Example.input must be a string, got {type(self.input).__name__}")
        if not isinstance(self.output, str):
            raise TypeError(f"Example.output must be a string, got {type(self.output).__name__}")
        if self.explanation is not None and not isinstance(self.explanation, str):
            raise TypeError(f"Example.explanation must be a string or None, got {type(self.explanation).__name__}")

        if not self.input.strip():
            raise ValueError("Example.input cannot be empty or whitespace-only.")
        if not self.output.strip():
            raise ValueError("Example.output cannot be empty or whitespace-only.")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dictionary."""
        res: Dict[str, Any] = {
            "input": self.input,
            "output": self.output,
        }
        if self.explanation is not None:
            res["explanation"] = self.explanation
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Self:
        """Instantiate from serialized JSON dictionary."""
        if not isinstance(data, dict):
            raise TypeError(f"Example.from_dict expected dict, got {type(data).__name__}")
        return cls(
            input=data["input"],
            output=data["output"],
            explanation=data.get("explanation"),
        )


@dataclass(frozen=True)
class ScrapedProblem:
    """Root data model representing raw/sanitized problem data extracted from LeetCode."""
    slug: str
    title: str
    number: int
    difficulty: Difficulty
    description: str
    constraints: List[str]
    examples: List[Example]
    tags: List[str]
    accepted_code: str
    code_language: str
    scraped_at: datetime

    def __post_init__(self) -> None:
        # Type Validation
        if not isinstance(self.slug, str):
            raise TypeError(f"ScrapedProblem.slug must be str, got {type(self.slug).__name__}")
        if not isinstance(self.title, str):
            raise TypeError(f"ScrapedProblem.title must be str, got {type(self.title).__name__}")
        if not isinstance(self.number, int):
            raise TypeError(f"ScrapedProblem.number must be int, got {type(self.number).__name__}")
        if not isinstance(self.difficulty, Difficulty):
            raise TypeError(f"ScrapedProblem.difficulty must be Difficulty Enum, got {type(self.difficulty).__name__}")
        if not isinstance(self.description, str):
            raise TypeError(f"ScrapedProblem.description must be str, got {type(self.description).__name__}")
        if not isinstance(self.constraints, list):
            raise TypeError(f"ScrapedProblem.constraints must be list, got {type(self.constraints).__name__}")
        if not isinstance(self.examples, list):
            raise TypeError(f"ScrapedProblem.examples must be list, got {type(self.examples).__name__}")
        if not isinstance(self.tags, list):
            raise TypeError(f"ScrapedProblem.tags must be list, got {type(self.tags).__name__}")
        if not isinstance(self.accepted_code, str):
            raise TypeError(f"ScrapedProblem.accepted_code must be str, got {type(self.accepted_code).__name__}")
        if not isinstance(self.code_language, str):
            raise TypeError(f"ScrapedProblem.code_language must be str, got {type(self.code_language).__name__}")
        if not isinstance(self.scraped_at, datetime):
            raise TypeError(f"ScrapedProblem.scraped_at must be datetime, got {type(self.scraped_at).__name__}")

        # Value & Constraint Validation
        if not self.slug.strip() or not re.match(r"^[a-z0-9-]+$", self.slug):
            raise ValueError(f"Invalid slug format: '{self.slug}'. Must be lowercase kebab-case.")
        if not self.title.strip():
            raise ValueError("ScrapedProblem.title cannot be empty.")
        if self.number <= 0:
            raise ValueError(f"ScrapedProblem.number must be positive, got {self.number}")
        if not self.description.strip():
            raise ValueError("ScrapedProblem.description cannot be empty.")
        if not self.examples:
            raise ValueError("ScrapedProblem.examples must contain at least one Example.")
        if not self.accepted_code.strip():
            raise ValueError("ScrapedProblem.accepted_code cannot be empty.")
        
        supported_langs = {"cpp", "python", "java", "javascript", "c"}
        if self.code_language.lower() not in supported_langs:
            raise ValueError(f"Unsupported code_language: '{self.code_language}'. Must be one of {supported_langs}")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dictionary."""
        return {
            "slug": self.slug,
            "title": self.title,
            "number": self.number,
            "difficulty": self.difficulty.value,
            "description": self.description,
            "constraints": list(self.constraints),
            "examples": [ex.to_dict() for ex in self.examples],
            "tags": list(self.tags),
            "accepted_code": self.accepted_code,
            "code_language": self.code_language,
            "scraped_at": self.scraped_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Self:
        """Instantiate from serialized JSON dictionary."""
        if not isinstance(data, dict):
            raise TypeError(f"ScrapedProblem.from_dict expected dict, got {type(data).__name__}")
            
        scraped_at_raw = data["scraped_at"]
        if isinstance(scraped_at_raw, str):
            # Parse ISO 8601 string
            scraped_at = datetime.fromisoformat(scraped_at_raw.replace("Z", "+00:00"))
        elif isinstance(scraped_at_raw, datetime):
            scraped_at = scraped_at_raw
        else:
            raise TypeError(f"Invalid scraped_at format: {type(scraped_at_raw).__name__}")

        difficulty = Difficulty.from_str(data["difficulty"]) if isinstance(data["difficulty"], str) else data["difficulty"]

        examples = [
            ex if isinstance(ex, Example) else Example.from_dict(ex)
            for ex in data.get("examples", [])
        ]

        return cls(
            slug=data["slug"],
            title=data["title"],
            number=data["number"],
            difficulty=difficulty,
            description=data["description"],
            constraints=list(data.get("constraints", [])),
            examples=examples,
            tags=list(data.get("tags", [])),
            accepted_code=data["accepted_code"],
            code_language=data["code_language"],
            scraped_at=scraped_at,
        )
```

---

## 3. Design Specification for `src/core/ingestion/sanitizer.py`

### 3.1 Sanitizer Architecture & Core Responsibilities

`src/core/ingestion/sanitizer.py` acts as the domain cleaning and validation engine. It takes raw HTML/JSON inputs from scrapers or connectors and transforms them into pristine, immutable `ScrapedProblem` instances.

#### Pipeline Flow:
```
Raw Dict / Connector Payload
        │
        ▼
1. HTML Entity Unescape (&quot;, &lt;, &gt;, &amp;, &nbsp;)
        │
        ▼
2. Structure Extraction (<pre><code> -> ``` blocks, <code> -> `code`)
        │
        ▼
3. CSS/HTML Tag Stripping (Remove spans, style attributes, residual tags)
        │
        ▼
4. Whitespace Normalization (Preserving code indentation in blocks)
        │
        ▼
5. Field-Level Standardization (Title, Difficulty, Tags, Constraints, Examples)
        │
        ▼
6. Validation & Construct Frozen ScrapedProblem
```

---

### 3.2 HTML Entity Unescaping & CSS Formatting Rules

1. **HTML Entity Unescaping:**
   Use standard library `html.unescape(text)`. Converts `&quot;` -> `"`, `&lt;` -> `<`, `&gt;` -> `>`, `&amp;` -> `&`, `&nbsp;` -> ` `, `&#39;` -> `'`, `&le;` -> `<=`, `&ge;` -> `>=`, `&times;` -> `*`, `&minus;` -> `-`.
2. **HTML Tag Conversion to Markdown:**
   - `<pre><code>(.*?)</code></pre>` or `<pre>(.*?)</pre>` -> ```\n\1\n``` (code block).
   - `<code>(.*?)</code>` -> `\1` (inline code).
   - `<strong>(.*?)</strong>` or `<b>(.*?)</b>` -> `**\1**` (bold).
   - `<em>(.*?)</em>` or `<i>(.*?)</i>` -> `*\1*` (italics).
   - `<sup>(.*?)</sup>` -> `^\1` (superscript).
   - `<sub>(.*?)</sub>` -> `_\1` (subscript).
   - `<li>(.*?)</li>` -> `- \1\n` (list items).
   - `<p>(.*?)</p>` -> `\1\n\n` (paragraphs).
   - `<br\s*/?>` -> `\n` (line break).
3. **CSS & Unwanted Tag Stripping:**
   - Remove `<style>...</style>` and `<script>...</script>` blocks entirely.
   - Strip all inline CSS attributes (e.g. `style="..."`, `class="..."`, `id="..."`).
   - Strip remaining generic tags (`<span>`, `<div>`, `<font>`, `<a>`) using `re.sub(r'<[^>]+>', '', text)`.

---

### 3.3 Code Block & Indentation Preservation Strategy

**Problem:** Standard whitespace normalization collapses multiple spaces into a single space and strips line prefixes. This ruins C++ / Python code indentation inside pre/code tags or solution submissions.

**Solution: Context-Aware Code Block Sanitization:**
1. Split document into code blocks (inside triple backticks ```) and narrative text (outside code blocks).
2. For narrative text:
   - Collapse multiple spaces (`r'[ \t]+'` -> `' '`).
   - Limit consecutive newlines to maximum 2 (`\n\n`).
3. For code blocks & `accepted_code`:
   - Do NOT collapse spaces at the beginning of lines (preserve indentation).
   - Expand tab characters `\t` to 4 spaces.
   - Strip trailing whitespace on each code line.
   - Standardize line endings to `\n` (converting `\r\n` -> `\n`).

---

### 3.4 Whitespace Normalization (Text vs. Code)

```python
def normalize_text_whitespace(text: str) -> str:
    """Normalizes narrative text whitespace without touching code blocks."""
    # Split text into code blocks and normal text
    parts = re.split(r"(```.*?```)", text, flags=re.DOTALL)
    cleaned_parts = []
    for part in parts:
        if part.startswith("```"):
            # Inside code block: preserve leading indentation, strip trailing line spaces
            lines = part.splitlines()
            cleaned_lines = [line.rstrip() for line in lines]
            cleaned_parts.append("\n".join(cleaned_lines))
        else:
            # Narrative text: collapse spaces, normalize newlines
            clean_part = re.sub(r"[ \t]+", " ", part)
            clean_part = re.sub(r"\n{3,}", "\n\n", clean_part)
            cleaned_parts.append(clean_part)
    return "".join(cleaned_parts).strip()
```

---

### 3.5 Title, Difficulty, and Tag Standardization

1. **Title Cleaning:**
   - Remove HTML tags and unescape entities.
   - Collapse internal whitespace.
   - Strip problem number prefixes if present in title string (e.g. `"1. Two Sum"` -> `"Two Sum"`), storing the number separately in `number`.
   - Strip leading/trailing whitespace.
2. **Difficulty Standardization:**
   - Route through `Difficulty.from_str(val)`.
   - Maps `"Easy"`, `"EASY"`, `"1"` -> `Difficulty.EASY`.
   - Maps `"Medium"`, `"MEDIUM"`, `"2"` -> `Difficulty.MEDIUM`.
   - Maps `"Hard"`, `"HARD"`, `"3"` -> `Difficulty.HARD`.
   - Raises `ValueError` on unmapped input.
3. **Tag Standardization:**
   - Clean HTML/entities from each tag.
   - Convert to lowercase kebab-case or trimmed standard string.
   - Deduplicate tags while maintaining original order (`list(dict.fromkeys(cleaned_tags))`).
   - Discard empty or space-only tags.

---

### 3.6 Example & Constraint Formatting Logic

1. **Example Parsing & Formatting:**
   - Extract raw text inside `Example 1: ...` blocks or structured JSON dictionaries.
   - Separate `Input: ...`, `Output: ...`, `Explanation: ...`.
   - Clean whitespace around equal signs (e.g., `nums = [2, 7, 11, 15] , target = 9` -> `nums = [2,7,11,15], target = 9`).
   - Parse `explanation` if present, setting `explanation=None` if empty or absent.
   - Instantiates frozen `Example(input=clean_in, output=clean_out, explanation=clean_exp)`.
2. **Constraint Formatting:**
   - Unescape math symbols: `&le;` -> `<=`, `&ge;` -> `>=`, `10<sup>4</sup>` -> `10^4`.
   - Ensure each constraint is formatted as a single concise bullet string (e.g., `2 <= nums.length <= 10^4`).
   - Filter out empty constraint items.

---

### 3.7 Complete Python Reference Implementation (`sanitizer.py`)

Below is the complete design specification for `src/core/ingestion/sanitizer.py`:

```python
"""
Knowledge Ingestion Problem Sanitizer.

Provides deterministic cleaning, HTML entity unescaping, markdown normalization,
code block indentation preservation, tag/difficulty standardization, and 
Example extraction for ScrapedProblem instantiation.
"""

import html
import re
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from src.models.enums import Difficulty
from src.models.problem import Example, ScrapedProblem


class ProblemSanitizer:
    """
    Sanitizes raw problem payloads from scrapers/connectors into pristine ScrapedProblem objects.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def sanitize(self, raw_data: Dict[str, Any]) -> ScrapedProblem:
        """
        Main entry point. Takes a raw dictionary payload and returns a frozen ScrapedProblem.
        """
        if not isinstance(raw_data, dict):
            raise TypeError(f"ProblemSanitizer expects dict payload, got {type(raw_data).__name__}")

        # 1. Clean Title & Number
        raw_title = str(raw_data.get("title", ""))
        raw_number = raw_data.get("number", 0)
        number, clean_title = self.standardize_title_and_number(raw_number, raw_title)

        # 2. Extract Slug
        raw_slug = str(raw_data.get("slug", "")).strip().lower()
        if not raw_slug and clean_title:
            raw_slug = re.sub(r"[^a-z0-9]+", "-", clean_title.lower()).strip("-")

        # 3. Standardize Difficulty
        raw_diff = raw_data.get("difficulty", "EASY")
        difficulty = Difficulty.from_str(str(raw_diff))

        # 4. Clean Description (HTML -> Markdown, preserve code blocks)
        raw_desc = str(raw_data.get("description", ""))
        clean_description = self.clean_html_description(raw_desc)

        # 5. Standardize Constraints
        raw_constraints = raw_data.get("constraints", [])
        clean_constraints = self.sanitize_constraints(raw_constraints)

        # 6. Standardize Tags
        raw_tags = raw_data.get("tags", [])
        clean_tags = self.sanitize_tags(raw_tags)

        # 7. Format Examples
        raw_examples = raw_data.get("examples", [])
        clean_examples = self.sanitize_examples(raw_examples, clean_description)

        # 8. Clean Accepted Code
        raw_code = str(raw_data.get("accepted_code", ""))
        clean_code = self.sanitize_code(raw_code)

        # 9. Language & Scraped Timestamp
        code_lang = str(raw_data.get("code_language", "cpp")).strip().lower()
        scraped_at_raw = raw_data.get("scraped_at")
        if isinstance(scraped_at_raw, datetime):
            scraped_at = scraped_at_raw
        elif isinstance(scraped_at_raw, str):
            scraped_at = datetime.fromisoformat(scraped_at_raw.replace("Z", "+00:00"))
        else:
            scraped_at = datetime.now(timezone.utc)

        # Construct and validate frozen ScrapedProblem
        return ScrapedProblem(
            slug=raw_slug,
            title=clean_title,
            number=number,
            difficulty=difficulty,
            description=clean_description,
            constraints=clean_constraints,
            examples=clean_examples,
            tags=clean_tags,
            accepted_code=clean_code,
            code_language=code_lang,
            scraped_at=scraped_at,
        )

    def standardize_title_and_number(self, raw_number: Any, raw_title: str) -> Tuple[int, str]:
        """Strips HTML, extracts problem number prefix if embedded in title, cleans spaces."""
        text = html.unescape(raw_title)
        text = re.sub(r"<[^>]+>", "", text).strip()

        # Check for title like "1. Two Sum"
        match = re.match(r"^(\d+)\s*\.\s*(.+)$", text)
        if match:
            num_from_title = int(match.group(1))
            title_str = match.group(2).strip()
            number = num_from_title if (not raw_number or raw_number <= 0) else int(raw_number)
            return number, title_str

        number = int(raw_number) if raw_number else 0
        return number, text

    def clean_html_description(self, html_text: str) -> str:
        """Converts raw HTML description into clean Markdown while preserving code indentation."""
        if not html_text:
            return ""

        # Unescape HTML entities
        text = html.unescape(html_text)

        # Remove <script> and <style> blocks
        text = re.sub(r"<script.*?>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style.*?>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

        # Pre/Code blocks
        text = re.sub(r"<pre>\s*<code>(.*?)</code>\s*</pre>", r"\n```\n\1\n```\n", text, flags=re.DOTALL)
        text = re.sub(r"<pre>(.*?)</pre>", r"\n```\n\1\n```\n", text, flags=re.DOTALL)
        text = re.sub(r"<code>(.*?)</code>", r"`\1`", text, flags=re.DOTALL)

        # Typography
        text = re.sub(r"<strong>(.*?)</strong>", r"**\1**", text, flags=re.DOTALL)
        text = re.sub(r"<b>(.*?)</b>", r"**\1**", text, flags=re.DOTALL)
        text = re.sub(r"<em>(.*?)</em>", r"*\1*", text, flags=re.DOTALL)
        text = re.sub(r"<i>(.*?)</i>", r"*\1*", text, flags=re.DOTALL)

        # Math scripts
        text = re.sub(r"<sup>(.*?)</sup>", r"^\1", text)
        text = re.sub(r"<sub>(.*?)</sub>", r"_\1", text)

        # Lists & Paragraphs
        text = re.sub(r"<li>(.*?)</li>", r"- \1\n", text, flags=re.DOTALL)
        text = re.sub(r"<p>(.*?)</p>", r"\1\n\n", text, flags=re.DOTALL)
        text = re.sub(r"<br\s*/?>", r"\n", text)

        # Strip remaining tags
        text = re.sub(r"<[^>]+>", "", text)

        # Whitespace normalization (preserving code blocks)
        return self._normalize_whitespace_preserve_code(text)

    def _normalize_whitespace_preserve_code(self, text: str) -> str:
        """Normalizes spaces outside code blocks, preserves exact indentation inside ``` blocks."""
        parts = re.split(r"(```.*?```)", text, flags=re.DOTALL)
        cleaned_parts = []
        for part in parts:
            if part.startswith("```"):
                # Inside code block
                lines = part.splitlines()
                cleaned_lines = [line.rstrip() for line in lines]
                cleaned_parts.append("\n".join(cleaned_lines))
            else:
                # Narrative text
                clean_part = re.sub(r"[ \t]+", " ", part)
                clean_part = re.sub(r"\n{3,}", "\n\n", clean_part)
                cleaned_parts.append(clean_part)

        res = "".join(cleaned_parts).strip()
        return res

    def sanitize_constraints(self, constraints: Any) -> List[str]:
        """Cleans constraint strings and unescapes mathematical symbols."""
        if not constraints:
            return []

        if isinstance(constraints, str):
            constraints = [c for c in constraints.split("\n") if c.strip()]

        cleaned = []
        for item in constraints:
            c_str = html.unescape(str(item))
            c_str = re.sub(r"<[^>]+>", "", c_str)
            c_str = c_str.replace("&le;", "<=").replace("&ge;", ">=")
            c_str = re.sub(r"\s+", " ", c_str).strip()
            # Strip bullet prefix if present
            c_str = re.sub(r"^[\*\-\•]\s*", "", c_str)
            if c_str:
                cleaned.append(c_str)

        return cleaned

    def sanitize_tags(self, tags: Any) -> List[str]:
        """Standardizes tags: trimmed, lowercased, deduplicated."""
        if not tags:
            return []

        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        cleaned = []
        for t in tags:
            tag_str = html.unescape(str(t))
            tag_str = re.sub(r"<[^>]+>", "", tag_str).strip().lower()
            tag_str = re.sub(r"\s+", "-", tag_str)
            if tag_str and tag_str not in cleaned:
                cleaned.append(tag_str)

        return cleaned

    def sanitize_examples(self, raw_examples: Any, clean_description: str) -> List[Example]:
        """Formats example test cases into Example dataclasses."""
        examples: List[Example] = []

        # Case A: Provided as structured dicts/objects
        if isinstance(raw_examples, list) and raw_examples:
            for ex in raw_examples:
                if isinstance(ex, Example):
                    examples.append(ex)
                elif isinstance(ex, dict):
                    inp = self._clean_example_field(str(ex.get("input", "")))
                    out = self._clean_example_field(str(ex.get("output", "")))
                    exp = ex.get("explanation")
                    exp_clean = self._clean_example_field(str(exp)) if exp else None
                    if inp and out:
                        examples.append(Example(input=inp, output=out, explanation=exp_clean))

        # Case B: Fallback - Extract examples from clean description Markdown
        if not examples and clean_description:
            examples = self._extract_examples_from_text(clean_description)

        if not examples:
            # Fallback dummy example to satisfy fail-fast non-empty validation if scraping was sparse
            self._logger.warning("No examples extracted from raw payload or description. Using fallback.")
            examples.append(Example(input="N/A", output="N/A", explanation="No example provided in source."))

        return examples

    def _clean_example_field(self, text: str) -> str:
        """Cleans whitespace inside example inputs/outputs."""
        text = html.unescape(text)
        text = re.sub(r"<[^>]+>", "", text).strip()
        text = re.sub(r"[ \t]+", " ", text)
        return text

    def _extract_examples_from_text(self, text: str) -> List[Example]:
        """Parses Example blocks from Markdown text (e.g. 'Example 1: Input: ... Output: ...')."""
        pattern = r"Example\s+\d+:\s*Input:\s*(.*?)\s*Output:\s*(.*?)(?=\s*Explanation:|\s*Example|\s*Constraints:|\Z)"
        matches = re.findall(pattern, text, flags=re.DOTALL | re.IGNORECASE)
        results = []
        for inp, out in matches:
            clean_in = self._clean_example_field(inp)
            clean_out = self._clean_example_field(out)
            if clean_in and clean_out:
                results.append(Example(input=clean_in, output=clean_out))
        return results

    def sanitize_code(self, code_text: str) -> str:
        """Standardizes C++ / solution code: converts tabs to spaces, standardizes line endings."""
        if not code_text:
            return ""

        text = html.unescape(code_text)
        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Expand tabs to 4 spaces
        text = text.expandtabs(4)
        # Strip trailing spaces on each line
        lines = [line.rstrip() for line in text.splitlines()]
        return "\n".join(lines).strip()
```

---

## 4. Immutability, Validation, and JSON Serialization

### 4.1 Frozen Dataclass Rules & Immutability Guarantees

All inter-module data objects (`ScrapedProblem`, `Example`) are declared with `@dataclass(frozen=True)`.

**Benefits:**
- **Thread Safety:** Immutability guarantees safe concurrent read access across asynchronous pipelines without lock contention.
- **Hashability:** Frozen dataclasses generate deterministic `__hash__` implementations (when fields are hashable or tuples), allowing them to be cached safely in memory or set operations.
- **No In-Place Mutation:** Prevents pipeline steps from accidentally modifying intermediate problem states.

---

### 4.2 Strict Validation Logic (`__post_init__`)

Validation occurs immediately upon object instantiation (`Fail Fast` principle):

1. **Type Verification:** Every field type is verified against its annotation (`isinstance(...)`). Raises `TypeError` if invalid.
2. **Slug Rule:** Must be lowercase kebab-case (`^[a-z0-9-]+$`).
3. **Number Rule:** Must be a positive integer (`number > 0`).
4. **Description & Code Rule:** Cannot be empty or whitespace-only.
5. **Examples Rule:** `examples` list cannot be empty. Each `Example` input and output cannot be empty.
6. **Code Language Rule:** `code_language` must belong to supported set (`{"cpp", "python", "java", "javascript", "c"}`).

---

### 4.3 JSON Round-Trip Serialization & Codecs

To support file-based caching under `data/scraped/{slug}.json`, domain models implement native `to_dict()` and `from_dict()` codecs:

```
Dataclass Object <---> Python dict <---> JSON File (data/scraped/{slug}.json)
```

- **`datetime` Handling:** Serialized as ISO 8601 string (`.isoformat()`). Deserialized via `datetime.fromisoformat()`.
- **`Enum` Handling:** Serialized as string value (`difficulty.value`). Deserialized via `Difficulty.from_str()`.
- **Indentation Standard:** 4 spaces for disk files (`json.dump(obj.to_dict(), f, indent=4)`).

---

## 5. Pipeline Integration Strategy

### 5.1 Integration with Connectors & Normalizers

`ProblemSanitizer` sits between the raw connectors (`LeetCodeConnector`, `RawContent`) and the downstream knowledge pipeline (`NormalizedDocument` / `ChromaRAGEngine`).

```
[LeetCode API / Raw Content]
            │
            ▼
   BaseSourceConnector (Raw Content Bytes/JSON)
            │
            ▼
    ProblemSanitizer (Sanitizes & Validates)
            │
            ▼
   ScrapedProblem (Frozen Dataclass)
       ┌────┴────────────────────────┬────────────────────────┐
       ▼                             ▼                        ▼
ProblemNormalizer             TagExplorer              ChromaRAGEngine
(Markdown Document)         (Gemini Tag Enriched)     (RAG Index & Context)
```

---

### 5.2 Downstream Contracts (RAG, Tag Explorer, Script Generator)

1. **Tag Explorer (`src/tags/`):** Accepts `ScrapedProblem` -> extracts `tags`, `title`, and `description` to infer pattern families and animation styles.
2. **RAG Knowledge Engine (`src/rag/`):** Accepts `ScrapedProblem` -> queries ChromaDB using `slug`, `title`, and `tags` to retrieve pedagogical context (`RAGContext`).
3. **Script Generator (`src/script/`):** Consumes `ScrapedProblem`, `TagKnowledge`, and `RAGContext` to generate structured JSON video scripts (`VideoScript`).

---

## 6. Testing Strategy & Edge Case Matrix

### Edge Case Coverage Matrix:

| Category | Input Scenario | Expected Sanitizer Behavior |
|---|---|---|
| **HTML Entities** | `"Input: &quot;hello&quot;, &lt;b&gt;tag&lt;/b&gt;"` | Unescapes to `"Input: \"hello\", **tag**"`. |
| **Code Indentation** | C++ code with 4 spaces inside `<pre><code>` | Preserves 4-space indentation; strips trailing line spaces. |
| **Title Parsing** | `"1. Two Sum"` or `"15. 3Sum"` | Extracts `number=1`, `title="Two Sum"` (or `number=15`, `title="3Sum"`). |
| **Difficulty Mapping**| `"easy"`, `"EASY"`, `"1"` | Standardizes to `Difficulty.EASY`. Invalid string raises `ValueError`. |
| **Tag Normalization** | `[" Array ", "Hash Table", "array"]` | Trims, lowercases, deduplicates to `["array", "hash-table"]`. |
| **Empty Payload** | `{}` or `description=""` | Raises `ValueError` or `TypeError` immediately during validation. |
| **JSON Roundtrip** | Dataclass -> dict -> JSON -> dict -> Dataclass | Exact equality check succeeds; `scraped_at` preserves UTC timezone. |

### Unit Test Plan (`tests/test_models/test_problem.py` & `tests/test_ingestion/test_sanitizer.py`):
1. `test_problem_dataclass_immutability()`: Verifies modifying `scraped_problem.title = "X"` raises `FrozenInstanceError`.
2. `test_problem_validation_fail_fast()`: Verifies negative problem numbers, empty slugs, or empty example lists raise `ValueError`.
3. `test_problem_json_roundtrip()`: Verifies `ScrapedProblem.from_dict(obj.to_dict()) == obj`.
4. `test_sanitizer_html_cleaning()`: Verifies tag stripping and markdown entity conversion.
5. `test_sanitizer_code_indentation_preservation()`: Verifies C++ solution code indentation remains untouched.
