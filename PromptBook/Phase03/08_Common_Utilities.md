# Phase03/08_Common_Utilities.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Filesystem & Environment (`paths.py`)](#2-filesystem--environment-pathspy)
3. [Serialization & Formatting (`serialization.py`)](#3-serialization--formatting-serializationpy)
4. [Hashing & Caching (`cache.py`)](#4-hashing--caching-cachepy)
5. [Resilience (`retry.py`)](#5-resilience-retrypy)
6. [Design Decisions](#6-design-decisions)

---

# 1. Executive Summary

This document provides the implementation for the core shared utilities layer. Rather than creating a massive, highly coupled `utils.py` dumping ground, the utilities are strictly partitioned by responsibility in `src/core/`. 

These utilities guarantee that every module in the pipeline handles files paths relative to the project root, serializes UUIDs and Datetimes correctly into JSON/YAML, hashes API requests for caching, and survives transient network failures through exponential backoff.

---

# 2. Filesystem & Environment (`paths.py`)

Handles safe, OS-agnostic path resolution and environment variable injection.

```python
"""
Filesystem and environment utilities.
"""

import os
from pathlib import Path


# Anchors the project root dynamically, regardless of where the script is executed from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def resolve_path(path: str | Path) -> Path:
    """
    Resolve a path relative to the PROJECT_ROOT.
    If the path is already absolute, it is returned as-is.
    """
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def ensure_dir(path: str | Path) -> Path:
    """
    Ensure a directory exists (creating parent directories if necessary).
    Returns the resolved Path object.
    """
    p = resolve_path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_env_var(key: str, default: str | None = None) -> str:
    """
    Safely fetch an environment variable, raising a clear error if missing 
    and no default is provided.
    """
    val = os.getenv(key, default)
    if val is None:
        from src.core.exceptions import ConfigurationError
        raise ConfigurationError(f"Required environment variable '{key}' is missing.")
    return val
```

---

# 3. Serialization & Formatting (`serialization.py`)

Handles JSON and YAML parsing, strict validation via Pydantic, timestamp formatting, and UUID encoding.

```python
"""
Serialization utilities for JSON, YAML, Datetimes, and UUIDs.
"""

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, ValidationError as PydanticValidationError

from src.core.exceptions import ValidationError

T = TypeVar("T", bound=BaseModel)


class CustomJSONEncoder(json.JSONEncoder):
    """Encodes custom standard library types safely into JSON strings."""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


def serialize_json(data: Any, path: Path | None = None, indent: int = 2) -> str:
    """Serialize an object to a JSON string, optionally saving it to a file."""
    # Convert Pydantic models to dict if necessary
    if isinstance(data, BaseModel):
        data = data.model_dump(mode="json")
        
    json_str = json.dumps(data, cls=CustomJSONEncoder, indent=indent)
    if path:
        path.write_text(json_str, encoding="utf-8")
    return json_str


def deserialize_json(source: str | Path, model: type[T] | None = None) -> Any:
    """
    Deserialize JSON from a string or file.
    If `model` (a Pydantic class) is provided, validates the data and returns the instance.
    """
    if isinstance(source, Path):
        raw_data = json.loads(source.read_text(encoding="utf-8"))
    else:
        raw_data = json.loads(source)

    if model:
        try:
            return model.model_validate(raw_data)
        except PydanticValidationError as e:
            raise ValidationError(f"Failed to validate JSON against {model.__name__}: {e}")
            
    return raw_data


def serialize_yaml(data: Any, path: Path | None = None) -> str:
    """Serialize a dictionary to YAML format."""
    yaml_str = yaml.dump(data, default_flow_style=False, sort_keys=False)
    if path:
        path.write_text(yaml_str, encoding="utf-8")
    return yaml_str


def deserialize_yaml(source: str | Path) -> dict[str, Any]:
    """Deserialize YAML from a string or file."""
    if isinstance(source, Path):
        return yaml.safe_load(source.read_text(encoding="utf-8"))
    return yaml.safe_load(source)


def generate_uuid() -> str:
    """Generate a standard UUID string."""
    return str(uuid.uuid4())


def format_timestamp(dt: datetime | None = None) -> str:
    """Format a UTC timestamp for safe usage in filenames."""
    dt = dt or datetime.now(timezone.utc)
    return dt.strftime("%Y%m%d_%H%M%S")
```

---

# 4. Hashing & Caching (`cache.py`)

A filesystem-backed caching utility using SHA-256 to hash complex identifiers (like GraphQL queries).

```python
"""
Filesystem caching and SHA-256 hashing utility.
"""

import hashlib
from pathlib import Path
from typing import Any

from src.core.paths import ensure_dir
from src.core.serialization import deserialize_json, serialize_json


class FileCache:
    """
    A robust, JSON-backed file cache. Perfect for caching API responses 
    (like LeetCode problems or Gemini tag extractions) to save bandwidth and tokens.
    """

    def __init__(self, cache_dir: Path | str) -> None:
        self._dir = ensure_dir(cache_dir)

    def _hash_key(self, identifier: str) -> str:
        """Generate a deterministic SHA-256 hash for the identifier."""
        return hashlib.sha256(identifier.encode("utf-8")).hexdigest()

    def get(self, identifier: str) -> Any | None:
        """Retrieve data from cache by its string identifier."""
        path = self._dir / f"{self._hash_key(identifier)}.json"
        if path.exists():
            return deserialize_json(path)
        return None

    def put(self, identifier: str, data: Any) -> None:
        """Serialize and store data in the cache."""
        path = self._dir / f"{self._hash_key(identifier)}.json"
        serialize_json(data, path)

    def invalidate(self, identifier: str) -> None:
        """Remove a specific identifier from the cache."""
        path = self._dir / f"{self._hash_key(identifier)}.json"
        if path.exists():
            path.unlink()

    def invalidate_all(self) -> None:
        """Clear the entire cache directory."""
        for file in self._dir.glob("*.json"):
            file.unlink()
```

---

# 5. Resilience (`retry.py`)

A `@retry` decorator utilizing exponential backoff. Crucially, it integrates directly with the semantic exception hierarchy (`RetryableError`) designed in the previous phase.

```python
"""
Exponential backoff and retry utility.
"""

import asyncio
import functools
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

from src.core.exceptions import RetryableError

T = TypeVar("T")
logger = logging.getLogger(__name__)


def retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (RetryableError,)
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to automatically retry a function if it raises specific exceptions.
    Supports both synchronous and asynchronous functions.

    Args:
        max_attempts: Maximum number of times to try before giving up.
        initial_delay: Seconds to wait before the first retry.
        backoff_factor: Multiplier applied to the delay after each failure.
        exceptions: Tuple of exception types to catch (defaults to RetryableError).
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                delay = initial_delay
                for attempt in range(1, max_attempts + 1):
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as e:
                        if attempt == max_attempts:
                            logger.error(f"Async attempt {attempt}/{max_attempts} failed. Aborting.")
                            raise
                        logger.warning(
                            f"Async attempt {attempt}/{max_attempts} failed: {e}. "
                            f"Retrying in {delay}s..."
                        )
                        await asyncio.sleep(delay)
                        delay *= backoff_factor

            return async_wrapper

        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                delay = initial_delay
                for attempt in range(1, max_attempts + 1):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        if attempt == max_attempts:
                            logger.error(f"Sync attempt {attempt}/{max_attempts} failed. Aborting.")
                            raise
                        logger.warning(
                            f"Sync attempt {attempt}/{max_attempts} failed: {e}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                        delay *= backoff_factor

            return sync_wrapper

    return decorator
```

---

# 6. Design Decisions

1. **`CustomJSONEncoder`:** By default, Python's `json` library crashes on UUIDs, `datetime` objects, `Path` objects, and Enums. The `serialization.py` module solves this silently and universally across the entire pipeline.
2. **Pydantic Validation Proxy:** `deserialize_json` optionally takes a Pydantic `model` reference. It wraps Pydantic's internal `ValidationError` and re-raises our custom infrastructure `ValidationError` from `src.core.exceptions`, preventing implementation details from leaking across module boundaries.
3. **Transparent Async Support:** The `@retry` decorator detects whether the decorated function is a standard `def` or an `async def` and adjusts its sleep behavior (`time.sleep` vs `asyncio.sleep`) automatically. Developers don't need to choose between `@retry_sync` and `@retry_async`.
