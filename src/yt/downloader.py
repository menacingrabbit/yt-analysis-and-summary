"""YouTube audio downloader and converter.

Provides ``download_audio`` which uses ``yt_dlp`` to fetch the best audio
stream, converts it to MP3 via ffmpeg (if available), and reports progress
through ``tqdm``.
"""

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from tqdm import tqdm
from yt_dlp import YoutubeDL

from ..utils.logging import logger
from .utils import clean_title, slugify

# Base options for every yt-dlp call. The ANDROID player client avoids the
# HTTP 403 that YouTube returns for stream downloads via the default
# ANDROID_VR client. See tests/test_youtube_api_access.py.
_BASE_YDL_OPTS: dict[str, Any] = {
    "quiet": True,
    "no_warnings": True,
    "extractor_args": {"youtube": {"player_client": ["ANDROID"]}},
}

# Leading YYYYMMDD- date prefix that slugify() prepends to filenames.
_DATE_PREFIX_RE = re.compile(r"^\d{8}-")


class ProgressManager:
    """Encapsulates tqdm progress bar state for a download."""

    def __init__(self) -> None:
        self._bar: tqdm | None = None

    def hook(self, d: dict) -> None:
        """yt-dlp progress callback that forwards progress to tqdm."""
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes")
            if self._bar is None:
                self._bar = tqdm(total=total, unit="B", unit_scale=True, desc="Downloading")
            self._bar.total = total or self._bar.total
            # Guard: downloaded may be missing on some callbacks.
            if downloaded is not None:
                self._bar.update(downloaded - self._bar.n)
        elif d.get("status") == "finished" and self._bar is not None:
            self._bar.close()
            logger.info("Download finished, now converting (if ffmpeg is available)...")


def _run_ffmpeg(input_path: Path, output_path: Path) -> None:
    """Convert *input_path* to MP3 *output_path* via ffmpeg, copying as fallback.

    If ffmpeg is unavailable or conversion fails, the original file is copied
    to *output_path* unchanged rather than failing the pipeline.
    """
    ffmpeg_exe = shutil.which("ffmpeg")
    if not ffmpeg_exe:
        logger.warning(
            "ffmpeg not found – copying original file to destination without conversion."
        )
        shutil.copyfile(input_path, output_path)
        return

    cmd = [
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
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.SubprocessError as exc:
        # Conversion failed — fall back to copying the original file.
        logger.warning(f"ffmpeg conversion failed ({exc}); copying original file instead.")
        shutil.copyfile(input_path, output_path)


def _audio_mp3_name(slug: str, video_id: str) -> str:
    """Return the MP3 filename (with extension) for a download.

    Includes the video ID when available so the file is uniquely identifiable
    for resume detection; otherwise falls back to the slug alone.
    """
    stem = f"{slug}-{video_id}" if video_id else slug
    return f"{stem}.mp3"


def _find_existing_audio(out_dir: Path, video_id: str, title_slug: str) -> Path | None:
    """Find an existing audio file for this video.

    Matching is keyed on the video ID (unique and stable) when present. For
    legacy files written before the video ID was part of the filename, a
    best-effort fallback matches by *exact* cleaned title only, after stripping
    the date prefix. The previous loose suffix match could collide with
    unrelated videos that share a title fragment.

    Args:
        out_dir: Directory to search in
        video_id: YouTube video ID
        title_slug: Cleaned title without date prefix

    Returns:
        Path to the most recently modified matching MP3 file, or None.
    """
    matches: list[Path] = []
    if video_id:
        # Precise, unique match on the stable video ID.
        matches = list(out_dir.glob(f"*-{video_id}.mp3"))

    if not matches and title_slug:
        # Legacy fallback: glob by title, then keep only exact-title matches so a
        # video whose clean title is a substring of another's is not resumed.
        for cand in out_dir.glob(f"*{title_slug}.mp3"):
            stem = _DATE_PREFIX_RE.sub("", cand.stem)
            if stem == title_slug:
                matches.append(cand)

    if matches:
        # glob order is unspecified; prefer the most recently modified file so
        # resume picks the latest download rather than a stale one.
        return max(matches, key=lambda p: p.stat().st_mtime)
    return None


def download_audio(url: str, out_dir: Path, force: bool = False) -> Path:
    """Download the best audio from *url* into *out_dir* and return the MP3 path.

    The function creates ``out_dir`` if it does not exist, generates a safe
    filename using :func:`slugify`, and runs ``ffmpeg`` to convert the downloaded
    file to MP3 when possible. Existing files are resumed unless ``force`` is
    set.

    Args:
        url: YouTube video URL to download
        out_dir: Directory where the audio file will be saved
        force: If True, re-download even if file exists

    Returns:
        Path to the downloaded MP3 file
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # First pass: fetch metadata so we can compute the slug and know the video
    # id for resume detection — before committing to a download.
    with YoutubeDL(_BASE_YDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=False)
    if info is None:
        raise RuntimeError(f"Could not fetch metadata for {url}")

    title = info.get("title") or "audio"
    video_id = str(info.get("id") or "")
    slug = slugify(title)
    mp3_path = out_dir / _audio_mp3_name(slug, video_id)

    # Resume support: skip the download if the audio already exists.
    if not force:
        existing = _find_existing_audio(out_dir, video_id, clean_title(title))
        if existing:
            logger.info(f"Audio already exists at {existing}, skipping download")
            return existing

    progress_mgr = ProgressManager()
    ydl_opts: dict[str, Any] = {
        **_BASE_YDL_OPTS,
        "format": "bestaudio/best",
        "outtmpl": str(out_dir / f"{slug}.%(ext)s"),
        "progress_hooks": [progress_mgr.hook],
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
    if info is None:
        raise RuntimeError(f"Could not download {url}")
    original_path = Path(ydl.prepare_filename(info))

    # Convert to MP3 using ffmpeg (or copy if unavailable/fails).
    _run_ffmpeg(original_path, mp3_path)

    # Remove the original download if it is different from the final output.
    if original_path.resolve() != mp3_path.resolve():
        original_path.unlink()

    return mp3_path
