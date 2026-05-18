"""Configuration handling for the project.

Loads environment variables (optionally from a .env file) and provides a simple
helper to retrieve required settings.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env if present at repository root (two levels up from this file)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

def get_env(name: str, *, default: str | None = None, required: bool = False) -> str:
    """Retrieve an environment variable.

    Args:
        name: Variable name.
        default: Value to return if variable is missing.
        required: If True and variable is missing, raise a RuntimeError.
    """
    value = os.getenv(name, default)
    if required and value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

def get_api_key() -> str:
    """Get the OpenRouter API key, raising an error only when actually needed.

    This defers validation to usage time so users can run --help without an API key.
    """
    return get_env("OPENROUTER_API_KEY", required=True)


# Lazy-evaluated API key - validates only when accessed
def __getattr__(name: str):
    """Lazy evaluation of OPENROUTER_API_KEY for backward compatibility."""
    if name == "OPENROUTER_API_KEY":
        return get_api_key()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
