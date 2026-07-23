"""
Empirical test suite for Challenge Focus 3: Exponential Backoff & Jitter Formulas
"""
import sys
import unittest
import asyncio
import random
from functools import wraps
from typing import Any, Callable

# Re-implementation from Section 4.1.1
def exponential_backoff_with_jitter(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter_type: str = "full",
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
):
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            current_delay = initial_delay
            while True:
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as exc:
                    attempt += 1
                    if attempt >= max_attempts:
                        raise exc
                    
                    if jitter_type == "full":
                        calculated = min(max_delay, initial_delay * (backoff_factor ** attempt))
                        sleep_time = random.uniform(0, calculated)
                    elif jitter_type == "decorrelated":
                        sleep_time = min(max_delay, random.uniform(initial_delay, current_delay * 3.0))
                        current_delay = sleep_time
                    else:
                        sleep_time = min(max_delay, initial_delay * (backoff_factor ** attempt))

                    await asyncio.sleep(sleep_time)
        return wrapper
    return decorator


class TestRetryJitter(unittest.TestCase):

    def test_sync_function_typeerror_crash(self):
        """
        EMPIRICAL BUG PROOF:
        The decorator produces an `async def wrapper` that performs `await func(*args, **kwargs)`.
        If applied to a synchronous function, calling it causes a TypeError because synchronous functions are not awaitable.
        """
        def sync_function(a, b):
            return a + b

        decorated = exponential_backoff_with_jitter()(sync_function)

        async def run():
            with self.assertRaises(TypeError) as ctx:
                await decorated(1, 2)
            self.assertIn("object int can't be used in 'await' expression", str(ctx.exception))

        asyncio.run(run())

    def test_decorrelated_jitter_potential_lower_bound_drift(self):
        """
        EMPIRICAL BUG PROOF:
        In decorrelated jitter: `sleep_time = min(max_delay, random.uniform(initial_delay, current_delay * 3.0))`
        `current_delay = sleep_time`
        If sleep_time happens to be close to initial_delay (e.g., initial_delay=0.1s),
        current_delay stays small for multiple retries, failing to grow exponentially as intended for decorrelated backoff.
        """
        delays = []
        current_delay = 1.0
        initial_delay = 1.0
        max_delay = 60.0
        
        # Simulate 100 decorrelated jitter sequences
        # Record whether current_delay ever shrinks back to near initial_delay
        shrank_count = 0
        for _ in range(100):
            current_delay = initial_delay
            seq = []
            for attempt in range(5):
                sleep_time = min(max_delay, random.uniform(initial_delay, current_delay * 3.0))
                current_delay = sleep_time
                seq.append(sleep_time)
            if seq[-1] < seq[0]:
                shrank_count += 1

        self.assertGreater(shrank_count, 0, "Decorrelated jitter can regress delay on successive attempts")

if __name__ == "__main__":
    unittest.main()
