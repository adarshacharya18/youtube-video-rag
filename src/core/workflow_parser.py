"""
Workflow Parser.

Validates and parses declarative JSON/YAML files into strict DAG models.
Provides human-readable error reporting and strictly rejects unknown fields.
"""

import json
import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from src.core.exceptions import PipelineError
from src.core.workflow_def import WorkflowDefinition


class ParserError(PipelineError):
    """Raised when a workflow file contains structural or syntax errors."""
    pass


class WorkflowParser:
    """
    Centralized file parsing utility for the Workflow Engine.
    Handles I/O safely and converts raw Python Exceptions into 
    human-readable DevOps formatting.
    """
    _logger = logging.getLogger(__name__)

    @staticmethod
    def parse(file_path: str | Path) -> WorkflowDefinition:
        """Dynamically routes the file to the correct decoding engine based on extension."""
        path = Path(file_path)
        if not path.exists():
            raise ParserError(f"Workflow file not found: {path.absolute()}")

        ext = path.suffix.lower()
        if ext in (".yml", ".yaml"):
            return WorkflowParser._parse_yaml(path)
        elif ext == ".json":
            return WorkflowParser._parse_json(path)
        else:
            raise ParserError(
                f"Unsupported workflow extension '{ext}'. Must be .json, .yml, or .yaml"
            )

    @staticmethod
    def _parse_yaml(path: Path) -> WorkflowDefinition:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return WorkflowParser._validate_and_build(data, path)
        except yaml.YAMLError as e:
            raise ParserError(f"YAML Syntax Error in '{path.name}':\n{e}") from e
        except Exception as e:
            if isinstance(e, ParserError):
                raise
            raise ParserError(f"Failed to read YAML file '{path.name}': {e}") from e

    @staticmethod
    def _parse_json(path: Path) -> WorkflowDefinition:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return WorkflowParser._validate_and_build(data, path)
        except json.JSONDecodeError as e:
            raise ParserError(f"JSON Syntax Error in '{path.name}':\n{e}") from e
        except Exception as e:
            if isinstance(e, ParserError):
                raise
            raise ParserError(f"Failed to read JSON file '{path.name}': {e}") from e

    @staticmethod
    def _validate_and_build(data: Any, path: Path) -> WorkflowDefinition:
        """
        Executes strict Pydantic model hydration. 
        Translates raw Pydantic errors into readable log traces.
        """
        if not isinstance(data, dict):
            raise ParserError(f"Root of workflow file '{path.name}' must be a key-value mapping (dict).")
            
        try:
            # 1. Pydantic Type & Unknown Field Validation
            model = WorkflowDefinition(**data)
            
            # 2. Mathematical Directed Acyclic Graph Validation
            model.validate_dag()
            
            WorkflowParser._logger.info(
                f"Successfully parsed workflow '{model.workflow_id}' (v{model.version}) from {path.name}"
            )
            return model
            
        except ValidationError as e:
            # Human readable error formatting for CLI/DevOps consumption
            errors = []
            for err in e.errors():
                loc = " -> ".join([str(l) for l in err["loc"]])
                msg = err["msg"]
                errors.append(f" - [Field: '{loc}'] {msg}")
                
            error_str = "\n".join(errors)
            raise ParserError(
                f"Schema Validation Failed for '{path.name}'. Correct the following errors:\n{error_str}"
            ) from e
