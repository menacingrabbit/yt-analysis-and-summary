# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common development commands

- **Setup a Python environment**
  ```
  python -m venv .venv
  .venv\Scripts\activate  # PowerShell: .\.venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  pip install -r requirements-dev.txt  # for development tools
  ```
- **Run the main script**
  ```
  python -m src.cli --url <youtube-url>
  ```
- **Run a single test** (when a test suite exists)
  ```
  pytest tests/test_module.py::test_name
  ```
- **Run the full test suite**
  ```
  pytest
  ```
- **Lint / format**
  ```
  ruff src/  # lint
  black src/  # code formatting
  ```

## High-level architecture & workflow

The repository provides a small end-to-end pipeline for extracting, transcribing, and summarising YouTube video content.

1. **Entry point** – `src/cli.py` that accepts a YouTube URL
2. **Audio extraction** – `src/yt/downloader.py` uses `yt-dlp` to download the best audio track
3. **Transcription** – `src/transcription/client.py` calls OpenRouter's speech-to-text API
4. **Summarisation** – `src/summarisation/summariser.py` generates bullet-point summaries
5. **Utilities** – shared modules in `src/utils/`

The overall data flow is:

```
YouTube URL → yt-dlp → audio file → Transcribe (OpenRouter) → transcript.txt → Summarise (OpenRouter) → summary.txt
```

## Project structure

```
src/
├── __init__.py
├── cli.py              # CLI entry point
├── config.py           # Environment variable handling (lazy API key validation)
├── yt/
│   ├── __init__.py
│   ├── downloader.py   # Audio download with ffmpeg conversion
│   └── utils.py        # Slugify helper
├── transcription/
│   ├── __init__.py
│   └── client.py       # OpenRouter API client
├── summarisation/
│   ├── __init__.py
│   └── summariser.py   # Summary generation wrapper
└── utils/
    ├── __init__.py
    ├── logging.py      # Rich console logger
    └── retry.py        # Tenacity retry decorator
```

## Key patterns

- **Lazy API key validation**: `config.py` defers validation until API calls are made, allowing `--help` without a key
- **ProgressManager class**: Thread-safe progress bar handling in `downloader.py`
- **Specific exception handling**: CLI catches specific exceptions rather than broad `Exception`