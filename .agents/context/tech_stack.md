# Context: Technology Stack & Performance Optimizations (`tech_stack.md`)

This document details the software libraries, frameworks, hardware acceleration configs, and API rate-limiting strategies for the Automated DSA Educational YouTube Video Automation Pipeline.

---

## 1. Core Technology Stack

- **Runtime Environment:** Python 3.12+ on Ubuntu 25.10 LTS
- **Scraper:** `requests` + LeetCode GraphQL API (`https://leetcode.com/graphql`)
- **RAG & Indexing:** LlamaIndex + ChromaDB (Local persistent `data/vector_store/`)
- **LLM API Client:** `google-genai` SDK (`gemini-2.5-flash`)
- **Embeddings:** Gemini `text-embedding-004` (768-dim)
- **Voice Synthesizer:** Kokoro-82M TTS model + OpenVINO runtime
- **Animation Engine:** Manim Community Edition (CE) + `manim-dsa`
- **Video Assembler:** FFmpeg + `ffmpeg-python`
- **YouTube API Client:** `google-api-python-client` (YouTube Data API v3)
- **Testing:** `pytest` + `unittest.mock`

---

## 2. API Rate-Limiting & Retry Strategy (Gemini 15 RPM)

The Gemini 2.5 Flash free tier enforces a rate limit of **15 Requests Per Minute (RPM)** and **1,500 Requests Per Day**.

### Exponential Backoff & Retry Protocol
- **Retry Decorator:** All calls to Gemini LLM and Embedding endpoints wrapped with `tenacity` retry decorators.
- **Backoff Configuration:** `stop=stop_after_attempt(5)`, `wait=wait_random_exponential(min=4, max=60)`.
- **Handling HTTP 429:** On `ResourceExhausted` (HTTP 429 Rate Limit), system sleeps automatically for 60 seconds before retrying.
- **In-Memory & SQLite Caching:** All embedding queries checked against local SQLite cache (`data/vector_store/cache.sqlite`) to eliminate unnecessary API requests.

---

## 3. Hardware Acceleration & OpenVINO Optimization (Intel Core Ultra 7)

Target Hardware: **Intel Core Ultra 7 155H** (16 Cores / 22 Threads) with integrated **Intel Arc GPU** (8 Xe Cores) and **Intel AI Boost NPU**.

### OpenVINO Runtime Tuning
- **Model Compilation:** Kokoro-82M TTS model exported to OpenVINO Intermediate Representation (IR) format (`.xml` / `.bin`).
- **Device Selection Priority:**
  1. Primary: `NPU` (Power-efficient neural processing for sustained background TTS).
  2. Fallback: `GPU` (Intel Arc GPU acceleration).
  3. Default: `CPU` (Optimized multi-threaded CPU inference using OpenVINO auto-threading).
- **Execution Performance:** Generates 15 minutes of audio narration in **under 3-5 minutes** locally.

### Manim Hardware Acceleration
- Manim CE configured to render using Cairo / Pyglet graphics accelerated by the integrated Intel Arc GPU driver.
