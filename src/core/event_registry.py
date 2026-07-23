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
