# Phase03/05_Dependency_Injection.md

**Author:** Principal Software Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Source Code: `src/core/container.py`](#2-source-code-srccorecontainerpy)
3. [Design Decisions](#3-design-decisions)
4. [Usage Example](#4-usage-example)

---

# 1. Executive Summary

This document provides the implementation for the system's Dependency Injection (DI) Container. Rather than relying on heavy third-party magic (like `dependency-injector`) or dangerous global state variables, this module implements a lightweight, explicitly typed IoC (Inversion of Control) container.

It supports:
- **Singletons:** For stateless utilities and configurations.
- **Transient Factories:** For objects that need fresh instantiation on every request.
- **Scoped Services:** For objects that share state per pipeline run (e.g., a database unit-of-work or shared API session).
- **Configuration Injection:** Seamlessly injecting `PipelineConfig` slices into services.
- **Strict Typing:** Guarantees that `container.resolve(MyProtocol)` returns a type-checked `MyProtocol` instance.

---

# 2. Source Code: `src/core/container.py`

```python
"""
Lightweight, strongly-typed Dependency Injection Container.

Provides registration and resolution of singletons, transient factories,
and scoped services without relying on global state.
"""

from collections.abc import Callable
from typing import Any, Protocol, TypeVar

T = TypeVar("T")


class ResolutionError(Exception):
    """Raised when a dependency cannot be resolved."""
    pass


class ResolverProtocol(Protocol):
    """Protocol defining the ability to resolve dependencies. 
    Implemented by both Container and Scope.
    """
    def resolve(self, interface: type[T]) -> T:
        ...


class Container:
    """
    A lightweight, strictly-typed Dependency Injection container.
    """

    def __init__(self) -> None:
        self._singletons: dict[type[Any], Any] = {}
        self._factories: dict[type[Any], Callable[[ResolverProtocol], Any]] = {}
        self._scoped_factories: dict[type[Any], Callable[[ResolverProtocol], Any]] = {}

    def register_singleton(self, interface: type[T], instance: T) -> None:
        """
        Register a pre-instantiated singleton.
        """
        self._singletons[interface] = instance

    def register_factory(
        self, 
        interface: type[T], 
        factory: Callable[[ResolverProtocol], T]
    ) -> None:
        """
        Register a transient factory. The factory is executed every time 
        the dependency is resolved.
        """
        self._factories[interface] = factory

    def register_scoped(
        self, 
        interface: type[T], 
        factory: Callable[[ResolverProtocol], T]
    ) -> None:
        """
        Register a factory whose result is cached per Scope.
        """
        self._scoped_factories[interface] = factory

    def resolve(self, interface: type[T]) -> T:
        """
        Resolve a dependency from the root container.
        
        Note: Scoped dependencies cannot be resolved directly from the 
        root container; they require a Scope context.
        """
        if interface in self._singletons:
            return self._singletons[interface]
        
        if interface in self._factories:
            return self._factories[interface](self)
            
        if interface in self._scoped_factories:
            raise ResolutionError(
                f"Cannot resolve scoped dependency '{interface.__name__}' from "
                "the root container. Use container.create_scope() instead."
            )

        raise ResolutionError(f"No registration found for '{interface.__name__}'")

    def create_scope(self) -> "Scope":
        """
        Create a new resolution scope for managing scoped lifecycles.
        """
        return Scope(self)


class Scope:
    """
    A resolution scope for caching scoped dependencies (e.g., per pipeline run).
    """

    def __init__(self, container: Container) -> None:
        self._container = container
        self._scoped_instances: dict[type[Any], Any] = {}

    def resolve(self, interface: type[T]) -> T:
        """
        Resolve a dependency within this scope.
        
        Resolution Order:
        1. Local scope cache.
        2. Local scope factories.
        3. Fallback to root container (for transients and singletons).
        """
        # 1. Check if already instantiated in this scope
        if interface in self._scoped_instances:
            return self._scoped_instances[interface]
            
        # 2. Check if there is a scoped factory
        if interface in self._container._scoped_factories:
            # Execute the factory, passing 'self' (the Scope) so any 
            # nested dependencies use this same scope.
            instance = self._container._scoped_factories[interface](self)
            self._scoped_instances[interface] = instance
            return instance
            
        # 3. Fallback to root container for Singletons and Transients
        # We temporarily hijack the root container's factory execution by passing 
        # 'self' (the Scope) to ensure nested transients resolve via the scope.
        if interface in self._container._singletons:
            return self._container._singletons[interface]
            
        if interface in self._container._factories:
            return self._container._factories[interface](self)
            
        raise ResolutionError(f"No registration found for '{interface.__name__}'")
```

---

# 3. Design Decisions

1. **No Global State:** There is no global `get_container()` or magic `@inject` decorators that hide dependencies. The container is instantiated in `__main__.py` and used solely to wire dependencies at the composition root.
2. **ResolverProtocol:** By defining a `ResolverProtocol`, factories don't need to know if they are being executed by the root `Container` or a localized `Scope`. This ensures nested transient dependencies correctly inherit the active scope.
3. **Lazy Loading:** Registration is extremely fast because factories are just function pointers. Heavy objects (like initializing ChromaDB or loading Kokoro models) are only executed the first time `.resolve()` is actually called on them.

---

# 4. Usage Example

This is how the system will be wired up inside `__main__.py`:

```python
from src.core.container import Container, ResolverProtocol
from src.core.config import PipelineConfig, load_config
from src.scraper.scraper import LeetCodeScraper
from src.models.protocols import ScraperProtocol

def bootstrap_container() -> Container:
    container = Container()
    
    # 1. Register Configuration (Singleton)
    config = load_config()
    container.register_singleton(PipelineConfig, config)
    
    # 2. Register Implementations (Factory)
    def build_scraper(resolver: ResolverProtocol) -> ScraperProtocol:
        cfg = resolver.resolve(PipelineConfig)
        return LeetCodeScraper(config=cfg.scraper)
        
    container.register_factory(ScraperProtocol, build_scraper)
    
    return container

# Usage
container = bootstrap_container()
scraper = container.resolve(ScraperProtocol)
```
