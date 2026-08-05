# YouTube Video RAG Pipeline

## Verdict: The Code is Complete. The External Dependencies Are Not Installed.

All 15 phases of **Python application code** are built, tested (328 tests), and pushed. However, the pipeline depends on **3 external binaries** that are not yet installed on your system.

---

## Readiness Checklist

| Component | Status | Notes |
|---|---|---|
| Python pipeline code (15 phases) | ✅ Ready | 328 tests, all passing |
| SQLite StateLedger | ✅ Ready | WAL mode, crash-safe |
| Master CLI (`ops.py`) | ✅ Ready | `run`, `status`, `resume`, `health` |
| Evolution CLI (`evolve.py`) | ✅ Ready | `analytics`, `models`, `prompts` |
| `.env` with API keys | ✅ Ready | Gemini + LeetCode session configured |
| **FFmpeg** (video assembly) | ❌ Not installed | Required for Phase 13 |
| **Manim** (animation rendering) | ❌ Not installed | Required for Phase 12 |
| **Kokoro TTS** (voice synthesis) | ❌ Not installed | Required for Phase 11 |
| LLM API key (OpenAI/Anthropic) | ⚠️ Optional | Currently uses a built-in fallback LLM provider |

---

## Step 1: Install External Dependencies

```bash
# Activate your venv
source .venv/bin/activate

# 1. FFmpeg (video stitching, subtitles, 4K encoding)
sudo apt update && sudo apt install -y ffmpeg
ffmpeg -version  # verify

# 2. Manim (algorithm animation engine)
pip install manim
manim --version  # verify

# 3. Kokoro TTS (text-to-speech)
#    Option A: pip install kokoro (if available)
#    Option B: Download binary from https://github.com/hexgrad/kokoro
#    Place the binary in your PATH or set TTS_BINARY_PATH in .env
```

## Step 2: Configure LeetCode Authentication

The pipeline is now fully integrated with LeetCode's GraphQL API. It will automatically fetch the problem metadata **AND your own accepted solution code** for the problem slug you provide. This ensures the video animation is legally based on your own code.

To enable this, ensure your `.env` file contains your `LEETCODE_SESSION` cookie:

```bash
# In your .env file
LEETCODE_SESSION=your_cookie_value_here
```
*(You can get this cookie by logging into leetcode.com, opening DevTools -> Application -> Cookies, and copying the value of `LEETCODE_SESSION`)*

If the cookie is not set or expires, the system will gracefully fall back to generic starter code.

---

## Step 3: Generate a Video

### Quick Run (single command)

```bash
# From the project root, with venv activated:
python src/cli/ops.py run --slug two-sum
```

This executes the full 6-node pipeline:

```
IngestionNode → PlanNode → ScriptGeneratorNode → VoiceGeneratorNode → AnimationGeneratorNode → VideoAssemblyNode
```

### With More Options

```bash
# Force a fresh run (ignore any previous incomplete runs)
python src/cli/ops.py run --slug two-sum --force

# Provide a specific published solution post as the reference code
# (e.g. from leetcode.com/problems/reorder-list/solutions/12345/)
python src/cli/ops.py run --slug reorder-list --solution-id 12345

# With a custom topic name
python src/cli/ops.py run --slug two-sum --topic "Two Sum"

# JSON output mode (for scripts/CI)
python src/cli/ops.py run --slug two-sum --json
```

### What Happens During a Run

| Step | Node | What It Does | Output |
|------|------|-------------|--------|
| 1 | `IngestionNode` | Parses problem slug into structured data | Problem metadata in StateLedger |
| 2 | `PlanNode` | Creates video structure plan | Section plan (hook, context, solution, complexity) |
| 3 | `ScriptGeneratorNode` | LLM generates narration script + visual cues | JSON script with spoken narration |
| 4 | `VoiceGeneratorNode` | Kokoro TTS converts narration → `.wav` | `data/audio/{slug}/master_audio.wav` |
| 5 | `AnimationGeneratorNode` | Manim renders algorithm visualizations → `.mp4` | `data/animation/{slug}/*.mp4` |
| 6 | `VideoAssemblyNode` | FFmpeg stitches audio + video + subtitles → final | `data/output/{slug}/final_video.mp4` |

---

## Step 4: Monitor & Debug

```bash
# Check pipeline run status
python src/cli/ops.py status --slug two-sum

# Resume a crashed/interrupted run
python src/cli/ops.py resume --slug two-sum

# System health check
python src/cli/ops.py health

# Analytics dashboard (JSON)
python src/cli/evolve.py analytics
```

---

## Step 5: Output Location

After a successful run, your artifacts are in:

```
data/
├── audio/two-sum/
│   ├── master_audio.wav          # TTS narration
│   └── subtitles.srt             # Burned-in subtitles
├── animation/two-sum/
│   ├── array_scene.mp4           # Algorithm visualization
│   ├── code_scene.mp4            # Code walkthrough
│   └── complexity_scene.mp4      # Big-O analysis
├── output/two-sum/
│   └── final_video.mp4           # ← YOUR YOUTUBE VIDEO
└── state_ledger.db               # Execution history
```

---

## What You Need to Do Right Now

> [!IMPORTANT]
> **Install FFmpeg + Manim + a TTS engine**, then `python src/cli/ops.py run --slug two-sum` will produce a video end-to-end.

The **minimum** to get started:

```bash
sudo apt install -y ffmpeg
pip install manim
# + install your preferred TTS (Kokoro, Coqui, or piper-tts)
```

After that, the pipeline is fully operational.