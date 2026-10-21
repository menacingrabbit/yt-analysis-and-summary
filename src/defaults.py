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
DEFAULT_SUMMARISE_MODEL = "anthropic/claude-haiku-5.5"

# OPENROUTER_TIMEOUT — timeout in seconds for OpenRouter requests.
DEFAULT_API_TIMEOUT = 60.0

# OPENROUTER_MAX_TOKENS — maximum tokens for a summarisation response.
DEFAULT_MAX_TOKENS = 1024

# OPENROUTER_CHUNK_SECONDS — maximum seconds per audio chunk when splitting.
# YouTube videos longer than ~10 minutes can exceed the OpenRouter
# transcription API's input limit, so we split at 590 seconds (just under
# 10 minutes) to stay safely within it.
DEFAULT_CHUNK_DURATION = 590

# OPENROUTER_CHUNK_OVERLAP — seconds of tail overlap between consecutive
# chunks. Each chunk starts this many seconds before the previous one ends, so
# speech straddling a boundary is still heard in full by at least one chunk.
DEFAULT_CHUNK_OVERLAP = 3
