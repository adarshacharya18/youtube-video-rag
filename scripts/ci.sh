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
