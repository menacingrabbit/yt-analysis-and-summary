"""YouTube audio downloader and converter.

Provides ``download_audio`` which uses ``yt_dlp`` to fetch the best audio
stream, converts it to MP3 via ffmpeg (if available), and reports progress
through ``tqdm``.
"""

import shutil
import subprocess
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL
from tqdm import tqdm

from .utils import slugify, _clean
from ..utils.logging import logger


class ProgressManager:
    """Manages tqdm progress bar state for downloads.

    This class encapsulates progress bar state, making it thread-safe for
    concurrent downloads (unlike storing state on function attributes).
    """

    def __init__(self):
        self._bar: tqdm | None = None

    def hook(self, d: dict) -> None:
        """Hook for yt-dlp to forward progress to tqdm.

        yt-dlp passes dictionaries with a ``status`` key. We handle ``downloading``
        and update the internal tqdm bar.
        """
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes")
            if self._bar is None:
                self._bar = tqdm(
                    total=total, unit="B", unit_scale=True, desc="Downloading"
                )
            self._bar.total = total or self._bar.total
            self._bar.update(downloaded - self._bar.n)
        elif d["status"] == "finished":
            if self._bar is not None:
                self._bar.close()
                print()
                logger.info(
                    "Download finished, now converting (if ffmpeg is available)..."
                )


def _run_ffmpeg(input_path: Path, output_path: Path) -> None:
    """Run ffmpeg to convert *input_path* to MP3 *output_path*.

    If ffmpeg is not installed or execution fails, the function copies the
    original file to the destination (preserving the original format) and logs a
    warning.
    """
    ffmpeg_exe = shutil.which("ffmpeg")
    if not ffmpeg_exe:
        logger.warning(
            "ffmpeg not found – copying original file to destination without conversion."
        )
        output_path.write_bytes(input_path.read_bytes())
        return

    ffmpeg_cmd = [
        ffmpeg_exe,
        "-y",  # overwrite output if exists
        "-i",
        str(input_path),
        "-vn",
        "-acodec",
        "mp3",
        str(output_path),
    ]
    logger.info("Starting ffmpeg conversion...")
    try:
        subprocess.run(
            ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except subprocess.SubprocessError as exc:
        # Specific exception: conversion failure
        logger.warning(
            f"ffmpeg conversion failed ({exc}); copying original file instead."
        )
        output_path.write_bytes(input_path.read_bytes())
        return


def _find_existing_audio(out_dir: Path, video_id: str, title_slug: str) -> Path | None:
    """Find an existing audio file for this video.

    Checks for files matching the video ID or title slug (handles date-prefixed names).

    Args:
        out_dir: Directory to search in
        video_id: YouTube video ID
        title_slug: Cleaned title without date prefix

    Returns:
        Path to existing MP3 file, or None if not found
    """
    # Look for files matching video_id format: YYYYMMDD-{video_id}.mp3 or similar patterns
    patterns = [
        f"*-{video_id}.mp3",  # Any date prefix + video ID
        f"*{title_slug}.mp3",  # Any date prefix + title
    ]
    for pattern in patterns:
        matches = list(out_dir.glob(pattern))
        if matches:
            return matches[0]
    return None


def download_audio(url: str, out_dir: Path, force: bool = False) -> Path:
    """Download the best audio from *url* into *out_dir* and return MP3 path.

    The function creates ``out_dir`` if it does not exist, generates a safe
    filename using :func:`slugify`, and runs ``ffmpeg`` to convert the downloaded
    file to MP3 when possible.

    Args:
        url: YouTube video URL to download
        out_dir: Directory where the audio file will be saved
        force: If True, re-download even if file exists

    Returns:
        Path to the downloaded MP3 file
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # Extract info once to get the title and generate our slug
    with YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
        info = ydl.extract_info(url, download=False)
        title = info.get("title", "audio")
        video_id = info.get("id", "")
        slug = slugify(title)

    # Use our slug as the base filename for yt-dlp
    temp_template = out_dir / f"{slug}.%(ext)s"
    mp3_path = out_dir / f"{slug}-{video_id}.mp3"

    # Check if file already exists (handles date prefix variations)
    if not force:
        # Get title without date prefix for searching
        title_only = _clean(title)
        existing = _find_existing_audio(out_dir, video_id, title_only)
        if existing:
            logger.info(f"Audio already exists at {existing}, skipping download")
            return existing

    progress_mgr = ProgressManager()
    ydl_opts: dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": str(temp_template),
        "progress_hooks": [progress_mgr.hook],
        "quiet": True,
        "no_warnings": True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        original_path = Path(ydl.prepare_filename(info))

    # Convert to MP3 using ffmpeg (or copy if unavailable/fails)
    _run_ffmpeg(original_path, mp3_path)

    # Remove the original download if it is different from the final output.
    if original_path.resolve() != mp3_path.resolve():
        original_path.unlink()

    return mp3_path
