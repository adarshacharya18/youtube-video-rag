# Review Report: Phase 15 Platform Evolution Architecture

**Deliverable under review:** `/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase15/01_Platform_Evolution_Architecture.md`  
**Reviewer:** `reviewer_m3_2`  
**Date:** 2026-07-23  
**Verdict:** **REQUEST_CHANGES**

---

## Executive Summary & Verdict Rationale

The deliverable `01_Platform_Evolution_Architecture.md` presents a comprehensive, well-structured, and realistic architectural specification for Phase 15 (Platform Evolution Architecture). The document effectively aligns with the synchronous 12-hour batch execution model, avoids anti-patterns, and details experiment routing, multi-tier subsystem integration, and safe upgrade strategies.

However, an independent execution test of the production SQL queries against a live SQLite database revealed a **Major Logical Flaw in Query 4 (Prompt Quality Decay Detection)**. The top-level `GROUP BY phase_id` collapses all records per phase *before* the `FIRST_VALUE` and `LAST_VALUE` window functions are evaluated. Consequently, the query always reports `initial_baseline_score == current_rolling_score`, causing `prompt_decay_pct` to permanently evaluate to `0.0%` even when severe prompt quality degradation occurs.

All 4 Mermaid diagrams, the SQLite DDL schema statements, Queries 1–3, the YAML experiment schema, and the `python -m src.cli evolution` subcommands were verified as syntactically valid, operational, and fully consistent with Phase 14 CLI conventions.

---

## Detailed Evaluation by Verification Criteria

### 1. Mermaid Architecture & Flow Diagrams (Requirement 1) — PASS
- **Integration Topology Diagram (Section 7.1):** Valid `flowchart TB`. Correctly represents the 4-tier flow topology from CLI/Config down through the 7 subsystems to `metadata.db`.
- **Sequence Flow Diagram (Section 7.2):** Valid `sequenceDiagram` with `autonumber`. Properly models synchronous item iteration, variant resolution, LLM-as-a-Judge evaluation, and Saga fallback rollback upon error.
- **Experimentation Lifecycle State Machine (Section 7.3):** Valid `stateDiagram-v2`. Properly covers states `DRAFT`, `ACTIVE`, `CANARY`, `CONCLUDED`, `PAUSED`, and `CANCELLED`.
- **Safe Upgrade Flowchart (Section 7.4):** Valid `flowchart TB`. Clear logic flow covering pre-flight validation, canary step-up ($5\% \to 20\% \to 50\% \to 100\%$), State Ledger audits, and auto-kill switch rollbacks.

### 2. SQL Schema & Production Queries (Requirement 2) — REQUEST_CHANGES
- **DDL Table Creation Statements (Section 5.3):** All 6 tables (`experiments`, `experiment_allocations`, `evolution_ledger`, `quality_metrics`, `model_drift_ledger`, `prompt_decay_ledger`) and 4 indices execute without error on SQLite.
- **Query 1 (Variant Performance Comparison, Section 6.1):** Executable and well-formed.
- **Query 2 (Error Trend & Classification, Section 6.2):** Executable and well-formed.
- **Query 3 (Model Drift Detection, Section 6.3):** Executable and well-formed.
- **Query 4 (Prompt Quality Decay Detection, Section 6.4):** **FAILED**. Contains a structural SQL logic defect where `GROUP BY phase_id` collapses rows before `FIRST_VALUE`/`LAST_VALUE` window functions compute, forcing `prompt_decay_pct` to always output `0.0`.

### 3. YAML Experiment Schema & CLI Subcommands (Requirement 3) — PASS
- **YAML Schema (`config/experiments.yaml`, Section 3.4):** Valid YAML format. Realistic parameter overrides (`prompt_template`, `llm_model`, `temperature`), deterministic salt, variant weights summing to 100, and automated safety thresholds.
- **CLI Subcommands (`python -m src.cli evolution`, Section 8):** Operational subcommand syntax (`experiment`, `analytics`, `upgrade`) adhering strictly to Phase 14 CLI conventions (`src/cli/ops.py`).

---

## Detailed Findings

### [Major] Finding 1: Top-level `GROUP BY` in Query 4 nullifies Prompt Quality Decay detection

- **What:** In Section 6.4 (lines 490–517), Query 4 attempts to measure prompt quality decay using `FIRST_VALUE` and `LAST_VALUE` window functions over `RollingScores`, but places `GROUP BY phase_id` at the top level of the `SELECT` query.
- **Where:** `/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase15/01_Platform_Evolution_Architecture.md` (lines 490–517)
- **Why:** In SQL query execution order, `GROUP BY phase_id` groups and collapses all rows for a phase into a single record *before* the outer window functions `FIRST_VALUE(...)` and `LAST_VALUE(...)` execute. Because the window functions run over a single collapsed row, `FIRST_VALUE(rolling_avg_score)` and `LAST_VALUE(rolling_avg_score)` return the exact same score. The resulting `prompt_decay_pct` formula `(initial - current) * 100 / initial` always evaluates to `0.0%`, completely hiding prompt degradation.
- **Verification:** Verified via SQLite execution script `test_q4_deep.py`. When sample scores degraded from 9.5 down to 5.5 (21.05% decay), Query 4 returned `initial=9.5, current=9.5, decay=0.0%`.
- **Suggested Fix:** Separate the window evaluation into a second CTE or subquery before applying `SELECT DISTINCT`, as shown below:

```sql
WITH RollingScores AS (
    SELECT 
        q.judge_model,
        l.phase_id,
        q.evaluated_at,
        q.overall_judge_score,
        AVG(q.overall_judge_score) OVER (
            PARTITION BY l.phase_id, l.variant_id 
            ORDER BY q.evaluated_at 
            ROWS BETWEEN 50 PRECEDING AND CURRENT ROW
        ) AS rolling_avg_score
    FROM quality_metrics q
    JOIN evolution_ledger l ON q.ledger_id = l.ledger_id
),
DecayMetrics AS (
    SELECT 
        phase_id,
        FIRST_VALUE(rolling_avg_score) OVER (
            PARTITION BY phase_id ORDER BY evaluated_at ASC
        ) AS initial_baseline_score,
        LAST_VALUE(rolling_avg_score) OVER (
            PARTITION BY phase_id ORDER BY evaluated_at ASC 
            RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS current_rolling_score
    FROM RollingScores
)
SELECT DISTINCT
    phase_id,
    ROUND(initial_baseline_score, 2) AS initial_baseline_score,
    ROUND(current_rolling_score, 2) AS current_rolling_score,
    ROUND(
        (initial_baseline_score - current_rolling_score) * 100.0 / initial_baseline_score, 
        2
    ) AS prompt_decay_pct
FROM DecayMetrics;
```

---

### [Minor] Finding 2: `SUM(q.hallucination_flag)` returns NULL on non-LLM phase joins

- **What:** In Section 6.1 (Query 1, line 439), `SUM(q.hallucination_flag)` evaluates to `NULL` when an experiment covers non-LLM phases (e.g. Manim rendering or FFmpeg assembly) where `quality_metrics` has no entries.
- **Where:** Section 6.1 (line 439)
- **Why:** `LEFT JOIN quality_metrics` produces `NULL` for `hallucination_flag`. `SUM(NULL)` returns `NULL` instead of `0`.
- **Suggested Fix:** Wrap in `COALESCE`: `COALESCE(SUM(q.hallucination_flag), 0) AS total_hallucinations`.

---

### [Minor] Finding 3: Unquoted comparison operators in Mermaid flowchart/state labels

- **What:** Unquoted `<` and `>` characters inside Mermaid node and edge labels (e.g., lines 629 and 650: `Error rate > 5% OR Judge score < 8.5`).
- **Where:** Section 7.3 (line 629) and Section 7.4 (line 650)
- **Why:** Some DOM-based Mermaid JS parsers treat unquoted `<` and `>` as unclosed HTML tags or syntax tokens.
- **Suggested Fix:** Enclose label text in double quotes: `AuditLedger -- "Error Rate > 5% OR Score < Threshold" --> TriggerKillSwitch`.

---

## Verified Claims

| Claim | Verification Method | Result |
|---|---|---|
| All 4 Mermaid diagrams parse and have valid node flow structures | Line-by-line inspection & block parsing | **PASS** |
| SQLite DDL statements create 6 tables and 4 indexes without errors | Executed DDL script in SQLite memory DB | **PASS** |
| SQL Query 1 (Variant Performance) runs correctly | Executed query on populated SQLite DB | **PASS** |
| SQL Query 2 (Error Classification) runs correctly | Executed query on populated SQLite DB | **PASS** |
| SQL Query 3 (Model Drift) runs correctly | Executed query on populated SQLite DB | **PASS** |
| SQL Query 4 (Prompt Decay) accurately calculates decay | Executed query on populated SQLite DB with decaying scores | **FAIL** (Returns 0.0% decay always) |
| YAML experiment schema is syntactically valid PyYAML | Parsed with `yaml.safe_load()` | **PASS** |
| CLI subcommands match Phase 14 `python -m src.cli` conventions | Compared with `src/cli/ops.py` & `11_Operations_CLI.md` | **PASS** |

---

## Coverage Gaps & Untested Areas

- None. All diagrams, DDL statements, SQL queries, YAML schemas, and CLI subcommands in the deliverable were tested and verified.
