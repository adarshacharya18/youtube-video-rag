## 2026-07-24T05:55:34Z
<USER_REQUEST>
You are Worker 2 for Phase 02 Knowledge Ingestion of the Automated DSA Educational YouTube Video Pipeline.

Your working directory is: /home/adarsh/Documents/Youtube-Channel/.agents/teamwork_preview_worker_phase02_2

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Tasks:
Fix 6 specific edge cases identified by Reviewer 2 and Challenger 1 in `src/core/ingestion/sanitizer.py`, `src/core/ingestion/parser.py`, and `tests/ingestion/test_parser.py`:

1. **HTML Entity & Tag Cleaning Order (`src/core/ingestion/sanitizer.py`)**:
   - Convert `<sup>(...)</sup>` to `^\\1` and `<sub>(...)</sub>` to `_\\1` FIRST.
   - Unescape HTML entities BEFORE or DURING tag stripping so that `&lt;p&gt;text&lt;/p&gt;` gets stripped of `<p>` tags cleanly rather than leaking raw `<p>` tags into markdown.

2. **Math Exponent Preservation (`src/core/ingestion/sanitizer.py`)**:
   - Ensure `10<sup>5</sup>` and `2<sup>3</sup>` become `10^5` and `2^3` rather than `105` and `23`.

3. **Problem Number <= 0 Validation (`src/core/ingestion/sanitizer.py`)**:
   - Validate that `number > 0` ALWAYS raises `ValueError("Problem number must be a positive integer")` regardless of whether `number` came from `data["number"]` or title regex extraction (e.g. `# 0. Title`).

4. **Code Block Section Scoping (`src/core/ingestion/parser.py`)**:
   - Prevent illustrative code fences inside `DESCRIPTION` or `EXAMPLES` from hijacking `accepted_code`. Only set `accepted_code` when `current_section` is `CODE` or `SOLUTION`, or explicitly designated.

5. **Single-Line Example Regex (`src/core/ingestion/parser.py`)**:
   - Update `_parse_examples` regex lookahead to handle same-line `Input: ..., Output: ...` without bleeding `Output:` into `input`.

6. **Emoji Title Slug Fallback (`src/core/ingestion/sanitizer.py`)**:
   - If title slug filtering results in empty string (e.g., `# 🚀🔥`), fallback to `f"problem-{number}"` or `"problem"`.

7. **Add Unit & Integration Tests**:
   - Add test cases in `tests/ingestion/test_parser.py` covering each of the 6 edge cases above.

8. **Execute Verification**:
   - Run `.venv/bin/pytest tests/ingestion/test_parser.py -v` using run_command.
   - Confirm all tests pass 100%.

Write your implementation report to:
`/home/adarsh/Documents/Youtube-Channel/.agents/teamwork_preview_worker_phase02_2/changes.md`

Write your handoff report to:
`/home/adarsh/Documents/Youtube-Channel/.agents/teamwork_preview_worker_phase02_2/handoff.md`

Notify orchestrator via send_message when done.
</USER_REQUEST>
