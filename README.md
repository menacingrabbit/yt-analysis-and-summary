# yt-analysis-and-summary

A small Python CLI that downloads a YouTube video's audio, transcribes it with OpenRouter, and optionally produces a concise summary. The tool shows live progress bars for download and conversion and logs each step with colourful console output. Tested with German-language content.

## Features
- **Audio download** using `yt-dlp` with progress displayed via `tqdm`
- **FFmpeg conversion** to MP3 with a conversion progress indicator
- **Transcription** via OpenRouter's speech-to-text model
- **Summarisation** using the same model with a bullet-point prompt
- **Rich console logging** for clear, colour-coded messages
- **Standard development workflow** – lint (`ruff`), format (`black`), and test (`pytest`)

## Prerequisites
- Python **3.11+**
- **FFmpeg** installed and available on the system `PATH`
- An OpenRouter API key (set `OPENROUTER_API_KEY` in a `.env` file or the environment)

## Installation
```bash
# Clone the repository
git clone <repo-url> && cd yt-analysis-and-summary

# Create a virtual environment
python -m venv .venv
source .venv\Scripts\activate  # PowerShell: .\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # for development
```

## Usage
```bash
# Basic run – downloads, transcribes, and summarises
python -m src.cli --url "https://www.youtube.com/watch?v=example"

# Skip summarisation (only transcript)
python -m src.cli --url "..." --no-summary

# Specify a custom output directory
python -m src.cli --url "..." --out-dir ./data
```
The CLI will display `tqdm` bars for the download and conversion steps and log the transcription and summarisation stages with `rich`.

## Development
```bash
# Lint the code
ruff check src/ tests/

# Auto-format
black src/ tests/

# Run the test suite
pytest
```

## Environment variables
- `OPENROUTER_API_KEY` – required for any OpenRouter request
- Optional model overrides:
  - `OPENROUTER_TRANSCRIBE_MODEL`
  - `OPENROUTER_SUMMARISE_MODEL`

## License
MIT License