# Phase05/14_PluginTests.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `tests/plugins/test_plugins.py`](#2-source-code-testspluginstest_pluginspy)
3. [Testing Strategies](#3-testing-strategies)

---

# 1. Executive Summary

This document introduces the comprehensive **Plugin SDK Test Suite**. To guarantee the stability of the Application Runtime when dealing with 3rd-party code, this test suite utilizes `pytest` to assert strict mathematical boundaries.

It thoroughly exercises:
- **Directed Acyclic Graph (DAG) Integrity:** Proving that dependencies are loaded first and missing requirements throw exact errors.
- **Alias Resolution:** Validating the thread-safe `PluginRegistry` can seamlessly resolve workflow aliases (e.g., `text-to-speech`) into concrete active plugins.
- **Immutability:** Defending the Configuration Manager against unauthorized deep-dictionary mutations.
- **Finite State Machine (FSM) Transitions:** Emulating a full start/pause/stop lifecycle utilizing the `PluginLifecycleSupervisor`.

---

# 2. Source Code: `tests/plugins/test_plugins.py`

*(The complete test suite is available in the codebase. It employs PyTest fixtures to simulate manifest loading without requiring real disk I/O, generating high-velocity unit tests.)*

---

# 3. Testing Strategies

1. **In-Memory Fixtures over Disk I/O:** Rather than forcing the `PluginDiscoverer` to actually read `manifest.yaml` files from `/tmp`, the tests dynamically construct `PluginManifest` objects using Pydantic. This speeds up the execution time dramatically and isolates the topological sort logic from OS-level disk permissions.
2. **Abstract Base Plugin Mocks:** The test suite generates a `MockPlugin(AbstractBasePlugin)` on the fly. Because `AbstractBasePlugin` natively satisfies the duck-typing `PluginProtocol`, we can accurately test the exact lifecycle logic (start, pause, shutdown) without needing to spin up heavy actual plugins (like FFmpeg or PostgreSQL).
3. **Immutability Assertions:** In `test_plugin_configuration_immutability`, we pull the configuration `snapshot`, deliberately attempt to inject a `["hacked"] = True` key into the dictionary, and assert that the internal `PluginConfigManager` remains unpolluted. This proves our `copy.deepcopy()` defense is working.
