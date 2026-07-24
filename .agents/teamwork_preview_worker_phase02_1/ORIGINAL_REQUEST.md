## 2026-07-24T05:50:36Z

<USER_REQUEST>
You are Worker 1 for Phase 02 Knowledge Ingestion of the Automated DSA Educational YouTube Video Pipeline.

Your working directory is: /home/adarsh/Documents/Youtube-Channel/.agents/teamwork_preview_worker_phase02_1

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Tasks:
1. Implement domain dataclasses & enums:
   - `src/models/enums.py`: `Difficulty` Enum (EASY, MEDIUM, HARD).
   - `src/models/problem.py`: `Example` dataclass (input, output, explanation) and `ScrapedProblem` frozen dataclass (slug, title, number, difficulty, description, constraints, examples, tags, accepted_code, code_language, scraped_at), with `to_dict()`/`from_dict()` serialization.
   - `src/models/__init__.py`: Re-export `Difficulty`, `Example`, `ScrapedProblem`.
   - `src/core/ingestion/models.py`: Bridge/re-export models for ingestion subsystem.

2. Implement Data Sanitization & Standardization (`src/core/ingestion/sanitizer.py`):
   - `MarkdownSanitizer` / `DataSanitizer` class.
   - HTML entity unescaping, tag stripping, code block indentation preservation, whitespace normalization.
   - Title, difficulty, tag cleaning and standardization.
   - Standardize outputs into `ScrapedProblem` and `Example` dataclasses with strict fail-fast validation.

3. Implement Markdown & AST Parsing (`src/core/ingestion/parser.py`):
   - Robust AST parsing using `markdown-it-py` (v3.0.0) and `bs4` (v4.13.3) instead of brittle regex.
   - AST token traversal for headings (# Title, ## Description, ## Examples, ## Constraints, ## Solution / Code), fenced code blocks, list items, and HTML blocks.
   - Extract problem metadata, difficulty, tags, description, constraints list, examples list, and accepted solution code (Python/C++).
   - Return fully parsed and sanitized `ScrapedProblem` instances.

4. Write Ingestion Strategy Documentation (`PromptBook/Phase02/01_Ingestion_Strategy.md`):
   - Document the complete architecture for Markdown/HTML parsing, AST token traversal with `markdown-it-py`, sanitization pipeline, data model contracts, error handling strategies, and performance guidelines.

5. Create Synthetic Mock Markdown Fixtures (`tests/fixtures/ingestion/`):
   - `two_sum.md` (canonical Array/Hash Table DSA problem)
   - `reverse_linked_list.md` (Linked List problem)
   - `binary_tree_level_order.md` (Tree BFS problem)
   - `messy_html_problem.md` (Messy HTML tags, unescaped entities)
   - `varied_code_headers_problem.md` (Varied section titles, non-standard code fence headers)
   - `missing_optional_fields.md` (Missing tags or explanations)
   - `malformed_invalid_problem.md` (Malformed syntax for invalid testing)

6. Implement Test Suite (`tests/ingestion/test_parser.py`):
   - Unit & integration tests validating `DSAParser` and `MarkdownSanitizer`.
   - Assert `pytest tests/ingestion/test_parser.py` runs and passes 100%.

7. Execute Test & Verification Commands:
   - Run `pytest tests/ingestion/test_parser.py -v` using run_command.
   - Document all test outcomes and commands in your handoff report.

Write your implementation report to:
`/home/adarsh/Documents/Youtube-Channel/.agents/teamwork_preview_worker_phase02_1/changes.md`

Write your handoff report to:
`/home/adarsh/Documents/Youtube-Channel/.agents/teamwork_preview_worker_phase02_1/handoff.md`

Notify orchestrator via send_message when done.
</USER_REQUEST>
