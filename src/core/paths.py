"""
Filesystem and environment utilities.
"""

import os
from pathlib import Path


# Anchors the project root dynamically, regardless of where the script is executed from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def resolve_path(path: str | Path) -> Path:
    """
    Resolve a path relative to the PROJECT_ROOT.
    If the path is already absolute, it is returned as-is.
    """
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def ensure_dir(path: str | Path) -> Path:
    """
    Ensure a directory exists (creating parent directories if necessary).
    Returns the resolved Path object.
    """
    p = resolve_path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_env_var(key: str, default: str | None = None) -> str:
    """
    Safely fetch an environment variable, raising a clear error if missing 
    and no default is provided.
    """
    val = os.getenv(key, default)
    if val is None:
        from src.core.exceptions import ConfigurationError
        raise ConfigurationError(f"Required environment variable '{key}' is missing.")
    return val
