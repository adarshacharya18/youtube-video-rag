"""
Model Manager with Circuit Breaker Fallback (Phase 15).

Provides automatic model failover when an LLM provider's failure rate
exceeds a configurable threshold. Uses a simple circuit-breaker pattern:
after N consecutive failures a model is marked unhealthy and traffic is
routed to its registered fallback.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ModelConfig:
    """Configuration for a registered LLM model.

    Attributes:
        provider: Provider name (e.g. 'openai', 'anthropic').
        model_id: Unique model identifier (e.g. 'gpt-4', 'claude-3').
        capability: Capability tag used for routing (e.g. 'llm', 'embedding').
        fallback_id: Optional model_id to fall back to on failure.
        max_consecutive_failures: Failures before circuit-breaker trips.
    """

    provider: str
    model_id: str
    capability: str
    fallback_id: Optional[str] = None
    max_consecutive_failures: int = 3


class ModelManager:
    """Circuit-breaker model manager for LLM provider failover.

    Tracks per-model health via consecutive failure counters.  When a model
    exceeds its ``max_consecutive_failures`` threshold the circuit-breaker
    trips and all subsequent requests are automatically routed to the
    configured fallback model.
    """

    def __init__(self) -> None:
        self._models: dict[str, ModelConfig] = {}
        self._health_status: dict[str, bool] = {}
        self._failure_counts: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_model(self, config: ModelConfig) -> None:
        """Register a model configuration.

        Args:
            config: ModelConfig dataclass with provider details and fallback.
        """
        self._models[config.model_id] = config
        self._health_status[config.model_id] = True
        self._failure_counts[config.model_id] = 0
        logger.info(
            "Registered model",
            model_id=config.model_id,
            provider=config.provider,
            capability=config.capability,
            fallback_id=config.fallback_id,
        )

    # ------------------------------------------------------------------
    # Execution with automatic fallback
    # ------------------------------------------------------------------

    def execute_with_fallback(
        self,
        capability: str,
        fn: Callable[[str], Any],
    ) -> Any:
        """Execute *fn(model_id)* with automatic circuit-breaker fallback.

        The method iterates through models matching *capability* in
        registration order, skipping unhealthy models, until one succeeds
        or all are exhausted.

        Args:
            capability: Required capability tag (e.g. 'llm').
            fn: Callable that accepts a model_id string and returns a result.
                It should raise on failure so the circuit-breaker can react.

        Returns:
            The return value of *fn* from the first successful model.

        Raises:
            RuntimeError: When no healthy model with the required capability
                is available.
        """
        candidates = self._resolve_chain(capability)

        if not candidates:
            raise RuntimeError(
                f"No models registered with capability '{capability}'."
            )

        last_error: Optional[Exception] = None
        for model_id in candidates:
            if not self._health_status.get(model_id, False):
                logger.info(
                    "Skipping unhealthy model",
                    model_id=model_id,
                    capability=capability,
                )
                continue

            try:
                result = fn(model_id)
                self._record_success(model_id)
                return result
            except Exception as exc:
                last_error = exc
                self._record_failure(model_id)
                logger.warning(
                    "Model execution failed, trying fallback",
                    model_id=model_id,
                    error=str(exc),
                )

        raise RuntimeError(
            f"All models for capability '{capability}' are exhausted. "
            f"Last error: {last_error}"
        )

    # ------------------------------------------------------------------
    # Health introspection
    # ------------------------------------------------------------------

    def get_health_report(self) -> dict[str, Any]:
        """Return a snapshot of every registered model's health state."""
        report: dict[str, Any] = {}
        for model_id, config in self._models.items():
            report[model_id] = {
                "provider": config.provider,
                "capability": config.capability,
                "healthy": self._health_status.get(model_id, False),
                "consecutive_failures": self._failure_counts.get(model_id, 0),
                "fallback_id": config.fallback_id,
            }
        return report

    def reset_circuit_breaker(self, model_id: str) -> None:
        """Manually reset a tripped circuit-breaker for *model_id*."""
        if model_id in self._models:
            self._health_status[model_id] = True
            self._failure_counts[model_id] = 0
            logger.info("Circuit breaker reset", model_id=model_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_chain(self, capability: str) -> list[str]:
        """Build an ordered list of model_ids matching *capability*.

        The primary model comes first, followed by its fallback chain.
        """
        chain: list[str] = []
        seen: set[str] = set()

        for model_id, cfg in self._models.items():
            if cfg.capability != capability:
                continue
            current: Optional[str] = model_id
            while current and current not in seen:
                seen.add(current)
                chain.append(current)
                fallback_cfg = self._models.get(current)
                current = fallback_cfg.fallback_id if fallback_cfg else None

        return chain

    def _record_success(self, model_id: str) -> None:
        self._failure_counts[model_id] = 0

    def _record_failure(self, model_id: str) -> None:
        self._failure_counts[model_id] = self._failure_counts.get(model_id, 0) + 1
        cfg = self._models.get(model_id)
        threshold = cfg.max_consecutive_failures if cfg else 3

        if self._failure_counts[model_id] >= threshold:
            self._health_status[model_id] = False
            logger.error(
                "Circuit breaker tripped — model marked unhealthy",
                model_id=model_id,
                consecutive_failures=self._failure_counts[model_id],
                threshold=threshold,
            )
