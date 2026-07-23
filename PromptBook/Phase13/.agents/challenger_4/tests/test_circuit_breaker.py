"""
Empirical test harness for CircuitBreaker consecutive failure state transition logic under simulated load.
"""

import sys
import unittest
import asyncio
import time
from enum import Enum
from typing import Any, Callable

class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitOpenError(Exception):
    """Raised when operation is attempted while circuit breaker is OPEN."""
    pass

# Copy of CircuitBreaker from 01_Media_Production_Architecture.md Section 4.1.2
class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        reset_timeout_seconds: float = 60.0,
        half_open_consecutive_successes: int = 3,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout_seconds = reset_timeout_seconds
        self.half_open_consecutive_successes = half_open_consecutive_successes
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_state_change = time.time()
        self._lock = asyncio.Lock()

    async def __call__(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        async with self._lock:
            now = time.time()
            if self.state == CircuitState.OPEN:
                if now - self.last_state_change > self.reset_timeout_seconds:
                    self.state = CircuitState.HALF_OPEN
                    self.last_state_change = now
                    self.success_count = 0
                    self.failure_count = 0
                else:
                    raise CircuitOpenError(
                        f"CircuitBreaker[{self.name}] is OPEN. Time until probe: {self.reset_timeout_seconds - (now - self.last_state_change):.1f}s"
                    )

        try:
            result = await func(*args, **kwargs)
            async with self._lock:
                if self.state == CircuitState.HALF_OPEN:
                    self.success_count += 1
                    if self.success_count >= self.half_open_consecutive_successes:
                        self.state = CircuitState.CLOSED
                        self.failure_count = 0
                        self.success_count = 0
                        self.last_state_change = time.time()
            return result
        except Exception as exc:
            async with self._lock:
                self.failure_count += 1
                if self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN):
                    if self.failure_count >= self.failure_threshold or self.state == CircuitState.HALF_OPEN:
                        self.state = CircuitState.OPEN
                        self.last_state_change = time.time()
            raise exc


class TestCircuitBreaker(unittest.TestCase):

    def test_consecutive_failures_trips_to_open(self):
        cb = CircuitBreaker("test_cb", failure_threshold=5, reset_timeout_seconds=60.0)

        async def failing_func():
            raise RuntimeError("API failure")

        async def run_test():
            for i in range(5):
                with self.assertRaises(RuntimeError):
                    await cb(failing_func)
            
            self.assertEqual(cb.state, CircuitState.OPEN)

            # 6th call should fail fast with CircuitOpenError
            with self.assertRaises(CircuitOpenError):
                await cb(failing_func)

        asyncio.run(run_test())

    def test_intermittent_failures_accumulate_and_trip_in_closed_state(self):
        """
        Tests behavior when successes occur between failures in CLOSED state.
        Worker 2 removed single-success failure_count reset.
        So 1 success does NOT reset failure_count.
        Thus, 4 failures + 1 success + 1 failure = 5 failures total -> trips OPEN.
        """
        cb = CircuitBreaker("test_cb", failure_threshold=5, reset_timeout_seconds=60.0)

        async def failing_func():
            raise RuntimeError("API failure")

        async def succeeding_func():
            return "OK"

        async def run_test():
            # 4 failures
            for i in range(4):
                with self.assertRaises(RuntimeError):
                    await cb(failing_func)
            self.assertEqual(cb.failure_count, 4)

            # 1 success
            res = await cb(succeeding_func)
            self.assertEqual(res, "OK")
            # Notice: failure_count remains 4 because success in CLOSED state doesn't reset it
            self.assertEqual(cb.failure_count, 4)

            # Next single failure trips circuit to OPEN
            with self.assertRaises(RuntimeError):
                await cb(failing_func)
            self.assertEqual(cb.state, CircuitState.OPEN)

        asyncio.run(run_test())

    def test_half_open_probe_concurrency(self):
        """
        Simulate load in HALF_OPEN state.
        When reset timeout expires, multiple concurrent requests arrive.
        Checks how many concurrent probe requests enter the function.
        """
        cb = CircuitBreaker("test_cb", failure_threshold=3, reset_timeout_seconds=0.05, half_open_consecutive_successes=3)

        async def failing_func():
            raise RuntimeError("API failure")

        concurrent_exec_count = 0

        async def slow_succeeding_func():
            nonlocal concurrent_exec_count
            concurrent_exec_count += 1
            await asyncio.sleep(0.05)
            return "OK"

        async def run_test():
            # 1. Trip circuit to OPEN
            for _ in range(3):
                with self.assertRaises(RuntimeError):
                    await cb(failing_func)
            self.assertEqual(cb.state, CircuitState.OPEN)

            # 2. Wait for reset timeout (50ms)
            await asyncio.sleep(0.06)

            # 3. Launch 10 concurrent requests
            tasks = [asyncio.create_task(cb(slow_succeeding_func)) for _ in range(10)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Analyze concurrency: how many probe calls executed concurrently?
            # Ideally HALF_OPEN limits probe requests to 1 or 3 concurrent calls.
            # But in the current implementation, all 10 tasks passed through into slow_succeeding_func!
            return concurrent_exec_count

        count = asyncio.run(run_test())
        # Print observation for analysis
        print(f"Concurrent probe calls in HALF_OPEN state: {count}")

    def test_half_open_to_closed_transition(self):
        cb = CircuitBreaker("test_cb", failure_threshold=3, reset_timeout_seconds=0.05, half_open_consecutive_successes=3)

        async def failing_func():
            raise RuntimeError("API failure")

        async def succeeding_func():
            return "OK"

        async def run_test():
            # Trip OPEN
            for _ in range(3):
                with self.assertRaises(RuntimeError):
                    await cb(failing_func)

            await asyncio.sleep(0.06)

            # 3 consecutive successes in HALF_OPEN state
            for i in range(3):
                res = await cb(succeeding_func)
                self.assertEqual(res, "OK")

            self.assertEqual(cb.state, CircuitState.CLOSED)
            self.assertEqual(cb.failure_count, 0)
            self.assertEqual(cb.success_count, 0)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
