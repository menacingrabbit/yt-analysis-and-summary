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
import sys
from pathlib import Path

from rich.console import Console

from .yt.downloader import download_audio
from .yt.utils import slugify
from .transcription.client import transcribe
from .summarisation.summariser import summarise_and_save
from .utils.logging import logger

console = Console()


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
    except ValueError as exc:  # Invalid input/URL
        logger.error(f"Invalid input: {exc}")
        console.print(f"[red]Error:[/] {exc}")
        return 1
    except RuntimeError as exc:  # Processing errors
        logger.error(f"Processing failed: {exc}")
        console.print(f"[red]Error:[/] {exc}")
        return 1
    except Exception as exc:  # pylint: disable=broad-except
        # Catch-all for unexpected errors
        logger.error(f"Unexpected error: {exc}")
        console.print(f"[red]Unexpected error:[/] {exc}")
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
    console.print("[bold cyan]Generating summary…[/]")
    summarise_and_save(transcript, out_dir, base_name)
    summary_path = out_dir / f"{base_name}_summary.txt"
    console.print(f"[green]Summary written to:[/] {summary_path}")


if __name__ == "__main__":
    sys.exit(main())
