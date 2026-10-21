"""Default settings for the pipeline.

These are the values used when the corresponding environment variable (or
``.env`` entry) is unset. They are gathered here so the defaults are easy to
find and change in one place; :mod:`src.config` reads them when resolving each
setting, and ``.env.example`` documents the override names.

To override any of them, set the environment variable named in the comment
above the constant — the environment always wins over the value here.
"""

# OPENROUTER_TRANSCRIBE_MODEL — model used for audio transcription.
DEFAULT_TRANSCRIBE_MODEL = "mistralai/voxtral-mini-transcribe"

# OPENROUTER_SUMMARISE_MODEL — model used for transcript summarisation.
DEFAULT_SUMMARISE_MODEL = "anthropic/claude-3.5-sonnet"

# OPENROUTER_TIMEOUT — timeout in seconds for OpenRouter requests.
DEFAULT_API_TIMEOUT = 60.0

# OPENROUTER_MAX_TOKENS — maximum tokens for a summarisation response.
DEFAULT_MAX_TOKENS = 1024
