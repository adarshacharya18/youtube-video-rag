"""Platform Evolution subsystem (Phase 15).

Provides model fallbacks with circuit breakers, prompt A/B testing
with regression kill-switches, feedback collection, analytics dashboards,
compatibility management, and safe upgrade orchestration.
"""

from src.core.evolution.model_manager import ModelConfig, ModelManager
from src.core.evolution.prompt_manager import PromptManager, PromptTemplate
from src.core.evolution.feedback import FeedbackEntry, FeedbackManager
from src.core.evolution.analytics_dashboard import AnalyticsDashboard
from src.core.evolution.compatibility_manager import CompatibilityManager
from src.core.evolution.upgrade_manager import UpgradeManager, UpgradeTask

__all__ = [
    "ModelConfig",
    "ModelManager",
    "PromptManager",
    "PromptTemplate",
    "FeedbackEntry",
    "FeedbackManager",
    "AnalyticsDashboard",
    "CompatibilityManager",
    "UpgradeManager",
    "UpgradeTask",
]
