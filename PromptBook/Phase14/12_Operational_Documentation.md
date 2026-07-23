# Phase 14 / 12: Operational Documentation (Runbook)

**Author:** Principal Site Reliability Engineer (SRE)  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Startup & Shutdown Procedures](#2-startup--shutdown-procedures)
3. [Deployment Pipeline](#3-deployment-pipeline)
4. [Backup & Restore](#4-backup--restore)
5. [Monitoring & Health](#5-monitoring--health)
6. [Troubleshooting & Incident Response](#6-troubleshooting--incident-response)
7. [Routine Maintenance](#7-routine-maintenance)

---

# 1. Executive Summary
This Runbook serves as the canonical operations manual for the DSA Pipeline. Because this system is a 12-hour batch processor (scraping, LLM generation, Manim rendering, uploading), interrupting the process or botching a deployment carries massive time penalties. This document defines the exact commands required to operate the system safely.

---

# 2. Startup & Shutdown Procedures

### 2.1 Graceful Startup
The pipeline is designed to run idempotently. You do not need to "clear" the database before starting.
```bash
# 1. Activate the environment
source /opt/dsa_pipeline/.venv/bin/activate

# 2. Export strict production profile
export PIPELINE_ENV=production

# 3. Trigger the Operations CLI
python -m src.cli.ops health
python -m src.core.orchestrator.pipeline
```

### 2.2 Graceful Shutdown (SIGINT)
**Do NOT use `kill -9`.** 
Send `SIGINT` (Ctrl+C) to the orchestrator. The pipeline will intercept the signal, finish the *current* video chunk (e.g., waiting for the current 2-minute FFmpeg render to finish), write the checkpoint to the SQLite Ledger, and exit cleanly.

### 2.3 Emergency Shutdown (SIGKILL)
If Manim hangs entirely (C-level segfault in libcairo), you may be forced to use `SIGKILL`. 
1. `kill -9 <PID>`
2. Because the process was killed violently, FFmpeg may leave massive `.mp4.part` files in the `/tmp/` directory. You **must** manually clear `/var/lib/dsa_pipeline/cache/` to prevent disk exhaustion.

---

# 3. Deployment Pipeline

Deployments must NEVER be performed while the Orchestrator is running.
```bash
# 1. Gracefully stop the current batch
# (Wait for process to exit)

# 2. Run the deployment wrapper (runs tests, checks FFmpeg, creates release)
python -m src.cli.ops deploy

# 3. Start the Orchestrator again
python -m src.core.orchestrator.pipeline
```
*Note: `ops deploy` automatically generates an immutable `.tar.gz` and logs the SHA-256 checksum in `releases/release_history.json`.*

---

# 4. Backup & Restore

### 4.1 Automated Backups
The SQLite Ledger (`prod_ledger.sqlite`) contains the sole source of truth for which videos have been published and which are pending.
- A chron job automatically creates a `.bak` copy of the SQLite database every night at 02:00 AM.
- `ops deploy` automatically creates a point-in-time backup before executing.

### 4.2 Restoring from Catastrophic Failure
If a migration or bad deployment corrupts the State Ledger:
```bash
# 1. View available backups
ls -la /var/lib/dsa_pipeline/backups/

# 2. Restore the database using the Ops CLI
python -m src.cli.ops rollback --file /var/lib/dsa_pipeline/backups/prod_ledger_20260723.sqlite
```

---

# 5. Monitoring & Health

### 5.1 Real-Time Status
To see exactly what the pipeline is doing right now without parsing a 2GB log file:
```bash
python -m src.cli.ops status
```
*Expected Output:* `vid_12345: [PHASE_13] RUNNING`

### 5.2 Datadog / ELK Integration
The Orchestrator utilizes the `ObservabilityManager` to output strict JSON logs to `/var/log/dsa_pipeline/orchestrator.json`. Ensure your Datadog agent is configured to ingest this file. Search for `event_type: "security_audit"` or `level: "ERROR"`.

---

# 6. Troubleshooting & Incident Response

### Incident: LLM Hallucinated Bad Manim Syntax
**Symptom:** Pipeline halts or skips a video, stating Phase 13 failed.
**Action:**
1. Run `python -m src.cli.ops diagnose`. This will parse the Dead Letter Queue (`dlq.jsonl`) and print the exact stack trace.
2. If the error is an unrecoverable hallucination (e.g., Manim `SyntaxError`), manually edit the generated `scene.py` file in the cache directory, and run the system again. The ledger will automatically pick up where it left off.

### Incident: FFmpeg Out of Memory (OOM)
**Symptom:** Kernel logs (`dmesg -T`) show the OOM Killer terminated the `ffmpeg` subprocess.
**Action:**
1. FFmpeg attempted to stitch too many 4K chunks simultaneously. 
2. Edit the `.env` file or export `MANIM_QUALITY=low_quality` to drop the resolution, or increase the EC2 instance's swap space.

### Incident: YouTube API Quota Exceeded
**Symptom:** Logs show HTTP 403 Quota Exceeded.
**Action:**
The system is designed to handle this via `ExponentialBackoff`. However, YouTube quotas reset at midnight Pacific Time. Stop the pipeline gracefully, and resume it tomorrow.

---

# 7. Routine Maintenance

1. **Cache Purging:** Every 7 days, run a cron job to `rm -rf /var/lib/dsa_pipeline/cache/*` to delete old `.mp4` chunks from videos that have already been successfully uploaded.
2. **Ledger Compaction:** Once a month, execute `VACUUM;` on the SQLite ledger to reclaim disk space from completed state transitions.
