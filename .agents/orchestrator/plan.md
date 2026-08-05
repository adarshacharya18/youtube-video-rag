# Orchestration Plan: Voice Production Subsystem (TTS Integration)

## Objective
Implement the Voice Production Subsystem (TTS Integration) for the automated DSA video pipeline, fulfilling all requirements R1, R2, R3, and acceptance criteria specified in `ORIGINAL_REQUEST.md`.

## Workflow Phases
1. **Phase 0: Survey & Discovery**
   - Dispatch 3 Explorers (including spec_miner if needed) to analyze:
     - `PromptBook/Phase13/02_Voice_Production.md`
     - Existing TTS code stub `src/voice/synthesizer.py` / `src/core/media/voice.py`
     - Node implementation `src/pipeline/nodes/voice_generator_node.py`
     - Pipeline runner `src/cli/ops.py` and test suite setup
     - Hardware environment (CPU/integrated GPU requirements, available packages like kokoro, edge-tts, pyttsx3, etc.)

2. **Phase 1: Project Architecture & Decomposition**
   - Synthesize survey findings into `PROJECT.md`.
   - Define milestones, interface contracts, and code layout.

3. **Phase 2: Milestone Execution Loop (Explorer -> Worker -> Reviewer -> Challenger -> Auditor)**
   - Milestone 1: Implement `VoiceProviderProtocol`, `KokoroVoiceProvider` (or CPU fallback), and `ManualVoiceProvider`.
   - Milestone 2: Update `VoiceGeneratorNode` in `src/pipeline/nodes/voice_generator_node.py` to use provider and synthesize `master_audio.wav`.
   - Milestone 3: Unit testing and End-to-End verification via CLI ops run command (`python src/cli/ops.py run --slug reorder-list --solution-id 4163684`).

4. **Phase 3: Final Gate & Reporting**
   - Run full gate checks (Reviewers, Challenger, Forensic Auditor).
   - Verify `data/audio/reorder-list/master_audio.wav` size > 0 bytes.
   - Message parent / Sentinel upon successful completion.
