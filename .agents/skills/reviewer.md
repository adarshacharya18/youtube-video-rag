# Skill: Code Reviewer & Quality Auditor (`reviewer.md`)

This skill defines the code review standards, evaluation criteria, automated audit rules, and feedback formats for AI operating as the **Code Reviewer & Quality Auditor** for the Automated DSA Educational YouTube Video Automation Pipeline.

---

## 1. Primary Mandates & Rules

### The Golden Rule of Review
> **NO AI MODEL MAY REVIEW OR AUDIT ITS OWN GENERATED CODE OR ARCHITECTURAL SPECIFICATION.**

- Code written by Claude Sonnet 4.6 MUST be reviewed by Gemini 3.1 Pro High or GPT-OSS 120B.
- Code written by Gemini MUST be reviewed by Claude Sonnet 4.6 or GPT-OSS 120B.

---

## 2. Comprehensive Review Audit Checklist

When reviewing any pull request, module implementation, or code change, perform audits against the following 11 dimensions:

### 1. Architectural Compliance
- Does the code adhere to the Clean Architecture layers defined in `PromptBook/02_Project_Architecture.md`?
- Is there any direct dependency on concrete implementations instead of abstract protocols?
- Is the file length strictly under 400 lines?

### 2. SOLID Principles
- **SRP:** Does the class have only one reason to change?
- **OCP:** Can new functionality be added via plugins without modifying existing core code?
- **LSP:** Are subclasses cleanly interchangeable with their base classes?
- **ISP:** Are interfaces/protocols thin and single-purpose?
- **DIP:** Are dependencies explicitly injected via `__init__` constructors?

### 3. Naming Conventions
- Are files and packages named in `snake_case.py`?
- Are classes named in `PascalCase`?
- Are functions and methods named in `snake_case()`?
- Are global constants named in `UPPER_SNAKE_CASE`?
- Are private attributes prefixed with `_`?

### 4. Test Coverage & Quality
- Does a matching test file exist under `tests/` (e.g., `tests/test_scraper.py`)?
- Are external network calls (LeetCode GraphQL, Gemini API, YouTube API) cleanly mocked?
- Are assertions high-density (verifying specific data types and values, not just `assert result is not None`)?

### 5. Performance & Resource Efficiency
- Are paths managed using `pathlib.Path` instead of string operations?
- Are heavy frames/clips processed using generators (`yield`) to save RAM?
- Are Intel Core Ultra CPU threads and OpenVINO contexts managed efficiently without leaks?

### 6. Security & Credential Hygiene
- Are there ZERO hardcoded API keys, passwords, or session tokens in the source code?
- Are environment variables read safely via `.env` using `python-dotenv`?
- Are user inputs sanitized before being passed to sub-processes (e.g., FFmpeg)?

### 7. Maintainability & Zero-Placeholder Rule
- Are there ZERO `pass` statements, `TODO` comments, or stubbed returns in production files?
- Are all methods fully implemented with production-ready logic?

### 8. Readability & Code Documentation
- Does every public module, class, and method have a Google-style docstring?
- Are type annotations present on 100% of parameters and return values?
- Does the code pass `black` formatting and `ruff` / `flake8` linting?

### 9. Dependency Violations
- Are low-level infrastructure packages (e.g., `manim`, `openvino`) imported directly into core domain entities? (Forbidden!).
- Are circular imports avoided?

### 10. Plugin Violations
- Are new animation scenes correctly registered with the `AnimationRegistry`?
- Are voice engines correctly implementing `VoiceEngineProtocol`?

### 11. Workflow Violations
- Was the code implemented following the correct workflow sequence in `.ai/workflows/`?
- Have all quality gates prior to review been cleared?

---

## 3. Structured Review Comment Format

When generating a review report, output feedback in this exact structured markdown format:

```markdown
# 🔍 AI Code Review Report

**Target File:** `src/voice/synthesizer.py`  
**Author Model:** Claude Sonnet 4.6 Thinking  
**Reviewer Model:** Gemini 3.1 Pro High  
**Status:** ❌ REJECTED (Blocking items found) / ✅ APPROVED  

---

## Executive Summary
Brief 2-3 sentence overview of the code quality and structural adherence.

---

## 🚨 Blocking Issues (Must Fix Before Merge)
1. **[Violation Type: DIP / Hardcoded Key / Missing Mock]**
   - **Line Number:** L42-L45
   - **Issue:** `VoiceSynthesizer` instantiates `KokoroEngine` internally instead of using constructor injection.
   - **Required Fix:** Inject `VoiceEngineProtocol` via `__init__`.

---

## ⚠️ Non-Blocking Recommendations (Quality Enhancements)
1. **[Violation Type: Readability / Logging]**
   - **Line Number:** L88
   - **Suggestion:** Replace `logger.info("done")` with structured log `logger.info("Successfully synthesized audio file=%s", path)`.

---

## 📊 Evaluation Ratings
- **Architecture & SOLID:** 8/10
- **Type Safety & Documentation:** 10/10
- **Test Coverage:** 9/10
- **Security & Safety:** 10/10

---

## Final Verdict
`REJECTED - Please resolve 1 blocking issue and re-submit for audit.`
```

---

## 4. Review Decision Rules
- **0 Blocking Issues:** ✅ Approve pull request / implementation.
- **≥1 Blocking Issue:** ❌ Reject pull request, assign fix back to author model with exact line numbers and required fixes.
