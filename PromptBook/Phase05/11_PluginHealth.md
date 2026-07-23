# Phase05/11_PluginHealth.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/plugins/health.py`](#2-source-code-srcpluginshealthpy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document introduces the **Plugin Health Monitor**. While the Core `HealthMonitor` checks OS-level statistics (CPU/Disk/RAM), the Plugin Health Monitor runs a background `asyncio` task specifically designed to ping the `.health()` and `.state` properties of every active plugin in the Registry.

It enforces **Liveness** (is the plugin hanging in an infinite loop?) and **Readiness** (is it in the `RUNNING` state and capable of accepting Event Bus messages?). If a plugin fails its heartbeat three times in a row, the Health Monitor automatically soft-disables it in the Registry to prevent the Workflow Engine from routing jobs into a dead node.

---

# 2. Source Code: `src/plugins/health.py`

```python
"""
Plugin Health Engine.

Aggregates and monitors the health, liveness, and readiness of all active plugins.
Integrates directly with the central Plugin Registry to perform auto-evictions.
"""

import asyncio
import logging
from typing import Any

from src.core.module_lifecycle import ModuleState
from src.plugins.base import PluginHealth, PluginProtocol
from src.plugins.registry import PluginRegistry


class PluginHealthMonitor:
    """
    Background daemon that continuously polls active plugins for heartbeats.
    Automatically disables crashing plugins after consecutive failures.
    """

    def __init__(self, registry: PluginRegistry, interval_sec: float = 30.0) -> None:
        self._registry = registry
        self._interval = interval_sec
        self._logger = logging.getLogger(__name__)
        
        self._running = False
        self._task: asyncio.Task[None] | None = None
        
        # Tracking consecutive failures: plugin_id -> fail_count
        self._failure_counts: dict[str, int] = {}
        
        # The threshold of consecutive failures before auto-eviction
        self._max_failures = 3

    async def start(self) -> None:
        """Starts the background heartbeat loop."""
        if self._running:
            return
            
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        self._logger.info(f"Plugin Health Monitor started. Polling every {self._interval}s.")

    async def stop(self) -> None:
        """Gracefully halts the polling loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._logger.info("Plugin Health Monitor stopped.")

    async def _monitor_loop(self) -> None:
        """The core polling loop running asynchronously in the background."""
        while self._running:
            try:
                await asyncio.sleep(self._interval)
                await self._check_all()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Plugin health monitor loop crashed: {e}", exc_info=True)

    async def _check_all(self) -> None:
        """Executes a ping against every active plugin."""
        active_plugins = self._registry.get_all_active()
        
        for plugin in active_plugins:
            manifest = plugin.manifest
            pid = manifest.id
            
            try:
                # 1. Readiness Check (Is it formally running?)
                if plugin.state in (ModuleState.FAILED, ModuleState.STOPPED, ModuleState.SHUTDOWN):
                    self._handle_unhealthy(pid, {"error": f"Invalid state for routing: {plugin.state.name}"})
                    continue
                    
                # 2. Liveness Check (Is the thread hanging?)
                # We wrap the synchronous .health() check in a thread and an asyncio timeout
                # to guarantee a hanging plugin doesn't hang the master health monitor.
                health: PluginHealth = await asyncio.wait_for(
                    asyncio.to_thread(plugin.health), 
                    timeout=5.0
                )
                
                # 3. Status Check (Did the plugin report an internal error, e.g., DB offline?)
                if not health.is_healthy:
                    self._handle_unhealthy(pid, health.details)
                else:
                    self._handle_healthy(pid)
                    
            except asyncio.TimeoutError:
                self._handle_unhealthy(pid, {"error": "Liveness check timed out after 5.0 seconds"})
            except Exception as e:
                self._handle_unhealthy(pid, {"error": f"Health check raised exception: {e}"})

    def _handle_unhealthy(self, plugin_id: str, details: dict[str, str]) -> None:
        """Increments the failure counter and triggers auto-eviction if threshold met."""
        count = self._failure_counts.get(plugin_id, 0) + 1
        self._failure_counts[plugin_id] = count
        
        self._logger.warning(
            f"[{plugin_id}] Health check failed (Strike {count}/{self._max_failures}). Details: {details}"
        )
        
        if count >= self._max_failures:
            self._logger.critical(
                f"[{plugin_id}] Reached maximum failure threshold. Auto-Evicting from Registry!"
            )
            # Soft-disable the plugin so the Workflow Engine stops routing traffic to it
            self._registry.disable(plugin_id)
            # Reset the count so if an admin manually hot-reloads it, it starts fresh
            self._failure_counts[plugin_id] = 0

    def _handle_healthy(self, plugin_id: str) -> None:
        """Resets the failure counter on a successful heartbeat."""
        if self._failure_counts.get(plugin_id, 0) > 0:
            self._logger.info(f"[{plugin_id}] Recovered. Health checks are passing again.")
            self._failure_counts[plugin_id] = 0

    def generate_report(self) -> dict[str, Any]:
        """
        Generates a comprehensive JSON-serializable snapshot of the ecosystem.
        Useful for the CLI `agy health` command or the HTTP Dashboard.
        """
        report = {}
        for plugin in self._registry.get_all_active():
            pid = plugin.manifest.id
            try:
                health = plugin.health()
                report[pid] = {
                    "status": "HEALTHY" if health.is_healthy else "UNHEALTHY",
                    "readiness_state": plugin.state.name,
                    "consecutive_failures": self._failure_counts.get(pid, 0),
                    "details": health.details
                }
            except Exception as e:
                report[pid] = {
                    "status": "ERROR",
                    "readiness_state": plugin.state.name,
                    "consecutive_failures": self._failure_counts.get(pid, 0),
                    "error_message": str(e)
                }
                
        return report
```

---

# 3. Design Decisions

1. **Background Daemon Architecture:** The monitor spawns as a native `asyncio.Task` that sleeps for 30 seconds. It operates entirely independently of the Event Bus or Workflow Engine. This separation of concerns means that even under 100% CPU video-rendering load, the application's health-check supervisor remains decoupled and highly responsive.
2. **Auto-Eviction Circuit Breaker:** By tying the Health Monitor directly to the `PluginRegistry`, we created a self-healing Pipeline. If the FFmpeg plugin crashes three times in a row, the Monitor calls `self._registry.disable(plugin_id)`. The Workflow Engine immediately receives `PluginNotFoundError` upon its next request and can gracefully re-route the job or pause the pipeline, rather than endlessly attempting to use a dead plugin.
3. **Thread-Safe Liveness Ping:** The `await asyncio.wait_for(asyncio.to_thread(plugin.health), timeout=5.0)` line is critical. If a plugin's `.health()` method involves pinging an offline PostgreSQL database with no timeout, calling it normally would freeze the master monitor. By pushing it to a background thread and wrapping it in an `asyncio` timeout, we guarantee the master supervisor cannot be frozen by poorly coded plugins.
