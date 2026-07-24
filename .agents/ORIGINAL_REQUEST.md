# Original User Request

## Initial Request — 2026-07-24T11:17:02+05:30

Implement Phase 02: Knowledge Ingestion for the Automated DSA Educational YouTube Video Pipeline. The system must ingest raw DSA problems (e.g. from LeetCode or markdown files) and parse descriptions, constraints, and solutions into standardized Python dataclasses.

Working directory: /home/adarsh/Documents/Youtube-Channel
Integrity mode: development

## Requirements

### R1. Markdown & AST Parsing
Create `src/core/ingestion/parser.py` to parse raw Markdown/HTML DSA problems. The parser must extract the problem description, constraints, and the optimal solution code (Python/C++). You must use a robust parsing library like `markdown-it-py` or `mistune` rather than brittle custom regex.

### R2. Data Sanitization & Standardization
Create `src/core/ingestion/sanitizer.py` to clean the parsed data and enforce strict standardization into Python dataclasses (building on Phase 01 configurations).

### R3. Ingestion Strategy Documentation
Document the ingestion pipeline architecture in `PromptBook/Phase02/01_Ingestion_Strategy.md`.

## Acceptance Criteria

### Verification & Testing
- [ ] The team must generate synthetic mock Markdown fixtures representing typical DSA problems.
- [ ] Running `pytest tests/ingestion/test_parser.py` executes successfully, validating that the parser correctly extracts data from the synthetic mock fixtures into the standardized Python dataclasses.
- [ ] `src/core/ingestion/parser.py` and `src/core/ingestion/sanitizer.py` exist and contain the required data extraction and cleaning logic.

### Documentation & Structure
- [ ] `PromptBook/Phase02/01_Ingestion_Strategy.md` exists and details the architecture for Markdown/HTML parsing and AST extraction.
