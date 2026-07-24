# Handoff Report: Phase 02 Data Models & Sanitizer Design

**Author:** Explorer 2 (Phase 02 Knowledge Ingestion)  
**Recipient:** Orchestrator (Phase 02) / Implementer  
**Working Directory:** `/home/adarsh/Documents/Youtube-Channel/.agents/teamwork_preview_explorer_phase02_2`  
**Date:** July 2026  

---

## 1. Observation

1. **`PromptBook/Phase01/04_Data_Models.md` (Lines 353-374, 118-137, 203-214):**
   - Defines `ScrapedProblem` with fields `slug`, `title`, `number`, `difficulty`, `description`, `constraints`, `examples`, `tags`, `accepted_code`, `code_language`, `scraped_at`.
   - Defines `Example` with fields `input`, `output`, `explanation`.
   - Defines `Difficulty` enum with values `EASY`, `MEDIUM`, `HARD`.
   - Specifies strict design principles: `frozen=True`, type safe, JSON compatible, fail-fast validation in `__post_init__`.

2. **`PromptBook/04_Folder_Structure.md` (Lines 63-78, 466-514):**
   - Layer 1 (`src/models/`) is designated as the true leaf package containing shared domain dataclasses and enums (`problem.py`, `enums.py`, `protocols.py`, `__init__.py`).
   - Layer 2 (`src/core/`) contains shared infrastructure (`config.py`, `logger.py`, `serialization.py`, `exceptions.py`).
   - Modular plugins under `src/plugins/ingestion/` currently contain `RawContent` and `NormalizedDocument` (`normalizer.py` lines 18-26, `connector_base.py` lines 32-39).

3. **Existing Workspace State:**
   - Files `src/models/__init__.py`, `src/models/enums.py`, `src/models/problem.py` exist as empty 0-byte placeholders.
   - Core ingestion directory `src/core/ingestion/` does not yet contain `sanitizer.py`.

---

## 2. Logic Chain

1. **Observation 1 & 2 -> Model Placement Strategy:**
   - `ScrapedProblem`, `Example`, and `Difficulty` are inter-module transfer models required across scraper, tag explorer, RAG engine, script generator, and orchestrator modules.
   - Placing them in Layer 1 (`src/models/problem.py` and `src/models/enums.py`) guarantees leaf purity (zero internal imports) and prevents circular dependencies across pipeline components.
   - Re-exporting these models from `src/core/ingestion/models.py` (or `src/models/__init__.py`) provides backward compatibility and modular access without architectural violation.

2. **Observation 1 & 3 -> Sanitizer Design Requirements:**
   - Raw HTML payloads scraped from LeetCode or external APIs contain HTML entities (`&quot;`, `&lt;`, `&nbsp;`), `<pre><code>` blocks, inline styles, math tags (`<sup>`, `<sub>`), and inconsistent formatting.
   - The sanitizer (`src/core/ingestion/sanitizer.py`) must convert HTML elements to clean Markdown, preserve 4-space code block indentation, standardize titles/difficulties/tags, format input/output examples into `Example` instances, and instantiate frozen `ScrapedProblem` objects with strict fail-fast `__post_init__` checks.

3. **Observation 1 & 2 -> Immutability and Serialization:**
   - `@dataclass(frozen=True)` ensures immutability across async processing.
   - Bidirectional JSON codecs (`to_dict()` / `from_dict()`) translate `datetime` to ISO 8601 strings and `Difficulty` enums to string names for persistence in `data/scraped/{slug}.json`.

---

## 3. Caveats

- **External HTML Edge Cases:** Web source format variations (e.g. custom math styling in legacy LeetCode descriptions) may require ongoing regex enhancements in `sanitizer.py`.
- **Read-Only Scope:** This investigation is read-only. Source files under `src/models/` and `src/core/ingestion/` have not been directly edited; complete code specifications are provided in `analysis_sanitizer.md` for implementation.

---

## 4. Conclusion

- `ScrapedProblem`, `Example`, and `Difficulty` MUST be implemented in `src/models/problem.py` and `src/models/enums.py`, with public re-exports in `src/models/__init__.py`. `src/core/ingestion/models.py` will serve as an ingestion bridge.
- `src/core/ingestion/sanitizer.py` design is complete and fully specified in `analysis_sanitizer.md`, featuring zero-dependency HTML cleaning, whitespace normalization, code indentation preservation, tag/difficulty standardization, and fail-fast validation.

---

## 5. Verification Method

1. **Inspect Analysis Report:**
   - View `/home/adarsh/Documents/Youtube-Channel/.agents/teamwork_preview_explorer_phase02_2/analysis_sanitizer.md`.
2. **Implementation & Test Verification (upon code creation):**
   - Once implemented in `src/models/` and `src/core/ingestion/sanitizer.py`, execute:
     ```bash
     pytest tests/test_models/test_problem.py
     pytest tests/test_ingestion/test_sanitizer.py
     ```
   - Confirm frozen immutability checks (`FrozenInstanceError` on assignment) and JSON round-trip serialization.
