# 03_Project_Standards.md — Engineering Standards

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Target Environment:** Intel Core Ultra 7 155H · Ubuntu 25.10 LTS · Python 3.12 · Intel Arc GPU  
**Document Version:** 1.0.0  
**Last Updated:** July 2026  
**Status:** Canonical — Every source file MUST comply with this document.

---

## Table of Contents

1. [Python Style Guide](#1-python-style-guide)
2. [Naming Conventions](#2-naming-conventions)
3. [Constants & Enums](#3-constants--enums)
4. [Dataclasses](#4-dataclasses)
5. [Type Hints](#5-type-hints)
6. [Imports](#6-imports)
7. [Dependency Injection](#7-dependency-injection)
8. [Error Handling](#8-error-handling)
9. [Logging](#9-logging)
10. [Configuration](#10-configuration)
11. [Testing](#11-testing)
12. [Docstrings](#12-docstrings)
13. [Comments](#13-comments)
14. [Performance Guidelines](#14-performance-guidelines)
15. [Memory Guidelines](#15-memory-guidelines)
16. [Code Review Checklist](#16-code-review-checklist)
17. [Security Checklist](#17-security-checklist)
18. [Forbidden Practices](#18-forbidden-practices)
19. [Required Practices](#19-required-practices)

---

## 1. Python Style Guide

### 1.1 Baseline

All code follows **PEP 8** as the baseline, with the project-specific extensions and clarifications documented below. Where this document and PEP 8 conflict, this document takes precedence.

### 1.2 Python Version

- **Target:** Python 3.12 exclusively.
- Use modern syntax features: `match` statements, `type` aliases (PEP 695), `X | Y` union syntax, `Self` type, f-string improvements.
- Do not write backward-compatible code for Python 3.11 or earlier.

### 1.3 Line Length

- **Maximum line length:** 99 characters for code.
- **Maximum line length:** 79 characters for docstrings and comments.
- **Exception:** URLs in comments/docstrings may exceed the limit. Do not break URLs across lines.

### 1.4 Indentation

- **4 spaces.** Never tabs.
- Continuation lines use 4-space hanging indent:

```python
# YES
result = some_function(
    argument_one,
    argument_two,
    argument_three,
)

# NO
result = some_function(argument_one,
                       argument_two,
                       argument_three)
```

### 1.5 Trailing Commas

- **Always** use trailing commas in multi-line structures (function arguments, list/dict/set literals, dataclass fields, import lists).
- Trailing commas produce cleaner diffs and prevent merge conflicts.

```python
# YES
names = [
    "scraper",
    "tags",
    "rag",
]

# NO
names = [
    "scraper",
    "tags",
    "rag"
]
```

### 1.6 Quotes

- **Double quotes** (`"..."`) for all strings.
- **Single quotes** (`'...'`) only inside f-strings or when the string itself contains double quotes.
- **Triple double quotes** (`"""..."""`) for all docstrings.

```python
# YES
message = "Pipeline completed"
query = f"SELECT * FROM memory WHERE slug = '{slug}'"
html = 'She said "hello"'

# NO
message = 'Pipeline completed'
```

### 1.7 Blank Lines

| Context | Blank Lines |
|---|---|
| Between top-level definitions (class, function) | 2 |
| Between methods inside a class | 1 |
| Between logical sections inside a function | 1 |
| After a class docstring | 0 (first method immediately follows) |
| After a module docstring | 1 |
| Before `return` at end of function | 0 (no gratuitous blank before return) |

### 1.8 String Formatting

- **f-strings** for all runtime string interpolation. No `.format()`, no `%` formatting.
- Exception: Logging messages use lazy formatting via `structlog` keyword args (see Section 9).

```python
# YES
path = f"data/scraped/{slug}.json"

# NO
path = "data/scraped/{}.json".format(slug)
path = "data/scraped/%s.json" % slug
```

### 1.9 Comparison Operators

```python
# Identity checks (singletons)
if value is None:       # YES
if value is not None:   # YES
if value == None:       # FORBIDDEN

# Boolean checks
if is_valid:            # YES
if not is_valid:        # YES
if is_valid == True:    # FORBIDDEN
if is_valid is True:    # FORBIDDEN (except for tri-state sentinel)

# Empty collection checks
if not items:           # YES (falsy check for empty list/dict/set)
if len(items) == 0:     # NO
```

### 1.10 Comprehensions

- Use comprehensions for simple transformations (one condition, one expression).
- **Never** nest comprehensions. Use a loop or extract a helper function.
- If a comprehension exceeds one line of logic, use an explicit loop.

```python
# YES — simple transformation
slugs = [p.slug for p in problems]

# YES — single filter
hard_problems = [p for p in problems if p.difficulty == Difficulty.HARD]

# NO — nested comprehension
# matrix = [[row[i] for row in data] for i in range(cols)]
# Instead: write a function.
```

### 1.11 Context Managers

- Use `with` statements for all resource management: files, database connections, HTTP sessions, locks.
- Implement `__enter__`/`__exit__` or use `@contextmanager` for custom resource wrappers.

```python
# YES
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# FORBIDDEN
f = open(path, "r")
content = f.read()
f.close()
```

### 1.12 Walrus Operator

- Permitted for `while` loops and `if` guards where it improves clarity.
- **Never** use inside comprehensions or deeply nested expressions.

```python
# YES
if (match := SLUG_PATTERN.match(url)) is not None:
    slug = match.group("slug")

# NO — too dense
results = [y for x in data if (y := transform(x)) is not None]
```

---

## 2. Naming Conventions

### 2.1 Folder Naming

| Scope | Convention | Examples |
|---|---|---|
| Source packages | `snake_case`, singular nouns | `src/scraper/`, `src/voice/`, `src/assembly/` |
| Sub-packages | `snake_case`, descriptive | `src/animation/scenes/` |
| Test packages | `test_` prefix + module name | `tests/test_scraper/`, `tests/test_voice/` |
| Data directories | `snake_case`, descriptive | `data/knowledge_base/`, `data/vector_store/` |
| Config directory | `config/` (singular) | `config/` |
| Prompt book | `PascalCase` (established convention) | `PromptBook/` |

**Rules:**
- All source package directories contain an `__init__.py`.
- No hyphens in Python package names. Hyphens are reserved for the project root folder.
- No uppercase letters in source package names.
- Maximum directory nesting depth: 3 levels under `src/` (e.g., `src/animation/scenes/`).

### 2.2 Module (File) Naming

| Category | Convention | Examples |
|---|---|---|
| Implementation modules | `snake_case.py`, noun or verb-noun | `scraper.py`, `client.py`, `parser.py` |
| Model modules | `snake_case.py`, domain noun | `problem.py`, `script.py`, `memory.py` |
| Utility modules | `snake_case.py`, `_utils` suffix if generic | `audio_utils.py`, `ffmpeg_commands.py` |
| Protocol definitions | `protocols.py` (one file, all protocols) | `src/models/protocols.py` |
| Exception definitions | `exceptions.py` (one file, all exceptions) | `src/core/exceptions.py` |
| Constants/Enums | `enums.py` for enums, inline for constants | `src/models/enums.py` |
| Test modules | `test_` prefix + target module name | `test_scraper.py`, `test_client.py` |
| Conftest | `conftest.py` (pytest convention) | `tests/conftest.py` |

**Rules:**
- One primary class per module. The module name matches the class concept.
  - `scraper.py` → contains `LeetCodeScraper`.
  - `engine.py` → contains `ChromaRAGEngine`.
- Helper/private classes may coexist in the same module if tightly coupled to the primary class.
- **Maximum file length: 400 lines.** If a file exceeds 400 lines, split it into cohesive sub-modules.

### 2.3 Class Naming

| Category | Convention | Examples |
|---|---|---|
| Concrete implementation classes | `PascalCase`, descriptive noun | `LeetCodeScraper`, `ChromaRAGEngine`, `KokoroVoiceSynthesizer` |
| Protocol interfaces | `PascalCase` + `Protocol` suffix | `ScraperProtocol`, `VoiceSynthesizerProtocol` |
| Dataclasses (models) | `PascalCase`, domain noun | `ScrapedProblem`, `VideoScript`, `MemoryRecord` |
| Enums | `PascalCase`, domain noun | `Difficulty`, `SectionType`, `PipelineStatus` |
| Exceptions | `PascalCase` + `Error` suffix | `ScraperError`, `AuthenticationError`, `RateLimitError` |
| Test classes | `Test` prefix + target class | `TestLeetCodeScraper`, `TestPipelineOrchestrator` |
| Private/internal classes | `_` prefix + `PascalCase` | `_GraphQLPayloadBuilder` |

**Rules:**
- Class names are always **nouns or noun phrases**, never verbs.
- Implementation class names encode both the *technology* and the *role*:
  - `LeetCodeScraper` (not just `Scraper`).
  - `GeminiScriptGenerator` (not just `ScriptGenerator`).
  - `FFmpegVideoAssembler` (not just `Assembler`).
- Protocol names encode only the *role* + `Protocol`:
  - `ScraperProtocol` (not `LeetCodeScraperProtocol`).
- No `Base`, `Abstract`, `Interface`, `Manager`, `Handler`, `Helper`, or `Util` suffixes on classes.

### 2.4 Function & Method Naming

| Category | Convention | Examples |
|---|---|---|
| Public methods | `snake_case`, verb or verb-noun | `scrape()`, `generate()`, `render()`, `upload()` |
| Private methods | `_snake_case`, `_` prefix | `_build_query()`, `_normalize_audio()` |
| Boolean-returning methods | `is_`, `has_`, `can_`, `should_` prefix | `is_valid()`, `has_been_generated()`, `can_retry()` |
| Factory methods | `create_` or `from_` prefix | `create_config()`, `from_json()` |
| Conversion methods | `to_` prefix | `to_dict()`, `to_json()` |
| Getter-style (no side effects) | `get_` prefix | `get_record()`, `get_all_tags()` |
| Test functions | `test_` prefix, descriptive | `test_scrape_returns_problem_for_valid_slug()` |
| Fixtures | `snake_case`, noun describing the fixture | `sample_problem()`, `mock_gemini_client()` |

**Rules:**
- Public module API methods are verbs: `scrape`, `explore`, `retrieve`, `generate`, `synthesize`, `render`, `assemble`, `upload`, `save`.
- Methods do one thing. If a method name contains `and`, split it.
- Maximum **4 parameters** per function (excluding `self`). If more are needed, group parameters into a config dataclass.
- Never use single-letter parameter names except:
  - `i`, `j`, `k` for loop indices (when semantically clear).
  - `n` for counts.
  - `k` for top-k retrieval.
  - `T` for generic type variables.

### 2.5 Variable Naming

| Category | Convention | Examples |
|---|---|---|
| Local variables | `snake_case`, descriptive | `scraped_problem`, `tag_knowledge`, `audio_path` |
| Loop variables | `snake_case`, meaningful noun | `for section in sections:`, `for chunk in chunks:` |
| Boolean variables | `is_`, `has_`, `should_` prefix | `is_cached`, `has_audio`, `should_upload` |
| Private instance attrs | `self._snake_case` | `self._config`, `self._logger`, `self._client` |
| Constants (module-level) | `UPPER_SNAKE_CASE` | `MAX_RETRIES`, `DEFAULT_CHUNK_SIZE` |
| Type aliases | `PascalCase` | `SectionMap = dict[str, ScriptSection]` |

**Rules:**
- Variable names communicate intent, not type. Name what it *is*, not what type it holds:
  - `problems` (not `problem_list`).
  - `slug` (not `slug_str`).
  - `retry_count` (not `retry_int`).
- Minimum 3 characters for non-index variables. No `x`, `d`, `s`, `p` as variable names.
- Avoid abbreviations unless universally understood:
  - Allowed: `config`, `db`, `url`, `api`, `id`, `fps`, `tts`, `rag`, `seo`.
  - Forbidden: `mgr`, `proc`, `req`, `resp`, `desc`, `btn`, `func`, `val`.

### 2.6 Naming Consistency Table

This table is the canonical reference. All names in the codebase must follow these exact patterns:

| What | Pattern | Example |
|---|---|---|
| Package | `snake_case/` | `src/scraper/` |
| Module file | `snake_case.py` | `scraper.py` |
| Class | `PascalCase` | `LeetCodeScraper` |
| Protocol | `PascalCase` + `Protocol` | `ScraperProtocol` |
| Dataclass | `PascalCase` | `ScrapedProblem` |
| Enum | `PascalCase` | `Difficulty` |
| Enum member | `UPPER_SNAKE_CASE` | `Difficulty.HARD` |
| Exception | `PascalCase` + `Error` | `ScraperError` |
| Function/method | `snake_case` | `scrape()` |
| Variable | `snake_case` | `scraped_problem` |
| Constant | `UPPER_SNAKE_CASE` | `MAX_RETRIES` |
| Type alias | `PascalCase` | `SectionMap` |
| Test function | `test_snake_case` | `test_scrape_valid_slug()` |
| Test class | `TestPascalCase` | `TestLeetCodeScraper` |
| Fixture | `snake_case` | `sample_problem` |
| Private attribute | `_snake_case` | `self._config` |
| Private method | `_snake_case` | `self._build_query()` |
| Dunder method | `__snake_case__` | `__init__`, `__repr__` |

---

## 3. Constants & Enums

### 3.1 Constants

- Define at **module level** in the file where they are used, or in a shared `constants.py` if used by multiple files within the same package.
- Never define cross-package constants. If a value is needed by multiple packages, it belongs in `src/core/` or `src/models/`.
- All constants are `UPPER_SNAKE_CASE`.
- All constants are annotated with a type hint.
- All constants have a trailing comment explaining their purpose if the name is not self-documenting.

```python
# YES
MAX_RETRIES: int = 3
DEFAULT_CHUNK_SIZE: int = 512
LEETCODE_GRAPHQL_URL: str = "https://leetcode.com/graphql"
SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"cpp", "python", "java"})

# NO — magic numbers inline
if attempt > 3:  # What is 3?
    raise RateLimitError(...)
```

**Rules:**
- **No magic numbers.** Every numeric literal used in logic must be assigned to a named constant or come from configuration.
- **No magic strings.** Repeated string literals (API endpoints, file extensions, default values) must be constants.
- Use `frozenset` for constant sets, `tuple` for constant sequences. Never use mutable `list` or `set` for module-level constants.

### 3.2 Enums

- All enums inherit from `enum.Enum` (or `enum.StrEnum` for string-valued enums).
- Enum members are `UPPER_SNAKE_CASE`.
- All enums are defined in `src/models/enums.py` unless exclusively used within a single module.
- Every enum has a docstring.
- Enums are never compared with `==` against raw strings. Always compare enum against enum.

```python
# src/models/enums.py

class Difficulty(StrEnum):
    """LeetCode problem difficulty levels."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class SectionType(StrEnum):
    """Video script section categories."""

    HOOK = "hook"
    PROBLEM_STATEMENT = "problem_statement"
    CONSTRAINTS = "constraints"
    BRUTE_FORCE = "brute_force"
    OPTIMIZED_APPROACH = "optimized_approach"
    VISUAL_WALKTHROUGH = "visual_walkthrough"
    DRY_RUN = "dry_run"
    CODE_WALKTHROUGH = "code_walkthrough"
    COMPLEXITY_ANALYSIS = "complexity_analysis"
    CLOSING = "closing"


class PipelineStatus(StrEnum):
    """Pipeline execution result states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"


class AnimationStyle(StrEnum):
    """Visual animation style categories for Manim scenes."""

    ARRAY_TRAVERSAL = "array_traversal"
    LINKED_LIST = "linked_list"
    TREE_RECURSION = "tree_recursion"
    GRAPH_BFS = "graph_bfs"
    GRAPH_DFS = "graph_dfs"
    HASH_MAP = "hash_map"
    STACK_QUEUE = "stack_queue"
    TWO_POINTERS = "two_pointers"
    SLIDING_WINDOW = "sliding_window"
    DYNAMIC_PROGRAMMING = "dynamic_programming"
    CODE_HIGHLIGHT = "code_highlight"
    COMPLEXITY_CHART = "complexity_chart"
```

```python
# YES — compare enum to enum
if problem.difficulty == Difficulty.HARD:

# FORBIDDEN — compare enum to string
if problem.difficulty == "hard":
```

---

## 4. Dataclasses

### 4.1 General Rules

- All inter-module data transfer objects are `@dataclass(frozen=True)`.
- Module-internal mutable state may use `@dataclass` without `frozen` only if mutation is genuinely required during construction.
- All fields have explicit type annotations.
- All fields are ordered: required fields first, optional/defaulted fields last.
- No mutable default values. Use `field(default_factory=list)` for collections.

### 4.2 Frozen Dataclasses (Inter-Module Contracts)

```python
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class ScrapedProblem:
    """Complete metadata and solution for a scraped LeetCode problem.

    This is the output contract of the Scraper module and the primary
    input to the Tag Explorer, RAG Engine, and Script Generator.
    """

    slug: str
    title: str
    number: int
    difficulty: Difficulty
    description: str
    constraints: list[str]
    examples: list[Example]
    tags: list[str]
    accepted_code: str
    code_language: str
    scraped_at: datetime
```

**Rules:**
- `frozen=True` for every dataclass that leaves a module boundary (appears in a Protocol method signature).
- `frozen=True` dataclasses must not contain mutable containers that could be mutated externally. Use defensive copying in the factory/`__post_init__` if needed, or document that consumers must not mutate inner lists.
- `slots=True` may be added for performance-critical dataclasses (reduces memory footprint).
- `eq=True` (default) is kept so dataclass equality works for testing assertions.
- Never override `__init__` on a dataclass. Use `__post_init__` for validation.

### 4.3 `__post_init__` for Validation

Use `__post_init__` exclusively for invariant enforcement, never for complex logic:

```python
@dataclass(frozen=True)
class SectionAudio:
    """Audio output for a single script section."""

    section_id: str
    audio_path: Path
    duration_seconds: float
    word_count: int

    def __post_init__(self) -> None:
        if self.duration_seconds <= 0:
            raise ValueError(
                f"duration_seconds must be positive, got {self.duration_seconds}"
            )
        if self.word_count < 0:
            raise ValueError(
                f"word_count must be non-negative, got {self.word_count}"
            )
```

### 4.4 Dataclass Serialization

- All dataclasses are serialized/deserialized through `src/core/serialization.py`.
- Dataclasses never implement their own `to_json()` / `from_json()` methods.
- Serialization converts `datetime` → ISO 8601 string, `Path` → POSIX string, `Enum` → `.value`.
- Serialization must be round-trip safe.

### 4.5 Dataclass Placement

| Dataclass Type | Location |
|---|---|
| Inter-module contracts (`ScrapedProblem`, `VideoScript`, etc.) | `src/models/{domain}.py` |
| Configuration dataclasses (`ScraperConfig`, `RAGConfig`, etc.) | `src/core/config.py` |
| Module-internal data structures | Inside the module's own package |
| Test fixtures / builders | `tests/conftest.py` or `tests/factories.py` |

---

## 5. Type Hints

### 5.1 Coverage Requirement

- **100% type annotation coverage** on all public and private functions, methods, and class attributes.
- Every function signature has fully typed parameters and a return type.
- Every class attribute and instance variable has a type annotation.
- `mypy --strict` must pass with zero errors.

### 5.2 Syntax

Use modern Python 3.12 syntax:

```python
# YES — Modern syntax (Python 3.10+)
def process(items: list[str]) -> dict[str, int]: ...
def find(slug: str) -> ScrapedProblem | None: ...
def get_tags() -> set[str]: ...

# NO — Legacy syntax
from typing import List, Dict, Optional, Set
def process(items: List[str]) -> Dict[str, int]: ...
def find(slug: str) -> Optional[ScrapedProblem]: ...
```

### 5.3 Common Patterns

```python
from typing import Any, Protocol, runtime_checkable, Self
from collections.abc import Sequence, Mapping, Iterator, Callable
from pathlib import Path

# Union types — use pipe syntax
value: str | int
result: ScrapedProblem | None

# Callable types
callback: Callable[[str, int], bool]
transform: Callable[..., VideoScript]

# Collection types — use lowercase builtins
items: list[str]
mapping: dict[str, int]
unique: set[str]
immutable: tuple[str, ...]
frozen: frozenset[str]

# Abstract collection types — for function parameters
def process(items: Sequence[str]) -> None: ...       # Accept list, tuple, etc.
def lookup(data: Mapping[str, int]) -> None: ...     # Accept dict, etc.

# Self type — for fluent interfaces and classmethods
@classmethod
def from_json(cls, path: Path) -> Self: ...

# TypeVar for generic functions
from typing import TypeVar
T = TypeVar("T")
def deserialize(path: Path, cls: type[T]) -> T: ...
```

### 5.4 When to Use `Any`

`Any` is permitted **only** in these cases:

1. **`visual_params: dict[str, Any]`** in `ScriptSection` — intentionally dynamic structure driven by LLM output.
2. **JSON serialization internals** — `json.loads()` returns `Any`.
3. **Third-party library interop** — when a library does not provide type stubs.

Every use of `Any` must have a comment justifying why a more specific type is not possible.

### 5.5 Protocols and `@runtime_checkable`

- All module protocols are `@runtime_checkable` (see `02_Project_Architecture.md`, Section 7).
- Protocol methods have full type annotations including return types.
- Protocol methods do not have method bodies beyond `...` (Ellipsis).

```python
@runtime_checkable
class ScraperProtocol(Protocol):
    def scrape(self, slug: str) -> ScrapedProblem: ...
```

### 5.6 Type Alias Conventions

```python
# Module-level type aliases — PascalCase
SectionMap = dict[str, ScriptSection]
ChunkList = list[RetrievedChunk]
TagSet = set[str]
```

---

## 6. Imports

### 6.1 Import Order

Imports are grouped in this exact order, with a blank line between each group:

```python
# Group 1: Standard library
import json
import logging
from datetime import datetime
from pathlib import Path

# Group 2: Third-party packages
import structlog
from chromadb import PersistentClient

# Group 3: Local — models and core (shared vocabulary)
from src.models.problem import ScrapedProblem
from src.models.enums import Difficulty
from src.core.config import ScraperConfig
from src.core.exceptions import ScraperError

# Group 4: Local — same package (relative imports)
from .client import LeetCodeClient
from .parser import ResponseParser
```

### 6.2 Import Style

```python
# YES — explicit named imports
from pathlib import Path
from datetime import datetime
from src.models.problem import ScrapedProblem

# YES — module import when using multiple names from it
import json
data = json.loads(content)

# NO — wildcard imports (FORBIDDEN)
from src.models import *

# NO — deep aliasing that hides origin
from src.models.problem import ScrapedProblem as SP
```

### 6.3 Import Rules

1. **No circular imports.** The dependency graph in `02_Project_Architecture.md`, Section 4.2 is enforced at import time. If you encounter a circular import, you have a design error.

2. **No cross-module imports.** Pipeline modules (`src/scraper/`, `src/tags/`, etc.) never import from each other. They import only from `src/models/` and `src/core/`.

3. **Relative imports within a package.** Files within the same package use relative imports:
   ```python
   # Inside src/scraper/scraper.py
   from .client import LeetCodeClient    # YES — relative
   from src.scraper.client import ...    # NO — absolute to own package
   ```

4. **Absolute imports across packages.** Files referencing other packages use absolute imports:
   ```python
   # Inside src/scraper/scraper.py
   from src.models.problem import ScrapedProblem    # YES — absolute
   from src.core.exceptions import ScraperError     # YES — absolute
   ```

5. **No import side effects.** Importing a module must not execute any logic, make network calls, or write files. All initialization happens explicitly via constructors or factory functions.

6. **`isort` profile.** Use `isort` with `profile = "black"` and `known_first_party = ["src"]`.

### 6.4 Forbidden Imports

| Import | Why |
|---|---|
| `from typing import List, Dict, Set, Tuple, Optional` | Use built-in generics and `X \| Y` syntax |
| `import os` for path manipulation | Use `pathlib.Path` |
| `import os.path` | Use `pathlib.Path` |
| `import glob` | Use `pathlib.Path.glob()` |
| `from unittest import *` | Use `pytest` exclusively |
| Any import from one pipeline module to another | Violates module independence |

---

## 7. Dependency Injection

### 7.1 Constructor Injection Only

All dependencies are injected through `__init__` parameters. No property injection, no setter injection, no service locators.

```python
class LeetCodeScraper:
    """Scrapes LeetCode problems via GraphQL API.

    Implements ScraperProtocol.
    """

    def __init__(
        self,
        config: ScraperConfig,
        logger: structlog.BoundLogger,
    ) -> None:
        self._config = config
        self._logger = logger
        self._client = LeetCodeClient(
            session_cookie=config.session_cookie,
            timeout=config.timeout_seconds,
        )
```

### 7.2 Rules

1. **Depend on protocols, not implementations.**
   ```python
   # YES — in orchestrator
   def __init__(self, scraper: ScraperProtocol) -> None:

   # NO
   def __init__(self, scraper: LeetCodeScraper) -> None:
   ```

2. **Store injected dependencies as private attributes.**
   ```python
   self._config = config    # YES
   self.config = config     # NO — exposes internal dependency
   ```

3. **One composition root.** Only `src/__main__.py` instantiates concrete classes and wires them together. All other files depend only on abstractions.

4. **No default values for injected dependencies.** Dependencies are always explicitly provided:
   ```python
   # YES
   def __init__(self, logger: structlog.BoundLogger) -> None:

   # NO — hidden dependency
   def __init__(self, logger: structlog.BoundLogger = get_logger()) -> None:
   ```

5. **No runtime `isinstance` checks inside module logic.** The Protocol guarantees are enforced at the composition root, not inside each method call.

### 7.3 Testing with DI

Tests inject fakes/stubs/mocks that satisfy the same Protocol:

```python
class FakeScraper:
    """Test double for ScraperProtocol."""

    def scrape(self, slug: str) -> ScrapedProblem:
        return ScrapedProblem(
            slug=slug,
            title=f"Test Problem: {slug}",
            number=1,
            difficulty=Difficulty.EASY,
            description="Test description",
            constraints=["1 <= n <= 100"],
            examples=[],
            tags=["Array"],
            accepted_code="int main() {}",
            code_language="cpp",
            scraped_at=datetime.utcnow(),
        )
```

---

## 8. Error Handling

### 8.1 Exception Hierarchy

All custom exceptions are defined in `src/core/exceptions.py` and inherit from `PipelineError`. See `02_Project_Architecture.md`, Section 10.1 for the full hierarchy.

### 8.2 Rules

1. **Catch specific, raise specific.**
   ```python
   # YES
   try:
       response = self._client.fetch(slug)
   except httpx.TimeoutException as exc:
       raise ScraperError(
           f"Timeout scraping '{slug}' after {self._config.timeout_seconds}s"
       ) from exc

   # FORBIDDEN
   try:
       response = self._client.fetch(slug)
   except Exception:
       pass
   ```

2. **Always chain exceptions with `from`.**
   ```python
   raise ScraperError("message") from original_exception
   ```

3. **Actionable error messages.** Every exception message answers three questions:
   - *What* failed?
   - *Why* did it likely fail?
   - *What* should the user do?

   ```python
   raise AuthenticationError(
       "LeetCode session cookie is expired or invalid. "
       "Update LEETCODE_SESSION in .env with a fresh cookie "
       "from your browser DevTools (Application → Cookies → LEETCODE_SESSION)."
   )
   ```

4. **No bare `except:`.**
   ```python
   # FORBIDDEN
   except:
       ...

   # FORBIDDEN
   except Exception:
       pass
   ```

5. **No `except Exception` with `pass` or `continue`.** If you catch a broad exception, you must log it and either re-raise or raise a domain exception.

6. **`finally` for cleanup only.** No logic, no return values, no variable assignments in `finally` blocks beyond resource cleanup.

7. **Validate inputs at module boundaries.** Public methods validate their arguments immediately and raise `ValueError` or a domain exception for invalid inputs. Do not let invalid data propagate.

   ```python
   def scrape(self, slug: str) -> ScrapedProblem:
       if not slug or not slug.strip():
           raise ValueError("slug must be a non-empty string")
       slug = slug.strip().lower()
       # ... proceed with valid slug
   ```

8. **Never use exceptions for control flow.** Exceptions are for *exceptional* situations. Use `if/else`, `Optional`, or sentinel values for expected conditions like cache misses.

### 8.3 Retry Pattern

Use the `@retry` decorator from `src/core/retry.py` for transient errors:

```python
from src.core.retry import retry

@retry(
    max_attempts=3,
    initial_delay=1.0,
    backoff_factor=2.0,
    retryable_exceptions=(RateLimitError, TimeoutError, ConnectionError),
)
def _fetch_graphql(self, query: str) -> dict[str, Any]:
    """Execute a GraphQL query against LeetCode's API."""
    ...
```

**Rules:**
- Only network I/O and external API calls are retryable.
- Local computation, file I/O, and configuration errors are never retried.
- Maximum retry count: 3 (configurable per module).
- Backoff strategy: exponential with jitter.
- All retry attempts are logged at `WARNING` level.

---

## 9. Logging

### 9.1 Logger Acquisition

Every module file creates its own logger:

```python
import structlog

logger = structlog.get_logger(__name__)
```

Or receives it via dependency injection (for classes):

```python
def __init__(self, logger: structlog.BoundLogger) -> None:
    self._logger = logger
```

### 9.2 Structured Logging Format

All log messages use structured keyword arguments, not string interpolation:

```python
# YES — structured context
self._logger.info(
    "Problem scraped successfully",
    slug=slug,
    difficulty=problem.difficulty.value,
    tag_count=len(problem.tags),
    elapsed_ms=elapsed_ms,
)

# NO — string interpolation in message
self._logger.info(f"Scraped {slug} with {len(tags)} tags in {elapsed_ms}ms")

# NO — .format() style
self._logger.info("Scraped %s with %d tags", slug, len(tags))
```

### 9.3 Log Level Guide

| Level | When to Use | Example |
|---|---|---|
| `DEBUG` | Internal variable values, algorithm steps, iteration details | `logger.debug("Chunk scored", chunk_idx=3, score=0.87)` |
| `INFO` | Module entry/exit, completed operations, timing | `logger.info("Scraping started", slug="two-sum")` |
| `WARNING` | Recoverable degradation, retries, cache miss, fallback | `logger.warning("Cache miss, fetching fresh", slug=slug)` |
| `ERROR` | Operation failed, non-fatal to pipeline (single section) | `logger.error("Section render failed", section_id="hook", error=str(e))` |
| `CRITICAL` | Pipeline cannot continue | `logger.critical("FFmpeg not found", path="/usr/bin/ffmpeg")` |

### 9.4 Rules

1. **Log at module boundaries.** Log at `INFO` level when entering and exiting each module's primary method.

2. **Log timing for external calls.** Every API call, subprocess invocation, and model inference records elapsed time:
   ```python
   start = time.perf_counter()
   result = self._client.fetch(slug)
   elapsed_ms = (time.perf_counter() - start) * 1000
   self._logger.info("GraphQL query completed", slug=slug, elapsed_ms=round(elapsed_ms, 1))
   ```

3. **Never log sensitive data.** API keys, session cookies, OAuth tokens, and file contents of secrets are never logged at any level. Log the *length* or *presence* of a secret if needed:
   ```python
   self._logger.info("Session cookie loaded", cookie_length=len(cookie))
   ```

4. **No logging inside tight loops.** If processing 1000 chunks, log the aggregate, not each iteration:
   ```python
   # YES
   self._logger.info("Embedding batch completed", chunk_count=len(chunks), elapsed_ms=elapsed)

   # NO
   for chunk in chunks:
       self._logger.debug("Embedding chunk", chunk_idx=i)  # 1000 log lines
   ```

5. **Pipeline run ID.** The orchestrator binds a `pipeline_run_id` to the logger context at startup. All downstream loggers inherit this binding via `structlog`'s context propagation:
   ```python
   logger = logger.bind(pipeline_run_id=f"run_{timestamp}_{slug}")
   ```

6. **No `print()` statements.** All output goes through `structlog`. The only permitted `print` is in CLI argument parsing for `--help` output.

---

## 10. Configuration

### 10.1 Rules

1. **Configuration is loaded once, at startup.** The `load_config()` function in `src/core/config.py` produces an immutable `PipelineConfig` dataclass. Modules receive their config slice through constructor injection.

2. **No module reads files, environment variables, or CLI args directly.** All configuration access goes through the injected config object:
   ```python
   # YES — injected config
   def __init__(self, config: ScraperConfig) -> None:
       self._timeout = config.timeout_seconds

   # FORBIDDEN — reading env directly
   import os
   timeout = int(os.getenv("SCRAPER_TIMEOUT", "30"))
   ```

3. **Secrets live in `.env` only.** API keys, session cookies, and OAuth secrets are never committed to YAML, JSON, or source code.

4. **Every config field has a sensible default.** The pipeline must start with `config/pipeline.yaml` missing entirely, using only defaults.

5. **Config is validated at load time.** Invalid values raise `ConfigurationError` immediately — not when first used.
   ```python
   if config.scraper.timeout_seconds <= 0:
       raise ConfigurationError(
           f"scraper.timeout_seconds must be positive, got {config.scraper.timeout_seconds}"
       )
   ```

6. **Config dataclasses are `frozen=True`.** No code modifies configuration after loading.

### 10.2 Config Dataclass Pattern

```python
@dataclass(frozen=True)
class ScraperConfig:
    """Configuration for the LeetCode scraper module."""

    session_cookie: str
    rate_limit_seconds: float = 2.0
    timeout_seconds: float = 30.0
    max_retries: int = 3
```

### 10.3 File Paths in Config

- All file paths in config are **relative to the project root**.
- The `src/core/paths.py` module provides a `resolve_path()` function that converts relative config paths to absolute `Path` objects based on a discovered project root.
- Modules never hardcode absolute paths.

```python
# src/core/paths.py
def resolve_path(relative: str) -> Path:
    """Resolve a config-relative path to an absolute Path."""
    return PROJECT_ROOT / relative
```

---

## 11. Testing

### 11.1 Framework & Structure

- **Framework:** `pytest` exclusively. No `unittest.TestCase` subclassing.
- **Test directory structure mirrors `src/`:**
  ```
  tests/
  ├── conftest.py
  ├── test_scraper/
  │   ├── conftest.py
  │   ├── test_scraper.py
  │   ├── test_client.py
  │   └── test_parser.py
  ├── test_tags/
  │   └── test_explorer.py
  ├── test_rag/
  │   ├── test_engine.py
  │   └── test_chunker.py
  └── ...
  ```

### 11.2 Test Naming

```python
# Test function names: test_{method}_{scenario}_{expected_outcome}
def test_scrape_returns_problem_for_valid_slug() -> None: ...
def test_scrape_raises_not_found_for_invalid_slug() -> None: ...
def test_scrape_retries_on_rate_limit() -> None: ...
def test_scrape_uses_cache_when_available() -> None: ...
```

- Names are descriptive sentences in `snake_case`.
- Names contain three parts: **what** is tested, **under what condition**, and **what is expected**.
- Never use numbered tests (`test_1`, `test_2`).

### 11.3 Test Organization: AAA Pattern

Every test follows the **Arrange → Act → Assert** pattern with clear visual separation:

```python
def test_scrape_returns_problem_for_valid_slug(
    mock_client: LeetCodeClient,
    sample_graphql_response: dict[str, Any],
) -> None:
    """Scraper returns a valid ScrapedProblem for a known slug."""
    # Arrange
    mock_client.fetch.return_value = sample_graphql_response
    scraper = LeetCodeScraper(config=test_config, logger=structlog.get_logger())

    # Act
    result = scraper.scrape("two-sum")

    # Assert
    assert result.slug == "two-sum"
    assert result.difficulty == Difficulty.EASY
    assert len(result.tags) > 0
    assert result.accepted_code != ""
```

### 11.4 Fixtures

- Shared fixtures live in `tests/conftest.py` (global) or `tests/test_{module}/conftest.py` (module-scoped).
- Fixtures return typed objects, never raw dicts.
- Factory fixtures return callables for parameterized creation:

```python
@pytest.fixture
def create_problem() -> Callable[..., ScrapedProblem]:
    """Factory fixture for creating ScrapedProblem instances."""
    def _create(
        slug: str = "two-sum",
        difficulty: Difficulty = Difficulty.EASY,
        **overrides: Any,
    ) -> ScrapedProblem:
        defaults = {
            "slug": slug,
            "title": f"Test: {slug}",
            "number": 1,
            "difficulty": difficulty,
            "description": "Test description",
            "constraints": ["1 <= n <= 100"],
            "examples": [],
            "tags": ["Array"],
            "accepted_code": "int main() {}",
            "code_language": "cpp",
            "scraped_at": datetime(2026, 7, 22),
        }
        defaults.update(overrides)
        return ScrapedProblem(**defaults)
    return _create
```

### 11.5 Mocking

1. **Prefer fakes over mocks.** Write simple fake classes that implement the Protocol, rather than using `unittest.mock.Mock` when possible.

2. **Mock at the boundary, not internally.** Mock external HTTP calls, API clients, and file I/O. Never mock private methods of the class under test.

3. **Use `unittest.mock.patch` only for external library calls** (e.g., `httpx.Client.post`, `subprocess.run`), not for internal module imports.

4. **Never mock the class you are testing.**

### 11.6 Coverage Requirements

| Scope | Minimum Coverage |
|---|---|
| `src/models/` | 100% (trivial dataclasses, but enforce completeness) |
| `src/core/` | 95% |
| `src/{module}/` | 90% per module |
| Overall project | 90% |

### 11.7 Test Types

| Type | Location | Scope | External Deps |
|---|---|---|---|
| Unit tests | `tests/test_{module}/test_{file}.py` | Single class/function | All mocked |
| Integration tests | `tests/test_{module}/test_{file}_integration.py` | Module with real local deps | Network mocked |
| End-to-end tests | `tests/test_orchestrator/test_pipeline_e2e.py` | Full pipeline with fakes | All mocked |

### 11.8 Testing Rules

1. **Tests are independent.** No test depends on the execution order or result of another test.
2. **Tests are deterministic.** No flaky tests. Mock all time-dependent and random behavior.
3. **Tests are fast.** Unit tests complete in under 1 second each. Use `@pytest.mark.slow` for integration tests.
4. **No test writes to `data/`.** Use `tmp_path` fixture for file system tests.
5. **Every bug fix includes a regression test.** The test must fail without the fix and pass with it.
6. **All public methods have at least one happy-path and one error-path test.**

---

## 12. Docstrings

### 12.1 Format

Use **Google-style** docstrings as the project standard:

```python
def scrape(self, slug: str) -> ScrapedProblem:
    """Scrape a LeetCode problem by its URL slug.

    Fetches the problem's metadata, description, constraints, examples,
    and the user's most recent accepted C++ submission via LeetCode's
    GraphQL API. Results are cached to disk for offline access.

    Args:
        slug: The URL-safe problem identifier (e.g., "two-sum").
            Must be a non-empty lowercase string.

    Returns:
        A frozen ScrapedProblem dataclass containing all problem data.

    Raises:
        ValueError: If slug is empty or contains invalid characters.
        AuthenticationError: If the LeetCode session cookie is expired.
        ProblemNotFoundError: If no problem exists with the given slug.
        RateLimitError: If LeetCode returns a 429 response after retries.
        ScraperError: For all other scraping failures.

    Example:
        >>> scraper = LeetCodeScraper(config, logger)
        >>> problem = scraper.scrape("two-sum")
        >>> problem.title
        '1. Two Sum'
    """
```

### 12.2 Coverage Requirements

| Element | Docstring Required? |
|---|---|
| Module (top of file) | Yes — one-line summary of the module's purpose |
| Public class | Yes — full docstring with purpose and usage |
| Public method | Yes — full docstring with Args, Returns, Raises |
| Private method (`_`) | Yes — at minimum a one-line summary |
| Dataclass | Yes — class-level docstring explaining the data contract |
| Dataclass fields | No — type hints and field names should be self-documenting. Add a comment only for non-obvious fields. |
| Enum | Yes — class-level docstring |
| Enum members | No — member names should be self-documenting |
| Test functions | Yes — one-line summary of what is being tested |
| Constants | Only if the name is not self-documenting |

### 12.3 Rules

1. **First line is a verb-phrase imperative sentence.** Start with a verb: "Scrape", "Generate", "Return", "Validate".
   ```python
   # YES
   """Scrape a LeetCode problem by its URL slug."""

   # NO
   """This method scrapes a LeetCode problem."""
   """Scrapes a LeetCode problem."""  # Third person is acceptable but imperative preferred
   ```

2. **First line fits on one line (≤79 chars).** The extended description follows after a blank line.

3. **Args section uses `name: Description` format** with 4-space indent for continuation lines.

4. **Returns section describes the return value**, not the return type (the type hint covers that).

5. **Raises section lists every exception this method intentionally raises**, including exceptions from called methods that are not caught.

6. **No redundant docstrings.** If a method is a trivial getter/setter whose behavior is obvious from the name and type signature alone, a one-line docstring suffices:
   ```python
   def get_record(self, slug: str) -> MemoryRecord | None:
       """Retrieve a memory record by problem slug, or None if not found."""
   ```

---

## 13. Comments

### 13.1 Comment Philosophy

> Code tells you *how*. Comments tell you *why*.

Comments explain intent, rationale, and non-obvious constraints. They do not restate what the code does.

### 13.2 Good Comments

```python
# GraphQL API returns HTML-encoded descriptions; we convert to Markdown
# for consistent downstream processing in the script generator.
description = html_to_markdown(raw_description)

# LeetCode rate-limits aggressive scraping. 2-second delay is the empirically
# safe minimum before 429 responses begin.
time.sleep(self._config.rate_limit_seconds)

# Kokoro-82M requires 24kHz sample rate. Mismatched rates cause pitch
# artifacts that are subtle but audible in final video.
assert sample_rate == 24000, f"Expected 24kHz, got {sample_rate}Hz"
```

### 13.3 Bad Comments (Forbidden)

```python
# FORBIDDEN — restates the code
i += 1  # increment i

# FORBIDDEN — journal/changelog comments
# Added by Adarsh on 2026-07-22

# FORBIDDEN — commented-out code (use git)
# old_value = compute_legacy(x)

# FORBIDDEN — TODO/FIXME/HACK/XXX in committed code
# TODO: implement this later

# FORBIDDEN — section dividers
# ==========================================
# ========== SCRAPER METHODS ==============
# ==========================================

# FORBIDDEN — closing bracket labels
}  # end if
```

### 13.4 Rules

1. **No TODO, FIXME, HACK, or XXX comments.** These indicate incomplete work. Complete the work or file an issue.
2. **No commented-out code.** Git preserves history. Delete dead code.
3. **No authorship comments.** Git blame provides attribution.
4. **Inline comments have 2 spaces before `#`.** Standard PEP 8.
5. **Block comments start with `# ` (hash + space).** Standard PEP 8.
6. **Comments are complete sentences.** Start with a capital letter, end with a period.
7. **Update comments when updating code.** Stale comments are worse than no comments.

---

## 14. Performance Guidelines

### 14.1 General Rules

1. **Measure before optimizing.** Profile with `cProfile` or `py-spy` before making performance changes. No speculative optimization.

2. **Optimize the bottleneck.** The two dominant bottlenecks are Voice Synthesis (CPU/NPU-bound) and Manim Rendering (CPU-bound). Optimizing anything else yields marginal improvement.

3. **Use generators for large sequences.** When processing more than 100 items, use generators or iterators instead of building full lists in memory:
   ```python
   # YES — lazy processing
   def iter_chunks(self, text: str) -> Iterator[str]:
       for start in range(0, len(text), self._chunk_size):
           yield text[start:start + self._chunk_size]

   # NO — materializes everything
   def get_chunks(self, text: str) -> list[str]:
       return [text[i:i+self._chunk_size] for i in range(0, len(text), self._chunk_size)]
   ```

4. **Subprocess over in-process for heavy work.** FFmpeg and Manim rendering run as subprocesses to isolate memory and enable OS-level process scheduling.

5. **Connection reuse.** HTTP clients (`httpx.Client`) are created once per module instance and reused for all requests. Never create a new client per request.

6. **Batch API calls.** When possible, batch multiple items into a single API call (e.g., batch embedding requests).

### 14.2 Specific Optimization Targets

| Component | Target | Approach |
|---|---|---|
| Voice synthesis | < 3 minutes for 10 sections | OpenVINO NPU acceleration, batch processing |
| Manim rendering | < 5 minutes for 10 sections | `production_quality` preset, parallel scene rendering |
| FFmpeg assembly | < 1 minute | Intel QSV hardware encoding (`h264_qsv`), streaming concat |
| RAG retrieval | < 2 seconds per query | Persistent ChromaDB index on SSD |
| Gemini API calls | < 30 seconds per call | Request-level timeout, connection pooling |

### 14.3 Caching

- Every module checks for a cached output before executing.
- Cache key: `(module_name, slug)` mapped to a file path: `data/{module}/{slug}*.json`.
- Cache invalidation is explicit: `--force-regenerate` flag or manual deletion.
- No time-based expiration. Cached artifacts are valid until explicitly invalidated.

### 14.4 Forbidden Anti-Patterns

```python
# FORBIDDEN — string concatenation in loops
result = ""
for item in items:
    result += str(item)
# YES
result = "".join(str(item) for item in items)

# FORBIDDEN — repeated file reads
for slug in slugs:
    config = load_config()  # Reloads from disk every iteration
# YES — load once, pass reference
config = load_config()
for slug in slugs:
    process(slug, config)

# FORBIDDEN — synchronous sleep in hot path
time.sleep(5)  # Blocks the entire thread for 5 seconds
# YES — sleep only for rate limiting with configurable duration
time.sleep(self._config.rate_limit_seconds)
```

---

## 15. Memory Guidelines

### 15.1 Rules

1. **Process sections individually.** Never load all 10 audio files or all 10 video clips into memory simultaneously. Process each section sequentially and release references.

2. **Use `Path` objects, not loaded content.** Pass file paths between modules, not file contents. Modules load content only when they need it and release it immediately after processing:
   ```python
   # YES — pass path
   @dataclass(frozen=True)
   class SectionAudio:
       audio_path: Path
       duration_seconds: float

   # NO — pass loaded bytes
   @dataclass(frozen=True)
   class SectionAudio:
       audio_data: bytes       # Holds megabytes in memory
       duration_seconds: float
   ```

3. **Close resources explicitly.** Use context managers for files, HTTP sessions, database connections, and model handles.

4. **No module-level caches without bounds.** If a function uses `@functools.lru_cache`, set `maxsize` explicitly:
   ```python
   @functools.lru_cache(maxsize=128)
   def get_embedding(self, text: str) -> list[float]: ...
   ```

5. **Subprocess for Manim scenes.** Each Manim scene renders in a separate subprocess. This prevents memory accumulation from Manim's internal caches across 10+ scene renders.

6. **No global mutable collections.** No module-level lists, dicts, or sets that grow unboundedly during a pipeline run.

### 15.2 Memory Budget

| Component | Expected Peak Memory |
|---|---|
| ChromaDB (loaded index) | 200-500 MB |
| Kokoro-82M model (OpenVINO) | 300-500 MB |
| Single audio section (in-memory) | 5-20 MB |
| Single video frame (in-memory) | 6 MB (1920×1080 RGB) |
| Manim subprocess | 200-500 MB (isolated) |
| FFmpeg subprocess | 100-300 MB (isolated) |
| **Total pipeline peak** | **~1.5 GB** |

---

## 16. Code Review Checklist

Every code change must be verified against this checklist before merging. Reviewers use this as their audit reference.

### 16.1 Correctness

- [ ] Does the code do what the specification requires?
- [ ] Are all edge cases handled (empty inputs, None values, boundary values)?
- [ ] Are error paths tested and do they produce actionable messages?
- [ ] Is exception chaining preserved (`raise X from Y`)?
- [ ] Are return types consistent with the declared type hints?

### 16.2 Architecture

- [ ] Does the change respect the module dependency graph? (No cross-module imports.)
- [ ] Are dependencies injected, not instantiated internally?
- [ ] Does the change depend on protocols, not concrete implementations?
- [ ] Are data contracts (dataclasses) defined in `src/models/`?
- [ ] Is the file under 400 lines?

### 16.3 Style

- [ ] Does the code pass `flake8` with zero warnings?
- [ ] Does the code pass `mypy --strict` with zero errors?
- [ ] Are imports ordered per Section 6?
- [ ] Are all naming conventions from Section 2 followed?
- [ ] Are trailing commas used in multi-line structures?

### 16.4 Documentation

- [ ] Do all public classes and methods have Google-style docstrings?
- [ ] Do docstrings include Args, Returns, and Raises sections?
- [ ] Are comments explaining *why*, not *what*?
- [ ] Are there no TODO/FIXME/HACK comments?
- [ ] Are there no commented-out code blocks?

### 16.5 Testing

- [ ] Is there at least one happy-path test per public method?
- [ ] Is there at least one error-path test per public method?
- [ ] Do tests follow the AAA (Arrange-Act-Assert) pattern?
- [ ] Do tests use the `tmp_path` fixture for file operations?
- [ ] Are external dependencies mocked at the boundary?
- [ ] Is test coverage at or above the module minimum?

### 16.6 Performance & Security

- [ ] Are there no magic numbers or magic strings?
- [ ] Are there no `print()` statements?
- [ ] Are there no secrets in source code, logs, or config files?
- [ ] Are HTTP timeouts set on all network calls?
- [ ] Are file paths constructed using `pathlib.Path`, not string concatenation?

---

## 17. Security Checklist

### 17.1 Secrets Management

- [ ] API keys (`GEMINI_API_KEY`) live in `.env` only, never in source code or YAML.
- [ ] Session cookies (`LEETCODE_SESSION`) live in `.env` only.
- [ ] OAuth tokens are stored in a local file with `600` permissions, never committed to git.
- [ ] `.env` is listed in `.gitignore`.
- [ ] `config/client_secrets.json` is listed in `.gitignore`.
- [ ] No secret is logged at any log level, even `DEBUG`.
- [ ] Error messages do not leak secret values.

### 17.2 Input Validation

- [ ] All user-provided inputs (CLI args, config values) are validated before use.
- [ ] LeetCode slugs are validated against a regex before being used in file paths or API calls.
- [ ] No user input is directly interpolated into shell commands. Use `subprocess.run` with a list of arguments, never `shell=True`.

```python
# YES — safe subprocess call
subprocess.run(
    ["ffmpeg", "-i", str(input_path), "-c:v", "libx264", str(output_path)],
    check=True,
    capture_output=True,
)

# FORBIDDEN — shell injection risk
subprocess.run(f"ffmpeg -i {input_path} -c:v libx264 {output_path}", shell=True)
```

### 17.3 File System Safety

- [ ] All file paths are constructed using `pathlib.Path`, never string concatenation.
- [ ] No path traversal vulnerabilities: slugs used in paths are sanitized (alphanumeric + hyphens only).
- [ ] Output directories are created with `mkdir(parents=True, exist_ok=True)`, never with shell commands.
- [ ] File permissions: no `chmod 777`. Generated files use system defaults.

```python
# Slug sanitization
import re

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

def validate_slug(slug: str) -> str:
    """Validate and return a sanitized LeetCode slug.

    Args:
        slug: The raw slug string to validate.

    Returns:
        The validated slug string.

    Raises:
        ValueError: If the slug contains invalid characters.
    """
    slug = slug.strip().lower()
    if not SLUG_PATTERN.match(slug):
        raise ValueError(
            f"Invalid slug '{slug}'. Slugs must contain only lowercase "
            f"letters, digits, and hyphens."
        )
    return slug
```

### 17.4 Network Security

- [ ] HTTPS is used for all external API calls.
- [ ] HTTP request timeouts are always set (never `timeout=None`).
- [ ] API rate limits are respected (minimum delays between calls).
- [ ] YouTube OAuth tokens are refreshed server-side; refresh tokens are stored locally with restricted permissions.
- [ ] No sensitive data is sent in URL query parameters (use request body or headers).

### 17.5 Dependency Security

- [ ] All dependencies are pinned to specific versions in `pyproject.toml`.
- [ ] No dependency uses `*` version ranges.
- [ ] Dependencies are periodically audited with `pip-audit` or `safety`.
- [ ] No unused dependencies remain in the dependency list.

---

## 18. Forbidden Practices

These practices are **unconditionally prohibited** across the entire codebase. Any code containing these patterns fails review immediately.

### 18.1 Code Quality

| Forbidden | Why | Alternative |
|---|---|---|
| `# TODO`, `# FIXME`, `# HACK`, `# XXX` | Indicates incomplete work | Complete the work or file an issue |
| Commented-out code | Dead code rot | Delete it; git preserves history |
| `print()` for output | Unstructured, unsuppressable | `structlog` logger |
| `except Exception: pass` | Silently swallows errors | Catch specific exceptions, log, and handle |
| `except:` (bare except) | Catches `SystemExit`, `KeyboardInterrupt` | Always specify exception type |
| `from module import *` | Pollutes namespace, hides dependencies | Explicit named imports |
| Global mutable state | Untestable, unpredictable | Dependency injection |
| Singleton pattern | Hidden global state | Constructor injection |
| `os.path` for file paths | Legacy, error-prone | `pathlib.Path` |
| `subprocess.run(..., shell=True)` | Shell injection vulnerability | Pass command as list |
| Magic numbers/strings | Obscure intent | Named constants or config values |
| Files > 400 lines | Monolithic, hard to review | Split into focused modules |
| Nested comprehensions | Unreadable | Explicit loops or helper functions |
| `isinstance()` checks in module logic | Violates polymorphism | Use Protocol dispatch |
| `type()` checks for control flow | Fragile, bypassed by inheritance | Use Protocol dispatch |
| Mutable default arguments | Shared across calls | `field(default_factory=...)` |
| `datetime.now()` without timezone | Ambiguous timezone | `datetime.now(timezone.utc)` |

### 18.2 Architecture

| Forbidden | Why | Alternative |
|---|---|---|
| Cross-module imports | Violates module independence | Communicate through `src/models/` dataclasses |
| Module instantiating its own dependencies | Violates DI, hides coupling | Constructor injection |
| Reading `.env` or `os.getenv` inside modules | Config must be injected | Receive config dataclass via `__init__` |
| Circular imports | Design error indicating tangled dependencies | Refactor dependency direction |
| Upward layer dependencies | Lower layers cannot depend on higher | Extract shared code to `src/core/` |
| Inheritance for code reuse | Creates tight coupling hierarchies | Composition and dependency injection |

### 18.3 Testing

| Forbidden | Why | Alternative |
|---|---|---|
| `unittest.TestCase` subclassing | Inconsistent with `pytest` | Use plain functions with `pytest` |
| Mocking the class under test | Tests internal implementation, not behavior | Mock external dependencies only |
| Test interdependence | Fragile, order-dependent | Each test fully self-contained |
| Writing to `data/` in tests | Pollutes runtime data | Use `tmp_path` fixture |
| Non-deterministic tests (time, random) | Flaky CI | Mock `time`, seed random |
| Tests without assertions | Provides false coverage | Every test asserts something |

---

## 19. Required Practices

These practices are **unconditionally mandatory** in every source file.

### 19.1 Every Source File Must Have

| Requirement | Detail |
|---|---|
| Module docstring | One-line summary of the file's purpose at the top |
| Type annotations | 100% coverage on all functions, methods, and attributes |
| Explicit imports | No wildcard imports, no unused imports |
| Logger instance | `logger = structlog.get_logger(__name__)` or injected via constructor |

### 19.2 Every Class Must Have

| Requirement | Detail |
|---|---|
| Docstring | Google-style, describing purpose and usage |
| Type-annotated `__init__` | All parameters and return type (`-> None`) annotated |
| Private attribute storage | Injected dependencies stored as `self._name` |
| Single responsibility | One clear purpose; if description uses "and", consider splitting |

### 19.3 Every Public Method Must Have

| Requirement | Detail |
|---|---|
| Docstring | Google-style with Args, Returns, Raises |
| Type-annotated signature | Parameters and return type |
| Input validation | Validate arguments at entry, raise `ValueError` for invalid inputs |
| Logging | `INFO` at entry and/or exit for significant operations |
| Error handling | Specific exceptions caught, chained, and raised as domain exceptions |

### 19.4 Every Dataclass Must Have

| Requirement | Detail |
|---|---|
| `frozen=True` | For all inter-module contracts |
| Docstring | Describing the data contract and which modules produce/consume it |
| Type annotations | On every field |
| Validation | `__post_init__` for invariants that must hold |

### 19.5 Every Test Must Have

| Requirement | Detail |
|---|---|
| Descriptive name | `test_{method}_{scenario}_{expectation}` |
| One-line docstring | What is being verified |
| AAA structure | Clear Arrange, Act, Assert sections |
| Type annotations | On all parameters and return (`-> None`) |
| Deterministic behavior | No reliance on time, network, or random state |

### 19.6 Every Commit Must Have

| Requirement | Detail |
|---|---|
| Passing linter | `flake8` with zero warnings |
| Passing type checker | `mypy --strict` with zero errors |
| Passing tests | `pytest` with zero failures |
| No new `TODO`/`FIXME` | Complete the work or defer to a tracked issue |
| No secrets in diff | No API keys, cookies, or tokens |

### 19.7 Configuration Enforcement Tools

| Tool | Purpose | Config Location |
|---|---|---|
| `flake8` | PEP 8 linting | `pyproject.toml` `[tool.flake8]` |
| `mypy` | Static type checking (strict mode) | `pyproject.toml` `[tool.mypy]` |
| `isort` | Import sorting | `pyproject.toml` `[tool.isort]` |
| `pytest` | Testing | `pyproject.toml` `[tool.pytest.ini_options]` |
| `pytest-cov` | Coverage enforcement | `pyproject.toml` `[tool.coverage]` |

### 19.8 Recommended `pyproject.toml` Tool Configuration

```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
no_implicit_optional = true
check_untyped_defs = true

[tool.isort]
profile = "black"
known_first_party = ["src"]
line_length = 99
force_single_line = false
lines_after_imports = 2

[tool.flake8]
max-line-length = 99
extend-ignore = ["E203", "W503"]
per-file-ignores = ["__init__.py:F401"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --strict-markers --tb=short"
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks integration tests",
]

[tool.coverage.run]
source = ["src"]
omit = ["src/__main__.py"]

[tool.coverage.report]
fail_under = 90
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.",
]
```

---

**End of Engineering Standards (`03_Project_Standards.md`).**
