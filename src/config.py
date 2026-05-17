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

# Example required variable for OpenRouter API
OPENROUTER_API_KEY = get_env("OPENROUTER_API_KEY", required=True)
