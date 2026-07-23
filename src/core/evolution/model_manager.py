"""
Model Manager (Phase 15)

Manages dynamic routing, fallbacks, and health checks across different
providers (LLMs, TTS, Embeddings, Animation).
"""
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable

logger = logging.getLogger("model_manager")

@dataclass
class ModelConfig:
    provider: str      # e.g., 'openai', 'anthropic', 'kokoro', 'manim'
    model_id: str      # e.g., 'gpt-4o-2024-05-13'
    category: str      # 'llm', 'embedding', 'tts', 'animation'
    is_active: bool = True
    capabilities: List[str] = None
    fallback_id: Optional[str] = None

class ModelManager:
    def __init__(self):
        self._models: Dict[str, ModelConfig] = {}
        self._health_status: Dict[str, bool] = {}
        self._metrics: Dict[str, dict] = {}

    def register_model(self, config: ModelConfig):
        """Registers a new model version into the active routing table."""
        self._models[config.model_id] = config
        self._health_status[config.model_id] = True
        self._metrics[config.model_id] = {"calls": 0, "errors": 0}
        logger.info(f"Registered {config.category} model: {config.model_id}")

    def get_primary_model(self, category: str) -> Optional[ModelConfig]:
        """Returns the first active and healthy model in a specified category."""
        for model in self._models.values():
            if model.category == category and model.is_active:
                if self._health_status.get(model.model_id, False):
                    return model
        return None

    def execute_with_fallback(self, category: str, execution_callback: Callable, *args, **kwargs):
        """
        Attempts to execute a task using the primary model. If it fails (e.g., HTTP 503),
        automatically routes to the defined fallback model.
        """
        primary = self.get_primary_model(category)
        if not primary:
            raise RuntimeError(f"No active models found for category: {category}")

        try:
            # Inject the primary model_id into the execution closure
            result = execution_callback(primary.model_id, *args, **kwargs)
            self._record_metric(primary.model_id, success=True)
            return result
        except Exception as e:
            logger.warning(f"Model {primary.model_id} failed: {e}. Attempting fallback.")
            self._record_metric(primary.model_id, success=False)
            
            # Circuit Breaker: Mark unhealthy to prevent subsequent cascading timeouts
            self._health_status[primary.model_id] = False

            if primary.fallback_id and primary.fallback_id in self._models:
                fallback = self._models[primary.fallback_id]
                logger.info(f"Routing to fallback model: {fallback.model_id}")
                try:
                    result = execution_callback(fallback.model_id, *args, **kwargs)
                    self._record_metric(fallback.model_id, success=True)
                    return result
                except Exception as fallback_error:
                    self._record_metric(fallback.model_id, success=False)
                    raise RuntimeError(f"Both primary and fallback models failed.") from fallback_error
            else:
                raise

    def _record_metric(self, model_id: str, success: bool):
        """Maintains telemetry for ops health dashboards."""
        if model_id in self._metrics:
            self._metrics[model_id]["calls"] += 1
            if not success:
                self._metrics[model_id]["errors"] += 1

    def generate_health_report(self) -> dict:
        return {
            "status": self._health_status,
            "metrics": self._metrics
        }
