# Phase04/08_Configuration_Runtime.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Target Environment:** Intel Core Ultra 7 155H · Ubuntu 25.10 LTS · Python 3.12 · Intel Arc GPU  
**Document Version:** 2.0.0  
**Status:** Canonical — Supersedes v1.0.0 after architectural audit.

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code Specification: `src/core/config.py`](#2-source-code-specification-srccoreconfigpy)
3. [Design Decisions & Architecture Compliance](#3-design-decisions--architecture-compliance)
4. [Change Log](#4-change-log)

---

# 1. Executive Summary

This document specifies the **Runtime Configuration Module** (`src/core/config.py`).

In the v2.0.0 canonical architecture, configuration is loaded **once at startup** and remains **immutable thereafter**. The entry point invokes `load_config()`, which parses configuration settings in a single pass according to strict precedence rules, validates fields, and constructs a frozen `PipelineConfig` instance.

### Precedence Hierarchy (Highest to Lowest)
1. **CLI Flag Overrides:** Explicit flags supplied to command invocation (e.g., `--log-level`).
2. **YAML Configuration File:** Runtime parameters defined in `config/pipeline.yaml`.
3. **Environment Variables / `.env` File:** Secret keys, credentials, and environment variables.

### Key Rules
- **Single-Pass Loading:** Configuration is loaded once during execution startup.
- **Fail-Fast Error Handling:** Any validation error or missing required setting raises `ConfigurationError` immediately and halts execution.
- **Frozen Dataclasses:** All configuration schemas use standard Python `@dataclass(frozen=True)` dataclasses. No Pydantic models.
- **No Hot-Reloading:** The config is loaded once and passed down via constructor injection. No `ConfigManager` state.

---

# 2. Source Code Specification: `src/core/config.py`

```python
"""
Runtime Configuration Module.

Loads configuration from .env, YAML files, and CLI overrides into
frozen dataclass instances. Enforces fail-fast validation at startup.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import yaml
from dotenv import load_dotenv

from src.core.exceptions import ConfigurationError


@dataclass(frozen=True)
class ScraperConfig:
    timeout_seconds: int = 30
    max_retries: int = 3
    user_agent: str = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) Pipeline/2.0"


@dataclass(frozen=True)
class TagsConfig:
    model_name: str = "gemini-2.5-flash"
    temperature: float = 0.2


@dataclass(frozen=True)
class RAGConfig:
    chroma_db_path: Path = Path("data/chroma")
    collection_name: str = "dsa_patterns"
    top_k: int = 5


@dataclass(frozen=True)
class ScriptConfig:
    model_name: str = "gemini-2.5-pro"
    max_tokens: int = 8192
    temperature: float = 0.7


@dataclass(frozen=True)
class VoiceConfig:
    voice_id: str = "af_sky"
    sample_rate: int = 24000
    speed: float = 1.0


@dataclass(frozen=True)
class AnimationConfig:
    quality: str = "1080p60"
    fps: int = 60
    output_format: str = "mp4"


@dataclass(frozen=True)
class AssemblyConfig:
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    resolution: str = "1920x1080"


@dataclass(frozen=True)
class YouTubeConfig:
    privacy_status: str = "unlisted"
    category_id: str = "27"
    credentials_file: Path = Path("config/youtube_credentials.json")


@dataclass(frozen=True)
class MemoryConfig:
    storage_file: Path = Path("data/memory.json")


@dataclass(frozen=True)
class PipelineConfig:
    """
    Root pipeline configuration dataclass. Immutable once loaded.
    """
    log_level: str = "INFO"
    output_dir: Path = Path("output")
    temp_dir: Path = Path("temp")
    cache_dir: Path = Path("cache")
    gemini_api_key: str = ""
    scraper: ScraperConfig = field(default_factory=ScraperConfig)
    tags: TagsConfig = field(default_factory=TagsConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    script: ScriptConfig = field(default_factory=ScriptConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    animation: AnimationConfig = field(default_factory=AnimationConfig)
    assembly: AssemblyConfig = field(default_factory=AssemblyConfig)
    youtube: YouTubeConfig = field(default_factory=YouTubeConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)


def _load_yaml_file(yaml_path: Path) -> dict[str, Any]:
    """Reads and parses the YAML configuration file."""
    if not yaml_path.is_file():
        return {}
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f)
            return content if isinstance(content, dict) else {}
    except Exception as e:
        raise ConfigurationError(f"Failed to parse configuration file '{yaml_path}': {e}") from e


def load_config(
    env_path: Optional[Path] = None,
    yaml_path: Optional[Path] = None,
    cli_overrides: Optional[dict[str, Any]] = None,
) -> PipelineConfig:
    """
    Loads and validates pipeline configuration in a single pass.

    Precedence:
    1. CLI overrides (highest)
    2. YAML configuration file
    3. Environment variables / .env (lowest)

    Returns:
        PipelineConfig: Validated, frozen configuration snapshot.

    Raises:
        ConfigurationError: On validation failure or missing required fields.
    """
    # 1. Load environment variables
    dotenv_file = env_path or Path(".env")
    if dotenv_file.is_file():
        load_dotenv(dotenv_path=dotenv_file)

    # 2. Read YAML config
    config_file = yaml_path or Path("config/pipeline.yaml")
    yaml_data = _load_yaml_file(config_file)

    # 3. Read environment variable overrides
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    log_level = os.getenv("LOG_LEVEL", yaml_data.get("log_level", "INFO"))

    # 4. Apply CLI overrides
    overrides = cli_overrides or {}
    if "log_level" in overrides and overrides["log_level"]:
        log_level = overrides["log_level"]

    # 5. Build sub-configuration objects
    try:
        scraper_cfg = ScraperConfig(**yaml_data.get("scraper", {}))
        tags_cfg = TagsConfig(**yaml_data.get("tags", {}))

        rag_raw = yaml_data.get("rag", {})
        if "chroma_db_path" in rag_raw:
            rag_raw["chroma_db_path"] = Path(rag_raw["chroma_db_path"])
        rag_cfg = RAGConfig(**rag_raw)

        script_cfg = ScriptConfig(**yaml_data.get("script", {}))
        voice_cfg = VoiceConfig(**yaml_data.get("voice", {}))
        anim_cfg = AnimationConfig(**yaml_data.get("animation", {}))
        assembly_cfg = AssemblyConfig(**yaml_data.get("assembly", {}))

        yt_raw = yaml_data.get("youtube", {})
        if "credentials_file" in yt_raw:
            yt_raw["credentials_file"] = Path(yt_raw["credentials_file"])
        youtube_cfg = YouTubeConfig(**yt_raw)

        mem_raw = yaml_data.get("memory", {})
        if "storage_file" in mem_raw:
            mem_raw["storage_file"] = Path(mem_raw["storage_file"])
        memory_cfg = MemoryConfig(**mem_raw)

        # 6. Construct master configuration
        config = PipelineConfig(
            log_level=log_level.upper(),
            output_dir=Path(yaml_data.get("output_dir", "output")),
            temp_dir=Path(yaml_data.get("temp_dir", "temp")),
            cache_dir=Path(yaml_data.get("cache_dir", "cache")),
            gemini_api_key=gemini_key,
            scraper=scraper_cfg,
            tags=tags_cfg,
            rag=rag_cfg,
            script=script_cfg,
            voice=voice_cfg,
            animation=anim_cfg,
            assembly=assembly_cfg,
            youtube=youtube_cfg,
            memory=memory_cfg,
        )

        # 7. Fail-fast validation
        if not config.gemini_api_key:
            raise ConfigurationError(
                "GEMINI_API_KEY environment variable is missing or empty."
            )

        return config

    except TypeError as e:
        raise ConfigurationError(f"Invalid configuration parameter type: {e}") from e
    except Exception as e:
        if isinstance(e, ConfigurationError):
            raise
        raise ConfigurationError(f"Unexpected error loading configuration: {e}") from e
```

---

# 3. Design Decisions & Architecture Compliance

1. **Immutable Frozen Dataclasses:** Every configuration class uses `@dataclass(frozen=True)`. Runtime parameters cannot be modified after initial creation, ensuring thread-safe read access and predictable behavior.
2. **Single-Pass Loader:** `load_config()` loads settings once at application start. There is no `ConfigManager` singleton or stateful registry.
3. **Fail-Fast Policy:** Startup halts immediately if `GEMINI_API_KEY` is missing or parameters fail type validation.
4. **Zero Dependency Frameworks:** Configuration parsing uses standard Python dataclasses, `pyyaml`, and `python-dotenv`. Pydantic is explicitly avoided per canonical rules.
5. **Constructor Injection Only:** Modules receive their specific `Config` object via constructor injection in the composition root (`src/__main__.py`).

---

# 4. Change Log

- **Removed `ConfigManager`:** Replaced by a simple `load_config()` function to adhere to the functional, stateless startup flow.
- **Removed Pydantic:** Replaced all Pydantic models with standard Python `@dataclass(frozen=True)` to comply with Rule 4 (Frozen dataclasses, NOT Pydantic).
- **Removed Hot-Reloading:** Removed any functionality for reloading configuration at runtime. Configuration is strictly immutable.
- **Removed Dynamic YAML Pipeline Parsers:** Ensured no YAML parsing is used for the execution graph or pipeline workflow (only for simple static configuration settings).
