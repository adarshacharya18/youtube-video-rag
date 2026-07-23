"""
Serialization utilities for JSON, YAML, Datetimes, and UUIDs.
"""

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, ValidationError as PydanticValidationError

from src.core.exceptions import ValidationError

T = TypeVar("T", bound=BaseModel)


class CustomJSONEncoder(json.JSONEncoder):
    """Encodes custom standard library types safely into JSON strings."""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


def serialize_json(data: Any, path: Path | None = None, indent: int = 2) -> str:
    """Serialize an object to a JSON string, optionally saving it to a file."""
    # Convert Pydantic models to dict if necessary
    if isinstance(data, BaseModel):
        data = data.model_dump(mode="json")
        
    json_str = json.dumps(data, cls=CustomJSONEncoder, indent=indent)
    if path:
        path.write_text(json_str, encoding="utf-8")
    return json_str


def deserialize_json(source: str | Path, model: type[T] | None = None) -> Any:
    """
    Deserialize JSON from a string or file.
    If `model` (a Pydantic class) is provided, validates the data and returns the instance.
    """
    if isinstance(source, Path):
        raw_data = json.loads(source.read_text(encoding="utf-8"))
    else:
        raw_data = json.loads(source)

    if model:
        try:
            return model.model_validate(raw_data)
        except PydanticValidationError as e:
            raise ValidationError(f"Failed to validate JSON against {model.__name__}: {e}")
            
    return raw_data


def serialize_yaml(data: Any, path: Path | None = None) -> str:
    """Serialize a dictionary to YAML format."""
    yaml_str = yaml.dump(data, default_flow_style=False, sort_keys=False)
    if path:
        path.write_text(yaml_str, encoding="utf-8")
    return yaml_str


def deserialize_yaml(source: str | Path) -> dict[str, Any]:
    """Deserialize YAML from a string or file."""
    if isinstance(source, Path):
        return yaml.safe_load(source.read_text(encoding="utf-8"))
    return yaml.safe_load(source)


def generate_uuid() -> str:
    """Generate a standard UUID string."""
    return str(uuid.uuid4())


def format_timestamp(dt: datetime | None = None) -> str:
    """Format a UTC timestamp for safe usage in filenames."""
    dt = dt or datetime.now(timezone.utc)
    return dt.strftime("%Y%m%d_%H%M%S")
