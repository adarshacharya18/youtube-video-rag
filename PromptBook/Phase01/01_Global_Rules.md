# Global Development Rules & Conventions

## 1. Python Code Quality & PEP 8 Standards
- **Compliance**: All code must strictly follow **PEP 8** style guidelines.
- **Formatting**: Limit line length to 88 or 100 characters. Use 4-space indentations without tabs.
- **Imports**: Organize imports into standard library, third-party libraries, and local imports (separated by blank lines). Absolute imports are required (`src.core.config` or relative within sub-package).
- **Naming Conventions**:
  - `snake_case` for functions, variables, methods, and module names.
  - `PascalCase` for classes, type aliases, and protocols.
  - `UPPER_SNAKE_CASE` for constants.
  - Lead single underscores (`_private_var`) for internal helpers.

## 2. Strict Static Typing & Type Hints
- **Explicit Annotations**: Every function, method, argument, and return type must have explicit Python type annotations.
- **Modern Typing**: Use built-in generics (e.g., `list[str]`, `dict[str, Any]`, `tuple[int, ...]`) or `typing` constructs (`Protocol`, `TypeVar`, `SecretStr`).
- **No Implicit Any**: Do not leave untyped function parameters or returns. Explicitly use `Any` only when necessary.
- **Pydantic V2 Models**: All domain configuration, DTOs, and pipeline state objects must inherit from Pydantic V2 models (`BaseModel`, `BaseSettings`) with field validation and strict typing.

## 3. Structural Logging with structlog
- **Logger Initialization**: All modules must utilize `structlog.get_logger(__name__)`.
- **JSON Formatting in Production**: Log formatters must emit structured JSON dictionaries in production environments for automated ingestion and search.
- **Console / Key-Value formatting in Development**: Human-readable colored output with key-value pairs during local development and test runs.
- **Contextual Key-Value Pairs**: Include key operational context as explicit log kwargs (e.g., `logger.info("stage_completed", stage="ingestion", duration_ms=45, records=12)`). Never build unparsed concatenated log strings.

## 4. Software Design & Architectural Guiding Rules
- **Synchronous Batch Pipeline**: Modular step-by-step execution. Avoid dynamic dependency injection frameworks or complex event buses.
- **Complete Implementations**: No placeholder methods, hardcoded test facades, `pass`-only logic, or "TODO implement later" markers in production code.
- **Centralized Error Hierarchy**: Custom exceptions must inherit from `PipelineError` in `src.core.exceptions` and specify operation impact (`RetryableError` vs `FatalError`).
- **Unit & Integration Testing**: Every core module and configuration component must be accompanied by comprehensive `pytest` test suites.
