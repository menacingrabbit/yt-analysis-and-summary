"""Command‑line entry point for the YouTube analysis tool.

Usage example:
    python -m src.cli --url "https://www.youtube.com/watch?v=..."

The CLI orchestrates:
1. Downloading audio with progress bars.
2. Transcribing the audio via OpenRouter.
3. Optionally summarising the transcript.

All steps are logged with rich‑styled output.
"""

import argparse
import re
import sys
from pathlib import Path

from rich.console import Console

from .yt.downloader import download_audio
from .transcription.client import transcribe
from .summarisation.summariser import summarise_and_save
from .utils.logging import logger

console = Console()

_YOUTUBE_URL_PATTERN = re.compile(
    r"^https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})"
)


def validate_youtube_url(url: str) -> None:
    """Validate that the URL is a valid YouTube video URL.

    Args:
        url: The URL to validate

    Raises:
        ValueError: If the URL is not a valid YouTube video URL
    """
    if not _YOUTUBE_URL_PATTERN.match(url):
        raise ValueError(
            "Invalid YouTube URL. Expected format: "
            "https://www.youtube.com/watch?v=... or https://youtu.be/..."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download, transcribe, and optionally summarise a YouTube video.")
    parser.add_argument("--url", required=True, help="YouTube video URL to process")
    parser.add_argument(
        "--out-dir",
        default="output",
        help="Directory where audio, transcript and summary files will be stored (default: ./output)",
    )
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Skip the summarisation step and only produce a transcript",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Validate URL before doing any work
    try:
        validate_youtube_url(args.url)
    except ValueError as exc:
        logger.error(f"Invalid input: {exc}")
        console.print(f"[red]Error:[/] {exc}")
        return 1

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        console.print("[bold cyan]Starting YouTube audio download…[/]")
        audio_path = download_audio(args.url, out_dir)
        console.print(f"[green]Audio saved to:[/] {audio_path}")

        console.print("[bold cyan]Transcribing audio…[/]")
        transcript = transcribe(audio_path)
        # Save transcript - use the same base name as the audio file (without extension)
        base_name = Path(audio_path).stem  # This already contains the date prefix from slugify
        _save_transcript(transcript, out_dir, base_name)

        if not args.no_summary:
            console.print("[bold cyan]Generating summary…[/]")
            _save_summary(transcript, out_dir, base_name)
        else:
            console.print("[yellow]Summary step skipped as requested.[/]")

        console.print("[bold green]All done![/]")
        return 0
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        console.print("[yellow]Process interrupted by user[/]")
        return 1
    except FileNotFoundError as exc:
        logger.error(f"File not found: {exc}")
        console.print(f"[red]Error:[/] {exc}")
        return 1
    except PermissionError as exc:
        logger.error(f"Permission denied: {exc}")
        console.print(f"[red]Error:[/] {exc}")
        return 1


def _save_transcript(transcript: str, out_dir: Path, base_name: str) -> None:
    """Save transcript to file.

    Args:
        transcript: The transcript text to save
        out_dir: Output directory
        base_name: Base filename (without extension)
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = out_dir / f"{base_name}_transcript.txt"
    transcript_path.write_text(transcript, encoding="utf-8")
    console.print(f"[green]Transcript written to:[/] {transcript_path}")


def _save_summary(transcript: str, out_dir: Path, base_name: str) -> None:
    """Generate and save summary to file.

    Args:
        transcript: The transcript text to summarize
        out_dir: Output directory
        base_name: Base filename (without extension)
    """
    summarise_and_save(transcript, out_dir, base_name)
    summary_path = out_dir / f"{base_name}_summary.txt"
    console.print(f"[green]Summary written to:[/] {summary_path}")


if __name__ == "__main__":
    sys.exit(main())