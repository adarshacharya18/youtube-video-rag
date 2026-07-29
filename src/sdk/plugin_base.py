"""
Plugin Base Module for Phase 09 External Plugin SDK.

Defines the restricted PluginNode interface for third-party developers.
Plugins operate on input dictionaries and return output payload dictionaries,
and are denied direct access to SQLite StateLedger or run identifiers.
"""

from abc import ABC, abstractmethod
from typing import Any


class PluginNode(ABC):
    """
    Restricted Abstract Base Class for external third-party workflow plugins.

    External plugins must inherit from PluginNode and implement `name` and `process()`.
    Plugins receive an inputs dictionary containing pipeline context and prior step outputs,
    and return an output dictionary payload to be persisted into StateLedger.
    Direct access to SQLite StateLedger or raw database connections is denied.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique name identifier for the plugin workflow step.

        Used as step_name in StateLedger tracking and for prior step output lookups.

        Returns:
            str: Unique plugin step identifier (e.g., 'custom_metrics', 'notion_sync').
        """
        pass

    @abstractmethod
    def process(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """
        Execute plugin processing logic in an isolated context.

        Args:
            inputs: Dictionary containing pipeline context and outputs from prior completed steps.
                    Keys typically include:
                      - 'run_id': String pipeline run identifier.
                      - 'slug': Problem identifier slug.
                      - 'metadata': Pipeline run metadata dictionary.
                      - 'steps': Dict mapping step names to their respective output dictionaries.
                      - 'prior_outputs': Alias dict mapping step names to output dictionaries.

        Returns:
            dict[str, Any]: Output dictionary payload to be safely stored in StateLedger by WorkflowEngine.

        Raises:
            Exception: If plugin execution fails. Errors will be caught by WorkflowEngine.
        """
        pass
