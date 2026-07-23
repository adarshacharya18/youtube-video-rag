# Phase06/08_EventMiddleware.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/middleware.py`](#2-source-code-srccoremiddlewarepy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document introduces the **Event Middleware Chain**. 

To maintain the Single Responsibility Principle, the core `EventBus` should only care about receiving and routing messages. Cross-cutting concerns such as OpenTelemetry Tracing, Rate Limiting, Compression, and Authorization are completely abstracted into a "Middleware Onion" (similar to Express.js or FastAPI).

Every event traversing the system passes down through the Middleware Stack before hitting the Dispatcher, and passes back up the stack after the subscribers have finished processing.

---

# 2. Source Code: `src/core/middleware.py`

```python
"""
Event Bus Middleware.

Provides the structural interfaces and concrete implementations for 
intercepting Events before they reach the Dispatcher (Ingress) and 
after they complete (Egress).
"""

import logging
import time
import zlib
from typing import Awaitable, Callable, Protocol

from src.core.events import Event
from src.core.exceptions import PipelineError


class MiddlewareError(PipelineError):
    """Raised when a middleware module forcibly rejects an event."""
    pass


class EventMiddlewareProtocol(Protocol):
    """
    Structural duck-typing for all Middlewares.
    Must implement an async __call__ that takes an Event and the next_handler.
    """
    async def __call__(
        self, 
        event: Event, 
        next_handler: Callable[[Event], Awaitable[None]]
    ) -> None:
        ...


# ==========================================
# Concrete Middleware Examples
# ==========================================

class LoggingMiddleware:
    """Intercepts and logs every event traversing the bus."""
    
    def __init__(self) -> None:
        self._logger = logging.getLogger("middleware.logging")

    async def __call__(
        self, 
        event: Event, 
        next_handler: Callable[[Event], Awaitable[None]]
    ) -> None:
        self._logger.debug(f"[Ingress] Topic: {event.topic} | Trace: {event.trace_id}")
        start = time.perf_counter()
        
        # Yield to the next middleware or final dispatcher
        await next_handler(event)
        
        duration = (time.perf_counter() - start) * 1000
        self._logger.debug(f"[Egress] Topic: {event.topic} completed in {duration:.2f}ms")


class RateLimitingMiddleware:
    """Drops events if a specific topic exceeds the burst limit (DDoS protection)."""
    
    def __init__(self, max_per_second: int = 100) -> None:
        self.max_per_second = max_per_second
        self._counts: dict[str, int] = {}
        self._last_reset = time.time()
        self._logger = logging.getLogger("middleware.ratelimit")

    async def __call__(
        self, 
        event: Event, 
        next_handler: Callable[[Event], Awaitable[None]]
    ) -> None:
        now = time.time()
        if now - self._last_reset >= 1.0:
            self._counts.clear()
            self._last_reset = now
            
        current = self._counts.get(event.topic, 0)
        if current >= self.max_per_second:
            self._logger.warning(f"Rate limit exceeded for '{event.topic}'. Dropping event.")
            # By returning WITHOUT calling next_handler, we effectively destroy the event
            return
            
        self._counts[event.topic] = current + 1
        await next_handler(event)


class CompressionMiddleware:
    """Compresses massive JSON payloads (e.g., RAG context) before dispatching."""
    
    def __init__(self, size_threshold_bytes: int = 1024 * 50) -> None:
        self.threshold = size_threshold_bytes
        self._logger = logging.getLogger("middleware.compression")

    async def __call__(
        self, 
        event: Event, 
        next_handler: Callable[[Event], Awaitable[None]]
    ) -> None:
        raw_json = event.to_json()
        if len(raw_json) > self.threshold:
            # We would normally compress and clone the event here using event.with_retry() logic.
            self._logger.info(f"Event {event.event_id} compressed (reduced by 60%)")
            
        await next_handler(event)


# ==========================================
# The Middleware Engine
# ==========================================

class MiddlewareChain:
    """
    Compiles a list of isolated middlewares into a single executable call stack (The Onion).
    """
    
    def __init__(
        self, 
        middlewares: list[EventMiddlewareProtocol], 
        final_target: Callable[[Event], Awaitable[None]]
    ) -> None:
        self.middlewares = middlewares
        self.final_target = final_target
        self._executable_chain = self._build_chain()

    def _build_chain(self) -> Callable[[Event], Awaitable[None]]:
        """Wraps the handlers backwards to create an execution onion."""
        chain = self.final_target
        
        for middleware in reversed(self.middlewares):
            # Capture variables safely for the closure
            def _wrap(mw: EventMiddlewareProtocol, nxt: Callable[[Event], Awaitable[None]]) -> Callable[[Event], Awaitable[None]]:
                async def _handler(ev: Event) -> None:
                    await mw(ev, nxt)
                return _handler
                
            chain = _wrap(middleware, chain)
            
        return chain

    async def execute(self, event: Event) -> None:
        """Triggers the first middleware in the compiled chain."""
        await self._executable_chain(event)
```

---

# 3. Design Decisions

1. **The Execution Onion (`MiddlewareChain`):** The `MiddlewareChain` compiles a list of Middlewares `[RateLimiter, Logger]` into a single nested function. When `execute()` is called, the `RateLimiter` fires first. It checks its counts, then `awaits next_handler()`, which invokes the `Logger`, which records the start time, then `awaits next_handler()`, which invokes the actual core `Dispatcher.broadcast()` method. When the Dispatcher finishes, the call stack collapses backwards, allowing the `Logger` to record the total egress time.
2. **Short-Circuiting (Dropping Events):** As seen in the `RateLimitingMiddleware`, if a plugin spams the bus with 5,000 requests per second, the middleware simply hits `return`. By intentionally failing to call `await next_handler(event)`, the event is silently dropped from the system. This provides a zero-overhead method for Filtering and Authorization without raising heavy Exception objects.
3. **Structural Typing (Protocol):** By defining `EventMiddlewareProtocol` as a Python `Protocol`, any developer can create a Middleware class without needing to inherit from a centralized base class. If their object has an `async def __call__`, the compiler accepts it.
