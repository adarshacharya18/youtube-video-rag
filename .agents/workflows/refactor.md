# Workflow: Code Refactoring (`refactor.md`)

## Purpose
Safe procedure for refactoring existing modules to improve maintainability or split large files.

## Steps
1. **Refactoring Plan:** Role: `Architect Model`. Identify target module decomposition plan.
2. **Execute Refactor:** Role: `Implementation Model`. Reorganize code into sub-modules without changing API contracts.
3. **Behavioral Audit:** Role: `Reviewer Model`. Run test suite to verify no functional regressions.
