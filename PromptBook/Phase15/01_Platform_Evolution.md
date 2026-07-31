# Phase 15: Platform Evolution Architecture

## Overview

Phase 15 implements the **self-improving evolution layer** that allows the DSA YouTube pipeline to safely upgrade its own components — LLM models, prompt templates, plugins, and schema — without human intervention.  When something regresses, automated kill-switches fire and the platform falls back to the last known-good configuration.

---

## 1. Model Manager — Circuit Breaker Failover

**Module**: `src/core/evolution/model_manager.py`

### Design

The `ModelManager` tracks per-model health via consecutive failure counters.  Each `ModelConfig` has a `max_consecutive_failures` threshold.  Once exceeded the circuit-breaker trips and the model is marked unhealthy.  All subsequent requests are routed to the configured `fallback_id`.

```
ModelConfig("openai", "gpt-4o", "llm", fallback_id="claude-3-5-sonnet", max_consecutive_failures=3)
```

### Key API

| Method | Description |
|--------|-------------|
| `register_model(config)` | Register a model with provider, capability, and fallback |
| `execute_with_fallback(capability, fn)` | Run `fn(model_id)` with automatic failover |
| `get_health_report()` | Snapshot of all model health states |
| `reset_circuit_breaker(model_id)` | Manually restore a tripped model |

### Flow

```
execute_with_fallback("llm", fn)
  → Try gpt-4o → ConnectionError
    → _record_failure(gpt-4o) → count >= threshold → mark unhealthy
    → Try claude-3-5-sonnet → Success ✓
```

---

## 2. Prompt Manager — A/B Testing with Regression Kill-Switch

**Module**: `src/core/evolution/prompt_manager.py`

### Design

The `PromptManager` routes pipeline traffic between a **baseline** prompt and one or more **experimental** variants.  After each pipeline run, quality scores are written to the `FeedbackManager`.  Before selecting a prompt for the next run, the manager computes moving averages and triggers the **regression kill-switch** if the experimental variant's score drops below `baseline_avg - regression_threshold`.

### Kill-Switch Logic

```python
delta = baseline_avg - experimental_avg
if delta >= regression_threshold:
    experimental_prompt.killed = True  # Permanently disabled this session
```

### Key API

| Method | Description |
|--------|-------------|
| `register_prompt(template)` | Register a baseline or experimental variant |
| `select_prompt(run_id)` | Select prompt with kill-switch evaluation |
| `get_prompt_report()` | Snapshot of all prompt states, scores, and kill status |

---

## 3. Feedback Manager — Quality Score Ledger

**Module**: `src/core/evolution/feedback.py`

### Design

SQLite-backed (WAL mode) ledger that stores `FeedbackEntry` records tagged by `prompt_id`.  Provides aggregate queries consumed by the `PromptManager` for regression detection.

### Schema

```sql
CREATE TABLE feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL,
    source TEXT NOT NULL,          -- 'judge', 'human', etc.
    prompt_id TEXT NOT NULL,       -- links to PromptTemplate
    score REAL NOT NULL,           -- 1.0–10.0
    metadata TEXT,                 -- JSON
    timestamp TEXT NOT NULL
);
```

### Key API

| Method | Description |
|--------|-------------|
| `record_feedback(entry)` | Persist a quality score |
| `get_average_score(prompt_id)` | Arithmetic mean for regression checks |
| `get_feedback_count(prompt_id)` | Total entries for a variant |
| `get_all_feedback(prompt_id?)` | Full history, optionally filtered |

---

## 4. Analytics Dashboard — Headless Telemetry

**Module**: `src/core/evolution/analytics_dashboard.py`

### Design

Reads from the production `StateLedger` and `feedback` databases to produce a single JSON report surfacing:

- **Pipeline stats**: total runs, completed, failed, success rate
- **Feedback stats**: per-prompt average scores, entry counts
- **Storage usage**: total artifact bytes on disk

### CLI Access

```bash
python -m src.cli.evolve analytics
```

---

## 5. Compatibility Manager — Semantic Versioning

**Module**: `src/core/evolution/compatibility_manager.py`

Enforces that plugins requiring a future core version are blocked from loading.  Uses simple `major.minor.patch` tuple comparison.

---

## 6. Upgrade Manager — Saga-Pattern Rollback

**Module**: `src/core/evolution/upgrade_manager.py`

### Design

Each upgrade is defined as an `UpgradeTask` with ordered `steps` and paired `rollbacks`.  Before execution a physical state snapshot is created.  If any step raises, completed steps are reversed in LIFO order.

### Flow

```
UpgradeTask("v2.1", steps=[s1, s2, s3], rollbacks=[r1, r2, r3])
  → create_state_snapshot("v2.1")
  → s1() ✓ → s2() ✗
    → r1() (reverse completed steps)
    → restore_state_snapshot("v2.1")
```

---

## 7. CLI Commands

**Module**: `src/cli/evolve.py`

| Command | Description |
|---------|-------------|
| `evolve analytics` | Generate JSON telemetry report |
| `evolve models` | List models and circuit-breaker health |
| `evolve prompts` | List prompt A/B test configurations |
| `evolve feedback --video-id V --score S` | Record manual quality feedback |
| `evolve evaluate --video-id V` | Trigger LLM-as-a-judge evaluation |
| `evolve plugins discover/install/rollback` | Plugin management |
| `evolve upgrade --version X.Y.Z` | Platform upgrade (dry run) |

---

## 8. Test Coverage

**File**: `tests/evolution/test_evolution_suite.py`

| Test | What It Proves |
|------|----------------|
| `test_model_manager_fallback` | Circuit breaker trips after N failures and routes to fallback |
| `test_prompt_ab_testing_and_regression` | Kill-switch fires when experimental score drops below threshold |
| `test_compatibility_manager_semver` | Future-version plugins are rejected |
| `test_analytics_dashboard_storage_calc` | Storage byte calculation is exact |
| `test_upgrade_manager_rollback_saga` | Failed upgrade step triggers LIFO rollback to clean state |

---

## 9. Architecture Diagram

```
┌──────────────────────────────────────────────────┐
│                 Evolution Layer                    │
│                                                    │
│  ┌──────────────┐  ┌──────────────┐               │
│  │ ModelManager  │  │PromptManager │               │
│  │ (Circuit      │  │ (A/B Test +  │               │
│  │  Breaker)     │  │  Kill-Switch)│               │
│  └──────┬───────┘  └──────┬───────┘               │
│         │                  │                        │
│         │         ┌────────▼────────┐              │
│         │         │ FeedbackManager │              │
│         │         │ (SQLite Ledger) │              │
│         │         └────────┬────────┘              │
│         │                  │                        │
│  ┌──────▼──────────────────▼───────┐               │
│  │      AnalyticsDashboard         │               │
│  │   (Headless JSON Reports)       │               │
│  └─────────────────────────────────┘               │
│                                                    │
│  ┌─────────────────┐  ┌──────────────┐            │
│  │CompatibilityMgr │  │UpgradeManager│            │
│  │ (Semver Check)   │  │ (Saga + LIFO)│            │
│  └─────────────────┘  └──────────────┘            │
│                                                    │
│  ┌─────────────────────────────────────┐          │
│  │          CLI: evolve.py             │          │
│  │ analytics | models | prompts | ...  │          │
│  └─────────────────────────────────────┘          │
└──────────────────────────────────────────────────┘
```
