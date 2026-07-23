# Workflow: Bug Investigation & Fixing (`bugfix.md`)

## Purpose
Protocol for diagnosing and resolving runtime defects or pipeline errors.

## Steps
1. **Log Analysis:** Role: `Debugger Model`. Trace exception stack traces and isolate root cause.
2. **Reproduction Test:** Role: `Implementation Model`. Write failing pytest test case proving bug existence.
3. **Fix Implementation:** Role: `Implementation Model`. Apply code fix to resolve defect.
4. **Regression Verification:** Role: `Reviewer Model`. Run test suite to verify fix and ensure no side-effects.
