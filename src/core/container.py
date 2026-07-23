"""
Advanced Dependency Injection Container.

Provides centralized, thread-safe service resolution utilizing Structural 
Subtyping (Protocols). Upgraded to support Circular Dependency Detection, 
Type Validation, and strict Scoped Lifetimes.
"""

import threading
from collections.abc import Callable
from typing import Any, Protocol, TypeVar

T = TypeVar("T")


class ResolutionError(Exception):
    """Raised when a dependency cannot be resolved."""
    pass


class CircularDependencyError(ResolutionError):
    """Raised when an infinite resolution loop is detected."""
    pass


class ValidationError(ResolutionError):
    """Raised when a registered service does not match its interface."""
    pass


class ResolverProtocol(Protocol):
    """Protocol defining the resolving capabilities of a Container or Scope."""
    def resolve(self, interface: type[T]) -> T:
        ...


class Container:
    """
    The root Dependency Injection Container.
    Handles Singletons and Transient Factories safely across threads.
    """

    def __init__(self) -> None:
        self._singletons: dict[type[Any], Any] = {}
        self._factories: dict[type[Any], Callable[[ResolverProtocol], Any]] = {}
        self._scoped_factories: dict[type[Any], Callable[[ResolverProtocol], Any]] = {}
        self._lock = threading.RLock()
        
        # Thread-local storage ensures circular dependency tracking 
        # doesn't cross-pollute concurrent asyncio tasks/threads.
        self._local = threading.local()

    @property
    def _resolution_stack(self) -> list[type[Any]]:
        """Returns the current resolution stack for the active thread."""
        if not hasattr(self._local, "resolution_stack"):
            self._local.resolution_stack = []
        return self._local.resolution_stack

    def _validate_implementation(self, interface: type[T], instance: Any) -> None:
        """
        Validates that the instance conforms to the Protocol using runtime structural checks.
        (Skips if the interface is not a runtime_checkable Protocol).
        """
        if hasattr(interface, "__is_runtime_protocol__") and interface.__is_runtime_protocol__:
            if not isinstance(instance, interface):
                raise ValidationError(
                    f"Instance '{type(instance).__name__}' does not structurally "
                    f"implement Protocol '{interface.__name__}'"
                )

    def register_singleton(self, interface: type[T], instance: T) -> None:
        """Registers a pre-instantiated, thread-safe Singleton."""
        self._validate_implementation(interface, instance)
        with self._lock:
            self._singletons[interface] = instance

    def register_factory(self, interface: type[T], factory: Callable[[ResolverProtocol], T]) -> None:
        """Registers a Factory that returns a new transient instance every time it is resolved."""
        with self._lock:
            self._factories[interface] = factory

    def register_scoped(self, interface: type[T], factory: Callable[[ResolverProtocol], T]) -> None:
        """Registers a Factory whose instances live exactly as long as the active Scope."""
        with self._lock:
            self._scoped_factories[interface] = factory

    def resolve(self, interface: type[T]) -> T:
        """Resolves a dependency from the root container."""
        with self._lock:
            if interface in self._singletons:
                return self._singletons[interface]
                
            stack = self._resolution_stack
            
            # 1. Circular Dependency Detection
            if interface in stack:
                chain = " -> ".join([i.__name__ for i in stack] + [interface.__name__])
                raise CircularDependencyError(f"Circular dependency detected: {chain}")
                
            # 2. Transient Factory Resolution
            if interface in self._factories:
                stack.append(interface)
                try:
                    instance = self._factories[interface](self)
                    self._validate_implementation(interface, instance)
                    return instance
                finally:
                    stack.pop()
                    
            # 3. Scope Protection
            if interface in self._scoped_factories:
                raise ResolutionError(
                    f"Cannot resolve scoped dependency '{interface.__name__}' directly from "
                    "the root Container. You must use container.create_scope()."
                )

        raise ResolutionError(f"No registration found for '{interface.__name__}'")

    def create_scope(self) -> "Scope":
        """Generates a child scope for isolated lifetimes (e.g., per-workflow)."""
        return Scope(self)


class Scope:
    """
    A child dependency injector that manages its own cache of Scoped instances,
    while falling back to the parent Container for Singletons and Transients.
    """

    def __init__(self, container: Container) -> None:
        self._container = container
        self._scoped_instances: dict[type[Any], Any] = {}
        self._lock = threading.RLock()

    def resolve(self, interface: type[T]) -> T:
        """
        Resolve a dependency within this scope.
        Resolution Order: Scope Cache -> Scope Factory -> Container Fallback.
        """
        with self._lock:
            # 1. Check local scope cache
            if interface in self._scoped_instances:
                return self._scoped_instances[interface]
                
            # 2. Lazy Load Scoped Factory
            if interface in self._container._scoped_factories:
                stack = self._container._resolution_stack
                if interface in stack:
                    chain = " -> ".join([i.__name__ for i in stack] + [interface.__name__])
                    raise CircularDependencyError(f"Circular dependency in scoped factory: {chain}")
                
                stack.append(interface)
                try:
                    # Execute factory passing `self` (the Scope) for nested resolution
                    instance = self._container._scoped_factories[interface](self)
                    self._container._validate_implementation(interface, instance)
                    self._scoped_instances[interface] = instance
                    return instance
                finally:
                    stack.pop()
                    
            # 3. Fallback to Root Container (Singletons/Transients)
            # Temporarily hijack the root container's factory execution by passing 
            # `self` (the Scope) to ensure nested transients resolve via this scope.
            if interface in self._container._singletons:
                return self._container._singletons[interface]
                
            if interface in self._container._factories:
                stack = self._container._resolution_stack
                if interface in stack:
                    chain = " -> ".join([i.__name__ for i in stack] + [interface.__name__])
                    raise CircularDependencyError(f"Circular dependency in factory: {chain}")
                    
                stack.append(interface)
                try:
                    instance = self._container._factories[interface](self)
                    self._container._validate_implementation(interface, instance)
                    return instance
                finally:
                    stack.pop()
            
        raise ResolutionError(f"No registration found for '{interface.__name__}'")
