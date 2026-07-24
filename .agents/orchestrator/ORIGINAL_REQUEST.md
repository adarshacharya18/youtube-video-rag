# Original User Request — Phase 01: Initial Setup & Global Architecture

## 2026-07-24T10:51:03Z

Implement Phase 01: Initial Setup & Global Architecture for an Automated DSA Educational YouTube Video Pipeline using a Synchronous Batch-Pipeline paradigm.

Working directory: /home/adarsh/Documents/Youtube-Channel
Integrity mode: development

## Requirements

### R1. Global Folder Structure & Rules
Define the global folder structure (`src/`, `tests/`, `scripts/`, `PromptBook/`) and establish `01_Global_Rules.md` outlining Python conventions (PEP 8, static typing, structural logging).

### R2. Core Foundation & Config
Create the foundational `src/core/base.py`, `src/core/exceptions.py`, and global configuration loaders in `src/core/config.py`. Ensure the configuration loader uses Pydantic for strict typing and environment variable validation.

### R3. Architectural Documentation
Scaffold the `PromptBook/Phase01/` documentation outlining the high-level Synchronous Batch-Pipeline architecture (explicitly forbidding complex async event buses and dynamic DI containers).

## Acceptance Criteria

### Verification & Testing
- [ ] Running `pytest tests/core/test_config.py` executes successfully, validating that environment variables correctly hydrate the Pydantic configuration models.
- [ ] `src/core/base.py` and `src/core/exceptions.py` exist and contain basic foundational classes (e.g. a base exception class).

### Documentation & Structure
- [ ] `PromptBook/Phase01/01_Global_Rules.md` exists and contains explicit guidelines for PEP 8, static typing, and structural logging.
- [ ] The global folder structure (`src/`, `tests/`, `scripts/`, `PromptBook/`) has been successfully scaffolded.
