# Phase06/07_EventRegistry.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/event_registry.py`](#2-source-code-srccoreevent_registrypy)
3. [Design Decisions](#3-design-decisions)

---

# 1. Executive Summary

This document introduces the **Event Registry**. 

In an asynchronous microservice or plugin-based architecture, it is incredibly easy for publishers to push arbitrary, malformed dictionaries to the Event Bus, causing downstream subscribers to crash with `KeyError`. 

The `EventRegistry` solves this by acting as a central Schema Catalog. During boot, plugins register their target Topics alongside a strict Pydantic `BaseModel` schema. When the `EventPublisher` attempts to broadcast an event, it queries the Registry to mathematically validate the payload dictionary against the registered schema, intercepting malformed data *before* it ever hits the Event Bus queues.

---

# 2. Source Code: `src/core/event_registry.py`

```python
"""
Event Registry.

Maintains a centralized catalog of all valid Event topics and their 
associated Pydantic schemas. Enforces payload validation and versioning.
"""

import logging
import threading
from typing import Any, Optional, Type

from pydantic import BaseModel, ValidationError

from src.core.exceptions import PipelineError


class EventRegistryError(PipelineError):
    """Raised on schema registration conflicts or payload validation failures."""
    pass


class EventSchemaMetadata:
    """Holds the logical mapping between a routing topic and its Pydantic schema."""
    def __init__(
        self, 
        topic: str, 
        version: str, 
        schema: Type[BaseModel], 
        description: str = ""
    ) -> None:
        self.topic = topic
        self.version = version
        self.schema = schema
        self.description = description
        self.aliases: set[str] = set()


class EventRegistry:
    """
    Thread-safe catalog for Event topics.
    Used by the EventPublisher to validate payloads before transmission.
    """

    def __init__(self) -> None:
        self._schemas: dict[str, EventSchemaMetadata] = {}
        self._aliases: dict[str, str] = {}
        
        # Protects the catalog during concurrent Plugin Discovery boots
        self._lock = threading.RLock()
        self._logger = logging.getLogger(__name__)

    def register(
        self, 
        topic: str, 
        version: str, 
        schema: Type[BaseModel], 
        description: str = "", 
        aliases: list[str] | None = None
    ) -> None:
        """
        Registers a new topic and its expected Pydantic schema.
        Throws an error on duplicate version collisions.
        """
        with self._lock:
            # 1. Duplicate & Version Conflict Detection
            if topic in self._schemas:
                existing = self._schemas[topic]
                if existing.version == version:
                    raise EventRegistryError(f"Duplicate registration for topic '{topic}' (v{version})")
                self._logger.warning(
                    f"Overwriting topic '{topic}' schema (v{existing.version} -> v{version})"
                )

            # 2. Build Metadata
            meta = EventSchemaMetadata(topic, version, schema, description)
            
            # 3. Alias Mapping (e.g., 'video.done' -> 'plugin.core.render.completed')
            if aliases:
                for alias in aliases:
                    if alias in self._aliases and self._aliases[alias] != topic:
                        raise EventRegistryError(
                            f"Alias '{alias}' is already mapped to '{self._aliases[alias]}'"
                        )
                    self._aliases[alias] = topic
                    meta.aliases.add(alias)
                    
            # 4. Commit
            self._schemas[topic] = meta
            self._logger.debug(f"Registered event schema: {topic} (v{version})")

    def lookup(self, topic_or_alias: str) -> Optional[EventSchemaMetadata]:
        """O(1) retrieval of a schema by its direct topic name or registered alias."""
        with self._lock:
            if topic_or_alias in self._schemas:
                return self._schemas[topic_or_alias]
            
            if topic_or_alias in self._aliases:
                real_topic = self._aliases[topic_or_alias]
                return self._schemas.get(real_topic)
                
            return None

    def validate_payload(self, topic_or_alias: str, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Validates a raw dictionary against the registered Pydantic schema.
        Returns the parsed/validated dictionary.
        """
        meta = self.lookup(topic_or_alias)
        if not meta:
            # Flexible routing: If a developer pushes a dynamic event without registering it,
            # we allow it through with a warning rather than hard-crashing the pipeline.
            self._logger.warning(
                f"Topic '{topic_or_alias}' is unregistered. Skipping strict schema validation."
            )
            return payload
            
        try:
            # Instantiate the Pydantic model to trigger native Rust-based validation,
            # then immediately dump it back to a dictionary for the Event envelope.
            model = meta.schema(**payload)
            return model.model_dump()
        except ValidationError as e:
            raise EventRegistryError(f"Payload validation failed for '{topic_or_alias}': {e}") from e

    def search(self, query: str) -> list[EventSchemaMetadata]:
        """
        Returns all schemas containing the query in their topic, alias, or description.
        Useful for the CLI `agy events search <query>` command.
        """
        query = query.lower()
        results = []
        with self._lock:
            for meta in self._schemas.values():
                if query in meta.topic.lower() or query in meta.description.lower():
                    results.append(meta)
                else:
                    for alias in meta.aliases:
                        if query in alias.lower():
                            results.append(meta)
                            break
        return results
```

---

# 3. Design Decisions

1. **Thread-Safety (`RLock`)**: During pipeline startup, multiple plugins (Scraper, RAG, Video) will initialize concurrently and attempt to register their schemas simultaneously. The `threading.RLock()` guarantees that the dictionary mappings do not suffer from race conditions or memory corruption.
2. **Pydantic Validation Bridging**: The `validate_payload()` method elegantly bridges the gap between raw dictionaries and Pydantic. It takes the `payload` dict, injects it into `meta.schema(**payload)`, letting Pydantic perform type-checking (e.g., ensuring `timeout` is an `int`), and then calls `.model_dump()` to return the sanitized dictionary to the Publisher.
3. **Flexible Degradation**: If a topic is not registered, the `validate_payload()` method logs a warning but allows the payload through. This prevents a forgotten registration line from fatally crashing a 2-hour video render in production.
4. **Alias Tracking**: We allow plugins to register human-readable aliases. For example, `plugin.core.renderer.ffmpeg.completed` can be aliased to `video.done`. If the Publisher transmits to `video.done`, the Registry instantly maps it to the correct schema and validates it.
