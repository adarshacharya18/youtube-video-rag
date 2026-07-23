"""
Abstract Source Connector Interface.

Defines the core contract for all Knowledge Ingestion plugins (e.g., LeetCode, Wikipedia, PDFs).
Provides built-in abstractions for Authentication, Pagination, Retries, and Rate Limiting.
"""

import abc
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from src.core.exceptions import PipelineError


class ConnectorError(PipelineError):
    """Base exception for extraction and connectivity failures."""
    pass


class RateLimitError(ConnectorError):
    """Raised when an API actively rejects a request due to TPS violations (HTTP 429)."""
    pass


class AuthError(ConnectorError):
    """Raised when API Keys expire or Login Cookies fail (HTTP 401/403)."""
    pass


@dataclass(frozen=True)
class RawContent:
    """The universal payload returned by a Connector before Normalization."""
    uri: str
    content_body: bytes | str
    content_type: str  # e.g., 'text/html', 'application/json', 'application/pdf'
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PaginationToken:
    """Standardized token for managing paginated REST endpoints or multi-page PDFs."""
    next_cursor: Optional[str] = None
    has_more: bool = False
    current_page: int = 1


class BaseSourceConnector(abc.ABC):
    """
    Abstract Base Class for all Ingestion Sources.
    """
    def __init__(self, name: str, rate_limit_ms: int = 1000) -> None:
        self.name = name
        self._rate_limit_ms = rate_limit_ms
        self._last_request_time = 0.0
        self._logger = logging.getLogger(f"connector.{name}")

    # ---------------------------------------------------------
    # Core Infrastructure
    # ---------------------------------------------------------
    async def _apply_rate_limit(self) -> None:
        """
        Enforces a strict delay between physical network requests to avoid IP bans.
        Uses the asyncio event loop clock for highly accurate microsecond sleeping.
        """
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        required_delay = (self._rate_limit_ms / 1000.0) - elapsed
        
        if required_delay > 0:
            await asyncio.sleep(required_delay)
            
        self._last_request_time = asyncio.get_event_loop().time()

    def validate_content(self, content: RawContent) -> None:
        """
        Ensures the payload is not malformed before passing it to the Semantic Normalizer.
        Can be overridden by concrete classes for strict Schema Validation.
        """
        if not content.content_body:
            raise ConnectorError(f"Extracted payload from {content.uri} is absolutely empty.")
        if not content.content_type:
            raise ConnectorError(f"Extracted payload from {content.uri} is missing MIME content_type.")

    # ---------------------------------------------------------
    # Abstract Contracts (To be implemented by Plugins)
    # ---------------------------------------------------------
    @abc.abstractmethod
    async def _do_health_check(self) -> bool:
        """Physical implementation of the connectivity check (e.g., pinging an API endpoint)."""
        pass

    @abc.abstractmethod
    async def authenticate(self, credentials: Dict[str, str]) -> None:
        """Handles OAuth, API Keys, or session cookies. Raises AuthError on failure."""
        pass

    @abc.abstractmethod
    async def discover(self, query: str) -> List[str]:
        """
        Translates a semantic query into concrete URIs.
        Example: discover("Dijkstra") -> ["https://en.wikipedia.org/wiki/Dijkstra%27s_algorithm"]
        """
        pass

    @abc.abstractmethod
    async def _do_fetch(self, uri: str) -> RawContent:
        """Physical implementation of the extraction (e.g., aiohttp.ClientSession.get)."""
        pass

    # ---------------------------------------------------------
    # Public APIs (With built-in resilience)
    # ---------------------------------------------------------
    async def check_health(self) -> bool:
        """Safely validates network connectivity without crashing the Orchestrator."""
        try:
            return await self._do_health_check()
        except Exception as e:
            self._logger.error(f"Health check completely failed for {self.name}: {e}")
            return False

    async def fetch(self, uri: str, max_retries: int = 3) -> RawContent:
        """
        Orchestrates the physical extraction with Automatic Retries and Rate Limiting.
        """
        attempt = 1
        while attempt <= max_retries:
            await self._apply_rate_limit()
            try:
                content = await self._do_fetch(uri)
                self.validate_content(content)
                return content
                
            except RateLimitError as e:
                wait_time = attempt * 2.0
                self._logger.warning(f"HTTP 429 Rate limited on {uri}. Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
                attempt += 1
                
            except Exception as e:
                self._logger.error(f"Fetch attempt {attempt}/{max_retries} failed for {uri}: {e}")
                if attempt == max_retries:
                    raise ConnectorError(f"FATAL: Failed to fetch {uri} after {max_retries} attempts.") from e
                
                # Exponential backoff for generic network blips
                await asyncio.sleep(attempt * 1.5)
                attempt += 1
                
        raise ConnectorError("Unreachable fetch execution state.")

    async def fetch_stream(self, uri: str) -> AsyncGenerator[RawContent, None]:
        """
        Yields paginated results for massive data sources (e.g., downloading 1,000 GitHub repos).
        Prevents Out-Of-Memory (OOM) crashes by streaming documents one by one.
        """
        token = PaginationToken(has_more=True)
        while token.has_more:
            await self._apply_rate_limit()
            
            # The concrete plugin must override _do_fetch_page for this to work
            content, next_token = await self._do_fetch_page(uri, token)
            
            self.validate_content(content)
            yield content
            token = next_token

    async def _do_fetch_page(self, uri: str, token: PaginationToken) -> Tuple[RawContent, PaginationToken]:
        """
        Physical implementation of paginated extraction. 
        Must be overridden by connectors that support massive API streaming.
        """
        raise NotImplementedError(f"Streaming/Pagination logic is not natively implemented by {self.name}.")
