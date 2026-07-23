# Phase01/06_Configuration_System.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Canonical

---

# Table of Contents

1. [Purpose & Philosophy](#1-purpose--philosophy)
2. [Override Precedence](#2-override-precedence)
3. [Directory Layout](#3-directory-layout)
4. [Profiles (Environments)](#4-profiles-environments)
5. [Configuration Sources](#5-configuration-sources)
6. [Secrets Management](#6-secrets-management)
7. [Typed Configuration & Validation](#7-typed-configuration--validation)
8. [Loading & Bootstrapping Flow](#8-loading--bootstrapping-flow)
9. [Best Practices](#9-best-practices)

---

# 1. Purpose & Philosophy

The Configuration System manages all runtime behaviors, API boundaries, tuning parameters, and feature flags. It abstracts away the complexity of merging multiple sources (YAML, JSON, `.env`, Environment Variables, and CLI args) into a single, **strongly typed, immutable** global configuration object.

**Core Philosophy:**
- **Strictly Typed:** Configuration values are verified at application startup. If a config is missing or malformed, the pipeline fails instantly before processing begins.
- **Immutable:** Once parsed, configuration objects are `frozen=True`. They cannot be modified at runtime.
- **Hierarchical:** Configuration is organized into modules (e.g., `ScraperConfig`, `VoiceConfig`).
- **Profile-Driven:** Easily switch between `development`, `production`, and `testing` behaviors without changing code.

---

# 2. Override Precedence

Configuration values are merged from multiple sources. If the same key exists in multiple places, the higher precedence source overwrites the lower precedence source.

*(Lowest to Highest Precedence)*
1. **Base Defaults:** Hardcoded dataclass defaults.
2. **Base YAML:** `config/base.yaml` (Common settings for all profiles).
3. **Profile YAML:** `config/profiles/{env}.yaml` (Environment-specific overrides).
4. **.env File:** Local secrets and developer-specific environment overrides.
5. **System Environment Variables:** OS-level exports (e.g., in CI/CD or docker runs).
6. **CLI Runtime Overrides:** Command-line arguments passed at execution time (e.g., `--disable-cache`).

---

# 3. Directory Layout

```text
config/
 ├── base.yaml                 # Baseline configuration for all environments
 ├── profiles/
 │    ├── development.yaml     # Fast loop, lower quality renders, verbose logging
 │    ├── production.yaml      # High quality, strict retries, info logging
 │    └── testing.yaml         # Mocked endpoints, disabled timeouts
 ├── .env.example              # Template for environment variables/secrets
 ├── .env                      # (Ignored in Git) Active local secrets
 └── client_secrets.json       # (Ignored in Git) YouTube OAuth 2.0 Credentials
```

---

# 4. Profiles (Environments)

The system operates under one of three defined profiles, controlled by the `PIPELINE_ENV` environment variable (default: `development`).

### 4.1 Development
- **Purpose:** Local prompt engineering and module testing.
- **Behaviors:** 
  - `manim.quality`: "low_quality" (480p/15fps) to speed up iterations.
  - `logging.level`: "DEBUG".
  - `cache.force_refresh`: `false` (relies heavily on disk caches).

### 4.2 Production
- **Purpose:** Actual generation of YouTube videos.
- **Behaviors:**
  - `manim.quality`: "production_quality" (1080p/30fps).
  - `logging.level`: "INFO".
  - `youtube.upload_enabled`: `true`.

### 4.3 Testing
- **Purpose:** CI/CD and Pytest suite.
- **Behaviors:**
  - Overrides API URLs to point to `localhost` mocks.
  - Disables expensive openvino NPU loading.
  - Disables ffmpeg system checks.

---

# 5. Configuration Sources

### 5.1 YAML
YAML is the primary source for non-sensitive configuration due to its support for comments and hierarchical structure.
*Usage:* Model parameters (temperature, max_tokens), UI colors, resolutions.

### 5.2 JSON
JSON is specifically reserved for external integration specs that natively demand it.
*Usage:* Google OAuth `client_secrets.json`.

### 5.3 .env & Environment Variables
Used strictly for secrets, system-specific paths, and dynamic CI/CD injections.
*Usage:* `GEMINI_API_KEY`, `LEETCODE_SESSION_COOKIE`, `PIPELINE_ENV`.

### 5.4 Runtime Overrides (CLI)
Used by the developer to modify a single run without altering the config files.
*Usage:* `--model=gemini-1.5-pro` (temporarily overrides the YAML config for this execution).

---

# 6. Secrets Management

- **No Secrets in YAML:** YAML files are committed to version control and must never contain API keys or session cookies.
- **.env Loading:** The system loads `.env` automatically via `python-dotenv` at startup.
- **YouTube OAuth:** Since the `google-auth` library explicitly requires a `client_secrets.json` file, we map its path in `.env` (e.g., `YOUTUBE_SECRETS_PATH=config/client_secrets.json`).
- **Validation:** If required secrets (`GEMINI_API_KEY`) are missing, the configuration loader raises a `ConfigurationError` immediately.

---

# 7. Typed Configuration & Validation

The raw dictionaries parsed from YAML/Env/CLI are mapped to standard `dataclass` instances with `__post_init__` for validation.

### Structure
A root `PipelineConfig` object acts as the composition root, containing sub-configs for every module, including a `pipeline` field for global settings.

```python
PipelineConfig
 ├── pipeline: PipelineGlobalConfig
 ├── scraper: ScraperConfig
 ├── tags: TagsConfig
 ├── rag: RAGConfig
 ├── script: ScriptConfig
 ├── voice: VoiceConfig
 ├── animation: AnimationConfig
 ├── assembly: AssemblyConfig
 ├── memory: MemoryConfig
 └── youtube: YouTubeConfig
```

### Validation
- **Type Checking:** Ensuring `timeout` is a `float` and not a `str`.
- **Value Constraints:** Ensuring `audio_loudness` is between `-20` and `-10` LUFS.
- **Path Resolution:** Relative paths in YAML (e.g., `data/memory/`) are resolved to absolute `pathlib.Path` objects relative to the project root during instantiation.

---

# 8. Loading & Bootstrapping Flow

The `ConfigLoader` acts as a Singleton builder at the start of the process:

1. **Initialize Loader:** Read `PIPELINE_ENV`.
2. **Load YAMLs:** Deep-merge `base.yaml` with `profiles/{env}.yaml`.
3. **Load Environment:** Parse `.env` and system variables. Overwrite YAML values where keys match (using a translation convention like `ANIMATION__RESOLUTION` -> `animation.resolution`).
4. **Apply CLI Args:** Overwrite fields based on `argparse` output.
5. **Instantiate Dataclasses:** Pass the final dictionary into `PipelineConfig(**config_dict)`.
6. **Validate:** `__post_init__` triggers validation. If successful, the configuration is frozen.
7. **Inject:** The Orchestrator passes specific sub-configs to individual modules during instantiation (e.g., `Scraper(config=global_config.scraper)`).

---

# 9. Best Practices

1. **Zero Global Config State:** Avoid accessing configuration via a global singleton (e.g., `from config import current_config`). Always pass configuration explicitly via Dependency Injection (`__init__`).
2. **Fail Fast on Missing Keys:** Use strict validation. Do not swallow missing keys with silent defaults unless the default is universally safe.
3. **Single Source of Truth:** Once loaded into the `PipelineConfig` object, the application must never re-read YAML or `os.environ` directly.
4. **Module Scoping:** The Voice Engine should only receive `VoiceConfig`, not `PipelineConfig`. This enforces encapsulation and makes modules highly testable.
