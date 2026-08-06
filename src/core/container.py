"""
Dependency Injection Container Protocol module.
"""
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ResolverProtocol(Protocol):
    """Protocol for resolving services from dependency injection container."""

    def resolve(self, interface: Any) -> Any:
        ...


__all__ = ["ResolverProtocol"]
