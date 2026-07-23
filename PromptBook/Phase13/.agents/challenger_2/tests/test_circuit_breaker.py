"""
Empirical test suite for Challenge Focus 3: Circuit Breaker State Machine & Resiliency
"""
import sys
import unittest
import asyncio
import time
from enum import Enum
from typing import Any, Callable

# Exact reference implementation of CircuitBreaker from Section 4.1.2
class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitOpenError(Exception):
    """Raised when operation is attempted while circuit breaker is OPEN."""
    pass

class SpecCircuitBreaker:
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

    async def __call__(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        now = time.time()
        
        if self.state == CircuitState.OPEN:
            if now - self.last_state_change > self.reset_timeout_seconds:
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = now
                self.success_count = 0
            else:
                raise CircuitOpenError(
                    f"CircuitBreaker[{self.name}] is OPEN. Time until probe: {self.reset_timeout_seconds - (now - self.last_state_change):.1f}s"
                )

        try:
            result = await func(*args, **kwargs)
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.half_open_consecutive_successes:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.last_state_change = now
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0  # <--- Spec code resets failure_count on single success
            return result
        except Exception as exc:
            self.failure_count += 1
            if self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN):
                if self.failure_count >= self.failure_threshold or self.state == CircuitState.HALF_OPEN:
                    self.state = CircuitState.OPEN
                    self.last_state_change = now
            raise exc


class TestCircuitBreaker(unittest.TestCase):

    def test_intermittent_failures_prevent_circuit_from_ever_opening(self):
        """
        EMPIRICAL BUG PROOF 1:
        In SpecCircuitBreaker, self.failure_count is reset to 0 on ANY successful call when CLOSED.
        If an upstream service experiences 4 failures then 1 success (80% error rate),
        the failure count resets to 0 after every success.
        As a result, the circuit breaker NEVER opens despite an 80% failure rate over 100 requests!
        """
        async def run():
            cb = SpecCircuitBreaker(name="test_cb", failure_threshold=5)
            
            async def failing_func():
                raise RuntimeError("Service failure")

            async def succeeding_func():
                return "OK"

            # Execute pattern: 4 fails, 1 success, repeated 20 times (total 100 requests, 80 failures)
            for cycle in range(20):
                for _ in range(4):
                    try:
                        await cb(failing_func)
                    except RuntimeError:
                        pass
                # 4 failures accumulated, failure_count = 4
                self.assertEqual(cb.failure_count, 4)
                self.assertEqual(cb.state, CircuitState.CLOSED)

                # 1 success occurs
                res = await cb(succeeding_func)
                self.assertEqual(res, "OK")
                
                # BUG DEMONSTRATION: failure_count wiped out to 0!
                self.assertEqual(cb.failure_count, 0)
                self.assertEqual(cb.state, CircuitState.CLOSED)

            # Circuit remained CLOSED throughout all 100 requests (80 failures)!
            self.assertEqual(cb.state, CircuitState.CLOSED, "BUG: Circuit never opened despite 80% failure rate!")

        asyncio.run(run())

    def test_concurrent_requests_race_condition_in_half_open(self):
        """
        EMPIRICAL BUG PROOF 2:
        SpecCircuitBreaker lacks locks/synchronization.
        When state transitions from OPEN to HALF_OPEN after timeout, multiple concurrent tasks
        all pass through as probes simultaneously, bypassing half_open_consecutive_successes rate limiting.
        """
        async def run():
            cb = SpecCircuitBreaker(name="test_cb", failure_threshold=2, reset_timeout_seconds=0.05, half_open_consecutive_successes=3)

            async def failing_func():
                raise RuntimeError("Fail")

            async def slow_success_func():
                await asyncio.sleep(0.02)
                return "OK"

            # Force state to OPEN
            for _ in range(2):
                try:
                    await cb(failing_func)
                except RuntimeError:
                    pass
            self.assertEqual(cb.state, CircuitState.OPEN)

            # Wait for reset timeout
            await asyncio.sleep(0.06)

            # Fire 10 concurrent requests
            tasks = [cb(slow_success_func) for _ in range(10)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # All 10 requests were allowed to run concurrently because there is no concurrency limit or lock!
            successful = [r for r in results if r == "OK"]
            self.assertEqual(len(successful), 10, "All 10 concurrent requests bypassed HALF_OPEN probe limiting!")

        asyncio.run(run())

    def test_failure_count_not_reset_when_entering_half_open(self):
        """
        EMPIRICAL BUG PROOF 3:
        When transitioning OPEN -> HALF_OPEN, success_count is reset to 0, but failure_count is NOT reset.
        So failure_count remains at 5. If a single failure occurs in HALF_OPEN, failure_count becomes 6.
        """
        async def run():
            cb = SpecCircuitBreaker(name="test_cb", failure_threshold=3, reset_timeout_seconds=0.05)

            async def failing_func():
                raise RuntimeError("Fail")

            for _ in range(3):
                try:
                    await cb(failing_func)
                except RuntimeError:
                    pass
            self.assertEqual(cb.state, CircuitState.OPEN)
            self.assertEqual(cb.failure_count, 3)

            await asyncio.sleep(0.06)

            # Next call moves to HALF_OPEN but fails
            try:
                await cb(failing_func)
            except RuntimeError:
                pass

            # failure_count is now 4 (retained old failure_count)
            self.assertEqual(cb.failure_count, 4)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
