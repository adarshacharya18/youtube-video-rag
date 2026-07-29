"""
Dynamic Plugin Loader and Adapter Module for Phase 09 Plugin SDK.

Provides PluginNodeAdapter to bridge restricted PluginNode instances to the core
Node interface, and PluginLoader to dynamically discover, validate, and instantiate
external plugins registered under entry points.
"""

import importlib.metadata
from typing import Any, Optional, Sequence

from src.core.exceptions import PipelineError
from src.core.logger import get_logger
from src.core.orchestrator.state_ledger import StateLedger
from src.core.workflow.node import Node
from src.sdk.plugin_base import PluginNode

logger = get_logger(__name__)

DEFAULT_ENTRY_POINT_GROUP = "dsa.plugins"


class PluginError(PipelineError):
    """Base exception for plugin operational errors."""
    pass


class PluginLoadError(PluginError):
    """Raised when an entry point fails to load or instantiate."""
    pass


class PluginValidationError(PluginError):
    """Raised when a discovered plugin class fails validation."""
    pass


class PluginNodeAdapter(Node):
    """
    Adapter bridging restricted PluginNode instances to the core Node interface.

    Handles reading prior step outputs and run metadata from StateLedger on behalf of
    the plugin, passing a clean inputs dictionary to plugin.process(inputs), and returning
    the resulting output dictionary for WorkflowEngine database management.
    """

    def __init__(self, plugin: PluginNode) -> None:
        """
        Initialize PluginNodeAdapter with a PluginNode instance.

        Args:
            plugin: An instance of a class inheriting from PluginNode.

        Raises:
            PluginValidationError: If plugin is not an instance of PluginNode.
        """
        if not isinstance(plugin, PluginNode):
            raise PluginValidationError(
                f"Plugin must be an instance of PluginNode, got {type(plugin).__name__}"
            )
        self.plugin = plugin

    @property
    def name(self) -> str:
        """Return the wrapped plugin's name property."""
        return self.plugin.name

    def execute(self, run_id: str, ledger: StateLedger) -> dict[str, Any]:
        """
        Execute the wrapped plugin by extracting state from ledger on its behalf.

        Args:
            run_id: Pipeline run identifier.
            ledger: Active StateLedger instance.

        Returns:
            dict[str, Any]: Output dictionary payload returned by plugin.process().

        Raises:
            PluginValidationError: If plugin output is not a dictionary.
            PipelineStageError: If run_id is missing from ledger.
        """
        run_record = self.get_run_record(run_id, ledger)
        completed_outputs = self.get_completed_step_outputs(run_id, ledger)

        inputs: dict[str, Any] = {
            "run_id": run_id,
            "slug": run_record.slug,
            "metadata": run_record.metadata or {},
            "steps": completed_outputs,
            "prior_outputs": completed_outputs,
        }

        output = self.plugin.process(inputs)
        if output is None:
            output = {}

        if not isinstance(output, dict):
            raise PluginValidationError(
                f"Plugin '{self.name}' process() must return a dictionary payload, got {type(output).__name__}."
            )

        return output


class PluginLoader:
    """
    Dynamic discovery, validation, and loader engine for third-party WorkflowEngine plugins.
    """

    DEFAULT_GROUP = DEFAULT_ENTRY_POINT_GROUP

    def __init__(self, group: str = DEFAULT_GROUP) -> None:
        """
        Initialize PluginLoader.

        Args:
            group: Entry point group name to discover (defaults to 'dsa.plugins').
        """
        self.group = group

    def discover_entry_points(
        self_or_cls, group: Optional[str] = None
    ) -> Sequence[importlib.metadata.EntryPoint]:
        """
        Discover entry points registered under the specified group.

        Args:
            group: Entry point group to query (defaults to configured instance group).

        Returns:
            Sequence[importlib.metadata.EntryPoint]: Discovered entry point objects.
        """
        if isinstance(self_or_cls, type):
            target_group = group if group is not None else self_or_cls.DEFAULT_GROUP
        else:
            target_group = group if group is not None else self_or_cls.group

        try:
            eps = importlib.metadata.entry_points(group=target_group)
        except TypeError:
            eps = importlib.metadata.entry_points()

        if hasattr(eps, "select"):
            return list(eps.select(group=target_group))
        elif isinstance(eps, dict):
            return list(eps.get(target_group, []))
        elif isinstance(eps, (list, tuple, set)):
            return list(eps)
        else:
            try:
                return list(eps)
            except Exception:
                return []

    def load_plugins(self_or_cls, group: Optional[str] = None) -> list[Node]:
        """
        Discover, validate, instantiate, and adapt external plugin nodes.

        Args:
            group: Entry point group namespace override.

        Returns:
            list[Node]: List of adapted PluginNodeAdapter instances ready for WorkflowEngine.

        Raises:
            PluginLoadError: If loading an entry point module or class instantiation fails.
            PluginValidationError: If loaded object does not inherit from PluginNode.
        """
        if isinstance(self_or_cls, type):
            loader = self_or_cls(group=group or self_or_cls.DEFAULT_GROUP)
            return loader.load_plugins(group=group)

        target_group = group if group is not None else self_or_cls.group
        discovered_eps = self_or_cls.discover_entry_points(group=target_group)
        adapted_nodes: list[Node] = []

        for ep in discovered_eps:
            ep_name = getattr(ep, "name", "unknown")
            logger.info("Loading plugin entry point", ep_name=ep_name, group=target_group)

            try:
                plugin_cls = ep.load()
            except Exception as e:
                logger.error("Failed to load plugin entry point", ep_name=ep_name, error=str(e))
                raise PluginLoadError(
                    f"Failed to load plugin entry point '{ep_name}': {e}"
                ) from e

            if not (
                isinstance(plugin_cls, type)
                and issubclass(plugin_cls, PluginNode)
                and plugin_cls is not PluginNode
            ):
                logger.error(
                    "Plugin class validation failed: must inherit from PluginNode",
                    ep_name=ep_name,
                    plugin_cls=str(plugin_cls),
                )
                raise PluginValidationError(
                    f"Plugin class '{plugin_cls}' from entry point '{ep_name}' must inherit from PluginNode."
                )

            try:
                plugin_instance = plugin_cls()
            except Exception as e:
                logger.error(
                    "Failed to instantiate plugin class",
                    ep_name=ep_name,
                    error=str(e),
                )
                raise PluginLoadError(
                    f"Failed to instantiate plugin class '{plugin_cls}' from entry point '{ep_name}': {e}"
                ) from e

            adapter = PluginNodeAdapter(plugin_instance)
            adapted_nodes.append(adapter)
            logger.info("Successfully loaded and adapted plugin node", step_name=adapter.name)

        return adapted_nodes
