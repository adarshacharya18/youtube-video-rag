# Handoff Report — Empirical Challenger 2 (Phase 14)

**Target Deliverable:** `/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase14/01_Production_Architecture.md`  
**Working Directory:** `/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase14/.agents/teamwork_preview_challenger_m3_2`  
**Handoff Type:** Hard  

---

## 1. Observation

Direct observations and empirical evidence gathered from `01_Production_Architecture.md` and executed test suites:

1. **CPU Pinning Topology (`01_Production_Architecture.md`, lines 712–720):**
   - Table assigns `taskset -c 6,7` to "E-Cores 6, 7", `taskset -c 8,9` to "E-Cores 8, 9", and `taskset -c 10,11,12,13` to "E-Cores 10, 11, 12, 13".
   - Executing `python3 test_hardware_pinning.py` outputs:
     `❌ ERROR: MISMAPPED: Claimed E-Cores 6, 7, but taskset [6, 7] maps to P-Core threads [6, 7]!`
     `❌ ERROR: MISMAPPED: Claimed E-Cores 8, 9, but taskset [8, 9] maps to P-Core threads [8, 9]!`
     `Total CPU Thread Conflicts: 6 logical CPU cores shared concurrently.`

2. **NPU Semaphore Lock Scope (`01_Production_Architecture.md`, lines 364 & 427):**
   - Line 364 specifies `NPU_SEMAPHORE = asyncio.Semaphore(1)` while line 427 specifies subprocess isolation (`subprocess.run(...)`).
   - Executing `python3 test_hardware_pinning.py` outputs:
     `Subprocesses executed concurrently without asyncio.Semaphore control! Active concurrent hardware accesses = 2`
     `❌ CRITICAL VULNERABILITY: asyncio.Semaphore(1) provides NO inter-process locking across Manim/FFmpeg/TTS subprocess boundaries!`

3. **Docker Container Permissions (`01_Production_Architecture.md`, lines 572, 576, 604–606):**
   - Line 572 creates `pipelineuser` (UID 1000). Line 576 sets `USER pipelineuser`.
   - Executing `python3 test_container_k8s.py` outputs:
     `❌ CRITICAL DEFECT: Container switches to unprivileged 'pipelineuser' (UID 1000) WITHOUT 'render', 'video', or 'accel' group membership or 'group_add' in docker-compose.`

4. **Kubernetes Device Mounts (`01_Production_Architecture.md`, lines 650–688):**
   - Spec contains `gpu.intel.com/i915: "1"`, but no `/dev/accel` or `/dev/dri` volume mounts.
   - Executing `python3 test_container_k8s.py` outputs:
     `❌ CRITICAL DEFECT: Kubernetes manifest COMPLETELY OMITS Intel AI Boost NPU device pass-through!`

5. **Saga Transaction Rollback (`01_Production_Architecture.md`, lines 336–340):**
   - Lines 336–340 describe unlinking WAV and MP4 files, but omit updating `artifact_registry.json` or database state.
   - Executing `python3 test_saga_rollback.py` outputs:
     `❌ LEDGER DESYNCHRONIZATION: Artifact 'scene_1' registered in ledger, but disk file '/.../scratch/scene_1.mp4' was deleted by Saga compensation!`
     `❌ DB INTEGRITY FAILURE: UNIQUE constraint failed: documents.slug`

---

## 2. Logic Chain

1. **Observation 1 $\rightarrow$ Inference:** On Linux kernel for Intel Core Ultra 7 155H, logical CPUs 0–11 are 6 P-Cores with HyperThreading. Assigning `taskset -c 6,7` and `8,9` targets P-Cores 3 & 4 rather than E-Cores. Because Manim rendering also runs on P-Cores 3–5 (threads 6–11), 6 out of 10 configured logical cores suffer 100% thread contention.
2. **Observation 2 $\rightarrow$ Inference:** Python `asyncio.Semaphore` operates exclusively inside a single event loop process. Subprocesses spawned via `subprocess.run` (Manim/FFmpeg) or separate workers bypass `asyncio.Semaphore(1)`, exposing `/dev/accel/accel0` to concurrent driver access and driver segmentation faults.
3. **Observation 3 $\rightarrow$ Inference:** Host device nodes `/dev/dri/renderD128` and `/dev/accel/accel0` are owned by `root:render`/`root:video` (mode `0660`). Running as UID 1000 without supplementary group membership (`render`/`video`/`accel`) or `group_add` results in `PermissionDeniedError (EACCES)`.
4. **Observation 4 $\rightarrow$ Inference:** Kubernetes CRI runtimes isolate host device nodes by default. Omitting `/dev/accel/accel0` hostPaths or NPU device plugin limits prevents OpenVINO from finding NPU hardware inside K8s pods (`DeviceNotFound`).
5. **Observation 5 $\rightarrow$ Inference:** Saga compensation unlinks media files from disk without updating `artifact_registry.json` or purging SQLite/ChromaDB records. Consequently, state re-hydration fails with `FileNotFoundError`, and retrying a failed slug triggers SQLite primary key collisions and vector embedding duplicates.

---

## 3. Caveats

- Tests were run on Linux system host environment using standalone empirical test harnesses (`test_hardware_pinning.py`, `test_container_k8s.py`, `test_saga_rollback.py`).
- Physical NPU driver calls were simulated where hardware drivers required root capabilities, but permission masks and device node paths reflect canonical Ubuntu 25.10 kernel 6.11+ specs.

---

## 4. Conclusion

`01_Production_Architecture.md` requires architectural revisions prior to implementation approval:
1. Re-map Section 5.3 `taskset` CPU masks to match Ultra 7 155H logical CPU topology (P-Cores 0–11, E-Cores 12–19).
2. Replace `asyncio.Semaphore(1)` with inter-process locks (`fcntl.flock`) for OpenVINO NPU access.
3. Add `usermod -aG render,video pipelineuser` in Dockerfile and `group_add` in docker-compose.
4. Mount `/dev/accel/accel0` and `/dev/dri` in `k8s-deployment.yaml`.
5. Update Saga compensation handlers to clean `artifact_registry.json` and tombstone SQLite/ChromaDB records, backed by a persistent Write-Ahead Log (`data/saga_wal.json`).

---

## 5. Verification Method

Run the empirical test harnesses in `/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase14/.agents/teamwork_preview_challenger_m3_2/`:

```bash
# 1. Hardware Pinning & NPU Lock Test
python3 /home/adarsh/Documents/Youtube-Channel/PromptBook/Phase14/.agents/teamwork_preview_challenger_m3_2/test_hardware_pinning.py

# 2. Container & K8s Manifest Test
python3 /home/adarsh/Documents/Youtube-Channel/PromptBook/Phase14/.agents/teamwork_preview_challenger_m3_2/test_container_k8s.py

# 3. Saga Rollback & Ledger Test
python3 /home/adarsh/Documents/Youtube-Channel/PromptBook/Phase14/.agents/teamwork_preview_challenger_m3_2/test_saga_rollback.py
```

Inspect generated report:
`/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase14/.agents/teamwork_preview_challenger_m3_2/challenge_report.md`
