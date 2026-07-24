"""
Core foundation package for Synchronous Batch Pipeline Architecture.

Provides essential base abstractions, settings configuration, centralized 
exception hierarchy, and structured logging.
"""

from src.core.base import (
    BasePipelineResult,
    Command,
    Factory,
    Lifecycle,
    PipelineModule,
    Provider,
    Repository,
    Service,
    Validator,
)
from src.core.config import (
    Environment,
    GeminiConfig,
    PipelineConfig,
    RAGConfig,
    ScraperConfig,
    YouTubeConfig,
    load_config,
)
from src.core.exceptions import (
    AnimationError,
    AssemblyError,
    AuthenticationError,
    ConfigurationError,
    EmbeddingError,
    FatalError,
    IndexNotFoundError,
    KnowledgeConflictError,
    NetworkError,
    PipelineError,
    PipelineStageError,
    PipelineValidationError,
    ProblemNotFoundError,
    RAGError,
    RateLimitError,
    RetryableError,
    ScraperError,
    ScriptGenerationError,
    TagExplorerError,
    ValidationError,
    VoiceGenerationError,
    YouTubeUploadError,
)
from src.core.logger import configure_logging, get_logger, log_execution_time

__all__ = [
    # Base Abstractions
    "BasePipelineResult",
    "PipelineModule",
    "Service",
    "Repository",
    "Provider",
    "Factory",
    "Command",
    "Lifecycle",
    "Validator",
    # Configuration
    "Environment",
    "PipelineConfig",
    "ScraperConfig",
    "RAGConfig",
    "GeminiConfig",
    "YouTubeConfig",
    "load_config",
    # Exceptions
    "PipelineError",
    "RetryableError",
    "FatalError",
    "ConfigurationError",
    "ValidationError",
    "PipelineValidationError",
    "PipelineStageError",
    "NetworkError",
    "AuthenticationError",
    "RateLimitError",
    "ScraperError",
    "ProblemNotFoundError",
    "TagExplorerError",
    "RAGError",
    "IndexNotFoundError",
    "EmbeddingError",
    "KnowledgeConflictError",
    "ScriptGenerationError",
    "VoiceGenerationError",
    "AnimationError",
    "AssemblyError",
    "YouTubeUploadError",
    # Logger
    "configure_logging",
    "get_logger",
    "log_execution_time",
]
