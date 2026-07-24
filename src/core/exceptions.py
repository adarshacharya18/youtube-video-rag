"""
Centralized Exception Hierarchy for the Pipeline.

All custom exceptions inherit from PipelineError. They are further classified
by their operational impact (RetryableError vs FatalError) and their originating
module (ScraperError, RAGError, etc.).
"""

# ==========================================
# 1. Base Exception
# ==========================================

class PipelineError(Exception):
    """Base exception for all pipeline errors."""
    pass


# ==========================================
# 2. Operational Classifications
# ==========================================

class RetryableError(PipelineError):
    """
    Indicates a transient error (e.g., network timeout) that may succeed 
    if the operation is retried after a delay.
    """
    pass


class FatalError(PipelineError):
    """
    Indicates an unrecoverable error (e.g., bad credentials) that must 
    halt the pipeline immediately. Do not retry.
    """
    pass


# ==========================================
# 3. Infrastructure & Core Errors
# ==========================================

class ConfigurationError(FatalError):
    """Raised when environment variables or config files are missing/invalid."""
    pass


class ValidationError(FatalError):
    """Raised when data fails strict schema validation (e.g., bad LLM JSON output)."""
    pass


class PipelineValidationError(ValidationError):
    """Raised when data fails strict pipeline schema validation."""
    pass


class PipelineStageError(FatalError):
    """Raised when a specific pipeline stage fails execution."""
    pass


class NetworkError(RetryableError):
    """Raised for timeouts or transient TCP/HTTP connection issues."""
    pass


class AuthenticationError(FatalError):
    """Raised when API keys, OAuth tokens, or session cookies are rejected."""
    pass


class RateLimitError(RetryableError):
    """Raised when a 429 Too Many Requests response is encountered."""
    pass


# ==========================================
# 4. Module-Specific Exceptions
# ==========================================

# -- Module 1: Scraper --
class ScraperError(PipelineError):
    """Base exception for the LeetCode Scraper module."""
    pass

class ProblemNotFoundError(ScraperError, FatalError):
    """Raised when the requested LeetCode slug does not exist (404)."""
    pass

# -- Module 2: Tag Explorer --
class TagExplorerError(PipelineError):
    """Base exception for the Tag Explorer module."""
    pass

# -- Module 3: RAG Engine --
class RAGError(PipelineError):
    """Base exception for the RAG Knowledge Engine."""
    pass

class IndexNotFoundError(RAGError, FatalError):
    """Raised when the ChromaDB index is missing and cannot be built automatically."""
    pass

class EmbeddingError(RAGError, RetryableError):
    """Raised when the vector embedding API fails transiently."""
    pass

class KnowledgeConflictError(RAGError, FatalError):
    """Raised when the KB Linter detects contradictory facts in the Markdown files."""
    pass

# -- Module 4: Script Generator --
class ScriptGenerationError(PipelineError):
    """Base exception for the Script Generator module."""
    pass

# -- Module 5: Voice Generation --
class VoiceGenerationError(PipelineError):
    """Base exception for the Voice module (Kokoro TTS)."""
    pass

# -- Module 6: Animation Engine --
class AnimationError(PipelineError):
    """Base exception for the Manim Animation module."""
    pass

# -- Module 7: Video Assembly --
class AssemblyError(PipelineError):
    """Base exception for the FFmpeg Video Assembly module."""
    pass

# -- Module 8: YouTube Upload --
class YouTubeUploadError(PipelineError):
    """Base exception for the YouTube Uploader module."""
    pass
