"""
Workflow Semantic Validator.

Performs deep structural and logical validation of parsed WorkflowDefinitions.
Integrates with the PluginManager to ensure all targeted plugins exist and are active.
"""

import logging

from src.core.exceptions import PipelineError
from src.core.plugin_manager import PluginManager
from src.core.workflow_def import WorkflowDefinition


class ValidatorError(PipelineError):
    """Raised when a parsed workflow fails logical semantic validation."""
    pass


class WorkflowValidator:
    """
    Executes cross-component semantic validation on declarative workflows.
    Ensures that definitions align with the actual physical state of the Runtime.
    """

    def __init__(self, plugin_manager: PluginManager) -> None:
        self._plugin_manager = plugin_manager
        self._logger = logging.getLogger(__name__)

    def validate(self, workflow: WorkflowDefinition) -> None:
        """
        Runs the full suite of Semantic tests.
        Raises ValidatorError on any failure.
        """
        self._logger.debug(f"Executing semantic validation on workflow '{workflow.workflow_id}' (v{workflow.version})...")
        
        self._validate_duplicate_steps(workflow)
        
        # Defer to the mathematical DFS check embedded in the model
        try:
            workflow.validate_dag()
        except Exception as e:
            raise ValidatorError(str(e)) from e
            
        self._validate_plugins_exist(workflow)
        self._validate_timeouts_and_retries(workflow)
        self._validate_conditions(workflow)
        
        self._logger.info(f"Workflow '{workflow.workflow_id}' passed strict validation.")

    def _validate_duplicate_steps(self, workflow: WorkflowDefinition) -> None:
        """Ensures step_ids are globally unique within the workflow context."""
        seen: set[str] = set()
        for step in workflow.steps:
            if step.step_id in seen:
                raise ValidatorError(f"Duplicate step_id detected: '{step.step_id}'")
            seen.add(step.step_id)

    def _validate_plugins_exist(self, workflow: WorkflowDefinition) -> None:
        """
        Cross-references the targeted plugins against the active PluginManager.
        Guarantees that a workflow will not crash halfway through due to a missing dependency.
        """
        for step in workflow.steps:
            try:
                # The PluginManager will throw an exception or return None if unregistered
                plugin = self._plugin_manager.get_plugin(step.plugin_id)
                if not plugin:
                    raise ValidatorError(
                        f"Step '{step.step_id}' targets unknown/inactive plugin '{step.plugin_id}'"
                    )
            except Exception as e:
                 raise ValidatorError(
                     f"Step '{step.step_id}' targets unknown/inactive plugin '{step.plugin_id}': {e}"
                 )

    def _validate_timeouts_and_retries(self, workflow: WorkflowDefinition) -> None:
        """
        Performs logical sanity checks on execution boundaries.
        Pydantic guarantees types (int/float), but this guarantees semantic safety.
        """
        for step in workflow.steps:
            # Check for absurdly high timeouts (e.g., > 24 hours)
            if step.timeout_sec > 86400:
                self._logger.warning(
                    f"Step '{step.step_id}' has an extreme timeout ({step.timeout_sec}s). "
                    "This may cause the pipeline to zombie indefinitely."
                )
            
            # Check for pipeline stagnation via excessive retries
            if step.retry_policy.max_retries > 10:
                self._logger.warning(
                    f"Step '{step.step_id}' has {step.retry_policy.max_retries} retries. "
                    "This may cause severe pipeline stagnation."
                )

            # Prevent instant backoff loops
            if step.retry_policy.initial_delay_sec == 0 and step.retry_policy.max_retries > 0:
                 self._logger.warning(
                     f"Step '{step.step_id}' has 0s initial delay. Retries will spam the Event Bus."
                 )

    def _validate_conditions(self, workflow: WorkflowDefinition) -> None:
        """Ensures the conditions dictionary follows strict key-value rules."""
        for step in workflow.steps:
            if not isinstance(step.conditions, dict):
                raise ValidatorError(f"Step '{step.step_id}' conditions must be a dictionary.")
                
            for key, val in step.conditions.items():
                if not isinstance(key, str):
                    raise ValidatorError(f"Step '{step.step_id}' condition key '{key}' must be a string.")
