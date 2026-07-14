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


def read_urls_from_file(path: Path) -> list[str]:
    """Read YouTube URLs from a text file, one per line.

    Args:
        path: Path to the file containing URLs

    Returns:
        List of validated URL strings

    Raises:
        ValueError: If any URL in the file is invalid
    """
    urls = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        validate_youtube_url(line)
        urls.append(line)
    if not urls:
        raise ValueError(f"No valid URLs found in {path}")
    return urls


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download, transcribe, and optionally summarise YouTube videos."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="YouTube video URL to process")
    group.add_argument(
        "--batch-file", type=Path, help="Text file with one YouTube URL per line"
    )
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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download audio even if file already exists",
    )
    return parser.parse_args()


def process_single_url(
    url: str, out_dir: Path, no_summary: bool, force: bool = False
) -> bool:
    """Process a single YouTube URL: download, transcribe, and optionally summarize.

    Args:
        url: YouTube video URL to process
        out_dir: Output directory for files
        no_summary: If True, skip summary generation
        force: If True, re-download audio even if file exists

    Returns:
        True on success, False on error
    """
    try:
        console.print(f"[bold cyan]Processing:[/] {url}")
        audio_path = download_audio(url, out_dir, force=force)
        console.print(f"[green]Audio saved to:[/] {audio_path}")

        console.print("[bold cyan]Transcribing audio…[/]")
        transcript = transcribe(audio_path)
        base_name = Path(audio_path).stem
        _save_transcript(transcript, out_dir, base_name)

        if not no_summary:
            console.print("[bold cyan]Generating summary…[/]")
            _save_summary(transcript, out_dir, base_name)

        console.print("[bold green]Complete![/]")
        return True
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        console.print("[yellow]Process interrupted by user[/]")
        raise
    except (FileNotFoundError, PermissionError) as exc:
        logger.error(f"Error: {exc}")
        console.print(f"[red]Error:[/] {exc}")
        return False
    except Exception as exc:
        logger.error(f"Unexpected error: {exc}")
        console.print(f"[red]Error:[/] {exc}")
        return False


def main() -> int:
    args = parse_args()

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.url:
        if not process_single_url(args.url, out_dir, args.no_summary, args.force):
            return 1
        return 0

    if args.batch_file:
        try:
            urls = read_urls_from_file(args.batch_file)
        except (FileNotFoundError, ValueError) as exc:
            logger.error(f"Batch file error: {exc}")
            console.print(f"[red]Error:[/] {exc}")
            return 1

        console.print(f"[bold cyan]Processing {len(urls)} video(s)…[/]")
        successes = 0
        for url in urls:
            if process_single_url(url, out_dir, args.no_summary, args.force):
                successes += 1
            else:
                console.print(f"[yellow]Skipping to next video…[/]")

        console.print(
            f"[bold green]Batch complete:[/] {successes}/{len(urls)} successful"
        )
        return 0

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
