# Phase03/07_Base_Classes.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/base.py`](#2-source-code-srccorebasepy)
3. [Design Decisions](#3-design-decisions)
4. [Usage Examples](#4-usage-examples)

---

# 1. Executive Summary

This document establishes the fundamental structural abstractions for the pipeline architecture. 

In modern Python, traditional `abc.ABC` (Abstract Base Classes) create rigid, nominal inheritance hierarchies that tightly couple modules together. To align with our strict Dependency Injection rules and favor composition, this module implements these architectural concepts using **`typing.Protocol`** (Structural Subtyping / Duck Typing). 

This allows a class to act as a `Repository` or a `PipelineModule` simply by implementing the required methods, without needing to explicitly subclass the base type.

---

# 2. Source Code: `src/core/base.py`

```python
"""
Core Structural Protocols and Base Classes.

Defines the architectural building blocks for the pipeline (Command, 
Factory, Repository, etc.). We utilize `@runtime_checkable` Protocols 
to enable strict typing and DI resolution without forcing concrete 
classes into rigid inheritance hierarchies.
"""

from typing import Any, Protocol, TypeVar, runtime_checkable

# Generic type variables for inputs, outputs, and standard entities
T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
T_contra = TypeVar("T_contra", contravariant=True)


# ==========================================
# 1. Pipeline Module
# ==========================================
@runtime_checkable
class PipelineModule(Protocol[T_contra, T_co]):
    """
    A core component of the Pipes and Filters architecture.
    Takes an input payload (T_contra) and produces an output payload (T_co).
    """
    def execute(self, payload: T_contra) -> T_co:
        ...


# ==========================================
# 2. Service
# ==========================================
@runtime_checkable
class Service(Protocol):
    """
    Marker protocol for Domain Services. 
    Services contain stateless business logic and orchestrate domain models.
    """
    pass


# ==========================================
# 3. Repository
# ==========================================
@runtime_checkable
class Repository(Protocol[T]):
    """
    Defines the contract for persistent storage (Database, Vector Store, File IO).
    Abstracts away the underlying storage mechanism.
    """
    def get(self, entity_id: str) -> T | None:
        ...

    def save(self, entity: T) -> None:
        ...

    def delete(self, entity_id: str) -> None:
        ...


# ==========================================
# 4. Provider
# ==========================================
@runtime_checkable
class Provider(Protocol[T_co]):
    """
    Provides read-only access to external data or resources 
    (e.g., an API Client or a configuration provider).
    """
    def provide(self) -> T_co:
        ...


# ==========================================
# 5. Factory
# ==========================================
@runtime_checkable
class Factory(Protocol[T_co]):
    """
    Responsible for encapsulating the complex creation logic of an object.
    """
    def create(self, **kwargs: Any) -> T_co:
        ...


# ==========================================
# 6. Command
# ==========================================
@runtime_checkable
class Command(Protocol):
    """
    Encapsulates a request as an object (Command Pattern).
    Useful for queuing background jobs (like YouTube upload tasks).
    """
    def execute(self) -> None:
        ...


# ==========================================
# 7. Configuration
# ==========================================
@runtime_checkable
class Configuration(Protocol):
    """
    Contract for configuration objects that require post-initialization validation.
    """
    def validate_config(self) -> None:
        ...


# ==========================================
# 8. Lifecycle
# ==========================================
@runtime_checkable
class Lifecycle(Protocol):
    """
    Defines startup and shutdown hooks for stateful components 
    (e.g., maintaining a persistent HTTP session or ChromaDB connection).
    """
    def initialize(self) -> None:
        ...

    def shutdown(self) -> None:
        ...


# ==========================================
# 9. Validation
# ==========================================
@runtime_checkable
class Validator(Protocol[T_contra]):
    """
    Contract for validating an object or data structure (e.g., JSON schema validation).
    """
    def validate(self, target: T_contra) -> bool:
        ...
```

---

# 3. Design Decisions

1. **Protocols over ABCs:** By using `Protocol`, our classes are completely decoupled. For example, `ChromaRAGEngine` doesn't need to `import Repository` and subclass it. It just implements `.get()` and `.save()`. Our `Container` can resolve it as a `Repository`, and `mypy` will perfectly type-check it without the rigid tight-coupling of `abc.ABC`.
2. **Covariance & Contravariance:** 
   - `T_co` (Covariant) is used for return types (like `Factory.create() -> T_co`). This allows a factory that creates `ScrapedProblem` to be recognized anywhere a factory that creates a generic `object` is expected.
   - `T_contra` (Contravariant) is used for input arguments (like `Validator.validate(target: T_contra)`). 
3. **`@runtime_checkable`:** Applied to all protocols. This allows developers to explicitly check `isinstance(obj, Lifecycle)` at runtime if they need to dynamically invoke `.shutdown()` on a collection of arbitrary plugins.

---

# 4. Usage Examples

### Example A: The Pipes & Filters Architecture
Because `PipelineModule` is fully generic, we can explicitly type the input/output boundaries of our modules.

```python
from src.core.base import PipelineModule
from src.models.problem import ScrapedProblem
from src.models.tags import TagKnowledge

# A module that takes a ScrapedProblem and outputs TagKnowledge
class GeminiTagExplorer:
    def execute(self, payload: ScrapedProblem) -> TagKnowledge:
        # Implementation...
        return tag_knowledge
        
# Mypy will correctly verify this assignment without inheritance:
explorer: PipelineModule[ScrapedProblem, TagKnowledge] = GeminiTagExplorer()
```

### Example B: Runtime Lifecycle Management
If the orchestrator manages multiple stateful services, it can gracefully shut them down using structural checking.

```python
from src.core.base import Lifecycle

services = [scraper_client, chroma_db, ffmpeg_assembler]

for service in services:
    if isinstance(service, Lifecycle):
        service.shutdown()  # Mypy knows .shutdown() exists here
```
