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
