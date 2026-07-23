# Skill: Python Backend Engineer (`python_backend.md`)

This skill defines the coding standards, typing guidelines, software engineering practices, and code structure rules for AI operating as the **Senior Python Backend Engineer** for the Automated DSA Educational YouTube Video Automation Pipeline.

---

## 1. Python 3.12+ Modern Syntax Standards
- Use modern built-in generic types (`list[str]`, `dict[str, Any]`, `set[int]`, `tuple[int, ...]`) instead of legacy `typing.List`, `typing.Dict`.
- Use the union operator `|` for optional and union types (`str | None`, `int | float`) instead of `Optional[str]` or `Union[int, float]`.
- Use `Self` from `typing` for method return types returning an instance of the class.
- Use `@override` decorator from `typing` when overriding abstract methods.

---

## 2. Type Hinting & Static Typing
- **100% Type Coverage:** Every function parameter, class attribute, and return value must have an explicit type hint.
- **Strict Typing Mode:** Code must pass `mypy --strict` with zero type errors.
- Never use `Any` unless interfacing with third-party untyped libraries (and isolate it with a wrapper).

---

## 3. Dataclasses & Immutable Domain Models
- Prefer `@dataclass(frozen=True, slots=True)` for domain entities, request parameters, and script sections.
- Immutable dataclasses guarantee thread safety, zero unintentional state mutations, and minimal memory overhead.

```python
from dataclasses import dataclass, field
from pathlib import Path

@dataclass(frozen=True, slots=True)
class ProblemMetadata:
    """Immutable domain representation of a scraped LeetCode problem."""
    problem_id: int
    title: str
    title_slug: str
    difficulty: str
    tags: list[str]
    solution_code: str
    explanation: str
    constraints: list[str] = field(default_factory=list)
```

---

## 4. Interfaces: Protocols & ABCs

### Protocols (Structural Subtyping / Duck Typing)
Use `typing.Protocol` for decoupled interfaces across application boundaries.

```python
from typing import Protocol, runtime_checkable
from pathlib import Path

@runtime_checkable
class VoiceEngineProtocol(Protocol):
    """Protocol for pluggable voice generation engines."""
    
    def synthesize_speech(self, text: str, output_path: Path) -> Path:
        """Synthesize text audio and save to output_path."""
        ...
```

### Abstract Base Classes (Nominal Subtyping)
Use `abc.ABC` when providing shared default behavior or base fields to sub-classes.

```python
from abc import ABC, abstractmethod
from pathlib import Path

class BaseSceneRenderer(ABC):
    """Abstract base class for all Manim scene renderers."""
    
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir

    @abstractmethod
    def render_scene(self, scene_params: dict[str, object]) -> Path:
        """Render the video scene and return the generated MP4 file path."""
        pass
```

---

## 5. Dependency Injection (DI)
- Inject dependencies explicitly via `__init__` constructors.
- Avoid instantiation inside constructors or methods.

```python
class VideoPipelineOrchestrator:
    """Orchestrates pipeline execution using injected interface engines."""

    def __init__(
        self,
        scraper: LeetCodeScraperProtocol,
        voice_engine: VoiceEngineProtocol,
        renderer: BaseSceneRenderer,
    ) -> None:
        self._scraper = scraper
        self._voice_engine = voice_engine
        self._renderer = renderer
```

---

## 6. Structured Logging
- Use standard `logging.getLogger(__name__)`.
- Never use raw `print()` statements in production backend modules.
- Include structured contextual data in log messages.

```python
import logging

logger = logging.getLogger(__name__)

def process_problem(problem_id: int) -> None:
    logger.info("Starting processing for problem_id=%d", problem_id)
    try:
        # Processing logic...
        logger.debug("Successfully parsed problem_id=%d", problem_id)
    except Exception as exc:
        logger.error("Failed to process problem_id=%d error=%s", problem_id, exc, exc_info=True)
        raise
```

---

## 7. Exception Hierarchy & Error Handling
- Never use generic `except Exception: pass`.
- Define a custom domain exception hierarchy inheriting from a base `PipelineError`.

```python
class PipelineError(Exception):
    """Base exception for all pipeline failures."""

class LeetCodeScraperError(PipelineError):
    """Raised when LeetCode GraphQL fetch or parsing fails."""

class VoiceSynthesisError(PipelineError):
    """Raised when Kokoro OpenVINO speech generation fails."""
```

---

## 8. Unit & Integration Testing (`pytest`)
- All tests reside under `tests/`.
- Use `pytest` fixtures for common setups.
- Mock all network, disk, and heavy model execution.

```python
import pytest
from unittest.mock import MagicMock
from pathlib import Path

def test_scraper_fetches_problem_successfully(mocker: pytest.FixtureRequest) -> None:
    mock_response = {"data": {"question": {"title": "Two Sum", "questionId": "1"}}}
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.json.return_value = mock_response
    mock_post.return_value.status_code = 200

    # Execute and assert...
```

---

## 9. Performance & CPU/NPU Optimization
- Use `pathlib.Path` for all filesystem path manipulations.
- Use generators (`yield`) for processing large video clips or audio frames to minimize RAM overhead.
- Utilize thread pooling or async IO when fetching multiple web/API requests.

---

## 10. Packaging, Formatting & Naming Conventions

### Naming Standards
- **Modules/Files:** `snake_case.py` (e.g., `leetcode_client.py`)
- **Classes:** `PascalCase` (e.g., `VoiceSynthesizer`)
- **Functions/Methods:** `snake_case()` (e.g., `synthesize_speech()`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `DEFAULT_SAMPLE_RATE = 22050`)
- **Private Attributes:** `_leading_underscore` (e.g., `self._voice_engine`)

### Folder Structure Standard
```
Youtube-Channel/
├── config/
│   ├── settings.yaml
│   └── theme.py
├── src/
│   ├── scraper/
│   ├── rag/
│   ├── script/
│   ├── voice/
│   ├── animation/
│   ├── assembler/
│   └── memory/
├── tests/
├── data/
├── requirements.txt
└── .env
```

---

## 11. Python Engineering Checklist
Before submitting Python code:
- [ ] 100% type annotations present (`mypy` clean).
- [ ] Format compliant with `black` / `ruff`.
- [ ] Zero `print()` statements (uses `logging`).
- [ ] Exceptions inherit from `PipelineError`.
- [ ] Dependencies injected via `__init__`.
- [ ] Dataclasses use `@dataclass(frozen=True, slots=True)`.
- [ ] No single file exceeds 400 lines.
- [ ] Pytest test case written and passing.
