"""
Configuration Profiles Management (Phase 14)

Provides environment-aware configuration profiles (Dev, Test, Prod, Offline, Benchmark).
Supports inheritance, environment variable overrides, and safe secrets referencing.
"""
import os
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict

logger = logging.getLogger("config")

@dataclass
class PipelineConfig:
    """Base Configuration Structure for the Pipeline."""
    profile_name: str = "base"
    
    # Feature Flags
    enable_llm_calls: bool = True
    enable_manim_rendering: bool = True
    enable_youtube_upload: bool = True
    
    # Subsystem Settings
    manim_quality: str = "high_quality"
    max_retries: int = 3
    db_path: str = "/tmp/dsa_ledger.sqlite"
    dlq_path: str = "/tmp/dlq.jsonl"
    
    # Secrets References (Resolved securely at runtime, not logged)
    _secrets: Dict[str, str] = field(default_factory=dict, repr=False)

    def load_secrets(self) -> None:
        """Safely pulls API keys from the environment."""
        self._secrets["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY")
        self._secrets["YOUTUBE_API_KEY"] = os.environ.get("YOUTUBE_API_KEY")

    def get_secret(self, key: str) -> Optional[str]:
        if not self._secrets:
            self.load_secrets()
        return self._secrets.get(key)


@dataclass
class DevelopmentConfig(PipelineConfig):
    profile_name: str = "development"
    manim_quality: str = "low_quality"       # Fast rendering for local iteration
    enable_youtube_upload: bool = False      # Never accidentally upload test videos
    db_path: str = "dev_ledger.sqlite"


@dataclass
class TestingConfig(PipelineConfig):
    profile_name: str = "testing"
    enable_llm_calls: bool = False           # Saves massive API costs during CI
    enable_manim_rendering: bool = False     # Saves hours of CI compute
    enable_youtube_upload: bool = False
    max_retries: int = 0
    db_path: str = ":memory:"                # Ephemeral test db


@dataclass
class ProductionConfig(PipelineConfig):
    profile_name: str = "production"
    manim_quality: str = "production_quality"  # 4K / 1080p 60fps
    db_path: str = "/var/lib/dsa_pipeline/prod_ledger.sqlite"
    dlq_path: str = "/var/log/dsa_pipeline/dlq.jsonl"


@dataclass
class OfflineConfig(DevelopmentConfig):
    """
    Inherits from Development, but strictly disables network-bound operations.
    Useful for testing local Manim rendering without pinging OpenAI.
    """
    profile_name: str = "offline"
    enable_llm_calls: bool = False
    enable_youtube_upload: bool = False


@dataclass
class BenchmarkConfig(PipelineConfig):
    """
    Used for hardware profiling. Forces high-quality renders but drops the 
    network uploads to purely test CPU/GPU capabilities.
    """
    profile_name: str = "benchmark"
    manim_quality: str = "production_quality"
    enable_youtube_upload: bool = False
    enable_llm_calls: bool = False


class ConfigFactory:
    """Instantiates the correct configuration based on the PIPELINE_ENV variable."""
    
    _PROFILES = {
        "development": DevelopmentConfig,
        "testing": TestingConfig,
        "production": ProductionConfig,
        "offline": OfflineConfig,
        "benchmark": BenchmarkConfig
    }

    @classmethod
    def get_config(cls) -> PipelineConfig:
        env_name = os.environ.get("PIPELINE_ENV", "development").lower()
        
        config_class = cls._PROFILES.get(env_name)
        if not config_class:
            logger.warning(f"Unknown profile '{env_name}'. Falling back to DevelopmentConfig.")
            config_class = DevelopmentConfig
            
        config = config_class()
        
        # Override specific keys via explicit Environment Variables
        if os.environ.get("MANIM_QUALITY"):
            config.manim_quality = os.environ.get("MANIM_QUALITY")
            
        return config
