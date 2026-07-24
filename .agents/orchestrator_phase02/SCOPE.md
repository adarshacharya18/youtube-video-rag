# Scope: Phase 02 Knowledge Ingestion

## Architecture
Phase 02 Knowledge Ingestion ingests raw DSA problem documents (Markdown/HTML/JSON), cleans and sanitizes content, extracts structural components via AST parsing (`markdown-it-py` or `mistune`), and standardizes output into strongly-typed Python dataclasses (`ScrapedProblem`, `Example`, `Difficulty`) for downstream RAG and video generation stages.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Architecture & Strategy Documentation | Write `PromptBook/Phase02/01_Ingestion_Strategy.md` detailing AST parsing, sanitizer design, and model contracts. | None | DONE |
| 2 | Ingestion Core Implementation | Implement `src/models/enums.py`, `src/models/problem.py`, `src/models/__init__.py`, `src/core/ingestion/models.py`, `src/core/ingestion/sanitizer.py`, and `src/core/ingestion/parser.py`. | M1 | DONE |
| 3 | Testing & Mock Fixtures | Create synthetic DSA Markdown test fixtures and unit/integration test suite `tests/ingestion/test_parser.py`. | M2 | DONE |

## Interface Contracts
### Raw Markdown/HTML Input ↔ Parser Output
- Inputs: Raw string containing Markdown/HTML DSA problem statements.
- Outputs: `ScrapedProblem` dataclass containing:
  - `slug`: str
  - `title`: str
  - `number`: int
  - `difficulty`: Difficulty Enum (EASY, MEDIUM, HARD)
  - `description`: str (cleaned markdown)
  - `constraints`: list[str]
  - `examples`: list[Example] (input, output, explanation)
  - `tags`: list[str]
  - `accepted_code`: str
  - `code_language`: str
  - `scraped_at`: datetime

## Code Layout
- `src/core/ingestion/parser.py`
- `src/core/ingestion/sanitizer.py`
- `PromptBook/Phase02/01_Ingestion_Strategy.md`
- `tests/ingestion/test_parser.py`
- `tests/fixtures/ingestion/` (mock Markdown fixtures)
