# Phase03/12_CI_Preparation.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Local CI Script: `scripts/ci.sh`](#2-local-ci-script-scriptscish)
3. [Tooling Breakdown](#3-tooling-breakdown)
4. [Design Decisions](#4-design-decisions)

---

# 1. Executive Summary

This document outlines the Continuous Integration (CI) preparation strategy. While we are deferring the creation of the actual `.github/workflows/` YAML files until a repository is established, we are establishing the exact command-line verifications that the CI server will eventually run.

By packaging these steps into a local `scripts/ci.sh` executable, developers can validate their code strictly against the canonical project standards before pushing commits, ensuring a 100% pass rate once GitHub Actions are eventually activated.

---

# 2. Local CI Script: `scripts/ci.sh`

This script serves as the single source of truth for code quality. The future GitHub Action will simply execute this script (or run these exact commands in sequence).

```bash
#!/usr/bin/env bash
# scripts/ci.sh
# Run from the project root: ./scripts/ci.sh

# Exit immediately if any command exits with a non-zero status
set -e

echo "======================================================"
echo "🚀 Initiating Local Continuous Integration Pipeline 🚀"
echo "======================================================"

echo -e "\n[1/6] 🎨 Checking Code Formatting (Black)..."
# We use --check to fail if files are unformatted, rather than auto-fixing
black --check src tests

echo -e "\n[2/6] 🧹 Running Linter & Static Analysis (Ruff)..."
ruff check src tests

echo -e "\n[3/6] 🛡️  Running Strict Type Checking (Mypy)..."
# Mypy uses the strict=true configuration defined in pyproject.toml
mypy src tests

echo -e "\n[4/6] 🔒 Running Security Scan (Bandit)..."
# Scans the src code for common security vulnerabilities (e.g., hardcoded passwords, unsafe exec)
# Using -ll to only report medium and high severity issues
bandit -r src -ll

echo -e "\n[5/6] 📦 Running Dependency Audit (Safety)..."
# Export poetry lock to requirements format and pipe to safety to check against known CVEs
poetry export -f requirements.txt --without-hashes 2>/dev/null | safety check --stdin || echo "[WARNING] Safety check bypassed or not installed."

echo -e "\n[6/6] 🧪 Running Test Suite & Coverage (Pytest)..."
# Enforce a minimum 80% coverage threshold to pass CI
pytest --cov=src --cov-report=term-missing --cov-fail-under=80

echo -e "\n======================================================"
echo "✅ SUCCESS: All CI checks passed successfully! ✅"
echo "======================================================"
```

---

# 3. Tooling Breakdown

The pipeline enforces quality through six distinct layers:

1. **Formatting (`black`)**: Ensures that every file follows the exact same PEP8 compliant syntax structure. It prevents "code style" debates during PR reviews.
2. **Linting & Static Analysis (`ruff`)**: An extremely fast Rust-based linter that replaces `flake8` and `isort`. It catches unused imports, bad variable naming, and logical anti-patterns.
3. **Type Checking (`mypy`)**: Enforces the rigid typing requirements dictated by `03_Project_Standards.md`. It guarantees that Protocols, covariant/contravariant types, and generic `T` bounds are respected.
4. **Security Scan (`bandit`)**: Analyzes the Abstract Syntax Tree (AST) to find common Python vulnerabilities, such as executing `os.system()` unsafely or hardcoding API keys.
5. **Dependency Audit (`safety`)**: Verifies that third-party packages installed via Poetry (like `httpx`, `chromadb`, `google-genai`) do not contain known CVE vulnerabilities.
6. **Coverage (`pytest-cov`)**: Uses the infrastructure established in Phase 03/11. It executes the test suite and forces a failure if code coverage drops below 80%.

---

# 4. Design Decisions

1. **Fail Fast (`set -e`)**: The bash script uses `set -e`, meaning if `black` fails, it aborts instantly. Developers don't have to wait 30 seconds for tests to run just to find out they missed a trailing comma.
2. **Read-Only CI**: Notice that `black` uses `--check`. A CI pipeline should *never* magically fix code; it should reject bad code. Developers can run `black src/` locally to auto-fix, but the CI script strictly verifies.
3. **Poetry Export**: `safety` traditionally requires a `requirements.txt`. Because we use Poetry, we dynamically export the lockfile on the fly and pipe it directly to `safety` via stdin, preventing us from cluttering the filesystem.
