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
