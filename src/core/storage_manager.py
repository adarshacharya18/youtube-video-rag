"""
Core Storage Management Engine.

Coordinates database connections, exposes the Unit of Work pattern for Transactions,
and manages the lifecycle and health of all registered Repositories.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional, Protocol

from src.core.exceptions import PipelineError
from src.core.metrics import MetricsRegistry


class StorageError(PipelineError):
    """Raised during connection failures or Transaction corruption."""
    pass


class StoreProtocol(Protocol):
    """
    Duck-typed interface that every Physical Repository (SQLite, ChromaDB, S3) 
    must rigidly implement to be registered.
    """
    async def initialize(self) -> None: ...
    async def shutdown(self) -> None: ...
    async def check_health(self) -> bool: ...


class TransactionProtocol(Protocol):
    """Duck-typed interface strictly for ACID-compliant databases."""
    async def begin(self) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...


class StorageManager:
    """Centralized Registry and Lifecycle orchestrator for physical databases."""

    def __init__(self, metrics: Optional[MetricsRegistry] = None) -> None:
        self._stores: dict[str, StoreProtocol] = {}
        self._metrics = metrics
        self._logger = logging.getLogger(__name__)
        self._initialized = False

    def register_store(self, name: str, store: StoreProtocol) -> None:
        """Injects a database wrapper into the universal registry."""
        if name in self._stores:
            raise StorageError(f"FATAL: Store '{name}' is already registered.")
        self._stores[name] = store
        self._logger.info(f"Registered storage backend: '{name}'")

    def get_store(self, name: str) -> StoreProtocol:
        """Retrieves a store. Highly useful for Dependency Injection in testing."""
        if name not in self._stores:
            raise StorageError(f"FATAL: Store '{name}' not found in registry.")
        return self._stores[name]

    async def initialize_all(self) -> None:
        """
        Executes the Boot Sequence for all databases (Schema Migrations, Socket bindings).
        """
        if self._initialized:
            return
        
        for name, store in self._stores.items():
            self._logger.info(f"Initializing Storage Connection: '{name}'...")
            try:
                await store.initialize()
            except Exception as e:
                # If one DB fails to boot, the entire application MUST halt
                raise StorageError(f"Failed to initialize database '{name}': {e}") from e
                
        self._initialized = True
        self._logger.info("All registered storage backends initialized successfully.")

    async def shutdown_all(self) -> None:
        """
        Safely flushes memory and closes all open Database connections.
        Prevents SQLite corruption during server reboots.
        """
        for name, store in self._stores.items():
            self._logger.info(f"Executing Safe Shutdown for: '{name}'...")
            try:
                await store.shutdown()
            except Exception as e:
                self._logger.error(f"Error shutting down '{name}' connection: {e}")
        self._initialized = False

    async def check_health(self) -> dict[str, bool]:
        """
        Proactively tests if the Databases are online.
        Used by the Web Server to return HTTP 500s on the /healthz endpoint if a DB crashes.
        """
        health: dict[str, bool] = {}
        for name, store in self._stores.items():
            try:
                # Use wait_for to prevent a hanging network DB from spin-locking the Health Check
                is_healthy = await asyncio.wait_for(store.check_health(), timeout=5.0)
                health[name] = is_healthy
            except asyncio.TimeoutError:
                self._logger.error(f"Health check for '{name}' TIMED OUT after 5s.")
                health[name] = False
            except Exception as e:
                self._logger.error(f"Health check for '{name}' FAILED: {e}")
                health[name] = False
        return health

    @asynccontextmanager
    async def transaction(self, store_name: str) -> AsyncGenerator[StoreProtocol, None]:
        """
        Unit of Work (UoW) Context Manager.
        Yields the store and mathematically guarantees an atomic Commit or Rollback.
        """
        store = self.get_store(store_name)
        
        # Runtime verification of the TransactionProtocol
        if not hasattr(store, "begin") or not hasattr(store, "commit") or not hasattr(store, "rollback"):
            raise StorageError(f"Database '{store_name}' does not natively support ACID transactions.")
        
        txn_store: Any = store 
        
        if self._metrics:
            timer = self._metrics.measure_time(f"storage.transaction.{store_name}")
            timer.__enter__()
            
        try:
            await txn_store.begin()
            
            # Yield control back to the Business Logic
            yield store
            
            # If no exception was raised in the Business Logic block, Commit to Disk
            await txn_store.commit()
            
            if self._metrics:
                self._metrics.increment_counter(f"storage.transaction.{store_name}.commit")
                
        except Exception as e:
            # If Business Logic crashes (e.g., KeyError, IOError), physically UNDO the DB changes
            self._logger.error(f"Transaction crash on '{store_name}'. Executing Database ROLLBACK! {e}")
            await txn_store.rollback()
            
            if self._metrics:
                self._metrics.increment_counter(f"storage.transaction.{store_name}.rollback")
            raise e
            
        finally:
            if self._metrics:
                timer.__exit__(None, None, None)
